"""Tests for VK content extractor."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_extract_vk_stories_returns_list(mock_vk_api, sample_target_dict, sample_vk_story_response):
    from bot.extractors.vk_extractor import VkExtractor

    mock_vk_api.stories.get = AsyncMock(return_value=sample_vk_story_response)

    extractor = VkExtractor(credentials={"user_token": "test_token"})
    extractor._api = mock_vk_api

    target = {**sample_target_dict, "content_type": "stories", "last_poll_pk": None}
    items = await extractor.poll(target)

    assert isinstance(items, list)
    assert len(items) == 2
    assert items[0].content_pk == 456789
    assert items[0].content_type == "story"
    assert items[0].is_video is False
    assert items[0].platform == "vk"
    assert items[1].content_pk == 456790
    assert items[1].is_video is True


@pytest.mark.asyncio
async def test_extract_vk_stories_empty(mock_vk_api, sample_target_dict):
    from bot.extractors.vk_extractor import VkExtractor

    mock_vk_api.stories.get = AsyncMock(return_value={"items": [], "count": 0})

    extractor = VkExtractor(credentials={"user_token": "test_token"})
    extractor._api = mock_vk_api

    target = {**sample_target_dict, "content_type": "stories", "last_poll_pk": None}
    items = await extractor.poll(target)

    assert items == []
    mock_vk_api.stories.get.assert_called_once()


@pytest.mark.asyncio
async def test_extract_vk_stories_auth_expired(mock_vk_api, sample_target_dict):
    from bot.extractors.vk_extractor import VkExtractor
    from bot.extractors.base import AuthExpiredError
    from vkbottle import APIAuthError

    mock_vk_api.stories.get = AsyncMock(side_effect=APIAuthError(error_msg="User authorization failed: access token has expired."))

    extractor = VkExtractor(credentials={"user_token": "expired_token"})
    extractor._api = mock_vk_api

    target = {**sample_target_dict, "content_type": "stories", "last_poll_pk": None}

    with pytest.raises(AuthExpiredError) as exc_info:
        await extractor.poll(target)

    assert exc_info.value.platform == "vk"


@pytest.mark.asyncio
async def test_extract_vk_posts_success(mock_vk_api, sample_target_dict, sample_vk_wall_response):
    from bot.extractors.vk_extractor import VkExtractor

    mock_vk_api.wall.get = AsyncMock(return_value=sample_vk_wall_response)

    extractor = VkExtractor(credentials={"user_token": "test_token"})
    extractor._api = mock_vk_api

    target = {**sample_target_dict, "content_type": "posts", "last_poll_pk": None}
    items = await extractor.poll(target)

    assert isinstance(items, list)
    assert len(items) == 1
    assert items[0].content_pk == 1001
    assert items[0].content_type == "post"
    assert items[0].caption == "Test post text"
    assert items[0].platform == "vk"
    assert len(items[0].media_urls) > 0
