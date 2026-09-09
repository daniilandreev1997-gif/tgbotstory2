"""Background poller — per-chat, per-platform polling logic."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import structlog
from telegram import Bot

from bot.config import (
    ERROR_COOLDOWN_MINUTES,
    TT_POSTS_SCAN_LIMIT,
    TZ_LABEL,
    TZ_OFFSET_HOURS,
    load_vk_token,
)
from bot.db import (
    clear_error_cooldown,
    get_error_count,
    get_targets,
    get_tt_post_index,
    is_in_cooldown,
    is_item_sent,
    mark_item_sent,
    set_error_cooldown,
    update_tt_post_index,
)
from bot.ig_client import fetch_instagram_stories
from bot.transport import send_photo, send_video
from bot.tt_client import fetch_tiktok_posts, fetch_tiktok_stories
from bot.vk_client import extract_story_media_url, fetch_stories

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Per-platform poll functions
# ---------------------------------------------------------------------------

async def poll_vk_stories(chat_id: int, bot: Bot) -> None:
    """Poll VK stories for all VK targets in a chat."""
    targets = await get_targets(chat_id, "vk")
    if not targets:
        return

    token = load_vk_token()

    for t in targets:
        target = t["target"]
        display_name = t["display_name"]

        if await is_in_cooldown(chat_id, "vk", target, ERROR_COOLDOWN_MINUTES):
            logger.debug("vk_cooldown_skip", chat_id=chat_id, target=target)
            continue

        try:
            stories = await fetch_stories(token, int(target))
        except Exception as exc:
            await _handle_error(chat_id, bot, "vk", target, display_name, exc)
            continue

        for s in stories:
            sid = str(s.get("id", ""))
            if not sid:
                continue
            if await is_item_sent(chat_id, "vk", target, sid, "story"):
                continue

            url = extract_story_media_url(s)
            if not url:
                continue

            caption = _build_caption(display_name, target, "vk")
            try:
                if s.get("type") == "photo":
                    await send_photo(bot, chat_id, url, caption)
                else:
                    await send_video(bot, chat_id, url, caption)
            except Exception as exc:
                logger.error("vk_delivery_failed", target=target, error=str(exc))
                continue

            await mark_item_sent(chat_id, "vk", target, sid, "story")
            logger.info("vk_item_delivered", chat_id=chat_id, target=target, item_id=sid)

        await clear_error_cooldown(chat_id, "vk", target)


async def poll_ig_stories(chat_id: int, bot: Bot) -> None:
    """Poll IG stories for all IG targets in a chat."""
    targets = await get_targets(chat_id, "ig")
    if not targets:
        return

    for t in targets:
        target = t["target"]
        display_name = t["display_name"]

        if await is_in_cooldown(chat_id, "ig", target, ERROR_COOLDOWN_MINUTES):
            logger.debug("ig_cooldown_skip", chat_id=chat_id, target=target)
            continue

        try:
            stories = await fetch_instagram_stories(target)
        except Exception as exc:
            if _is_chrome_not_found(exc):
                logger.debug("ig_chrome_not_found_skip", chat_id=chat_id, target=target)
                continue
            await _handle_error(chat_id, bot, "ig", target, display_name, exc)
            continue

        for s in stories:
            if not s.get("url"):
                continue
            if await is_item_sent(chat_id, "ig", target, s["id"], "story"):
                continue

            caption = _build_caption(display_name, target, "ig")
            try:
                if s["type"] == "photo":
                    await send_photo(bot, chat_id, s["url"], caption)
                else:
                    await send_video(bot, chat_id, s["url"], caption)
            except Exception as exc:
                logger.error("ig_delivery_failed", target=target, error=str(exc))
                continue

            await mark_item_sent(chat_id, "ig", target, s["id"], "story")
            logger.info("ig_item_delivered", chat_id=chat_id, target=target, item_id=s["id"])

        await clear_error_cooldown(chat_id, "ig", target)


async def poll_tt_stories(chat_id: int, bot: Bot) -> None:
    """Poll TT stories for all TT targets in a chat."""
    targets = await get_targets(chat_id, "tt")
    if not targets:
        return

    for t in targets:
        target = t["target"]
        display_name = t["display_name"]

        if await is_in_cooldown(chat_id, "tt", target, ERROR_COOLDOWN_MINUTES):
            logger.debug("tt_stories_cooldown_skip", chat_id=chat_id, target=target)
            continue

        try:
            stories = await fetch_tiktok_stories(target)
        except Exception as exc:
            if _is_chrome_not_found(exc):
                logger.debug("tt_stories_chrome_not_found_skip", chat_id=chat_id, target=target)
                continue
            await _handle_error(chat_id, bot, "tt", target, display_name, exc)
            continue

        for s in stories:
            if not s.get("url"):
                continue
            if await is_item_sent(chat_id, "tt", target, s["id"], "story"):
                continue

            caption = _build_caption(display_name, target, "tt")
            try:
                await send_video(bot, chat_id, s["url"], caption)
            except Exception as exc:
                logger.error("tt_stories_delivery_failed", target=target, error=str(exc))
                continue

            await mark_item_sent(chat_id, "tt", target, s["id"], "story")
            logger.info("tt_story_delivered", chat_id=chat_id, target=target, item_id=s["id"])

        await clear_error_cooldown(chat_id, "tt", target)


async def poll_tt_posts(chat_id: int, bot: Bot) -> None:
    """Poll TT posts — send 1 new post per 10 min interval."""
    targets = await get_targets(chat_id, "tt")
    if not targets:
        return

    for t in targets:
        target = t["target"]
        display_name = t["display_name"]

        if await is_in_cooldown(chat_id, "tt", target, ERROR_COOLDOWN_MINUTES):
            continue

        try:
            posts = await fetch_tiktok_posts(target, limit=TT_POSTS_SCAN_LIMIT)
        except Exception as exc:
            if _is_chrome_not_found(exc):
                logger.debug("tt_posts_chrome_not_found_skip", chat_id=chat_id, target=target)
                continue
            await _handle_error(chat_id, bot, "tt", target, display_name, exc)
            continue

        if not posts:
            continue

        idx_row = await get_tt_post_index(chat_id, target)
        last_sent = idx_row["last_sent_index"] if idx_row else -1
        total = len(posts)

        # First scan — send all immediately
        if last_sent == -1 and total > 0:
            for i, post in enumerate(posts):
                if not post.get("url"):
                    continue
                if await is_item_sent(chat_id, "tt", target, post["id"], "post"):
                    continue
                caption = _build_caption(display_name, target, "tt")
                try:
                    await send_video(bot, chat_id, post["url"], caption)
                except Exception as exc:
                    logger.error("tt_post_delivery_failed", target=target, error=str(exc))
                    continue
                await mark_item_sent(chat_id, "tt", target, post["id"], "post")
                logger.info("tt_post_delivered", chat_id=chat_id, target=target, post_id=post["id"])
            await update_tt_post_index(chat_id, target, total, total - 1)

        # Subsequent scans — send 1 new
        elif last_sent < total - 1:
            next_idx = last_sent + 1
            post = posts[next_idx]
            if post.get("url") and not await is_item_sent(chat_id, "tt", target, post["id"], "post"):
                caption = _build_caption(display_name, target, "tt")
                try:
                    await send_video(bot, chat_id, post["url"], caption)
                except Exception as exc:
                    logger.error("tt_post_delivery_failed", target=target, error=str(exc))
                else:
                    await mark_item_sent(chat_id, "tt", target, post["id"], "post")
                    logger.info("tt_post_delivered", chat_id=chat_id, target=target, post_id=post["id"])
            await update_tt_post_index(chat_id, target, total, next_idx)

        await clear_error_cooldown(chat_id, "tt", target)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_caption(display_name: str, target: str, platform: str) -> str:
    """Build a caption for a story/post."""
    if platform == "vk":
        link = f"https://vk.com/id{target}/"
    elif platform == "ig":
        link = f"https://instagram.com/{target}"
    else:
        link = f"https://tiktok.com/@{target}"
    return f"👁 {display_name} ({link})"


async def _handle_error(
    chat_id: int, bot: Bot, platform: str, target: str, display_name: str, exc: Exception,
) -> None:
    """Record error and notify chat once."""
    logger.error(
        f"{platform}_poll_error",
        chat_id=chat_id,
        target=target,
        error=str(exc),
    )

    await set_error_cooldown(chat_id, platform, target)
    error_count = await get_error_count(chat_id, platform, target)

    if error_count == 1:
        # First error — notify
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=f"❌ Ошибка {platform.upper()} для {display_name}: {_error_message(platform, exc)}",
            )
        except Exception:
            pass


def _is_chrome_not_found(exc: Exception) -> bool:
    """Return True if the exception is caused by missing browser binary (Selenium).

    In the HTTP-only version this always returns False since no browser is used.
    """
    msg = str(exc).lower()
    return ("cannot find" in msg and "binary" in msg) or "cannot find chrome" in msg


def _error_message(platform: str, exc: Exception) -> str:
    """Human-readable error message per platform."""
    msg = str(exc)[:200]
    if platform == "vk":
        if "token" in msg.lower() or "401" in msg:
            return "токен истёк. Обновите токен."
        return "ошибка сервера. Попробуем позже."
    elif platform == "ig":
        return "не удалось получить истории."
    else:
        return "не удалось получить контент."