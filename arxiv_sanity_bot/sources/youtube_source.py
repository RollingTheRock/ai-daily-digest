"""YouTube content source for AI Daily Digest."""

from datetime import datetime, timedelta
from typing import Any

from pydantic import ValidationError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from arxiv_sanity_bot.logger import get_logger
from arxiv_sanity_bot.config import TIMEZONE
from arxiv_sanity_bot.schemas import ContentItem

logger = get_logger(__name__)

# Curated AI YouTube channels (selected high-quality sources)
DEFAULT_YOUTUBE_CHANNELS = [
    "UCXUPKJOdoz9XylBV4T2hpdQ",  # Two Minute Papers
    "UCvjgXvBlbQiydffZUzzmYJw",  # Yannic Kilcher
    "UCbfYPyITQ-7l4upoX8nvctg",  # AI Explained
    "UCZHmQk67mSJgfCCTnMGEA7w",  # David Shapiro
    "UCP7jMXSY2xbc3KCAE0MHQ-A",  # DeepLearningAI
    "UC1LpsuAUaKoMzzJSEt5Wpgw",  # Lex Fridman
]

# AI-related keywords for filtering video titles/descriptions
AI_KEYWORDS = [
    "AI", "artificial intelligence", "machine learning", "deep learning",
    "LLM", "large language model", "GPT", "Claude", "transformer",
    "neural network", "computer vision", "NLP", "multimodal",
    "reinforcement learning", "diffusion", "stable diffusion",
    "fine-tuning", "training", "model", "paper", "research",
]

DEFAULT_NUM_RETRIES = 3
DEFAULT_WAIT_TIME = 20
DEFAULT_MIN_VIEWS = 10000
DEFAULT_MIN_DURATION_MINUTES = 5
DEFAULT_MAX_VIDEOS_PER_CHANNEL = 3


class YouTubeError(Exception):
    """Exception raised for YouTube API errors."""
    pass


class YouTubeClient:
    """Client for fetching AI-related videos from specified YouTube channels.

    Lightweight approach: only fetches video metadata (title, description, views),
    does not download or process video content.
    """

    def __init__(
        self,
        api_key: str | None = None,
        num_retries: int = DEFAULT_NUM_RETRIES,
        wait_time: int = DEFAULT_WAIT_TIME,
    ):
        """
        Initialize the YouTube client.

        Args:
            api_key: YouTube Data API Key (from env YOUTUBE_API_KEY)
            num_retries: Number of retry attempts per API call
            wait_time: Maximum wait time between retries
        """
        self.api_key = api_key
        self.num_retries = num_retries
        self.wait_time = wait_time
        self._client: Any | None = None

    def _get_client(self) -> Any:
        """Lazy initialization of YouTube API client."""
        if self._client is None:
            try:
                from googleapiclient.discovery import build
            except ImportError:
                raise YouTubeError(
                    "google-api-python-client is required for YouTube support. "
                    "Install with: pip install arxiv-sanity-bot[youtube]"
                )

            key = self.api_key
            if not key:
                import os
                key = os.environ.get("YOUTUBE_API_KEY", "")

            if not key:
                raise YouTubeError(
                    "YouTube API Key not provided. "
                    "Set YOUTUBE_API_KEY environment variable."
                )

            self._client = build("youtube", "v3", developerKey=key, cache_discovery=False)
            logger.debug("Initialized YouTube API client")

        return self._client

    @retry(
        retry=retry_if_exception_type((YouTubeError, Exception)),
        stop=stop_after_attempt(DEFAULT_NUM_RETRIES),
        wait=wait_exponential(multiplier=1, min=1, max=DEFAULT_WAIT_TIME),
        reraise=True,
    )
    def fetch_recent_videos(
        self,
        channel_ids: list[str] | None = None,
        days: int = 7,
        min_views: int = DEFAULT_MIN_VIEWS,
        min_duration_minutes: int = DEFAULT_MIN_DURATION_MINUTES,
        max_videos_per_channel: int = DEFAULT_MAX_VIDEOS_PER_CHANNEL,
        keywords: list[str] | None = None,
    ) -> list[ContentItem]:
        """
        Fetch recent videos from specified AI YouTube channels.

        Args:
            channel_ids: List of YouTube channel IDs. Defaults to curated AI channels.
            days: Only return videos from last N days
            min_views: Minimum view count threshold
            min_duration_minutes: Minimum video duration in minutes
            max_videos_per_channel: Maximum videos to fetch per channel
            keywords: Keywords to filter videos (title/description). Defaults to AI keywords.

        Returns:
            List of ContentItem objects sorted by view count (highest first)
        """
        channels = channel_ids if channel_ids else DEFAULT_YOUTUBE_CHANNELS
        filter_keywords = keywords if keywords else AI_KEYWORDS
        all_videos: list[ContentItem] = []
        cutoff_date = datetime.now(tz=TIMEZONE) - timedelta(days=days)

        client = self._get_client()

        for channel_id in channels:
            try:
                videos = self._fetch_channel_videos(
                    client=client,
                    channel_id=channel_id,
                    cutoff_date=cutoff_date,
                    min_views=min_views,
                    min_duration_minutes=min_duration_minutes,
                    max_results=max_videos_per_channel,
                    keywords=filter_keywords,
                )
                all_videos.extend(videos)
                logger.info(f"Fetched {len(videos)} videos from channel {channel_id}")
            except Exception as e:
                logger.error(
                    f"Failed to fetch videos for channel {channel_id}: {e}",
                    exc_info=True,
                    extra={"channel_id": channel_id},
                )
                continue

        # Sort by engagement score (views), highest first
        all_videos.sort(key=lambda v: v.engagement_score, reverse=True)

        logger.info(f"Total videos fetched: {len(all_videos)} from {len(channels)} channels")
        return all_videos

    def _fetch_channel_videos(
        self,
        client: Any,
        channel_id: str,
        cutoff_date: datetime,
        min_views: int,
        min_duration_minutes: int,
        max_results: int,
        keywords: list[str],
    ) -> list[ContentItem]:
        """Fetch videos from a single channel."""
        try:
            # Get the channel's uploads playlist ID
            channel_response = client.channels().list(
                part="snippet,contentDetails",
                id=channel_id,
            ).execute()

            if not channel_response.get("items"):
                logger.warning(f"Channel {channel_id} not found")
                return []

            channel_info = channel_response["items"][0]
            channel_name = channel_info["snippet"]["title"]

            # Get uploads playlist ID
            uploads_playlist_id = channel_info["contentDetails"]["relatedPlaylists"]["uploads"]

            # Fetch recent videos from uploads playlist
            videos_response = client.playlistItems().list(
                part="snippet,contentDetails",
                playlistId=uploads_playlist_id,
                maxResults=min(max_results * 3, 20),  # Fetch extra to filter
            ).execute()

            if not videos_response.get("items"):
                return []

            videos: list[ContentItem] = []
            video_ids = []
            video_snippets = {}

            for item in videos_response["items"]:
                video_id = item["contentDetails"]["videoId"]
                video_ids.append(video_id)
                video_snippets[video_id] = {
                    "snippet": item["snippet"],
                    "channel_name": channel_name,
                }

            # Batch fetch video statistics and details
            if video_ids:
                stats_response = client.videos().list(
                    part="snippet,statistics,contentDetails",
                    id=",".join(video_ids),
                ).execute()

                for video_data in stats_response.get("items", []):
                    try:
                        video_item = self._parse_video(
                            video_data=video_data,
                            channel_name=channel_name,
                            cutoff_date=cutoff_date,
                            min_views=min_views,
                            min_duration_minutes=min_duration_minutes,
                            keywords=keywords,
                        )
                        if video_item:
                            videos.append(video_item)
                    except ValidationError as e:
                        logger.warning(f"Failed to parse video: {e}")
                        continue
                    except Exception as e:
                        logger.warning(f"Unexpected error parsing video: {e}")
                        continue

            return videos[:max_results]

        except Exception as e:
            logger.error(f"Error fetching videos for channel {channel_id}: {e}")
            raise

    def _parse_video(
        self,
        video_data: dict[str, Any],
        channel_name: str,
        cutoff_date: datetime,
        min_views: int,
        min_duration_minutes: int,
        keywords: list[str],
    ) -> ContentItem | None:
        """Parse a single video into ContentItem."""
        snippet = video_data.get("snippet", {})
        statistics = video_data.get("statistics", {})
        content_details = video_data.get("contentDetails", {})

        # Parse published date
        published_at_str = snippet.get("publishedAt", "")
        if published_at_str:
            try:
                from dateutil import parser
                published_at = parser.isoparse(published_at_str)
            except Exception:
                published_at = datetime.now(tz=TIMEZONE)
        else:
            published_at = datetime.now(tz=TIMEZONE)

        # Check date
        if published_at.replace(tzinfo=TIMEZONE) < cutoff_date:
            return None

        # Parse duration (ISO 8601 format: PT#M#S)
        duration_str = content_details.get("duration", "")
        duration_minutes = self._parse_duration_minutes(duration_str)

        if duration_minutes < min_duration_minutes:
            return None

        # Get view count
        view_count = int(statistics.get("viewCount", 0))
        if view_count < min_views:
            return None

        # Get title and description for keyword filtering
        title = snippet.get("title", "")
        description = snippet.get("description", "")

        # Keyword filtering
        combined_text = f"{title} {description}".lower()
        if not any(keyword.lower() in combined_text for keyword in keywords):
            return None

        # Build video URL
        video_id = video_data.get("id", "")
        video_url = f"https://youtube.com/watch?v={video_id}"

        # Get thumbnail (prefer medium quality)
        thumbnails = snippet.get("thumbnails", {})
        thumbnail_url = ""
        for quality in ["medium", "standard", "high", "default"]:
            if quality in thumbnails:
                thumbnail_url = thumbnails[quality].get("url", "")
                break

        return ContentItem(
            id=video_id,
            title=title,
            source=channel_name,
            source_type="youtube",
            url=video_url,
            published_on=published_at.replace(tzinfo=TIMEZONE) if published_at.tzinfo is None else published_at,
            author=channel_name,
            summary=description[:300] + "..." if len(description) > 300 else description,
            content=description,
            engagement_score=view_count,
            metadata={
                "view_count": view_count,
                "like_count": int(statistics.get("likeCount", 0)),
                "duration_minutes": duration_minutes,
                "duration_iso": duration_str,
                "thumbnail_url": thumbnail_url,
            },
        )

    def _parse_duration_minutes(self, duration_iso: str) -> int:
        """Parse ISO 8601 duration to minutes."""
        import re

        if not duration_iso:
            return 0

        # Pattern: PT#H#M#S
        pattern = r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?"
        match = re.match(pattern, duration_iso)

        if not match:
            return 0

        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)

        return hours * 60 + minutes + (1 if seconds >= 30 else 0)


def fetch_youtube_content(
    channel_ids: list[str] | None = None,
    days: int = 7,
    min_views: int = DEFAULT_MIN_VIEWS,
    max_videos_per_channel: int = DEFAULT_MAX_VIDEOS_PER_CHANNEL,
) -> list[ContentItem]:
    """
    Convenience function to fetch recent AI videos from YouTube channels.

    Args:
        channel_ids: Specific channels to fetch (None = default AI channels)
        days: Only return videos from last N days
        min_views: Minimum view count threshold
        max_videos_per_channel: Maximum videos per channel

    Returns:
        List of ContentItem objects
    """
    client = YouTubeClient()
    return client.fetch_recent_videos(
        channel_ids=channel_ids,
        days=days,
        min_views=min_views,
        max_videos_per_channel=max_videos_per_channel,
    )
