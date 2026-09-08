"""Add target FSM wizard."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

add_target_router = Router(name="add_target")


class AddTargetStates(StatesGroup):
    """FSM states for add target wizard."""

    waiting_platform = State()
    waiting_target_type = State()
    waiting_username = State()
    waiting_content_type = State()
    waiting_confirm = State()


PLATFORMS = ["vk", "instagram", "tiktok"]
PLATFORM_LABELS = {"vk": "VK", "instagram": "Instagram*", "tiktok": "TikTok"}
CONTENT_TYPES = ["stories", "posts"]
CONTENT_LABELS = {"stories": "📸 Истории", "posts": "📝 Посты"}
TARGET_TYPES = ["user", "public"]
TARGET_LABELS = {"user": "👤 Пользователь", "public": "📢 Паблик"}


def platform_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=f"{PLATFORM_LABELS[p]}", callback_data=f"add_target:platform:{p}")]
        for p in PLATFORMS
    ]
    buttons.append([InlineKeyboardButton(text="← Назад", callback_data="menu:back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def content_type_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=CONTENT_LABELS[ct], callback_data=f"add_target:content:{ct}")]
        for ct in CONTENT_TYPES
    ]
    buttons.append([InlineKeyboardButton(text="← Назад", callback_data="menu:back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def target_type_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=TARGET_LABELS[tt], callback_data=f"add_target:target_type:{tt}")]
        for tt in TARGET_TYPES
    ]
    buttons.append([InlineKeyboardButton(text="← Назад", callback_data="menu:back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data="add_target:confirm"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="menu:back"),
            ],
        ]
    )


@add_target_router.callback_query(lambda c: c.data == "add_target:start")
async def start_add_target(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddTargetStates.waiting_platform)
    await callback.message.edit_text("🎯 Выберите платформу:", reply_markup=platform_keyboard())
    await callback.answer()


@add_target_router.callback_query(AddTargetStates.waiting_platform, F.data.startswith("add_target:platform:"))
async def platform_selected(callback: CallbackQuery, state: FSMContext) -> None:
    platform = callback.data.split(":")[-1]
    await state.update_data(platform=platform)

    if platform == "vk":
        await state.set_state(AddTargetStates.waiting_target_type)
        await callback.message.edit_text(
            f"Платформа: **{PLATFORM_LABELS[platform]}**\n\nВыберите тип цели:",
            reply_markup=target_type_keyboard(),
        )
    else:
        await state.update_data(target_type="user")
        await state.set_state(AddTargetStates.waiting_username)
        await callback.message.edit_text(
            f"Платформа: **{PLATFORM_LABELS[platform]}**\n\nВведите username (без @):",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="← Назад", callback_data="menu:back")]]
            ),
        )
    await callback.answer()


@add_target_router.callback_query(AddTargetStates.waiting_target_type, F.data.startswith("add_target:target_type:"))
async def target_type_selected(callback: CallbackQuery, state: FSMContext) -> None:
    target_type = callback.data.split(":")[-1]
    await state.update_data(target_type=target_type)
    await state.set_state(AddTargetStates.waiting_username)
    await callback.message.edit_text(
        "Введите username (без @) или ID (например, 12345 или club12345):",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="← Назад", callback_data="menu:back")]]
        ),
    )
    await callback.answer()


@add_target_router.message(AddTargetStates.waiting_username)
async def username_entered(message: Message, state: FSMContext) -> None:
    username = message.text.strip() if message.text else ""
    if not username:
        await message.answer("❌ Имя пользователя не может быть пустым. Попробуйте ещё раз:")
        return
    username = username.lstrip("@")
    if len(username) < 2:
        await message.answer("❌ Слишком короткое имя. Попробуйте ещё раз:")
        return

    await state.update_data(username=username)
    await state.set_state(AddTargetStates.waiting_content_type)
    await message.answer(
        f"Username: **{username}**\n\nВыберите тип контента для отслеживания:",
        reply_markup=content_type_keyboard(),
    )


@add_target_router.callback_query(AddTargetStates.waiting_content_type, F.data.startswith("add_target:content:"))
async def content_type_selected(callback: CallbackQuery, state: FSMContext) -> None:
    content_type = callback.data.split(":")[-1]
    await state.update_data(content_type=content_type)
    data = await state.get_data()

    summary = (
        f"📋 **Подтверждение добавления:**\n\n"
        f"Платформа: **{PLATFORM_LABELS.get(data['platform'], data['platform'])}**\n"
        f"Тип: **{TARGET_LABELS.get(data.get('target_type', 'user'), data.get('target_type', 'user'))}**\n"
        f"Username: **{data['username']}**\n"
        f"Контент: **{CONTENT_LABELS[content_type]}**\n"
    )

    await state.set_state(AddTargetStates.waiting_confirm)
    await callback.message.edit_text(summary, reply_markup=confirm_keyboard())
    await callback.answer()


@add_target_router.callback_query(AddTargetStates.waiting_confirm, F.data == "add_target:confirm")
async def confirm_add(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await callback.message.edit_text(
        f"✅ Цель добавлена!\n\n"
        f"**{data['username']}** — {PLATFORM_LABELS.get(data['platform'], data['platform'])} "
        f"({CONTENT_LABELS.get(data['content_type'], data['content_type'])})",
    )
    await state.clear()
    await callback.answer("✅ Добавлено!")
