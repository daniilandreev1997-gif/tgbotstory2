"""Load configuration from D:/AI/secrets/ — never hardcode tokens."""

from __future__ import annotations

import os
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

# Default base path for secrets
_SECRETS_BASE = Path(os.environ.get("SECRETS_DIR", "D:/AI/secrets"))


def _read_file(path: Path) -> str:
    """Read a secret file and return stripped content."""
    if not path.exists():
        raise FileNotFoundError(f"Secret file not found: {path}")
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        raise ValueError(f"Secret file is empty: {path}")
    return content


# ---------------------------------------------------------------------------
# Token paths (can be overridden via environment variables)
# ---------------------------------------------------------------------------
_VK_TOKEN_PATH = Path(os.environ.get("VK_TOKEN_PATH", _SECRETS_BASE / "vk-user-token-new-1.txt"))
_TG_TOKEN_PATH = Path(os.environ.get("TG_TOKEN_PATH", _SECRETS_BASE / "botfathertg.txt"))


def load_vk_token() -> str:
    """Return the VK access token."""
    # Bothost/Docker: read from env var
    token = os.environ.get("VK_TOKEN")
    if token:
        return token.strip()
    # Local dev: read from D:/AI/secrets/
    token = _read_file(_VK_TOKEN_PATH)
    logger.debug("vk_token_loaded", path=str(_VK_TOKEN_PATH))
    return token


def load_tg_token() -> str:
    """Return the Telegram bot token."""
    # Bothost/Docker: read from env var
    token = os.environ.get("BOT_TOKEN")
    if token:
        return token.strip()
    # Local dev: read from D:/AI/secrets/
    token = _read_file(_TG_TOKEN_PATH)
    logger.debug("tg_token_loaded", path=str(_TG_TOKEN_PATH))
    return token


# ---------------------------------------------------------------------------
# API Constants
# ---------------------------------------------------------------------------
VK_API_VERSION = "5.199"
VK_STORIES_URL = "https://api.vk.com/method/stories.get"
VK_USERS_URL = "https://api.vk.com/method/users.get"

# ---------------------------------------------------------------------------
# Scheduler intervals (seconds)
# ---------------------------------------------------------------------------
VK_POLL_INTERVAL = 5 * 60       # 5 minutes
IG_POLL_INTERVAL = 5 * 60       # 5 minutes
TT_STORIES_INTERVAL = 5 * 60    # 5 minutes
TT_POSTS_INTERVAL = 10 * 60     # 10 minutes

# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------
ERROR_COOLDOWN_MINUTES = 30
TT_POSTS_SCAN_LIMIT = 20

# Chrome binary path (for Selenium IG/TT clients).
# On bothost/Docker, set via env: CHROME_BINARY=/usr/bin/google-chrome
CHROME_BINARY = os.environ.get("CHROME_BINARY", "")

# ---------------------------------------------------------------------------
# Timezone
# ---------------------------------------------------------------------------
TZ_OFFSET_HOURS: int = 4
TZ_LABEL: str = "GMT+4.0"

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DB_PATH: Path = Path(os.environ.get("DB_PATH", "bot.db"))
LOG_DIR: Path = Path(os.environ.get("LOG_DIR", "logs"))