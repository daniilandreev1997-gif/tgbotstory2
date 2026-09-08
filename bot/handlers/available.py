"""Available accounts catalog handler."""

from aiogram import Router
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

available_router = Router(name="available")


@available_router.callback_query(lambda c: c.data == "available")
async def show_available(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "👁 **Доступные аккаунты**\n\n"
        "Каталог поддерживаемых платформ:\n"
        "• **VK** — пользователи и паблики\n"
        "• **Instagram*** — пользователи\n"
        "• **TikTok** — пользователи\n\n"
        "Для мониторинга добавьте цель и токен.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="← Назад", callback_data="menu:back")],
            ]
        ),
    )
    await callback.answer()
