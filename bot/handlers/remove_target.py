"""Remove target handler."""

from aiogram import F, Router
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from sqlalchemy import select

from bot.db.models import Target
from bot.db.session import get_session_factory

remove_target_router = Router(name="remove_target")


def _target_to_dict(t: Target) -> dict:
    """Convert ORM Target to dict for keyboard builder."""
    return {
        "id": t.id,
        "platform": t.platform,
        "target_username": t.target_username,
        "content_type": t.content_type,
        "is_active": t.is_active,
    }


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


async def _fetch_active_targets() -> list[dict]:
    """Fetch all active targets from DB, returned as dicts."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        stmt = select(Target).where(Target.is_active == True).order_by(Target.added_at.desc())
        result = await session.execute(stmt)
        targets = result.scalars().all()
        return [_target_to_dict(t) for t in targets]


@remove_target_router.callback_query(lambda c: c.data == "remove_target:start")
async def start_remove_target(callback: CallbackQuery) -> None:
    targets = await _fetch_active_targets()
    await callback.message.edit_text(
        "❌ **Удаление цели**\n\nВыберите цель для удаления:",
        reply_markup=build_remove_list_keyboard(targets),
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
