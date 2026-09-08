"""Instagram stories client — anonymous viewer via Selenium (headless Chrome)."""

from __future__ import annotations

import asyncio
import hashlib
import re
import time
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Public async API
# ---------------------------------------------------------------------------


async def fetch_instagram_stories(username: str) -> list[dict[str, Any]]:
    """Fetch current stories for an Instagram user (anonymous, no login).

    Tries several anonymous viewer sites in order.  All Selenium calls are
    run inside ``loop.run_in_executor`` to avoid blocking the asyncio
    event loop.

    Args:
        username: Instagram username (without @).

    Returns:
        List of story dicts: ``[{"id": "md5hash", "type": "photo"/"video", "url": "..."}]``.
        Returns an empty list on error or when no stories are found.
    """
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(None, _sync_fetch_instagram_stories, username)
    except Exception as exc:
        logger.error("instagram_fetch_unexpected_error", username=username, error=str(exc))
        return []


# ---------------------------------------------------------------------------
# Synchronous Selenium logic (runs in thread pool)
# ---------------------------------------------------------------------------


def _sync_fetch_instagram_stories(username: str) -> list[dict[str, Any]]:
    """Synchronous Selenium routine — runs in a thread pool executor."""

    # Try primary source first, then fallback
    for source_name, source_url in _story_sources(username):
        logger.info("ig_trying_source", username=username, source=source_name)
        result = _try_source(username, source_name, source_url)
        if result:
            return result
        logger.info("ig_source_failed_or_empty", username=username, source=source_name)

    logger.info("instagram_no_stories_found", username=username)
    return []


def _story_sources(username: str) -> list[tuple[str, str]]:
    """Return (name, url) pairs for anonymous IG story viewers."""
    return [
        ("anonyig", f"https://anonyig.com/en/profile/{username}"),
        ("dumpoir", f"https://dumpoir.com/u/{username}"),
    ]


def _try_source(username: str, source_name: str, url: str) -> list[dict[str, Any]]:
    """Attempt to scrape stories from a single anonymous viewer site.

    Returns a list of story dicts on success, or an empty list on failure.
    """
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager

    from bot.config import CHROME_BINARY

    options = Options()
    if CHROME_BINARY:
        options.binary_location = CHROME_BINARY
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    driver = None
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
    except Exception as exc:
        error_msg = str(exc)
        if "cannot find Chrome binary" in error_msg:
            logger.info(
                "ig_chrome_not_found",
                username=username,
                source=source_name,
                hint="Set CHROME_BINARY env var or install Chrome",
            )
        else:
            logger.error(
                "ig_driver_init_failed",
                username=username,
                source=source_name,
                error=error_msg,
            )
        return []

    try:
        driver.get(url)
        time.sleep(4)

        page_source = driver.page_source

        media_items: list[dict[str, Any]] = []

        # --- Extract videos ---
        video_urls = re.findall(r'<video[^>]*src="([^"]+)"', page_source)
        for v_url in video_urls:
            media_items.append({"type": "video", "url": v_url})

        # Also check <source> tags inside <video>
        source_urls = re.findall(r'<source[^>]*src="([^"]+)"', page_source)
        for s_url in source_urls:
            # Avoid duplicates if already captured as video
            if not any(item["url"] == s_url for item in media_items):
                media_items.append({"type": "video", "url": s_url})

        # --- Extract photos ---
        photo_urls = re.findall(r'<img[^>]*src="([^"]+)"[^>]*>', page_source)
        for p_url in photo_urls:
            # Skip tiny icons, avatars, and known tracking pixels
            if _is_likely_story_image(p_url):
                # Avoid duplicates
                if not any(item["url"] == p_url for item in media_items):
                    media_items.append({"type": "photo", "url": p_url})

        # Deduplicate by URL and build final result
        result: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        for item in media_items:
            url = item["url"]
            if url in seen_urls:
                continue
            seen_urls.add(url)
            story_id = hashlib.md5(url.encode()).hexdigest()
            result.append({
                "id": story_id,
                "type": item["type"],
                "url": url,
            })

        if result:
            logger.info(
                "instagram_stories_fetched",
                username=username,
                source=source_name,
                count=len(result),
            )
        else:
            logger.info(
                "instagram_source_empty",
                username=username,
                source=source_name,
            )

        return result

    except Exception as exc:
        logger.warning(
            "ig_source_error",
            username=username,
            source=source_name,
            error=str(exc),
        )
        return []

    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Common patterns for images that are NOT story content
_UNWANTED_IMAGE_PATTERNS = [
    r"/favicon",
    r"/logo",
    r"/avatar",
    r"/profile",
    r"/icon",
    r"\.svg",
    r"data:image",
    r"1x1",
    r"pixel",
    r"tracking",
    r"google",
    r"facebook",
    r"analytics",
]


def _is_likely_story_image(url: str) -> bool:
    """Heuristic: return True if the URL looks like actual story content."""
    url_lower = url.lower()

    # Must be an image URL
    if not any(url_lower.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp")):
        if "cdninstagram" not in url_lower and "fbcdn" not in url_lower and "scontent" not in url_lower:
            return False

    for pattern in _UNWANTED_IMAGE_PATTERNS:
        if re.search(pattern, url_lower):
            return False

    return True