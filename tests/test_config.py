"""Tests for bot configuration module."""

import os
from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_config_loads_from_env(clean_env):
    from bot.config import Settings

    test_env = {
        "BOT_TOKEN": "test_bot_token_123",
        "ADMIN_IDS": "111,222,333",
        "CHAT_ID": "-1001234567890",
        "VK_USER_TOKEN": "vk_user_token_abc",
        "VK_SERVICE_TOKEN": "vk_service_token_def",
        "IG_USERNAME": "test_ig_user",
        "IG_PASSWORD": "test_ig_pass",
        "TT_MS_TOKEN": "test_tt_ms_token",
        "DB_PATH": "sqlite+aiosqlite:///data/test.db",
        "POLL_TIMEOUT": "45",
        "MAX_CONCURRENT_POLLS": "5",
        "TEMP_MEDIA_DIR": "/tmp/test_media",
        "MAX_MEDIA_SIZE_MB": "50",
        "LOG_LEVEL": "DEBUG",
        "LOG_FILE": "logs/test.log",
    }

    with patch.dict(os.environ, test_env, clear=True):
        settings = Settings()

    assert settings.bot_token == "test_bot_token_123"
    assert settings.admin_ids == [111, 222, 333]
    assert settings.chat_id == -1001234567890
    assert settings.vk_user_token == "vk_user_token_abc"
    assert settings.vk_service_token == "vk_service_token_def"
    assert settings.ig_username == "test_ig_user"
    assert settings.ig_password == "test_ig_pass"
    assert settings.tt_ms_token == "test_tt_ms_token"
    assert settings.db_path == "sqlite+aiosqlite:///data/test.db"
    assert settings.poll_timeout == 45
    assert settings.max_concurrent_polls == 5
    assert settings.temp_media_dir == "/tmp/test_media"
    assert settings.max_media_size_mb == 50
    assert settings.log_level == "DEBUG"
    assert settings.log_file == "logs/test.log"


@pytest.mark.asyncio
async def test_db_models_create_tables():
    from bot.db.models import Base
    from sqlalchemy import create_engine, inspect

    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    assert "target" in table_names
    assert "content_hash" in table_names
    assert "auth_credential" in table_names
    assert "poll_log" in table_names

    target_cols = {col["name"] for col in inspector.get_columns("target")}
    required_target_cols = {"id", "platform", "target_type", "target_username", "target_id", "content_type", "is_active", "added_by", "added_at", "last_polled_at", "last_poll_pk", "error_count", "last_error"}
    assert required_target_cols.issubset(target_cols)

    ch_cols = {col["name"] for col in inspector.get_columns("content_hash")}
    required_ch_cols = {"id", "target_id", "platform", "content_pk", "content_type", "content_hash", "media_urls", "content_meta", "delivered_at", "telegram_msg_ids"}
    assert required_ch_cols.issubset(ch_cols)

    engine.dispose()
