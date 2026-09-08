"""Tests for TikTok content extractor."""

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_extract_tt_posts_success(mock_tt_api, sample_target_dict, sample_tt_post_response):
    from bot.extractors.tt_extractor import TtExtractor

    user_obj = MagicMock()
    user_obj.posts = AsyncMock(return_value=sample_tt_post_response)
    mock_tt_api.user = MagicMock(return_value=user_obj)

    extractor = TtExtractor(credentials={"ms_token": "test_ms_token"})
    extractor._api = mock_tt_api

    target = {**sample_target_dict, "platform": "tiktok", "target_username": "test_tiktok_user", "content_type": "posts", "last_poll_pk": None}
    items = await extractor.poll(target)

    assert isinstance(items, list)
    assert len(items) == 1
    assert items[0].content_pk == "1234567890123456789"
    assert items[0].content_type == "post"
    assert items[0].platform == "tiktok"
    assert items[0].is_video is True
    assert items[0].caption == "Test TikTok caption"


@pytest.mark.asyncio
async def test_extract_tt_cookies_expired(mock_tt_api, sample_target_dict):
    from bot.extractors.tt_extractor import TtExtractor
    from bot.extractors.base import AuthExpiredError

    user_obj = MagicMock()
    user_obj.posts = AsyncMock(side_effect=AuthExpiredError(platform="tiktok", credential_id=1))
    mock_tt_api.user = MagicMock(return_value=user_obj)

    extractor = TtExtractor(credentials={"cookies": {"sessionid": "expired"}})
    extractor._api = mock_tt_api

    target = {**sample_target_dict, "platform": "tiktok", "target_username": "test_tiktok_user", "content_type": "posts", "last_poll_pk": None}

    with pytest.raises(AuthExpiredError) as exc_info:
        await extractor.poll(target)

    assert exc_info.value.platform == "tiktok"


@pytest.mark.asyncio
async def test_extract_tt_stories_unavailable(mock_tt_api, sample_target_dict):
    from bot.extractors.tt_extractor import TtExtractor

    user_obj = MagicMock()
    user_obj.stories = AsyncMock(side_effect=NotImplementedError("Stories not available"))
    mock_tt_api.user = MagicMock(return_value=user_obj)

    extractor = TtExtractor(credentials={"ms_token": "test_ms_token"})
    extractor._api = mock_tt_api

    target = {**sample_target_dict, "platform": "tiktok", "target_username": "test_tiktok_user", "content_type": "stories", "last_poll_pk": None}

    items = await extractor.poll(target)
    assert items == []
