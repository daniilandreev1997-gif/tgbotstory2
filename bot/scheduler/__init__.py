"""Scheduler manager — per-chat job lifecycle."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.config import (
    IG_POLL_INTERVAL,
    TT_POSTS_INTERVAL,
    TT_STORIES_INTERVAL,
    VK_POLL_INTERVAL,
)
from bot.db import get_all_chat_ids, get_targets

if TYPE_CHECKING:
    from telegram import Bot

logger = structlog.get_logger(__name__)

_scheduler: AsyncIOScheduler | None = None
# Keep a reference to bot for poll functions
_bot: "Bot | None" = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def init_scheduler(bot: "Bot") -> None:
    """Initialise the global scheduler. Call once on startup."""
    global _scheduler, _bot
    _bot = bot
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
        _scheduler.start()
        logger.info("scheduler_started")


async def restore_jobs() -> None:
    """Restore jobs for all chats that have targets (on startup)."""
    if _scheduler is None:
        return
    chat_ids = await get_all_chat_ids()
    for chat_id in chat_ids:
        _ensure_jobs(chat_id)
    logger.info("scheduler_jobs_restored", chat_count=len(chat_ids))


async def ensure_scheduler(chat_id: int) -> None:
    """Ensure jobs exist for a chat. Call after adding a target."""
    if _scheduler is None:
        return
    _ensure_jobs(chat_id)


async def stop_scheduler(chat_id: int) -> None:
    """Remove all jobs for a chat. Call when all targets are removed."""
    if _scheduler is None:
        return
    _remove_jobs(chat_id)


async def shutdown_scheduler() -> None:
    """Shut down the scheduler entirely."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("scheduler_shutdown")


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

def _job_id(chat_id: int, suffix: str) -> str:
    return f"{suffix}_{chat_id}"


def _ensure_jobs(chat_id: int) -> None:
    """Add jobs for a chat if they don't already exist."""
    from bot.scheduler.poller import (
        poll_ig_stories,
        poll_tt_posts,
        poll_tt_stories,
        poll_vk_stories,
    )

    assert _scheduler is not None
    assert _bot is not None

    jobs = [
        (_job_id(chat_id, "vk"), poll_vk_stories, VK_POLL_INTERVAL),
        (_job_id(chat_id, "ig"), poll_ig_stories, IG_POLL_INTERVAL),
        (_job_id(chat_id, "tt_stories"), poll_tt_stories, TT_STORIES_INTERVAL),
        (_job_id(chat_id, "tt_posts"), poll_tt_posts, TT_POSTS_INTERVAL),
    ]

    for jid, func, interval in jobs:
        existing = _scheduler.get_job(jid)
        if existing is not None:
            continue
        _scheduler.add_job(
            func,
            trigger="interval",
            seconds=interval,
            id=jid,
            kwargs={"chat_id": chat_id, "bot": _bot},
            replace_existing=True,
        )
        logger.debug("job_added", job_id=jid, interval_seconds=interval)


def _remove_jobs(chat_id: int) -> None:
    """Remove all jobs for a chat."""
    assert _scheduler is not None

    for suffix in ("vk", "ig", "tt_stories", "tt_posts"):
        jid = _job_id(chat_id, suffix)
        try:
            _scheduler.remove_job(jid)
            logger.debug("job_removed", job_id=jid)
        except Exception:
            pass