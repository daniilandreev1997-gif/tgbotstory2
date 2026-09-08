"""VK content extractor via vkbottle async API."""

from datetime import datetime

from bot.extractors.base import (
    AuthExpiredError,
    BaseExtractor,
    MediaItem,
    RateLimitError,
)


class VkExtractor(BaseExtractor):
    """VK content extractor via vkbottle."""

    def __init__(self, credentials: dict) -> None:
        super().__init__(credentials)
        self._api = None
        self._user_token = credentials.get("user_token", "")

    async def poll(self, target: dict) -> list[MediaItem]:
        content_type = target.get("content_type", "stories")
        last_poll_pk = target.get("last_poll_pk")

        if content_type == "stories":
            return await self._poll_stories(target, last_poll_pk)
        elif content_type == "posts":
            return await self._poll_posts(target, last_poll_pk)
        else:
            return []

    async def _poll_stories(self, target: dict, last_poll_pk: str | None) -> list[MediaItem]:
        target_id = target.get("target_id", "")
        target_type = target.get("target_type", "user")

        try:
            owner_id = int(target_id)
            if target_type == "public":
                owner_id = -abs(owner_id)

            response = await self._api.stories.get(owner_id=owner_id, extended=1)
        except Exception as e:
            return self._handle_api_error(e, "vk")

        # VK API stories.get with extended=1 returns a **grouped** response:
        #   response.items[]  — each element is a story group (one per user)
        #   group.stories[]   — actual story objects inside the group
        result = []
        for group in response.get("items", []):
            for story in group.get("stories", []):
                story_pk = story.get("id")
                if last_poll_pk is not None and str(story_pk) <= str(last_poll_pk):
                    continue

                result.append(self._parse_story_to_media_item(story, target_id))

        return result

    async def _poll_posts(self, target: dict, last_poll_pk: str | None) -> list[MediaItem]:
        target_id = target.get("target_id", "")
        target_type = target.get("target_type", "user")

        try:
            owner_id = int(target_id)
            if target_type == "public":
                owner_id = -abs(owner_id)

            response = await self._api.wall.get(owner_id=owner_id, count=10, filter="owner")
        except Exception as e:
            return self._handle_api_error(e, "vk")

        items = response.get("items", [])
        result = []

        for post in items:
            post_id = post.get("id")
            if last_poll_pk is not None and str(post_id) <= str(last_poll_pk):
                continue

            result.append(self._parse_post_to_media_item(post, target_id))

        return result

    async def check_health(self) -> bool:
        try:
            await self._api.users.get(user_ids=[1])
            return True
        except Exception:
            return False

    def _parse_story_to_media_item(self, story: dict, target_id: str) -> MediaItem:
        media_urls = []
        is_video = story.get("type") == "video"

        if is_video and "video" in story:
            video = story["video"]
            # vkbottle may provide video.url directly; fallback to sizes extraction
            if video.get("url"):
                media_urls.append(video["url"])
            elif video.get("files"):
                # Some VK video responses nest URLs under 'files'
                files = video["files"]
                if isinstance(files, dict):
                    best = files.get("mp4_1080") or files.get("mp4_720") or files.get("mp4_480") or files.get("mp4_360")
                    if best:
                        media_urls.append(best)
        elif "photo" in story:
            photo = story["photo"]
            # vkbottle returns photo.sizes[] (list of {url, width, height, type})
            sizes = photo.get("sizes", [])
            if sizes:
                # Last size is the largest (w > z > y > x)
                media_urls.append(sizes[-1].get("url", ""))
            elif photo.get("url"):
                # Fallback: raw dict may have url directly
                media_urls.append(photo["url"])

        timestamp = None
        if "date" in story:
            raw_date = story["date"]
            if isinstance(raw_date, (int, float)):
                timestamp = datetime.fromtimestamp(raw_date)
            elif isinstance(raw_date, str):
                # vkbottle returns ISO-format datetime strings
                timestamp = datetime.fromisoformat(raw_date)
            elif isinstance(raw_date, datetime):
                timestamp = raw_date

        duration_sec = None
        if is_video and "video" in story:
            duration_sec = story["video"].get("duration")

        return MediaItem(
            platform="vk",
            content_pk=story.get("id", 0),
            content_type="story",
            target_id=target_id,
            media_urls=[u for u in media_urls if u],
            caption=None,
            timestamp=timestamp,
            is_video=is_video,
            duration_sec=duration_sec,
            metadata={"type": story.get("type")},
        )

    def _parse_post_to_media_item(self, post: dict, target_id: str) -> MediaItem:
        attachments = post.get("attachments", [])
        media_urls = self._extract_post_media_urls(attachments)
        is_video = any(a.get("type") == "video" for a in attachments)

        timestamp = None
        if "date" in post:
            timestamp = datetime.fromtimestamp(post["date"])

        return MediaItem(
            platform="vk",
            content_pk=post.get("id", 0),
            content_type="post",
            target_id=target_id,
            media_urls=media_urls,
            caption=post.get("text"),
            timestamp=timestamp,
            is_video=is_video,
            duration_sec=None,
            metadata={"attachments_count": len(attachments)},
        )

    def _extract_post_media_urls(self, attachments: list[dict]) -> list[str]:
        urls = []
        for att in attachments:
            att_type = att.get("type", "")
            if att_type == "photo":
                photo = att.get("photo", {})
                sizes = photo.get("sizes", [])
                if sizes:
                    urls.append(sizes[-1].get("url", ""))
            elif att_type == "video":
                video = att.get("video", {})
                vid = video.get("id", "")
                owner_id = video.get("owner_id", "")
                if vid and owner_id:
                    urls.append(f"https://vk.com/video{owner_id}_{vid}")
        return urls

    def _handle_api_error(self, error: Exception, platform: str) -> list[MediaItem]:
        from bot.extractors.base import NetworkError

        try:
            from vkbottle import VKAPIError

            if isinstance(error, VKAPIError):
                code = getattr(error, "code", 0)
                if code == 5:
                    raise AuthExpiredError(platform=platform) from error
                elif code == 6 or code == 9:
                    raise RateLimitError(platform=platform) from error
                raise NetworkError(platform=platform, original_error=str(error)) from error
        except ImportError:
            pass

        if isinstance(error, (AuthExpiredError, RateLimitError, NetworkError)):
            raise

        raise NetworkError(platform=platform, original_error=str(error)) from error
