"""Remove target handler."""

from aiogram import F, Router
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

remove_target_router = Router(name="remove_target")


def build_remove_list_keyboard(targets: list) -> InlineKeyboardMarkup:
    if not targets:
        return InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="← Назад", callback_data="menu:back")]]
        )

    buttons = []
    for t in targets:
        label = f"{t.get('platform', '?')} | {t.get('target_username', '?')} ({t.get('content_type', '?')})"
        buttons.append([
            InlineKeyboardButton(
                text=f"❌ {label}",
                callback_data=f"remove_target:confirm:{t.get('id', 0)}",
            )
        ])

    buttons.append([InlineKeyboardButton(text="← Назад", callback_data="menu:back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@remove_target_router.callback_query(lambda c: c.data == "remove_target:start")
async def start_remove_target(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "❌ **Удаление цели**\n\nСписок целей загружается...\nВыберите цель для удаления:",
        reply_markup=build_remove_list_keyboard([]),
    )
    await callback.answer()


@remove_target_router.callback_query(lambda c: c.data.startswith("remove_target:confirm:"))
async def confirm_remove(callback: CallbackQuery) -> None:
    target_id = callback.data.split(":")[-1]
    await callback.message.edit_text(
        f"✅ Цель удалена!",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="← Назад", callback_data="menu:back")]]
        ),
    )
    await callback.answer("✅ Удалено!")
