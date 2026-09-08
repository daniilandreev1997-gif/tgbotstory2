"""/start command and main menu navigation."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import structlog

from bot.db import get_targets

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# /start
# ---------------------------------------------------------------------------

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start — show the main menu with two buttons."""
    if update.effective_chat is None:
        return
    assert update.message is not None

    keyboard = [
        [InlineKeyboardButton("📡 Мониторинг", callback_data="monitoring")],
        [InlineKeyboardButton("👁 Показать сейчас", callback_data="show_now")],
    ]
    await update.message.reply_text(
        "👋 Привет! Я бот мониторинга VK, IG и TT контента.\n\n"
        "Выберите действие:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ---------------------------------------------------------------------------
# Button handler — handles all non-add flows
# ---------------------------------------------------------------------------

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline button callbacks (except add_* which go to ConversationHandler)."""
    query = update.callback_query
    if query is None:
        return
    await query.answer()

    data = query.data

    if data == "monitoring":
        await _show_monitoring_menu(query)
    elif data == "main_menu":
        await _show_main_menu(query)
    elif data == "show_now":
        await _handle_show_now(query, context)
    elif data is not None and data.startswith("platform_"):
        platform = data.split("_", 1)[1]
        await _show_platform_menu(query, platform)
    elif data is not None and data.startswith("remove_"):
        platform = data.split("_", 1)[1]
        await _handle_remove_target(query, platform)
    elif data is not None and data.startswith("rm_"):
        # rm_vk_75327684
        parts = data.split("_", 2)
        if len(parts) == 3:
            platform = parts[1]
            target = parts[2]
            await _confirm_remove(query, platform, target)
    else:
        logger.debug("unknown_callback", data=data)


# ---------------------------------------------------------------------------
# Menu helpers
# ---------------------------------------------------------------------------

async def _show_main_menu(query) -> None:
    """Show the main menu."""
    keyboard = [
        [InlineKeyboardButton("📡 Мониторинг", callback_data="monitoring")],
        [InlineKeyboardButton("👁 Показать сейчас", callback_data="show_now")],
    ]
    await query.edit_message_text(
        "Главное меню:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def _show_monitoring_menu(query) -> None:
    """Show platform selection menu."""
    keyboard = [
        [
            InlineKeyboardButton("VK", callback_data="platform_vk"),
            InlineKeyboardButton("IG", callback_data="platform_ig"),
            InlineKeyboardButton("TT", callback_data="platform_tt"),
        ],
        [InlineKeyboardButton("← Назад", callback_data="main_menu")],
    ]
    await query.edit_message_text(
        "Выберите платформу:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def _show_platform_menu(query, platform: str) -> None:
    """Show targets for a platform + add/remove buttons."""
    if query.message is None:
        return
    chat_id = query.message.chat_id
    targets = await get_targets(chat_id, platform)

    if targets:
        lines = [f"{i+1}. {t['display_name']} ({t['target']})" for i, t in enumerate(targets)]
        text = f"📡 Мониторинг {platform.upper()}:\n" + "\n".join(lines)
    else:
        text = f"📡 Мониторинг {platform.upper()}:\n— пусто —"

    keyboard = [
        [InlineKeyboardButton("➕ Добавить", callback_data=f"add_{platform}")],
        [InlineKeyboardButton("➖ Удалить", callback_data=f"remove_{platform}")],
        [InlineKeyboardButton("← Назад", callback_data="monitoring")],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


# ---------------------------------------------------------------------------
# Remove target
# ---------------------------------------------------------------------------

async def _handle_remove_target(query, platform: str) -> None:
    """Show numbered list of targets for removal."""
    if query.message is None:
        return
    chat_id = query.message.chat_id
    targets = await get_targets(chat_id, platform)

    if not targets:
        await query.edit_message_text(
            f"Нет целей для удаления на платформе {platform.upper()}.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("← Назад", callback_data=f"platform_{platform}")]
            ]),
        )
        return

    keyboard = []
    for t in targets:
        label = f"{t['display_name']} ({t['target']})"
        keyboard.append([
            InlineKeyboardButton(f"❌ {label}", callback_data=f"rm_{platform}_{t['target']}")
        ])
    keyboard.append([
        InlineKeyboardButton("← Назад", callback_data=f"platform_{platform}")
    ])

    await query.edit_message_text(
        f"Выберите цель для удаления ({platform.upper()}):",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def _confirm_remove(query, platform: str, target: str) -> None:
    """Remove the target and show updated menu."""
    from bot.db import remove_target, count_targets
    from bot.scheduler import stop_scheduler

    if query.message is None:
        return
    chat_id = query.message.chat_id
    removed = await remove_target(chat_id, platform, target)

    if removed:
        total = await count_targets(chat_id)
        if total == 0:
            await stop_scheduler(chat_id)

    await _show_platform_menu(query, platform)


# ---------------------------------------------------------------------------
# Show now
# ---------------------------------------------------------------------------

async def _handle_show_now(query, context) -> None:
    """Trigger immediate poll for all targets."""
    from bot.handlers.show_now import execute_show_now
    await execute_show_now(query, context)