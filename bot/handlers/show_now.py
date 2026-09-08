"""/show_now logic — immediately fetch and deliver content for all targets."""

from __future__ import annotations

import structlog
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.config import load_vk_token
from bot.db import get_targets, is_item_sent, mark_item_sent
from bot.ig_client import fetch_instagram_stories
from bot.tt_client import fetch_tiktok_posts, fetch_tiktok_stories
from bot.transport import send_photo, send_video
from bot.vk_client import extract_story_media_url, fetch_stories

logger = structlog.get_logger(__name__)


async def execute_show_now(query, context) -> None:
    """Fetch and deliver all current content for the chat's targets."""
    if query.message is None:
        return
    chat_id = query.message.chat_id
    bot = context.bot

    status_msg = await query.edit_message_text("⏳ Собираю текущий контент...")

    targets = await get_targets(chat_id)
    if not targets:
        await status_msg.edit_text(
            "Нет добавленных целей. Добавьте цель через 📡 Мониторинг.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("← Назад", callback_data="main_menu")]
            ]),
        )
        return

    vk_token = load_vk_token()
    delivered = {"vk": 0, "ig": 0, "tt": 0}

    for t in targets:
        platform = t["platform"]
        target = t["target"]
        display_name = t["display_name"]

        try:
            if platform == "vk":
                stories = await fetch_stories(vk_token, int(target))
                for s in stories:
                    sid = str(s.get("id", ""))
                    if not sid:
                        continue
                    if await is_item_sent(chat_id, "vk", target, sid, "story"):
                        continue
                    url = extract_story_media_url(s)
                    if not url:
                        continue
                    caption = _build_caption(display_name, target, platform)
                    if s.get("type") == "photo":
                        await send_photo(bot, chat_id, url, caption)
                    else:
                        await send_video(bot, chat_id, url, caption)
                    await mark_item_sent(chat_id, "vk", target, sid, "story")
                    delivered["vk"] += 1

            elif platform == "ig":
                stories = await fetch_instagram_stories(target)
                for s in stories:
                    if not s.get("url"):
                        continue
                    if await is_item_sent(chat_id, "ig", target, s["id"], "story"):
                        continue
                    caption = _build_caption(display_name, target, platform)
                    if s["type"] == "photo":
                        await send_photo(bot, chat_id, s["url"], caption)
                    else:
                        await send_video(bot, chat_id, s["url"], caption)
                    await mark_item_sent(chat_id, "ig", target, s["id"], "story")
                    delivered["ig"] += 1

            elif platform == "tt":
                # Stories
                stories = await fetch_tiktok_stories(target)
                for s in stories:
                    if not s.get("url"):
                        continue
                    if await is_item_sent(chat_id, "tt", target, s["id"], "story"):
                        continue
                    caption = _build_caption(display_name, target, platform)
                    await send_video(bot, chat_id, s["url"], caption)
                    await mark_item_sent(chat_id, "tt", target, s["id"], "story")
                    delivered["tt"] += 1

                # Posts (last 1)
                posts = await fetch_tiktok_posts(target, limit=1)
                for p in posts:
                    if not p.get("url"):
                        continue
                    if await is_item_sent(chat_id, "tt", target, p["id"], "post"):
                        continue
                    caption = _build_caption(display_name, target, platform)
                    await send_video(bot, chat_id, p["url"], caption)
                    await mark_item_sent(chat_id, "tt", target, p["id"], "post")
                    delivered["tt"] += 1

        except Exception as exc:
            logger.error(
                "show_now_error",
                platform=platform,
                target=target,
                error=str(exc),
            )

    total = sum(delivered.values())
    msg = (
        f"✅ Проверено: {len(targets)} целей.\n"
        f"Нового: {total} (VK: {delivered['vk']}, IG: {delivered['ig']}, TT: {delivered['tt']})."
    )
    await status_msg.edit_text(
        msg,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("← Назад", callback_data="main_menu")]
        ]),
    )


def _build_caption(display_name: str, target: str, platform: str) -> str:
    """Build a caption for a story/post."""
    if platform == "vk":
        link = f"https://vk.com/id{target}/"
    elif platform == "ig":
        link = f"https://instagram.com/{target}"
    else:
        link = f"https://tiktok.com/@{target}"
    return f"👁 {display_name} ({link})"