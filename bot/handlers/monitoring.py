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

    # P3: Clean input — support id75327684, vk.com/id123, etc.
    # 1. Extract numeric ID from vk.com/idXXXX URL
    url_match = re.match(r"(?:https?://)?(?:m\.)?vk\.(?:com|ru)/id(\d+)", text)
    if url_match:
        text = url_match.group(1)
    elif re.match(r"(?:https?://)?(?:m\.)?vk\.(?:com|ru)/", text):
        # vk.com URL but not a numeric ID (screenname) — can't use
        await update.message.reply_text("❌ ID должен быть числом. Попробуйте ещё раз:")
        return WAITING_VK_TARGET
    else:
        # 2. Remove id/ID prefix (lstrip removes all 'i'/'d' chars from left)
        text = text.strip().lstrip("id").lstrip("ID")

    # 3. Validate it's a number
    if not text:
        await update.message.reply_text("❌ ID должен быть числом. Попробуйте ещё раз:")
        return WAITING_VK_TARGET

    try:
        target_id = int(text)
    except ValueError:
        await update.message.reply_text("❌ ID должен быть числом. Попробуйте ещё раз:")
        return WAITING_VK_TARGET

    vk_token = load_vk_token()
    display_name, error_type, error_code = await _resolve_vk_name(vk_token, target_id)

    # P1: Distinguish error types with specific messages
    if error_type == "network":
        await update.message.reply_text(
            "❌ Не удалось подключиться к VK API. Попробуйте позже.",
            reply_markup=_back_button("platform_vk"),
        )
        return WAITING_VK_TARGET

    if error_type == "api_error":
        await update.message.reply_text(
            f"❌ Ошибка VK API (код {error_code}). Попробуйте позже.",
            reply_markup=_back_button("platform_vk"),
        )
        return WAITING_VK_TARGET

    if display_name is None:
        await update.message.reply_text(
            "❌ Не удалось найти пользователя VK с таким ID.",
            reply_markup=_back_button("platform_vk"),
        )
        return WAITING_VK_TARGET  # P2: allow retry instead of END

    added = await add_target(chat_id, "vk", str(target_id), display_name)
    if not added:
        await update.message.reply_text(
            f"⚠️ {display_name} ({target_id}) уже в мониторинге.",
            reply_markup=_back_button("platform_vk"),
        )
        return ConversationHandler.END  # P2: END only for "already in monitoring"

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


async def _resolve_vk_name(access_token: str, user_id: int) -> tuple[str | None, str | None, str | None]:
    """Resolve VK user ID to display name via users.get.

    Returns (name, error_type, error_code):
    - name: display name if found, None otherwise
    - error_type: "network" | "api_error" | "not_found" | None
    - error_code: VK error code string if api_error, None otherwise
    """
    import aiohttp

    from bot.vk_client import _SSL_CONTEXT

    params = {
        "user_ids": str(user_id),
        "access_token": access_token,
        "v": VK_API_VERSION,
    }

    # Try direct connection first, then fall back to proxy
    proxy_url = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")

    for attempt, (use_proxy, proxy) in enumerate(((False, None), (True, proxy_url)), 1):
        # P0: Skip proxy attempt if no proxy configured
        if use_proxy and not proxy:
            continue

        try:
            proxy_connector = aiohttp.TCPConnector(
                ssl=_SSL_CONTEXT,
                proxy=proxy if use_proxy and proxy else None,
            )
            async with aiohttp.ClientSession(connector=proxy_connector) as session:
                async with session.get(VK_USERS_URL, params=params, timeout=10) as resp:
                    data = await resp.json()
            logger.debug("vk_users_get_response", user_id=user_id,
                          attempt=attempt, has_error="error" in data,
                          response_keys=list(data.keys()))
            if "error" in data:
                err = data["error"]
                error_code = err.get("error_code", "?")
                logger.error("vk_users_get_error", user_id=user_id,
                              error_code=error_code,
                              error_msg=err.get("error_msg"))
                return (None, "api_error", str(error_code))
            users = data.get("response", [])
            if users:
                user = users[0]
                name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
                return (name if name else None, None, None)
            return (None, "not_found", None)
        except Exception as exc:
            logger.error("resolve_vk_name_failed", user_id=user_id,
                            attempt=attempt, error=str(exc))
            if attempt == 1:
                continue  # try next attempt (with/without proxy)

    # All attempts exhausted — network error
    return (None, "network", None)