"""TikTok client — fetches stories and posts via pure HTTP (no browser).

Approach:
1. Scrape the TikTok profile HTML (anonymous GET).
2. Extract JSON from <script id="__UNIVERSAL_DATA_FOR_REHYDRATION__">.
3. Parse story/post data from the JSON structure.
4. Extract video/image URLs.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from typing import Any

import aiohttp
import structlog

logger = structlog.get_logger(__name__)

# TikTok's embedded data script ID
_REHYDRATION_RE = re.compile(
    r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>',
    re.DOTALL,
)

# SSL context (Windows workaround)
import ssl
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


# ---------------------------------------------------------------------------
# Stories
# ---------------------------------------------------------------------------

async def fetch_tiktok_stories(username: str) -> list[dict[str, Any]]:
    """Fetch current stories for a TikTok user via HTTP scraping.

    Parses the TikTok profile HTML for story data embedded in the
    ``__UNIVERSAL_DATA_FOR_REHYDRATION__`` script tag.

    Args:
        username: TikTok username (without @).

    Returns:
        List of story dicts. Empty list on error or no stories.
    """
    url = f"https://www.tiktok.com/@{username}"
    html = await _fetch_html(url)
    if not html:
        return []

    data = _extract_rehydration_json(html)
    if not data:
        logger.debug("tt_no_rehydration_data", username=username)
        return []

    stories = _parse_stories_from_json(data, username)
    logger.info("tiktok_stories_fetched", username=username, count=len(stories))
    return stories


# ---------------------------------------------------------------------------
# Posts
# ---------------------------------------------------------------------------

async def fetch_tiktok_posts(username: str, limit: int = 20) -> list[dict[str, Any]]:
    """Fetch recent TikTok posts for a user via HTTP scraping.

    Parses the TikTok profile HTML for post data embedded in the
    ``__UNIVERSAL_DATA_FOR_REHYDRATION__`` script tag.

    Args:
        username: TikTok username (without @).
        limit: Maximum number of posts to return (default 20).

    Returns:
        List of post dicts. Empty list on error.
    """
    url = f"https://www.tiktok.com/@{username}"
    html = await _fetch_html(url)
    if not html:
        return []

    data = _extract_rehydration_json(html)
    if not data:
        logger.debug("tt_no_rehydration_data", username=username)
        return []

    posts = _parse_posts_from_json(data, username, limit)
    logger.info("tiktok_posts_fetched", username=username, count=len(posts), limit=limit)
    return posts


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

async def _fetch_html(url: str) -> str | None:
    """Fetch HTML from a URL via aiohttp."""
    connector = aiohttp.TCPConnector(ssl=_SSL_CTX)
    timeout = aiohttp.ClientTimeout(total=20)
    try:
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            async with session.get(url, headers=_HEADERS) as resp:
                if resp.status != 200:
                    logger.warning("tt_http_error", url=url, status=resp.status)
                    return None
                return await resp.text()
    except Exception as exc:
        logger.error("tt_http_fetch_failed", url=url, error=str(exc))
        return None


def _extract_rehydration_json(html: str) -> dict[str, Any] | None:
    """Extract the __UNIVERSAL_DATA_FOR_REHYDRATION__ JSON from TikTok HTML."""
    match = _REHYDRATION_RE.search(html)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        logger.debug("tt_rehydration_json_parse_failed", error=str(exc))
        return None


def _find_user_detail(data: dict[str, Any]) -> dict[str, Any]:
    """Navigate __DEFAULT_SCOPE__ to find the user-detail object."""
    scope = data.get("__DEFAULT_SCOPE__", {})
    for key in scope:
        if "user" in key.lower() and "detail" in key.lower():
            return scope[key]
    return {}


def _parse_stories_from_json(data: dict[str, Any], username: str) -> list[dict[str, Any]]:
    """Extract story items from the rehydration JSON.

    TikTok story structure:
      __DEFAULT_SCOPE__."webapp.user-detail".userInfo.story.storyList[]
    Or: __DEFAULT_SCOPE__."webapp.user-detail".storyList (in some versions)
    """
    result: list[dict[str, Any]] = []
    try:
        user_detail = _find_user_detail(data)
        user_info = user_detail.get("userInfo", {})
        story_data = user_info.get("story", {})

        if not story_data:
            # Try direct storyList in user_info
            story_data = user_info

        story_list = (
            story_data.get("storyList", [])
            or story_data.get("items", [])
            or []
        )
        if not story_list:
            # Try user_detail.storyList directly
            story_list = user_detail.get("storyList", [])

        for item in story_list:
            sid = str(item.get("id", item.get("awemeId", "")))
            if not sid:
                continue

            # Video
            video_info = item.get("video", {})
            if video_info:
                url = (
                    video_info.get("downloadAddr")
                    or video_info.get("playAddr")
                    or video_info.get("downloadURL", "")
                )
                if url:
                    result.append({"id": sid, "type": "video", "url": url})
                    continue

            # Photo
            image_url = item.get("imageUrl") or item.get("displayImage", {}).get("urlList", [""])[0]
            if image_url:
                result.append({"id": sid, "type": "photo", "url": image_url})

        logger.debug("tt_stories_parsed", username=username, found=len(result),
                      story_data_keys=list(story_data.keys())[:5] if story_data else [],
                      list_count=len(story_list))
    except Exception as exc:
        logger.warning("tt_stories_parse_error", username=username, error=str(exc))

    return result


def _parse_posts_from_json(data: dict[str, Any], username: str, limit: int) -> list[dict[str, Any]]:
    """Extract recent posts from the rehydration JSON.

    TikTok post structure (varies by app version):
      __DEFAULT_SCOPE__."webapp.user-detail".postInfo.itemList[]
    or: __DEFAULT_SCOPE__."webapp.user-detail".itemList[]
    or: __DEFAULT_SCOPE__."webapp.user-detail".userInfo.itemList[]
    """
    result: list[dict[str, Any]] = []
    seen: set[str] = set()

    try:
        user_detail = _find_user_detail(data)

        # Try multiple paths for items
        item_list: list[dict[str, Any]] = []
        for path in [
            lambda d: d.get("postInfo", {}).get("itemList", []),
            lambda d: d.get("itemList", []),
            lambda d: d.get("userInfo", {}).get("post", {}).get("itemList", []),
            lambda d: d.get("userInfo", {}).get("itemList", []),
        ]:
            items = path(user_detail)
            if items:
                item_list = items
                break

        if not item_list:
            # Try searching the whole scope for any list with videos
            scope = data.get("__DEFAULT_SCOPE__", {})
            for key in scope:
                val = scope[key]
                if isinstance(val, dict):
                    for sub_key in val:
                        sub_val = val[sub_key]
                        if isinstance(sub_val, list) and len(sub_val) > 0:
                            first = sub_val[0]
                            if isinstance(first, dict) and first.get("video"):
                                item_list = sub_val
                                logger.debug("tt_posts_found_in_key", key=f"{key}.{sub_key}", count=len(item_list))
                                break
                    if item_list:
                        break

        for item in item_list:
            if len(result) >= limit:
                break

            post_id = str(item.get("id", item.get("awemeId", "")))
            if not post_id or post_id in seen:
                continue
            seen.add(post_id)

            # Video
            video_info = item.get("video", {})
            if video_info:
                url = video_info.get("downloadAddr") or video_info.get("playAddr", "")
                if url:
                    result.append({"id": post_id, "type": "video", "url": url})
                    continue

            # Image gallery
            image_post = item.get("imagePost", {})
            images = image_post.get("images", [])
            if images:
                first_img = images[0]
                image_url = ""
                if isinstance(first_img, dict):
                    iu = first_img.get("imageURL", {})
                    if isinstance(iu, dict):
                        url_list = iu.get("urlList", [])
                        image_url = url_list[0] if url_list else ""
                if image_url:
                    result.append({"id": post_id, "type": "photo", "url": image_url})
                    continue

        logger.debug("tt_posts_parsed", username=username, found=len(result),
                      list_count=len(item_list))

    except Exception as exc:
        logger.warning("tt_posts_parse_error", username=username, error=str(exc))

    return result