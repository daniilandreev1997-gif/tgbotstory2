"""Tests for remove_target handler."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_remove_target_success():
    from bot.handlers.remove_target import build_remove_list_keyboard, start_remove_target, confirm_remove

    callback = AsyncMock()
    callback.data = "remove_target:start"
    callback.message = AsyncMock()
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()

    await start_remove_target(callback)

    callback.message.edit_text.assert_called_once()
    callback.answer.assert_called_once()


@pytest.mark.asyncio
async def test_remove_target_not_found():
    from bot.handlers.remove_target import build_remove_list_keyboard

    keyboard = build_remove_list_keyboard([])

    assert keyboard is not None
    all_buttons = []
    for row in keyboard.inline_keyboard:
        for btn in row:
            all_buttons.append(btn.text)

    assert "← Назад" in all_buttons
