"""Tests for Instagram content extractor."""

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_extract_ig_stories_success(mock_ig_client, sample_target_dict, sample_ig_story_response):
    from bot.extractors.ig_extractor import IgExtractor

    mock_ig_client.user_stories = AsyncMock(return_value=sample_ig_story_response)

    extractor = IgExtractor(credentials={"session_file": "/tmp/test_session.json"})
    extractor._client = mock_ig_client

    target = {**sample_target_dict, "platform": "instagram", "target_id": "123456789", "content_type": "stories", "last_poll_pk": None}
    items = await extractor.poll(target)

    assert isinstance(items, list)
    assert len(items) == 1
    assert items[0].content_pk == "12345678901234567"
    assert items[0].content_type == "story"
    assert items[0].platform == "instagram"
    assert items[0].is_video is False


@pytest.mark.asyncio
async def test_extract_ig_rate_limit(mock_ig_client, sample_target_dict):
    from bot.extractors.ig_extractor import IgExtractor
    from bot.extractors.base import RateLimitError
    from instagrapi.exceptions import ClientError

    mock_ig_client.user_stories = AsyncMock(side_effect=ClientError(status_code=429, message="Rate limit exceeded", response=MagicMock()))

    extractor = IgExtractor(credentials={"session_file": "/tmp/test_session.json"})
    extractor._client = mock_ig_client

    target = {**sample_target_dict, "platform": "instagram", "target_id": "123456789", "content_type": "stories", "last_poll_pk": None}

    with pytest.raises(RateLimitError) as exc_info:
        await extractor.poll(target)

    assert exc_info.value.platform == "instagram"


@pytest.mark.asyncio
async def test_extract_vk_public_stories(mock_vk_api, sample_vk_story_response):
    from bot.extractors.vk_extractor import VkExtractor

    mock_vk_api.stories.get = AsyncMock(return_value=sample_vk_story_response)

    extractor = VkExtractor(credentials={"user_token": "test_token"})
    extractor._api = mock_vk_api

    target = {"target_id": "98765", "target_type": "public", "content_type": "stories", "last_poll_pk": None, "target_username": "test_public"}

    items = await extractor.poll(target)

    call_kwargs = mock_vk_api.stories.get.call_args.kwargs
    assert call_kwargs["owner_id"] == -98765
    assert len(items) == 2
