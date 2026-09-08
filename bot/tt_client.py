"""TikTok client — fetches stories and posts via Selenium (headless Chrome)."""

from __future__ import annotations

import asyncio
import re
import time
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Stories
# ---------------------------------------------------------------------------

async def fetch_tiktok_stories(username: str) -> list[dict[str, Any]]:
    """Fetch current stories for a TikTok user.

    All Selenium calls are run inside ``loop.run_in_executor`` to avoid
    blocking the asyncio event loop.

    Args:
        username: TikTok username (without @).

    Returns:
        List of story dicts: ``[{"id": "hash_or_url", "type": "video", "url": "..."}]``.
        Returns an empty list on error or when no stories are found.
    """
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(None, _sync_fetch_tiktok_stories, username)
    except Exception as exc:
        logger.error("tiktok_fetch_unexpected_error", username=username, error=str(exc))
        return []


def _sync_fetch_tiktok_stories(username: str) -> list[dict[str, Any]]:
    """Synchronous Selenium routine — runs in a thread pool executor."""

    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
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

    url = f"https://www.tiktok.com/@{username}"

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
    except Exception as exc:
        error_msg = str(exc)
        if "cannot find Chrome binary" in error_msg:
            logger.info(
                "tt_stories_chrome_not_found",
                username=username,
                hint="Set CHROME_BINARY env var or install Chrome",
            )
        else:
            logger.error("tiktok_driver_init_failed", username=username, error=error_msg)
        return []

    try:
        driver.get(url)
        time.sleep(3)

        # Click #1: open the story overlay
        try:
            actions = ActionChains(driver)
            actions.move_by_offset(760, 276).click().perform()
            time.sleep(2)
        except Exception as exc:
            logger.warning("tiktok_click1_failed", username=username, error=str(exc))

        # Click #2: reset mouse and click to focus
        try:
            actions = ActionChains(driver)
            actions.move_by_offset(275, 25).click().perform()
            time.sleep(3)
        except Exception as exc:
            logger.warning("tiktok_click2_failed", username=username, error=str(exc))

        page_source = driver.page_source

        # Regex: prefer crossorigin="use-credentials" videos, fallback to any video
        video_urls = re.findall(
            r'<video[^>]*crossorigin="use-credentials"[^>]*src="([^"]+)"',
            page_source,
        )
        if not video_urls:
            video_urls = re.findall(
                r'<video[^>]*src="([^"]+)"[^>]*>',
                page_source,
            )

        # Deduplicate preserving order
        seen: set[str] = set()
        result: list[dict[str, Any]] = []
        for url in video_urls:
            if url in seen:
                continue
            seen.add(url)
            story_id = url[-32:] if len(url) >= 32 else url
            result.append({"id": story_id, "type": "video", "url": url})

        logger.info(
            "tiktok_stories_fetched",
            username=username,
            count=len(result),
        )
        return result

    except Exception as exc:
        logger.error("tiktok_selenium_error", username=username, error=str(exc))
        return []

    finally:
        try:
            driver.quit()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Posts
# ---------------------------------------------------------------------------

async def fetch_tiktok_posts(
    username: str, limit: int = 20,
) -> list[dict[str, Any]]:
    """Fetch recent TikTok posts for a user via Selenium scraping.

    Args:
        username: TikTok username (without @).
        limit: Maximum number of posts to return (default 20).

    Returns:
        List of post dicts: ``[{"id": "post_id", "type": "video", "url": "..."}]``.
        Returns an empty list on error or when no posts are found.
    """
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(None, _sync_fetch_tiktok_posts, username, limit)
    except Exception as exc:
        logger.error("tiktok_posts_unexpected_error", username=username, error=str(exc))
        return []


def _sync_fetch_tiktok_posts(username: str, limit: int) -> list[dict[str, Any]]:
    """Synchronous Selenium routine for posts — runs in a thread pool executor.

    Uses SIGI_STATE JSON embedded in the page (contains all post data with
    video download URLs).  Falls back to raw ``<video>`` tag extraction if
    SIGI_STATE is unavailable.
    """
    import json

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

    url = f"https://www.tiktok.com/@{username}"

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
    except Exception as exc:
        error_msg = str(exc)
        if "cannot find Chrome binary" in error_msg:
            logger.info(
                "tt_posts_chrome_not_found",
                username=username,
                hint="Set CHROME_BINARY env var or install Chrome",
            )
        else:
            logger.error("tiktok_posts_driver_init_failed", username=username, error=error_msg)
        return []

    try:
        driver.get(url)
        time.sleep(5)  # wait for dynamic content (JS rendering)

        page_source = driver.page_source

        # ---- Method 1: SIGI_STATE (contains all post data) ----
        sigi_match = re.search(
            r'<script id="SIGI_STATE"[^>]*>(.*?)</script>',
            page_source,
            re.DOTALL,
        )
        sigi_used = False
        result: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        if sigi_match:
            try:
                sigi_data = json.loads(sigi_match.group(1))
                # Navigate: ItemModule -> {video_id: {video: {downloadAddr, playAddr}}}
                item_module = sigi_data.get("ItemModule", {})
                for post_id, item in item_module.items():
                    if not isinstance(item, dict):
                        continue
                    video_info = item.get("video", {})
                    if not video_info:
                        continue
                    # Prefer downloadAddr (highest quality), fallback to playAddr
                    download_addr = video_info.get("downloadAddr", "")
                    play_addr = video_info.get("playAddr", "")
                    video_url = download_addr or play_addr
                    if not video_url:
                        continue
                    if post_id in seen_ids:
                        continue
                    seen_ids.add(post_id)
                    result.append({
                        "id": post_id,
                        "type": "video",
                        "url": video_url,
                    })
                    if len(result) >= limit:
                        break
                sigi_used = True
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                logger.debug(
                    "sigi_state_parse_failed",
                    username=username,
                    error=str(exc),
                )

        # ---- Method 2: Fallback — raw <video> extraction ----
        if not sigi_used:
            video_urls = re.findall(
                r'<video[^>]*src="([^"]+)"',
                page_source,
            )
            for i, vurl in enumerate(video_urls):
                if i >= limit:
                    break
                result.append({
                    "id": f"tt_post_{i}",
                    "type": "video",
                    "url": vurl,
                })

        logger.info(
            "tiktok_posts_fetched",
            username=username,
            count=len(result),
            limit=limit,
            method="sigi_state" if sigi_used else "fallback_video_tags",
        )
        return result

    except Exception as exc:
        logger.error("tiktok_posts_selenium_error", username=username, error=str(exc))
        return []

    finally:
        try:
            driver.quit()
        except Exception:
            pass