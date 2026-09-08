"""Add target FSM wizard."""

import asyncio
import hashlib
import logging
from datetime import datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from bot.config import load_settings
from bot.crypto import CredentialEncryption
from bot.db.models import AuthCredential, ContentHash, Target
from bot.db.session import get_session_factory
from bot.extractors import VkExtractor
from bot.transport.delivery import MediaDelivery

logger = logging.getLogger(__name__)

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


async def _immediate_poll_and_deliver(
    session,
    target: Target,
    callback: CallbackQuery,
) -> int | None:
    """Immediately poll VK for stories and deliver results.

    Best-effort: failures do not affect target creation.

    Returns:
        Number of items found (>=0), None if credentials missing,
        or -1 if an error occurred.
    """
    try:
        # 1. Get VK credentials from DB
        stmt = select(AuthCredential).where(
            AuthCredential.platform == "vk",
            AuthCredential.is_valid == True,
        )
        result = await session.execute(stmt)
        cred_row = result.scalars().first()
        if not cred_row:
            return None

        # 2. Load settings
        settings = load_settings()

        # 3. Build VkExtractor with VK API (same pattern as scheduler._build_extractor)
        cred_dict = CredentialEncryption.decrypt_string(
            cred_row.credential_data, settings.encryption_key,
        )
        extractor = VkExtractor(credentials=cred_dict)

        from vkbottle import API
        extractor._api = API(token=cred_dict.get("user_token", ""))

        # 4. Poll for stories (first poll — get ALL active stories)
        target_dict = {
            "target_id": target.target_id,
            "target_type": target.target_type,
            "target_username": target.target_username,
            "content_type": "stories",
            "last_poll_pk": None,
        }
        items = await asyncio.wait_for(extractor.poll(target_dict), timeout=30)

        # 5. Deliver each item (same pattern as scheduler._poll_platform)
        delivery = MediaDelivery(
            bot=callback.bot,
            chat_id=callback.message.chat.id,
            temp_dir=settings.temp_media_dir,
            max_size_mb=settings.max_media_size_mb,
        )

        new_items = 0
        for item in items:
            content_hash = hashlib.sha256(
                f"{item.platform}:{item.content_pk}:{item.content_type}".encode("utf-8"),
            ).hexdigest()

            dup_stmt = select(ContentHash).where(
                ContentHash.target_id == target.id,
                ContentHash.content_hash == content_hash,
            )
            dup_result = await session.execute(dup_stmt)
            if dup_result.scalars().first():
                continue

            ch = ContentHash(
                target_id=target.id,
                platform=item.platform,
                content_pk=str(item.content_pk),
                content_type=item.content_type,
                content_hash=content_hash,
                media_urls={"urls": item.media_urls},
                content_meta=item.metadata,
                telegram_msg_ids=[],
            )
            session.add(ch)
            await session.flush()

            try:
                msg_ids = await delivery.deliver(item)
                ch.telegram_msg_ids = msg_ids
            except Exception:
                logger.warning(
                    "immediate_delivery_failed: content_pk=%s platform=%s",
                    item.content_pk,
                    "vk",
                )

            await session.commit()
            new_items += 1

        # 6. Update target polling state
        if items:
            target.last_poll_pk = str(items[-1].content_pk)
        target.last_polled_at = datetime.utcnow()
        target.error_count = 0
        target.last_error = None
        await session.commit()

        return len(items)

    except asyncio.TimeoutError:
        logger.warning("immediate_poll_timeout: target_id=%s", target.target_id)
        return -1
    except Exception:
        logger.exception("immediate_poll_failed: target_id=%s", target.target_id)
        return -1


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
    platform = data["platform"]
    target_type = data.get("target_type", "user")
    username = data["username"]
    content_type = data["content_type"]

    session_factory = get_session_factory()
    async with session_factory() as session:
        # Check for duplicate before inserting
        stmt = select(Target).where(
            Target.platform == platform,
            Target.target_id == username,
            Target.content_type == content_type,
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is not None:
            await callback.message.edit_text(
                "⚠️ Эта цель уже отслеживается.",
            )
            await state.clear()
            await callback.answer("⚠️ Уже существует")
            return

        # Persist to database
        target = Target(
            platform=platform,
            target_type=target_type,
            target_username=username,
            target_id=username,
            content_type=content_type,
            is_active=True,
            added_by=callback.from_user.id if callback.from_user else None,
        )
        session.add(target)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            await callback.message.edit_text(
                "⚠️ Эта цель уже отслеживается.",
            )
            await state.clear()
            await callback.answer("⚠️ Уже существует")
            return

        # If VK stories — immediately poll and deliver current stories
        items_count = -1
        if platform == "vk" and content_type == "stories":
            items_count = await _immediate_poll_and_deliver(
                session=session,
                target=target,
                callback=callback,
            )

    # Build success message based on immediate poll result
    if platform == "vk" and content_type == "stories":
        if items_count is None:
            await callback.message.edit_text(
                f"✅ Цель добавлена!\n\n"
                f"**{username}** — {PLATFORM_LABELS.get(platform, platform)} "
                f"({CONTENT_LABELS.get(content_type, content_type)})\n\n"
                f"_(Авторизация VK не настроена — stories будут проверены по расписанию.)_",
            )
        elif items_count > 0:
            await callback.message.edit_text(
                f"✅ Цель добавлена! Найдено {items_count} активных stories.\n\n"
                f"**{username}** — {PLATFORM_LABELS.get(platform, platform)} "
                f"({CONTENT_LABELS.get(content_type, content_type)})",
            )
        elif items_count == 0:
            await callback.message.edit_text(
                f"✅ Цель добавлена! Активных stories не найдено.\n\n"
                f"**{username}** — {PLATFORM_LABELS.get(platform, platform)} "
                f"({CONTENT_LABELS.get(content_type, content_type)})",
            )
        else:
            await callback.message.edit_text(
                f"✅ Цель добавлена!\n\n"
                f"**{username}** — {PLATFORM_LABELS.get(platform, platform)} "
                f"({CONTENT_LABELS.get(content_type, content_type)})\n\n"
                f"_(Не удалось проверить stories — будут проверены по расписанию.)_",
            )
    else:
        await callback.message.edit_text(
            f"✅ Цель добавлена!\n\n"
            f"**{username}** — {PLATFORM_LABELS.get(platform, platform)} "
            f"({CONTENT_LABELS.get(content_type, content_type)})",
        )
    await state.clear()
    await callback.answer("✅ Добавлено!")