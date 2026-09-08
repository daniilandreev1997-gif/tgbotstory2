"""Instagram content extractor via instagrapi."""

from datetime import datetime

from bot.extractors.base import (
    AuthExpiredError,
    BaseExtractor,
    MediaItem,
    RateLimitError,
)


class IgExtractor(BaseExtractor):
    """Instagram content extractor via instagrapi."""

    def __init__(self, credentials: dict) -> None:
        super().__init__(credentials)
        self._client = None
        self._session_file = credentials.get("session_file")

    async def poll(self, target: dict) -> list[MediaItem]:
        content_type = target.get("content_type", "stories")
        target_id = target.get("target_id", "")

        try:
            if content_type == "stories":
                return await self._poll_stories(target_id)
            elif content_type == "posts":
                return await self._poll_posts(target_id)
            else:
                return []
        except AuthExpiredError:
            raise
        except RateLimitError:
            raise
        except Exception as e:
            return self._handle_api_error(e)

    async def _poll_stories(self, target_id: str) -> list[MediaItem]:
        stories = await self._client.user_stories(target_id)
        result = []

        for story in stories:
            media_item = self._parse_story_media(story, target_id)
            result.append(media_item)

        return result

    async def _poll_posts(self, target_id: str) -> list[MediaItem]:
        medias = await self._client.user_medias(target_id)
        result = []

        for media in medias:
            media_item = self._parse_post_media(media, target_id)
            result.append(media_item)

        return result

    async def check_health(self) -> bool:
        try:
            await self._client.user_info(self._client.user_id)
            return True
        except Exception:
            return False

    def _parse_story_media(self, story, target_id: str) -> MediaItem:
        media_urls = []
        is_video = False

        media_type = getattr(story, "media_type", 1)
        if media_type == 2:
            is_video = True
            video_url = getattr(story, "video_url", None)
            if video_url:
                media_urls.append(video_url)
        else:
            thumbnail = getattr(story, "thumbnail_url", None)
            if thumbnail:
                media_urls.append(thumbnail)

        taken_at = getattr(story, "taken_at", None)
        timestamp = taken_at if isinstance(taken_at, datetime) else None

        return MediaItem(
            platform="instagram",
            content_pk=str(getattr(story, "pk", "")),
            content_type="story",
            target_id=target_id,
            media_urls=media_urls,
            caption=None,
            timestamp=timestamp,
            is_video=is_video,
            duration_sec=None,
            metadata={"media_type": media_type},
        )

    def _parse_post_media(self, media, target_id: str) -> MediaItem:
        media_urls = []
        is_video = False

        media_type = getattr(media, "media_type", 1)
        if media_type == 2:
            is_video = True
            video_url = getattr(media, "video_url", None)
            if video_url:
                media_urls.append(video_url)
        else:
            thumbnail = getattr(media, "thumbnail_url", None)
            if thumbnail:
                media_urls.append(thumbnail)

        resources = getattr(media, "resources", [])
        for resource in resources:
            res_url = getattr(resource, "thumbnail_url", None)
            if res_url:
                media_urls.append(res_url)

        taken_at = getattr(media, "taken_at", None)
        timestamp = taken_at if isinstance(taken_at, datetime) else None

        return MediaItem(
            platform="instagram",
            content_pk=str(getattr(media, "pk", "")),
            content_type="post",
            target_id=target_id,
            media_urls=media_urls,
            caption=getattr(media, "caption_text", None),
            timestamp=timestamp,
            is_video=is_video,
            duration_sec=None,
            metadata={"media_type": media_type},
        )

    def _handle_api_error(self, error: Exception) -> list[MediaItem]:
        from bot.extractors.base import NetworkError

        try:
            from instagrapi.exceptions import ClientError

            if isinstance(error, ClientError):
                status_code = getattr(error, "status_code", 0)
                if status_code == 429:
                    raise RateLimitError(platform="instagram", retry_after_sec=300) from error
                elif status_code in (401, 403):
                    raise AuthExpiredError(platform="instagram") from error
                raise NetworkError(platform="instagram", original_error=str(error)) from error
        except ImportError:
            pass

        if isinstance(error, (AuthExpiredError, RateLimitError, NetworkError)):
            raise

        raise NetworkError(platform="instagram", original_error=str(error)) from error
