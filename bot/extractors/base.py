"""Abstract extractor interface and shared data types.

All platform extractors must implement this interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class MediaItem:
    """Standardised content item from any platform."""

    platform: str
    content_pk: str | int
    content_type: str
    target_id: str
    media_urls: list[str] = field(default_factory=list)
    caption: str | None = None
    timestamp: datetime | None = None
    is_video: bool = False
    duration_sec: int | None = None
    metadata: dict = field(default_factory=dict)


class AuthExpiredError(Exception):
    """Raised when platform credentials are invalid or expired."""

    def __init__(self, platform: str, credential_id: int | None = None, message: str | None = None) -> None:
        self.platform = platform
        self.credential_id = credential_id
        super().__init__(message or f"Auth expired for {platform}")


class RateLimitError(Exception):
    """Raised when platform rate limit is hit."""

    def __init__(self, platform: str, retry_after_sec: int = 60, message: str | None = None) -> None:
        self.platform = platform
        self.retry_after_sec = retry_after_sec
        super().__init__(message or f"Rate limited on {platform}, retry after {retry_after_sec}s")


class NetworkError(Exception):
    """Raised on connection failures."""

    def __init__(self, platform: str, original_error: str = "", message: str | None = None) -> None:
        self.platform = platform
        self.original_error = original_error
        super().__init__(message or f"Network error on {platform}: {original_error}")


class BaseExtractor(ABC):
    """Interface for all platform extractors."""

    def __init__(self, credentials: dict) -> None:
        self._credentials = credentials

    @abstractmethod
    async def poll(self, target: dict) -> list[MediaItem]:
        """Poll platform for new content from target."""
        ...

    @abstractmethod
    async def check_health(self) -> bool:
        """Verify credentials are still valid."""
        ...

    async def download(self, media_item: MediaItem, dest_dir: str) -> list[str]:
        """Download all media files from MediaItem to dest_dir."""
        import os
        import aiohttp

        downloaded: list[str] = []
        os.makedirs(dest_dir, exist_ok=True)

        async with aiohttp.ClientSession() as session:
            for i, url in enumerate(media_item.media_urls):
                ext = ".mp4" if media_item.is_video else ".jpg"
                filename = f"{media_item.platform}_{media_item.content_pk}_{i}{ext}"
                filepath = os.path.join(dest_dir, filename)

                try:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                        if resp.status == 200:
                            content = await resp.read()
                            with open(filepath, "wb") as f:
                                f.write(content)
                            downloaded.append(filepath)
                except Exception:
                    continue

        return downloaded
