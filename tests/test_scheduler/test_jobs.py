"""Tests for scheduler jobs."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_scheduler_job_executes_on_time(mock_scheduler):
    from bot.scheduler.jobs import SchedulerService

    assert len(SchedulerService.JOBS) == 8

    job_ids = [j[0] for j in SchedulerService.JOBS]
    assert "poll_vk_user_stories" in job_ids
    assert "poll_vk_user_posts" in job_ids
    assert "poll_vk_public_stories" in job_ids
    assert "poll_vk_public_posts" in job_ids
    assert "poll_ig_stories" in job_ids
    assert "poll_ig_posts" in job_ids
    assert "poll_tt_posts" in job_ids
    assert "poll_tt_stories" in job_ids

    intervals = {j[0]: j[1] for j in SchedulerService.JOBS}
    assert intervals["poll_vk_user_stories"] == 5
    assert intervals["poll_vk_user_posts"] == 120
    assert intervals["poll_ig_stories"] == 5
    assert intervals["poll_ig_posts"] == 160
    assert intervals["poll_tt_posts"] == 15
    assert intervals["poll_tt_stories"] == 20


@pytest.mark.asyncio
async def test_scheduler_job_handles_network_failure(mock_scheduler):
    from bot.scheduler.jobs import SchedulerService

    service = SchedulerService(
        scheduler=mock_scheduler,
        session_factory=AsyncMock(),
        bot=AsyncMock(),
        chat_id=123456,
        settings=MagicMock(),
    )

    service.start()

    assert mock_scheduler.add_job.call_count >= 9
    mock_scheduler.start.assert_called_once()
