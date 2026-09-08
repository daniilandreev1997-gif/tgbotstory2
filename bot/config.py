"""Configuration via pydantic-settings.

All settings are loaded from environment variables or .env file.
No hardcoded values. Secrets are in D:/AI/secrets/.env
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from .env / environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Telegram ---
    bot_token: str
    admin_ids: str = ""
    chat_id: int = 0

    # --- VK ---
    vk_user_token: str | None = None
    vk_service_token: str | None = None

    # --- Instagram ---
    ig_username: str | None = None
    ig_password: str | None = None

    # --- TikTok ---
    tt_ms_token: str | None = None

    # --- Database ---
    db_path: str = "sqlite+aiosqlite:///data/bot.db"

    # --- Polling ---
    poll_timeout: int = 30
    max_concurrent_polls: int = 3

    # --- Media ---
    temp_media_dir: str = "/tmp/tgbotstory2_media"
    max_media_size_mb: int = 50

    # --- Encryption ---
    encryption_key: str = ""

    # --- Logging ---
    log_level: str = "INFO"
    log_file: str = "logs/bot.log"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Parse admin_ids from comma-separated string to list[int]
        if isinstance(self.admin_ids, str):
            raw = self.admin_ids.strip()
            if raw:
                object.__setattr__(
                    self,
                    "admin_ids",
                    [int(x.strip()) for x in raw.split(",") if x.strip()],
                )
            else:
                object.__setattr__(self, "admin_ids", [])


@lru_cache
def load_settings() -> Settings:
    """Return cached Settings singleton. Reads .env once."""
    return Settings()
