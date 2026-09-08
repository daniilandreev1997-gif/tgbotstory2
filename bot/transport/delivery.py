"""Transport helpers — download and send media to Telegram."""

from __future__ import annotations

import io
import ssl
from typing import TYPE_CHECKING

import aiohttp
import structlog

if TYPE_CHECKING:
    from telegram import Bot

logger = structlog.get_logger(__name__)

# Workaround for Windows SSL certificate issues
_SSL_CONTEXT = ssl.create_default_context()
_SSL_CONTEXT.check_hostname = False
_SSL_CONTEXT.verify_mode = ssl.CERT_NONE


async def send_photo(bot: Bot, chat_id: int, photo_url: str, caption: str | None = None) -> None:
    """Download a photo from VK and send it to a Telegram chat."""
    connector = aiohttp.TCPConnector(ssl=_SSL_CONTEXT)
    async with aiohttp.ClientSession(connector=connector) as session:
        try:
            async with session.get(photo_url, timeout=30) as resp:
                resp.raise_for_status()
                photo_bytes = await resp.read()
        except aiohttp.ClientError as exc:
            logger.error("photo_download_failed", url=photo_url, error=str(exc))
            return

    photo_file = io.BytesIO(photo_bytes)
    photo_file.name = "story.jpg"
    await bot.send_photo(chat_id=chat_id, photo=photo_file, caption=caption or "")
    logger.debug("photo_sent", url=photo_url)


async def send_video(bot: Bot, chat_id: int, video_url: str, caption: str | None = None) -> None:
    """Download a video from VK and send it to a Telegram chat."""
    connector = aiohttp.TCPConnector(ssl=_SSL_CONTEXT)
    async with aiohttp.ClientSession(connector=connector) as session:
        try:
            async with session.get(video_url, timeout=60) as resp:
                resp.raise_for_status()
                video_bytes = await resp.read()
        except aiohttp.ClientError as exc:
            logger.error("video_download_failed", url=video_url, error=str(exc))
            return

    video_file = io.BytesIO(video_bytes)
    video_file.name = "story.mp4"
    await bot.send_video(chat_id=chat_id, video=video_file, caption=caption or "")
    logger.debug("video_sent", url=video_url)