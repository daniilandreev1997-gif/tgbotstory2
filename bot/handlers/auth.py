"""Auth handler - token/cookie upload FSM wizard."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from bot.config import load_settings
from bot.crypto import CredentialEncryption
from bot.db.models import AuthCredential
from bot.db.session import get_session_factory

auth_router = Router(name="auth")


class AuthStates(StatesGroup):
    """FSM states for auth wizard."""

    waiting_platform = State()
    waiting_credential_type = State()
    waiting_token_value = State()
    waiting_file_upload = State()
    waiting_label = State()
    waiting_confirm = State()


PLATFORMS = ["vk", "instagram", "tiktok"]
PLATFORM_LABELS = {"vk": "VK", "instagram": "Instagram*", "tiktok": "TikTok"}
CREDENTIAL_TYPES = ["token", "cookie", "session_file"]
CREDENTIAL_LABELS = {
    "token": "🔑 Токен",
    "cookie": "🍪 Cookie",
    "session_file": "📁 Файл сессии",
}


def platform_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=PLATFORM_LABELS[p], callback_data=f"auth:platform:{p}")]
        for p in PLATFORMS
    ]
    buttons.append([InlineKeyboardButton(text="← Назад", callback_data="menu:back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def credential_type_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=CREDENTIAL_LABELS[ct], callback_data=f"auth:cred_type:{ct}")]
        for ct in CREDENTIAL_TYPES
    ]
    buttons.append([InlineKeyboardButton(text="← Назад", callback_data="menu:back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Сохранить", callback_data="auth:confirm"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="menu:back"),
            ],
        ]
    )


@auth_router.callback_query(lambda c: c.data == "auth:start")
async def start_auth(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AuthStates.waiting_platform)
    await callback.message.edit_text(
        "🔑 **Загрузка токена/сессии**\n\nВыберите платформу:",
        reply_markup=platform_keyboard(),
    )
    await callback.answer()


@auth_router.callback_query(AuthStates.waiting_platform, F.data.startswith("auth:platform:"))
async def platform_selected(callback: CallbackQuery, state: FSMContext) -> None:
    platform = callback.data.split(":")[-1]
    await state.update_data(platform=platform)
    await state.set_state(AuthStates.waiting_credential_type)
    await callback.message.edit_text(
        f"Платформа: **{PLATFORM_LABELS[platform]}**\n\nВыберите тип данных:",
        reply_markup=credential_type_keyboard(),
    )
    await callback.answer()


@auth_router.callback_query(AuthStates.waiting_credential_type, F.data.startswith("auth:cred_type:"))
async def credential_type_selected(callback: CallbackQuery, state: FSMContext) -> None:
    cred_type = callback.data.split(":")[-1]
    await state.update_data(credential_type=cred_type)

    if cred_type in ("token", "cookie"):
        await state.set_state(AuthStates.waiting_token_value)
        await callback.message.edit_text(
            f"Тип: **{CREDENTIAL_LABELS[cred_type]}**\n\nОтправьте значение токена/куки текстом:",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="← Назад", callback_data="menu:back")]]
            ),
        )
    else:
        await state.set_state(AuthStates.waiting_file_upload)
        await callback.message.edit_text(
            f"Тип: **{CREDENTIAL_LABELS[cred_type]}**\n\nОтправьте файл сессии:",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="← Назад", callback_data="menu:back")]]
            ),
        )
    await callback.answer()


@auth_router.message(AuthStates.waiting_token_value)
async def token_value_entered(message: Message, state: FSMContext) -> None:
    value = message.text.strip() if message.text else ""
    if not value:
        await message.answer("❌ Значение не может быть пустым. Попробуйте ещё раз:")
        return

    await state.update_data(credential_value=value)
    await state.set_state(AuthStates.waiting_label)

    await message.answer(
        "Введите название для этого токена (например, 'Мой аккаунт VK'):",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="Пропустить", callback_data="auth:skip_label")]]
        ),
    )


@auth_router.message(AuthStates.waiting_file_upload)
async def file_uploaded(message: Message, state: FSMContext) -> None:
    if not message.document:
        await message.answer("❌ Отправьте файл (document). Попробуйте ещё раз:")
        return

    await state.update_data(
        file_name=message.document.file_name,
        file_id=message.document.file_id,
    )
    await state.set_state(AuthStates.waiting_label)

    await message.answer(
        "Введите название для этого файла:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="Пропустить", callback_data="auth:skip_label")]]
        ),
    )


@auth_router.message(AuthStates.waiting_label)
async def label_entered(message: Message, state: FSMContext) -> None:
    label = message.text.strip() if message.text else ""
    await state.update_data(label=label)
    await _show_confirm(message, state)


@auth_router.callback_query(AuthStates.waiting_label, F.data == "auth:skip_label")
async def skip_label(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(label="")
    await _show_confirm(callback, state)


async def _show_confirm(source, state: FSMContext) -> None:
    data = await state.get_data()
    await state.set_state(AuthStates.waiting_confirm)

    platform = PLATFORM_LABELS.get(data.get("platform", ""), data.get("platform", "?"))
    cred_type = CREDENTIAL_LABELS.get(data.get("credential_type", ""), data.get("credential_type", "?"))
    label = data.get("label", "")

    summary = (
        f"📋 **Подтверждение сохранения:**\n\n"
        f"Платформа: **{platform}**\n"
        f"Тип: **{cred_type}**\n"
        f"Название: **{label or '—'}**\n"
    )

    if isinstance(source, CallbackQuery):
        await source.message.edit_text(summary, reply_markup=confirm_keyboard())
        await source.answer()
    else:
        await source.answer(summary, reply_markup=confirm_keyboard())


@auth_router.callback_query(AuthStates.waiting_confirm, F.data == "auth:confirm")
async def confirm_auth(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    platform = data["platform"]
    credential_type = data["credential_type"]
    label = data.get("label", "")
    settings = load_settings()

    # Build credential payload dict based on type
    if credential_type in ("token", "cookie"):
        payload = {"token": data["credential_value"]}
    else:
        # session_file: store file_id + file_name
        payload = {
            "file_id": data.get("file_id", ""),
            "file_name": data.get("file_name", ""),
        }

    # Encrypt credential data before storing
    encrypted_data = CredentialEncryption.encrypt_dict(payload, settings.encryption_key)

    # Persist to database
    session_factory = get_session_factory()
    async with session_factory() as session:
        cred = AuthCredential(
            platform=platform,
            credential_type=credential_type,
            label=label or None,
            credential_data=encrypted_data,
            is_valid=True,
            added_by=callback.from_user.id if callback.from_user else None,
        )
        session.add(cred)
        await session.commit()

    await callback.message.edit_text(
        f"✅ Токен **{label or '—'}** сохранён!\n\n"
        f"Платформа: {PLATFORM_LABELS.get(platform, platform)}",
    )
    await state.clear()
    await callback.answer("✅ Сохранено!")
