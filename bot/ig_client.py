"""Instagram stories client — HTTP-only via instagrapi.

Requires a pre-authenticated session file. Run scripts/setup_ig_session.py
once to log in and save the session to D:/AI/secrets/ig-session.json.
After that the bot fetches stories via pure HTTP — no Selenium, no browser.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# Session file path
_SECRETS_BASE = Path(os.environ.get("SECRETS_DIR", "D:/AI/secrets"))
_SESSION_FILE = Path(os.environ.get("IG_SESSION_PATH", _SECRETS_BASE / "ig-session.json"))


# ---------------------------------------------------------------------------
# Public async API
# ---------------------------------------------------------------------------

async def fetch_instagram_stories(username: str) -> list[dict[str, Any]]:
    """Fetch current stories for an Instagram user via instagrapi (HTTP-only).

    Requires a valid session file at D:/AI/secrets/ig-session.json.
    Run scripts/setup_ig_session.py once to create it.

    Args:
        username: Instagram username (without @).

    Returns:
        List of story dicts: ``[{"id": "story_pk", "type": "photo"/"video", "url": "..."}]``.
        Empty list on error or when no stories are found.
    """
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(None, _sync_fetch, username)
    except Exception as exc:
        logger.error("instagram_fetch_unexpected_error", username=username, error=str(exc))
        return []


def _sync_fetch(username: str) -> list[dict[str, Any]]:
    """Synchronous instagrapi call — runs in thread pool executor."""

    if not _SESSION_FILE.exists():
        logger.error(
            "ig_session_missing",
            path=str(_SESSION_FILE),
            hint="Run: python scripts/setup_ig_session.py",
        )
        return []

    try:
        from instagrapi import Client
    except ImportError:
        logger.error("instagrapi_not_installed", hint="Run: pip install instagrapi")
        return []

    client = Client()

    try:
        client.load_settings(_SESSION_FILE)
        logger.debug("ig_session_loaded", path=str(_SESSION_FILE))
    except Exception as exc:
        logger.error("ig_session_load_failed", error=str(exc))
        return []

    # Resolve username → user_id
    try:
        user_id = client.user_id_from_username(username)
    except Exception as exc:
        logger.error("ig_user_resolve_failed", username=username, error=str(exc))
        client.logout()
        return []

    # Fetch stories
    try:
        stories = client.user_stories(user_id)
    except Exception as exc:
        logger.error("ig_stories_fetch_failed", username=username, error=str(exc))
        client.logout()
        return []

    if not stories:
        logger.info("instagram_no_stories_found", username=username)
        return []

    result: list[dict[str, Any]] = []
    for s in stories:
        story_type = "video" if s.media_type == 2 else "photo"
        # instagrapi Story model has thumbnail_url (photo) and video_url (video)
        url = s.video_url if story_type == "video" else s.thumbnail_url
        if not url:
            continue
        result.append({
            "id": str(s.pk),
            "type": story_type,
            "url": str(url),
            "taken_at": s.taken_at,
        })

    logger.info("instagram_stories_fetched", username=username, count=len(result))
    return result