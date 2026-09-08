"""Media delivery pipeline: download -> compress -> upload -> cleanup."""

import asyncio
import os
from pathlib import Path
from typing import TYPE_CHECKING

import aiohttp

if TYPE_CHECKING:
    from aiogram import Bot


class MediaDelivery:
    """Download media files from platform URLs and deliver via Telegram bot."""

    def __init__(self, bot: "Bot", chat_id: int, temp_dir: str, max_size_mb: int = 50) -> None:
        self._bot = bot
        self._chat_id = chat_id
        self._temp_dir = temp_dir
        self._max_size_mb = max_size_mb
        self._max_size_bytes = max_size_mb * 1024 * 1024
        os.makedirs(temp_dir, exist_ok=True)

    async def deliver(self, media_item) -> list[int]:
        downloaded: list[str] = []
        msg_ids: list[int] = []

        async with aiohttp.ClientSession() as http_session:
            try:
                for i, url in enumerate(media_item.media_urls):
                    local_path = await self._download_file(url, media_item, i, http_session)
                    if local_path:
                        downloaded.append(local_path)

                if not downloaded:
                    return []

                if len(downloaded) == 1:
                    mid = await self._send_single(downloaded[0], media_item)
                    if mid:
                        msg_ids.append(mid)
                else:
                    mids = await self._send_media_group(downloaded, media_item)
                    msg_ids.extend(mids)

            finally:
                await self._cleanup(downloaded)

        return msg_ids

    async def _download_file(self, url: str, media_item, index: int, session) -> str | None:
        ext = ".mp4" if media_item.is_video else ".jpg"
        filename = f"{media_item.platform}_{media_item.content_pk}_{index}{ext}"
        filepath = os.path.join(self._temp_dir, filename)

        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                if resp.status == 200:
                    content = await resp.read()
                    with open(filepath, "wb") as f:
                        f.write(content)
                    return filepath
        except Exception:
            self._remove_file(filepath)

        return None

    @staticmethod
    def _remove_file(filepath: str) -> None:
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except OSError:
            pass

    async def _send_single(self, filepath: str, media_item) -> int | None:
        try:
            if media_item.is_video:
                file_size = os.path.getsize(filepath) if os.path.exists(filepath) else 0
                if file_size > self._max_size_bytes:
                    compressed = await self._compress_video(filepath)
                    if compressed and os.path.exists(compressed):
                        filepath = compressed
                msg = await self._send_with_retry(
                    lambda: self._bot.send_video(
                        chat_id=self._chat_id,
                        video=filepath,
                        caption=media_item.caption,
                    )
                )
            else:
                msg = await self._send_with_retry(
                    lambda: self._bot.send_photo(
                        chat_id=self._chat_id,
                        photo=filepath,
                        caption=media_item.caption,
                    )
                )
            return msg.message_id if msg else None
        except Exception:
            return None

    async def _send_media_group(self, filepaths: list[str], media_item) -> list[int]:
        from aiogram.types import FSInputFile, InputMediaPhoto, InputMediaVideo

        media = []
        for i, fp in enumerate(filepaths):
            if not os.path.exists(fp):
                continue
            caption = media_item.caption if i == 0 and media_item.caption else None
            if media_item.is_video:
                media.append(InputMediaVideo(media=FSInputFile(fp), caption=caption))
            else:
                media.append(InputMediaPhoto(media=FSInputFile(fp), caption=caption))

        if not media:
            return []

        try:
            msgs = await self._bot.send_media_group(chat_id=self._chat_id, media=media)
            return [m.message_id for m in msgs]
        except Exception:
            return []

    async def _send_with_retry(self, send_func, max_retries: int = 2):
        from aiogram.exceptions import TelegramNetworkError

        for attempt in range(max_retries):
            try:
                return await send_func()
            except TelegramNetworkError:
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(1)
        return None

    async def _compress_video(self, filepath: str) -> str | None:
        compressed = filepath.replace(".mp4", "_compressed.mp4")
        try:
            import subprocess

            result = subprocess.run(
                ["ffmpeg", "-y", "-i", filepath, "-c:v", "libx264", "-crf", "28", "-preset", "fast", "-movflags", "+faststart", compressed],
                capture_output=True,
                timeout=120,
            )
            if result.returncode == 0 and os.path.exists(compressed):
                return compressed
        except Exception:
            pass
        return None

    async def _cleanup(self, filepaths: list[str]) -> None:
        for fp in filepaths:
            self._remove_file(fp)
