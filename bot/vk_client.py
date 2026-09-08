"""VK API client — fetches stories via stories.get."""

from __future__ import annotations

import os
import ssl
from typing import Any

import aiohttp
import structlog

from bot.config import VK_API_VERSION, VK_STORIES_URL

logger = structlog.get_logger(__name__)

# Workaround for Windows SSL certificate issues
_SSL_CONTEXT = ssl.create_default_context()
_SSL_CONTEXT.check_hostname = False
_SSL_CONTEXT.verify_mode = ssl.CERT_NONE


async def fetch_stories(access_token: str, owner_id: int) -> list[dict[str, Any]]:
    """Fetch current stories for a single VK user.

    VK API returns grouped stories: top-level items may have ``type: "stories"``
    with a nested ``stories[]`` array.  This function flattens them so every
    returned dict is a concrete story (``type: "photo"`` or ``type: "video"``).
    Each flattened story gets an ``_owner_id`` field for context.

    Args:
        access_token: VK API access token.
        owner_id: VK user/community ID.

    Returns:
        A list of story dicts (each containing at least 'id', 'type', '_owner_id').
        Returns an empty list when no stories exist or on error.
    """
    params: dict[str, str | int] = {
        "owner_id": owner_id,
        "access_token": access_token,
        "v": VK_API_VERSION,
    }

    # Check if proxy is available for VK API (may need it for Russia)
    proxy_url = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
    connector_kwargs = {"ssl": _SSL_CONTEXT}
    if proxy_url:
        connector_kwargs["proxy"] = proxy_url
    connector = aiohttp.TCPConnector(**connector_kwargs)
    async with aiohttp.ClientSession(connector=connector) as session:
        try:
            async with session.get(VK_STORIES_URL, params=params, timeout=15) as resp:
                data: dict[str, Any] = await resp.json()
        except aiohttp.ClientError as exc:
            logger.error("vk_api_request_failed", owner_id=owner_id, error=str(exc))
            return []
        except Exception as exc:
            logger.error("vk_api_unexpected_error", owner_id=owner_id, error=str(exc))
            return []

    if "error" in data:
        logger.error(
            "vk_api_error_response",
            owner_id=owner_id,
            error_code=data["error"].get("error_code"),
            error_msg=data["error"].get("error_msg"),
        )
        return []

    items: list[dict[str, Any]] = data.get("response", {}).get("items", [])
    logger.debug("vk_stories_fetched_raw", owner_id=owner_id, count=len(items))

    # Flatten grouped stories: items with type="stories" wrap a stories[] array
    flat_stories: list[dict[str, Any]] = []
    for item in items:
        if item.get("type") == "stories":
            nested = item.get("stories", [])
            for s in nested:
                s["_owner_id"] = owner_id
                flat_stories.append(s)
        else:
            item["_owner_id"] = owner_id
            flat_stories.append(item)

    logger.debug("vk_stories_fetched_flat", owner_id=owner_id, count=len(flat_stories))
    return flat_stories


def extract_story_media_url(story: dict[str, Any]) -> str | None:
    """Extract the best available media URL from a story object.

    - For 'photo' type: uses the largest size from ``photo.sizes``.
    - For 'video' type: picks the highest available quality mp4 file from
      ``video.files``, falling back to ``video.player`` (iframe) or
      ``video.first_frame`` (preview image).

    Returns:
        Direct URL string or None if extraction fails.
    """
    story_id: str = story.get("id", "")
    story_type: str = story.get("type", "")

    # Temporary debug log — remove after confirming the structure
    logger.debug("story_structure_dump", story_id=story_id, story_type=story_type, keys=list(story.keys()))

    if story_type == "photo":
        photo = story.get("photo", {})
        sizes: list[dict[str, Any]] = photo.get("sizes", [])
        if not sizes:
            logger.warning("photo_story_no_sizes", story_id=story_id)
            return None
        # The last element in sizes is the largest
        url = sizes[-1].get("url")
        if url:
            logger.debug("photo_url_extracted", story_id=story_id, url=url[:80])
        return url

    if story_type == "video":
        video = story.get("video", {})
        files: dict[str, str] = video.get("files", {})
        if files:
            # Quality preference order
            for quality in ("mp4_1080", "mp4_720", "mp4_480", "mp4_360", "mp4_240"):
                url = files.get(quality)
                if url:
                    logger.debug("video_url_extracted", story_id=story_id, quality=quality, url=url[:80])
                    return url
            # Fallback: first available key
            url = next(iter(files.values()))
            logger.debug("video_url_fallback", story_id=story_id, url=url[:80])
            return url

        # Fallback: video.player (iframe embed) — not a direct media URL, but log it
        player = video.get("player", "")
        if player:
            logger.warning("video_story_player_only", story_id=story_id, player=player[:80])

        # Fallback: first_frame preview image
        first_frame: list[dict[str, Any]] = video.get("first_frame", [])
        if first_frame:
            url = first_frame[-1].get("url")
            if url:
                logger.debug("video_first_frame_preview", story_id=story_id, url=url[:80])
                return url

        logger.warning("video_story_no_files", story_id=story_id)
        return None

    logger.warning("unknown_story_type", story_type=story_type, story_id=story_id)
    return None