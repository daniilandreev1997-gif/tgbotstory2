"""Tests for add_target handler."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_add_target_wizard_full_flow():
    from bot.handlers.add_target import (
        add_target_router,
        AddTargetStates,
        platform_keyboard,
        content_type_keyboard,
    )

    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.storage.memory import MemoryStorage

    storage = MemoryStorage()

    callback = AsyncMock()
    callback.data = "add_target:start"
    callback.message = AsyncMock()
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()

    state = FSMContext(storage=storage, key="test_add_target")

    from bot.handlers.add_target import start_add_target
    await start_add_target(callback, state)

    current_state = await state.get_state()
    assert current_state == AddTargetStates.waiting_platform
    callback.message.edit_text.assert_called_once()
    callback.answer.assert_called_once()


@pytest.mark.asyncio
async def test_add_target_invalid_username():
    from bot.handlers.add_target import add_target_router, AddTargetStates
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.storage.memory import MemoryStorage

    storage = MemoryStorage()
    state = FSMContext(storage=storage, key="test_invalid_username")
    await state.set_state(AddTargetStates.waiting_username)

    message = AsyncMock()
    message.text = ""
    message.answer = AsyncMock()

    from bot.handlers.add_target import username_entered
    await username_entered(message, state)

    message.answer.assert_called_once()
    call_arg = message.answer.call_args[0][0]
    assert "не может быть пустым" in call_arg
