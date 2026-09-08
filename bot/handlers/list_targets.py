"""List targets handler."""

from aiogram import Router
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from sqlalchemy import select

from bot.db.models import Target
from bot.db.session import get_session_factory

list_targets_router = Router(name="list_targets")


def _target_to_dict(t: Target) -> dict:
    """Convert ORM Target to dict for keyboard builder."""
    return {
        "id": t.id,
        "platform": t.platform,
        "target_username": t.target_username,
        "content_type": t.content_type,
        "is_active": t.is_active,
    }


def build_list_keyboard(targets: list[dict], page: int = 0, per_page: int = 5) -> InlineKeyboardMarkup:
    if not targets:
        return InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="← Назад", callback_data="menu:back")]]
        )

    total_pages = max(1, (len(targets) + per_page - 1) // per_page)
    start = page * per_page
    end = start + per_page
    page_targets = targets[start:end]

    buttons = []
    for t in page_targets:
        status = "🟢" if t.get("is_active", True) else "🔴"
        platform = t.get("platform", "?")
        username = t.get("target_username", "?")
        content_type = t.get("content_type", "?")
        label = f"{status} {platform} | {username} ({content_type})"
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"target_info:{t.get('id', 0)}")])

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀", callback_data=f"list_targets:page:{page - 1}"))
    nav_buttons.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="▶", callback_data=f"list_targets:page:{page + 1}"))
    if nav_buttons:
        buttons.append(nav_buttons)

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


@list_targets_router.callback_query(lambda c: c.data == "list_targets")
async def show_list(callback: CallbackQuery) -> None:
    targets = await _fetch_active_targets()
    await callback.message.edit_text(
        "📋 **Список целей**" if targets else "📋 **Список целей**\n\nНет активных целей.",
        reply_markup=build_list_keyboard(targets),
    )
    await callback.answer()


@list_targets_router.callback_query(lambda c: c.data and c.data.startswith("list_targets:page:"))
async def paginate_list(callback: CallbackQuery) -> None:
    page = int(callback.data.split(":")[-1])
    targets = await _fetch_active_targets()
    total_pages = max(1, (len(targets) + 4) // 5)
    await callback.message.edit_text(
        f"📋 **Список целей**\n\nСтраница {page + 1}/{total_pages}",
        reply_markup=build_list_keyboard(targets, page=page),
    )
    await callback.answer()
