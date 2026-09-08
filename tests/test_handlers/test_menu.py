"""Tests for menu handler."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_menu_shows_all_buttons():
    from bot.handlers.menu import get_main_menu_keyboard

    keyboard = get_main_menu_keyboard()
    assert keyboard is not None
    assert hasattr(keyboard, 'inline_keyboard')

    all_buttons = []
    for row in keyboard.inline_keyboard:
        for btn in row:
            all_buttons.append(btn.text)

    assert "🎯 Выбрать" in all_buttons
    assert "🔑 Токен" in all_buttons
    assert "📋 Список" in all_buttons
    assert "❌ Убрать" in all_buttons
    assert "👁 Доступные" in all_buttons
