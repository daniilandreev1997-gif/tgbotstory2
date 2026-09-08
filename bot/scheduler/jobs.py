"""APScheduler job definitions."""

import asyncio
import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)


class SchedulerService:
    """Manages all APScheduler polling jobs."""

    JOBS = [
        ("poll_vk_user_stories", 5, "vk", "stories", "user"),
        ("poll_vk_user_posts", 120, "vk", "posts", "user"),
        ("poll_vk_public_stories", 120, "vk", "stories", "public"),
        ("poll_vk_public_posts", 120, "vk", "posts", "public"),
        ("poll_ig_stories", 5, "instagram", "stories", "user"),
        ("poll_ig_posts", 160, "instagram", "posts", "user"),
        ("poll_tt_posts", 15, "tiktok", "posts", "user"),
        ("poll_tt_stories", 20, "tiktok", "stories", "user"),
    ]

    def __init__(self, scheduler, session_factory, bot, chat_id, settings) -> None:
        self._scheduler = scheduler
        self._session_factory = session_factory
        self._bot = bot
        self._chat_id = chat_id
        self._settings = settings

    def start(self) -> None:
        for job_id, interval, platform, content_type, target_type in self.JOBS:
            self._scheduler.add_job(
                self._poll_platform,
                trigger=IntervalTrigger(minutes=interval),
                id=job_id,
                args=[platform, content_type, target_type, job_id],
                replace_existing=True,
            )

        self._scheduler.add_job(
            self._cleanup_old_hashes,
            trigger=IntervalTrigger(hours=24),
            id="cleanup_old_hashes",
            replace_existing=True,
        )

        self._scheduler.start()

    def stop(self) -> None:
        self._scheduler.shutdown(wait=False)

    async def _poll_platform(self, platform, content_type, target_type, job_name) -> None:
        from bot.db.models import Target, PollLog, ContentHash, AuthCredential
        from bot.extractors import VkExtractor, IgExtractor, TtExtractor
        from bot.extractors.base import AuthExpiredError, RateLimitError, NetworkError
        from bot.transport.delivery import MediaDelivery
        from sqlalchemy import select
        import hashlib

        logger.info("poll_started: platform=%s content_type=%s target_type=%s job_name=%s", platform, content_type, target_type, job_name)

        async with self._session_factory() as session:
            stmt = select(Target).where(
                Target.platform == platform,
                Target.content_type == content_type,
                Target.target_type == target_type,
                Target.is_active == True,
            )
            result = await session.execute(stmt)
            targets = result.scalars().all()

            if not targets:
                logger.debug("poll_no_targets: platform=%s content_type=%s", platform, content_type)
                return

            auth_stmt = select(AuthCredential).where(
                AuthCredential.platform == platform,
                AuthCredential.is_valid == True,
            )
            auth_result = await session.execute(auth_stmt)
            credentials = auth_result.scalars().first()

            if not credentials:
                logger.warning("poll_no_credentials: platform=%s", platform)
                return

            extractor = self._build_extractor(platform, credentials)
            delivery = MediaDelivery(bot=self._bot, chat_id=self._chat_id, temp_dir=self._settings.temp_media_dir, max_size_mb=self._settings.max_media_size_mb)

            for target in targets:
                await session.refresh(target, attribute_names=["is_active"])
                if not target.is_active:
                    logger.debug("poll_target_inactive: target_id=%s", target.id)
                    continue

                log_entry = PollLog(target_id=target.id, platform=platform, content_type=content_type, job_name=job_name, started_at=datetime.utcnow(), status="success")

                try:
                    target_dict = {"target_id": target.target_id, "target_type": target.target_type, "target_username": target.target_username, "content_type": target.content_type, "last_poll_pk": target.last_poll_pk}
                    items = await asyncio.wait_for(extractor.poll(target_dict), timeout=self._settings.poll_timeout)
                    log_entry.items_found = len(items)
                    new_items = 0

                    for item in items:
                        content_hash = hashlib.sha256(f"{item.platform}:{item.content_pk}:{item.content_type}".encode("utf-8")).hexdigest()
                        dup_stmt = select(ContentHash).where(ContentHash.target_id == target.id, ContentHash.content_hash == content_hash)
                        dup_result = await session.execute(dup_stmt)
                        if dup_result.scalars().first():
                            continue

                        ch = ContentHash(target_id=target.id, platform=item.platform, content_pk=str(item.content_pk), content_type=item.content_type, content_hash=content_hash, media_urls={"urls": item.media_urls}, content_meta=item.metadata, telegram_msg_ids=[])
                        session.add(ch)
                        await session.flush()

                        try:
                            msg_ids = await delivery.deliver(item)
                            ch.telegram_msg_ids = msg_ids
                        except Exception:
                            logger.warning("delivery_failed_content_hash_saved: content_pk=%s platform=%s", item.content_pk, platform)

                        await session.commit()
                        new_items += 1

                    log_entry.items_new = new_items
                    if new_items == 0:
                        log_entry.status = "empty"

                    if items:
                        target.last_poll_pk = str(items[-1].content_pk)
                    target.last_polled_at = datetime.utcnow()
                    target.error_count = 0
                    target.last_error = None
                    await session.commit()

                except asyncio.TimeoutError:
                    log_entry.status = "timeout"
                    log_entry.error_message = f"Poll timeout after {self._settings.poll_timeout}s"
                    target.error_count += 1
                    target.last_error = "timeout"
                    logger.warning("poll_timeout: target_id=%s platform=%s", target.id, platform)

                except AuthExpiredError as e:
                    log_entry.status = "error"
                    log_entry.error_message = str(e)
                    target.error_count += 1
                    target.last_error = "auth_expired"
                    credentials.is_valid = False
                    logger.error("poll_auth_expired: platform=%s error=%s", platform, str(e))

                except RateLimitError as e:
                    log_entry.status = "rate_limited"
                    log_entry.error_message = str(e)
                    target.error_count += 1
                    target.last_error = "rate_limited"
                    logger.warning("poll_rate_limited: platform=%s retry_after=%s", platform, e.retry_after_sec)

                except NetworkError as e:
                    log_entry.status = "error"
                    log_entry.error_message = str(e)
                    target.error_count += 1
                    target.last_error = "network_error"
                    logger.error("poll_network_error: platform=%s error=%s", platform, str(e))

                except Exception as e:
                    log_entry.status = "error"
                    log_entry.error_message = str(e)
                    target.error_count += 1
                    target.last_error = type(e).__name__
                    logger.error("poll_unexpected_error: platform=%s error=%s", platform, str(e))

                finally:
                    log_entry.finished_at = datetime.utcnow()
                    session.add(log_entry)
                    await session.commit()

        logger.info("poll_finished: platform=%s content_type=%s target_type=%s job_name=%s", platform, content_type, target_type, job_name)

    def _build_extractor(self, platform, credentials):
        from bot.extractors import VkExtractor, IgExtractor, TtExtractor
        from bot.crypto import CredentialEncryption

        cred_dict = CredentialEncryption.decrypt_string(credentials.credential_data, self._settings.encryption_key)

        if platform == "vk":
            return VkExtractor(credentials=cred_dict)
        elif platform == "instagram":
            return IgExtractor(credentials=cred_dict)
        elif platform == "tiktok":
            return TtExtractor(credentials=cred_dict)
        else:
            raise ValueError(f"Unknown platform: {platform}")

    async def _cleanup_old_hashes(self) -> None:
        from datetime import timedelta
        from bot.db.models import ContentHash
        from sqlalchemy import delete

        cutoff = datetime.utcnow() - timedelta(days=30)

        async with self._session_factory() as session:
            stmt = delete(ContentHash).where(ContentHash.delivered_at < cutoff)
            result = await session.execute(stmt)
            await session.commit()
            logger.info("cleanup_old_hashes: deleted_count=%s", result.rowcount)
