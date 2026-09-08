"""Tests for auth handler."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_auth_token_validation():
    from bot.handlers.auth import auth_router, AuthStates, platform_keyboard
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.storage.memory import MemoryStorage

    storage = MemoryStorage()

    callback = AsyncMock()
    callback.data = "auth:start"
    callback.message = AsyncMock()
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()

    state = FSMContext(storage=storage, key="test_auth")

    from bot.handlers.auth import start_auth
    await start_auth(callback, state)

    current_state = await state.get_state()
    assert current_state == AuthStates.waiting_platform
    callback.message.edit_text.assert_called_once()
    callback.answer.assert_called_once()
