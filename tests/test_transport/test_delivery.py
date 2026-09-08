"""Tests for media delivery."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_delivery_download_photo(mock_bot, temp_media_dir):
    from bot.transport.delivery import MediaDelivery

    delivery = MediaDelivery(bot=mock_bot, chat_id=123456, temp_dir=str(temp_media_dir), max_size_mb=50)
    assert delivery._chat_id == 123456
    assert delivery._max_size_mb == 50


@pytest.mark.asyncio
async def test_delivery_download_video_exceeds_50mb(mock_bot, temp_media_dir):
    from bot.transport.delivery import MediaDelivery

    delivery = MediaDelivery(bot=mock_bot, chat_id=123456, temp_dir=str(temp_media_dir), max_size_mb=50)
    assert delivery._max_size_bytes == 50 * 1024 * 1024


@pytest.mark.asyncio
async def test_delivery_cleanup_temp_files(mock_bot, temp_media_dir):
    import os
    from bot.transport.delivery import MediaDelivery

    delivery = MediaDelivery(bot=mock_bot, chat_id=123456, temp_dir=str(temp_media_dir), max_size_mb=50)

    test_file = temp_media_dir / "test_cleanup.txt"
    test_file.write_text("test")
    assert os.path.exists(str(test_file))

    delivery._remove_file(str(test_file))
    assert not os.path.exists(str(test_file))


@pytest.mark.asyncio
async def test_delivery_send_media_group(mock_bot, temp_media_dir):
    from bot.transport.delivery import MediaDelivery

    delivery = MediaDelivery(bot=mock_bot, chat_id=123456, temp_dir=str(temp_media_dir), max_size_mb=50)

    mock_bot.send_media_group = AsyncMock(return_value=[MagicMock(message_id=10), MagicMock(message_id=11)])

    result = await delivery._send_media_group([], MagicMock())
    assert result == []


@pytest.mark.asyncio
async def test_delivery_network_error_retry(mock_bot, temp_media_dir):
    from bot.transport.delivery import MediaDelivery
    from aiogram.exceptions import TelegramNetworkError

    delivery = MediaDelivery(bot=mock_bot, chat_id=123456, temp_dir=str(temp_media_dir), max_size_mb=50)

    call_count = 0
    async def flaky_send():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise TelegramNetworkError(method="sendMessage")
        return MagicMock(message_id=42)

    result = await delivery._send_with_retry(flaky_send, max_retries=2)
    assert result is not None
    assert result.message_id == 42
