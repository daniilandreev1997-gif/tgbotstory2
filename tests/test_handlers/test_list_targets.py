"""Tests for list_targets handler."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_list_targets_shows_active():
    from bot.handlers.list_targets import build_list_keyboard, show_list

    callback = AsyncMock()
    callback.data = "list_targets"
    callback.message = AsyncMock()
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()

    await show_list(callback)

    callback.message.edit_text.assert_called_once()
    callback.answer.assert_called_once()

    call_arg = callback.message.edit_text.call_args[0][0]
    assert "Список целей" in call_arg
