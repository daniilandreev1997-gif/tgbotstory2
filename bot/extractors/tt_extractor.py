"""TikTok content extractor via TikTokApi."""

from datetime import datetime

from bot.extractors.base import (
    AuthExpiredError,
    BaseExtractor,
    MediaItem,
)


class TtExtractor(BaseExtractor):
    """TikTok content extractor via TikTokApi."""

    def __init__(self, credentials: dict) -> None:
        super().__init__(credentials)
        self._api = None
        self._ms_token = credentials.get("ms_token")
        self._cookies = credentials.get("cookies")

    async def poll(self, target: dict) -> list[MediaItem]:
        content_type = target.get("content_type", "posts")
        target_username = target.get("target_username", "")
        last_poll_pk = target.get("last_poll_pk")

        try:
            if content_type == "stories":
                return await self._poll_stories(target_username, last_poll_pk)
            elif content_type == "posts":
                return await self._poll_posts(target_username, last_poll_pk)
            else:
                return []
        except AuthExpiredError:
            raise
        except Exception as e:
            return self._handle_api_error(e)

    async def _poll_stories(self, username: str, last_poll_pk: str | None) -> list[MediaItem]:
        try:
            user = self._api.user(username)
            stories = await user.stories()
        except NotImplementedError:
            return []
        except Exception:
            raise

        result = []
        for story in stories:
            story_id = str(getattr(story, "id", ""))
            if last_poll_pk is not None and story_id <= str(last_poll_pk):
                continue

            result.append(self._parse_story_media(story, username))

        return result

    async def _poll_posts(self, username: str, last_poll_pk: str | None) -> list[MediaItem]:
        user = self._api.user(username)
        posts = await user.posts()

        result = []
        for post in posts:
            post_id = str(getattr(post, "id", ""))
            if last_poll_pk is not None and post_id <= str(last_poll_pk):
                continue

            result.append(self._parse_post_media(post, username))

        return result

    async def check_health(self) -> bool:
        try:
            await self._api.create_sessions()
            return True
        except Exception:
            return False

    def _parse_story_media(self, story, username: str) -> MediaItem:
        media_urls = []
        is_video = getattr(story, "is_video", True)
        video_url = getattr(story, "video_url", None)
        image_url = getattr(story, "image_url", None)

        if video_url:
            media_urls.append(video_url)
        if image_url:
            media_urls.append(image_url)

        create_time = getattr(story, "create_time", None)
        timestamp = create_time if isinstance(create_time, datetime) else None

        return MediaItem(
            platform="tiktok",
            content_pk=str(getattr(story, "id", "")),
            content_type="story",
            target_id=username,
            media_urls=media_urls,
            caption=getattr(story, "description", None),
            timestamp=timestamp,
            is_video=is_video,
            duration_sec=None,
            metadata={},
        )

    def _parse_post_media(self, post, username: str) -> MediaItem:
        media_urls = []
        is_video = getattr(post, "is_video", True)
        video_url = getattr(post, "video_url", None)
        image_url = getattr(post, "image_url", None)

        if video_url:
            media_urls.append(video_url)
        if image_url:
            media_urls.append(image_url)

        create_time = getattr(post, "create_time", None)
        timestamp = create_time if isinstance(create_time, datetime) else None

        return MediaItem(
            platform="tiktok",
            content_pk=str(getattr(post, "id", "")),
            content_type="post",
            target_id=username,
            media_urls=media_urls,
            caption=getattr(post, "description", None),
            timestamp=timestamp,
            is_video=is_video,
            duration_sec=None,
            metadata={},
        )

    def _handle_api_error(self, error: Exception) -> list[MediaItem]:
        from bot.extractors.base import NetworkError

        if isinstance(error, AuthExpiredError):
            raise

        raise NetworkError(platform="tiktok", original_error=str(error)) from error
