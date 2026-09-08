"""Shared fixtures for tgbotstory2 test suite.

London School TDD (Mockist): all external dependencies are mocked.
Requires: pytest-asyncio, pytest-mock.
"""

import asyncio
import os
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio


@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def test_db_session():
    """Async mock SQLAlchemy session for database tests."""
    session = AsyncMock(name="AsyncSession")
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.add = MagicMock()
    session.delete = MagicMock()
    session.execute = AsyncMock()
    session.scalars = AsyncMock()
    session.scalar = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    yield session
    await session.close()


@pytest_asyncio.fixture
async def test_db_engine():
    """In-memory SQLite async engine for schema tests."""
    try:
        from sqlalchemy.ext.asyncio import create_async_engine
        engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        yield engine
        await engine.dispose()
    except ImportError:
        pytest.skip("SQLAlchemy not installed")


@pytest.fixture
def temp_media_dir(tmp_path: Path) -> Path:
    """Temporary directory for media download/cleanup tests."""
    media_dir = tmp_path / "tgbotstory2_media"
    media_dir.mkdir(parents=True, exist_ok=True)
    return media_dir


@pytest.fixture
def mock_bot():
    """Mock aiogram Bot instance."""
    bot = AsyncMock(name="Bot")
    bot.send_message = AsyncMock(return_value=MagicMock(message_id=1))
    bot.send_photo = AsyncMock(return_value=MagicMock(message_id=2))
    bot.send_video = AsyncMock(return_value=MagicMock(message_id=3))
    bot.send_media_group = AsyncMock(return_value=[MagicMock(message_id=4), MagicMock(message_id=5)])
    bot.send_document = AsyncMock(return_value=MagicMock(message_id=6))
    bot.get_file = AsyncMock()
    bot.download_file = AsyncMock(return_value=b"fake-file-bytes")
    bot.edit_message_text = AsyncMock()
    bot.edit_message_reply_markup = AsyncMock()
    bot.answer_callback_query = AsyncMock()
    bot.token = "test_bot_token"
    return bot


@pytest.fixture
def mock_dispatcher(mock_bot):
    """Mock aiogram Dispatcher."""
    try:
        from aiogram import Dispatcher
        from aiogram.fsm.storage.memory import MemoryStorage
        storage = MemoryStorage()
        dp = Dispatcher(storage=storage)
        return dp
    except ImportError:
        dp = MagicMock(name="Dispatcher")
        dp.bot = mock_bot
        return dp


@pytest.fixture
def mock_vk_api():
    """Mock vkbottle API instance."""
    api = AsyncMock(name="VkApi")
    api.stories = MagicMock()
    api.stories.get = AsyncMock()
    api.wall = MagicMock()
    api.wall.get = AsyncMock()
    api.users = MagicMock()
    api.users.get = AsyncMock()
    api.groups = MagicMock()
    api.groups.getById = AsyncMock()
    return api


@pytest.fixture
def mock_ig_client():
    """Mock instagrapi Client."""
    client = AsyncMock(name="IgClient")
    client.user_stories = AsyncMock()
    client.user_medias = AsyncMock()
    client.user_id_from_username = AsyncMock()
    client.user_info = AsyncMock()
    client.user_info_by_username = AsyncMock()
    client.login = AsyncMock()
    client.load_settings = AsyncMock()
    client.dump_settings = AsyncMock()
    client.photo_download = AsyncMock()
    client.video_download = AsyncMock()
    client.album_download = AsyncMock()
    return client


@pytest.fixture
def mock_tt_api():
    """Mock TikTokApi instance."""
    api = AsyncMock(name="TikTokApi")
    user_obj = MagicMock()
    user_obj.posts = AsyncMock()
    user_obj.stories = AsyncMock()
    user_obj.info = AsyncMock()
    api.user = MagicMock(return_value=user_obj)
    api.create_sessions = AsyncMock()
    return api


@pytest.fixture
def mock_tt_playwright():
    """Mock playwright async_api for TikTok cookie refresh."""
    playwright = AsyncMock(name="Playwright")
    browser = AsyncMock()
    context = AsyncMock()
    page = AsyncMock()
    playwright.chromium = MagicMock()
    playwright.chromium.launch = AsyncMock(return_value=browser)
    browser.new_context = AsyncMock(return_value=context)
    context.new_page = AsyncMock(return_value=page)
    context.cookies = AsyncMock(return_value=[{"name": "sessionid", "value": "fake"}])
    page.goto = AsyncMock()
    page.wait_for_load_state = AsyncMock()
    browser.close = AsyncMock()
    playwright.stop = AsyncMock()
    return playwright


@pytest.fixture
def mock_scheduler():
    """Mock APScheduler AsyncIOScheduler."""
    scheduler = MagicMock(name="AsyncIOScheduler")
    scheduler.start = MagicMock()
    scheduler.shutdown = MagicMock(wait=False)
    scheduler.add_job = MagicMock()
    scheduler.get_jobs = MagicMock(return_value=[])
    scheduler.remove_job = MagicMock()
    scheduler.pause = MagicMock()
    scheduler.resume = MagicMock()
    return scheduler


@pytest.fixture
def mock_aiohttp_session():
    """Mock aiohttp ClientSession for media download tests."""
    session = AsyncMock(name="ClientSession")
    session.get = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.fixture
def sample_target_dict():
    return {"target_id": "12345", "target_type": "user", "content_type": "stories", "last_poll_pk": None, "target_username": "test_user"}


@pytest.fixture
def sample_vk_story_response():
    return {"items": [{"id": 456789, "owner_id": 12345, "date": 1725710400, "type": "photo", "photo": {"url": "https://example.com/story_photo.jpg", "width": 1080, "height": 1920}}, {"id": 456790, "owner_id": 12345, "date": 1725714000, "type": "video", "video": {"url": "https://example.com/story_video.mp4", "duration": 15}}], "count": 2}


@pytest.fixture
def sample_vk_wall_response():
    return {"items": [{"id": 1001, "owner_id": 12345, "date": 1725710000, "text": "Test post text", "attachments": [{"type": "photo", "photo": {"id": 2001, "sizes": [{"type": "z", "url": "https://example.com/photo_large.jpg"}]}}]}], "count": 1}


@pytest.fixture
def sample_ig_story_response():
    story = MagicMock()
    story.pk = "12345678901234567"
    story.media_type = 1
    story.taken_at = datetime(2026, 9, 7, 12, 0, 0)
    story.thumbnail_url = "https://instagram.com/story_thumb.jpg"
    story.video_url = None
    return [story]


@pytest.fixture
def sample_ig_media_response():
    media = MagicMock()
    media.pk = "98765432109876543"
    media.media_type = 2
    media.taken_at = datetime(2026, 9, 7, 12, 0, 0)
    media.thumbnail_url = "https://instagram.com/post_thumb.jpg"
    media.video_url = "https://instagram.com/post_video.mp4"
    media.caption_text = "Test instagram caption"
    media.resources = []
    return [media]


@pytest.fixture
def sample_tt_post_response():
    post = MagicMock()
    post.id = "1234567890123456789"
    post.description = "Test TikTok caption"
    post.create_time = datetime(2026, 9, 7, 12, 0, 0)
    post.is_video = True
    post.video_url = "https://tiktok.com/video.mp4"
    post.image_url = None
    return [post]


@pytest.fixture
def sample_media_item_dict():
    return {"platform": "vk", "content_pk": "story_456789", "content_type": "story", "target_id": "12345", "media_urls": ["https://example.com/photo.jpg"], "caption": "Test caption", "timestamp": datetime(2026, 9, 7, 12, 0, 0), "is_video": False, "duration_sec": None, "metadata": {}}


@pytest.fixture
def clean_env():
    saved = {}
    keys_to_remove = [k for k in os.environ if k.startswith(("BOT_", "VK_", "IG_", "TT_", "DB_", "POLL_", "MEDIA_", "LOG_"))]
    for k in keys_to_remove:
        saved[k] = os.environ.pop(k)
    yield
    os.environ.update(saved)
