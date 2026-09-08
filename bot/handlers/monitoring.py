"""Monitoring handlers — add/remove/list targets with ConversationHandler."""

from __future__ import annotations

import os
import re

import structlog
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.config import VK_API_VERSION, VK_USERS_URL, load_vk_token
from bot.db import add_target, count_targets
from bot.scheduler import ensure_scheduler

logger = structlog.get_logger(__name__)

# Conversation states
(
    WAITING_VK_TARGET,
    WAITING_IG_TARGET,
    WAITING_TT_TARGET,
) = range(3)


# ---------------------------------------------------------------------------
# Entry points — triggered by callback "add_vk", "add_ig", "add_tt"
# ---------------------------------------------------------------------------

async def start_add_vk(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompt user for VK ID."""
    query = update.callback_query
    if query is not None:
        await query.answer()
        await query.edit_message_text(
            "Введите ID пользователя VK (цифры):\n"
            "Например: 75327684\n\n"
            "Где найти ID:\n"
            "1. Откройте профиль в VK\n"
            "2. Скопируйте цифры из адресной строки\n"
            "   vk.com/id123456789 → 123456789"
        )
    return WAITING_VK_TARGET


async def start_add_ig(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompt user for IG username."""
    query = update.callback_query
    if query is not None:
        await query.answer()
        await query.edit_message_text(
            "Введите username Instagram (без @):\n"
            "Например: username\n\n"
            "Допустимы: буквы, цифры, точка, подчёркивание"
        )
    return WAITING_IG_TARGET


async def start_add_tt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompt user for TT username."""
    query = update.callback_query
    if query is not None:
        await query.answer()
        await query.edit_message_text(
            "Введите username TikTok (без @):\n"
            "Например: username\n\n"
            "Допустимы: буквы, цифры, точка, подчёркивание"
        )
    return WAITING_TT_TARGET


# ---------------------------------------------------------------------------
# Receivers
# ---------------------------------------------------------------------------

async def _receive_vk_target(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Validate and add VK target."""
    if update.message is None or update.effective_chat is None:
        return ConversationHandler.END

    chat_id = update.effective_chat.id
    text = update.message.text.strip()

    try:
        target_id = int(text)
    except ValueError:
        await update.message.reply_text("❌ ID должен быть числом. Попробуйте ещё раз:")
        return WAITING_VK_TARGET

    vk_token = load_vk_token()
    display_name = await _resolve_vk_name(vk_token, target_id)
    if display_name is None:
        await update.message.reply_text(
            "❌ Не удалось найти пользователя VK с таким ID.",
            reply_markup=_back_button("platform_vk"),
        )
        return ConversationHandler.END

    added = await add_target(chat_id, "vk", str(target_id), display_name)
    if not added:
        await update.message.reply_text(
            f"⚠️ {display_name} ({target_id}) уже в мониторинге.",
            reply_markup=_back_button("platform_vk"),
        )
        return ConversationHandler.END

    await ensure_scheduler(chat_id)

    await update.message.reply_text(
        f"✅ {display_name} ({target_id}) добавлен в мониторинг.",
        reply_markup=_back_button("platform_vk"),
    )
    return ConversationHandler.END


async def _receive_ig_target(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Validate and add IG target."""
    if update.message is None or update.effective_chat is None:
        return ConversationHandler.END

    chat_id = update.effective_chat.id
    username = update.message.text.strip().lstrip("@")

    if not re.match(r"^[a-zA-Z0-9._]+$", username):
        await update.message.reply_text(
            "❌ Некорректный username. Только буквы, цифры, точка, подчёркивание."
        )
        return WAITING_IG_TARGET

    display_name = f"@{username}"
    added = await add_target(chat_id, "ig", username, display_name)
    if not added:
        await update.message.reply_text(
            f"⚠️ {display_name} уже в мониторинге.",
            reply_markup=_back_button("platform_ig"),
        )
        return ConversationHandler.END

    await ensure_scheduler(chat_id)

    await update.message.reply_text(
        f"✅ {display_name} добавлен в мониторинг.",
        reply_markup=_back_button("platform_ig"),
    )
    return ConversationHandler.END


async def _receive_tt_target(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Validate and add TT target."""
    if update.message is None or update.effective_chat is None:
        return ConversationHandler.END

    chat_id = update.effective_chat.id
    username = update.message.text.strip().lstrip("@")

    if not re.match(r"^[a-zA-Z0-9._]+$", username):
        await update.message.reply_text(
            "❌ Некорректный username. Только буквы, цифры, точка, подчёркивание."
        )
        return WAITING_TT_TARGET

    display_name = f"@{username}"
    added = await add_target(chat_id, "tt", username, display_name)
    if not added:
        await update.message.reply_text(
            f"⚠️ {display_name} уже в мониторинге.",
            reply_markup=_back_button("platform_tt"),
        )
        return ConversationHandler.END

    await ensure_scheduler(chat_id)

    await update.message.reply_text(
        f"✅ {display_name} добавлен в мониторинг.",
        reply_markup=_back_button("platform_tt"),
    )
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# Cancel handler
# ---------------------------------------------------------------------------

async def cancel_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel add target."""
    await update.message.reply_text("❌ Добавление отменено.")
    # Import locally to avoid circular import
    from bot.handlers.menu import start_command
    await start_command(update, context)
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# ConversationHandler factory
# ---------------------------------------------------------------------------

def build_monitoring_conv_handler() -> ConversationHandler:
    """Build a ConversationHandler for adding targets."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_add_vk, pattern="^add_vk$"),
            CallbackQueryHandler(start_add_ig, pattern="^add_ig$"),
            CallbackQueryHandler(start_add_tt, pattern="^add_tt$"),
        ],
        states={
            WAITING_VK_TARGET: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _receive_vk_target),
            ],
            WAITING_IG_TARGET: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _receive_ig_target),
            ],
            WAITING_TT_TARGET: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _receive_tt_target),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_add, pattern="^(main_menu|monitoring|platform_)"),
        ],
        per_message=False,
        per_chat=True,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _back_button(callback_data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("← Назад", callback_data=callback_data)]
    ])


async def _resolve_vk_name(access_token: str, user_id: int) -> str | None:
    """Resolve VK user ID to display name via users.get."""
    import aiohttp

    from bot.vk_client import _SSL_CONTEXT

    params = {
        "user_ids": str(user_id),
        "access_token": access_token,
        "v": VK_API_VERSION,
    }
    try:
        # Check if proxy is available for VK API (may need it for Russia)
        proxy_url = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
        connector_kwargs = {"ssl": _SSL_CONTEXT}
        if proxy_url:
            connector_kwargs["proxy"] = proxy_url
        connector = aiohttp.TCPConnector(**connector_kwargs)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(VK_USERS_URL, params=params, timeout=10) as resp:
                data = await resp.json()
        if "error" in data:
            return None
        users = data.get("response", [])
        if users:
            user = users[0]
            name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
            return name if name else None
    except Exception as exc:
        logger.warning("resolve_vk_name_failed", user_id=user_id, error=str(exc))
    return None