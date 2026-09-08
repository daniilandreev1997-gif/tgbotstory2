"""Main menu handler - /start command with 5 inline buttons."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

menu_router = Router(name="menu")


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Build the main menu inline keyboard with 5 buttons."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎯 Выбрать", callback_data="add_target:start"),
                InlineKeyboardButton(text="🔑 Токен", callback_data="auth:start"),
            ],
            [
                InlineKeyboardButton(text="📋 Список", callback_data="list_targets"),
                InlineKeyboardButton(text="❌ Убрать", callback_data="remove_target:start"),
            ],
            [
                InlineKeyboardButton(text="👁 Доступные", callback_data="available"),
            ],
        ]
    )
    return keyboard


@menu_router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    """Handle /start command - show main menu."""
    await message.answer(
        "🤖 **tgbotstory2** — мультиплатформенный мониторинг\n\n"
        "Отслеживаю контент в VK, Instagram* и TikTok.\n"
        "Выберите действие:",
        reply_markup=get_main_menu_keyboard(),
    )


@menu_router.callback_query(lambda c: c.data == "menu:back")
async def back_to_menu(callback_query) -> None:
    """Return to main menu."""
    await callback_query.message.edit_text(
        "🤖 **tgbotstory2** — мультиплатформенный мониторинг\n\n"
        "Выберите действие:",
        reply_markup=get_main_menu_keyboard(),
    )
    await callback_query.answer()
