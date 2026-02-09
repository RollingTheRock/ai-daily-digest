"""Tech blog RSS parser for AI Daily Digest."""

from datetime import datetime, timedelta
from typing import Any

import feedparser
from pydantic import BaseModel, Field
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from arxiv_sanity_bot.logger import get_logger
from arxiv_sanity_bot.config import TIMEZONE

logger = get_logger(__name__)

DEFAULT_NUM_RETRIES = 3
DEFAULT_WAIT_TIME = 20

# RSS Feed URLs for AI/ML tech blogs
TECH_BLOG_FEEDS = {
    "OpenAI": "https://openai.com/blog/rss.xml",
    "Anthropic": "https://www.anthropic.com/blog/rss.xml",
    "Google AI": "https://ai.googleblog.com/feeds/posts/default",
    "DeepMind": "https://deepmind.google/blog/rss.xml",
    "HuggingFace": "https://huggingface.co/blog/feed.xml",
    "Pytorch": "https://pytorch.org/blog/rss.xml",
    "TensorFlow": "https://blog.tensorflow.org/feeds/posts/default",
    "Papers with Code": "https://paperswithcode.com/rss",
    "AI2": "https://allenai.org/blog/feed.xml",
    "Berkeley AI": "https://bair.berkeley.edu/blog/feed.xml",
}


class BlogPost(BaseModel):
    """Model for a tech blog post."""

    title: str = Field(..., description="Post title")
    source: str = Field(..., description="Blog source name (e.g., 'OpenAI')")
    summary: str = Field("", description="Post summary/excerpt")
    url: str = Field(..., description="Post URL")
    published_on: datetime = Field(..., description="Publication date")
    author: str = Field("", description="Post author(s)")


class TechBlogError(Exception):
    """Exception raised for tech blog fetch errors."""

    pass


class TechBlogClient:
    """Client for fetching tech blog posts via RSS."""

    def __init__(
        self,
        num_retries: int = DEFAULT_NUM_RETRIES,
        wait_time: int = DEFAULT_WAIT_TIME,
    ):
        """
        Initialize the tech blog client.

        Args:
            num_retries: Number of retry attempts per feed
            wait_time: Maximum wait time between retries
        """
        self.num_retries = num_retries
        self.wait_time = wait_time
        self.feeds = TECH_BLOG_FEEDS.copy()

    def fetch_recent_posts(
        self,
        days: int = 7,
        limit_per_source: int = 3,
        sources: list[str] | None = None,
    ) -> list[BlogPost]:
        """
        Fetch recent blog posts from configured RSS feeds.

        Args:
            days: Only return posts from last N days
            limit_per_source: Maximum posts per source
            sources: Specific sources to fetch (None = all)

        Returns:
            List of BlogPost objects sorted by date (newest first)
        """
        feeds_to_fetch = sources if sources else list(self.feeds.keys())
        all_posts: list[BlogPost] = []
        cutoff_date = datetime.now(tz=TIMEZONE) - timedelta(days=days)

        for source in feeds_to_fetch:
            if source not in self.feeds:
                logger.warning(f"Unknown blog source: {source}")
                continue

            feed_url = self.feeds[source]
            try:
                posts = self._fetch_feed_with_retry(source, feed_url)
                # Filter by date and limit
                recent_posts = [p for p in posts if p.published_on >= cutoff_date][
                    :limit_per_source
                ]
                all_posts.extend(recent_posts)
            except Exception as e:
                logger.error(
                    f"Failed to fetch feed for {source}: {e}",
                    exc_info=True,
                    extra={"source": source, "url": feed_url},
                )
                continue

        # Sort by date, newest first
        all_posts.sort(key=lambda p: p.published_on, reverse=True)

        logger.info(
            f"Fetched {len(all_posts)} blog posts from {len(feeds_to_fetch)} sources"
        )
        return all_posts

    def add_feed(self, name: str, url: str) -> None:
        """
        Add a custom RSS feed.

        Args:
            name: Source name
            url: RSS feed URL
        """
        self.feeds[name] = url
        logger.info(f"Added RSS feed: {name}", extra={"url": url})

    @retry(
        retry=retry_if_exception_type((Exception, TechBlogError)),
        stop=stop_after_attempt(DEFAULT_NUM_RETRIES),
        wait=wait_exponential(multiplier=1, min=1, max=DEFAULT_WAIT_TIME),
        reraise=True,
    )
    def _fetch_feed_with_retry(self, source: str, url: str) -> list[BlogPost]:
        """Fetch a single RSS feed with retry logic."""
        logger.debug("Fetching RSS feed", extra={"source": source, "url": url})

        feed = feedparser.parse(url)

        if feed.bozo and feed.bozo_exception:
            # Some feeds have parse errors but still work
            logger.warning(
                f"RSS parse warning for {source}: {feed.bozo_exception}",
                extra={"source": source},
            )

        posts: list[BlogPost] = []

        for entry in feed.entries:
            try:
                post = self._parse_entry(source, entry)
                if post:
                    posts.append(post)
            except Exception as e:
                logger.warning(f"Failed to parse entry from {source}: {e}")
                continue

        logger.info(f"Fetched {len(posts)} posts from {source}")
        return posts

    def _parse_entry(self, source: str, entry: Any) -> BlogPost | None:
        """Parse a single RSS entry into a BlogPost."""
        # Extract title
        title = entry.get("title", "").strip()
        if not title:
            return None

        # Extract URL
        url = ""
        if "link" in entry:
            url = entry.link
        elif "links" in entry and entry.links:
            for link in entry.links:
                if link.get("rel") == "alternate" or link.get("type") == "text/html":
                    url = link.get("href", "")
                    break

        if not url:
            return None

        # Extract summary (prefer summary, then description, then content)
        summary = ""
        if "summary" in entry:
            summary = entry.summary
        elif "description" in entry:
            summary = entry.description
        elif "content" in entry and entry.content:
            summary = entry.content[0].get("value", "")

        # Clean up HTML tags from summary
        summary = self._clean_html(summary)

        # Truncate long summaries
        if len(summary) > 500:
            summary = summary[:497] + "..."

        # Extract publication date
        published_on = datetime.now(tz=TIMEZONE)
        if "published_parsed" in entry and entry.published_parsed:
            # feedparser returns time.struct_time, convert to timestamp
            import time

            ts = time.mktime(entry.published_parsed)
            published_on = datetime.fromtimestamp(ts, tz=TIMEZONE)
        elif "updated_parsed" in entry and entry.updated_parsed:
            import time

            ts = time.mktime(entry.updated_parsed)
            published_on = datetime.fromtimestamp(ts, tz=TIMEZONE)
        elif "published" in entry:
            try:
                published_on = self._parse_date(entry.published)
            except Exception:
                pass

        # Extract author
        author = ""
        if "author" in entry:
            author = entry.author
        elif "authors" in entry and entry.authors:
            author = ", ".join(
                a.get("name", "") for a in entry.authors if a.get("name")
            )

        return BlogPost(
            title=title,
            source=source,
            summary=summary,
            url=url,
            published_on=published_on,
            author=author,
        )

    def _clean_html(self, text: str) -> str:
        """Remove HTML tags from text."""
        import re

        # Remove HTML tags
        clean = re.sub(r"<[^>]+>", "", text)
        # Decode HTML entities
        import html

        clean = html.unescape(clean)
        # Normalize whitespace
        clean = " ".join(clean.split())
        return clean.strip()

    def _parse_date(self, date_str: str) -> datetime:
        """Parse various date formats."""
        formats = [
            "%a, %d %b %Y %H:%M:%S %z",
            "%a, %d %b %Y %H:%M:%S GMT",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d %H:%M:%S",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt).replace(tzinfo=TIMEZONE)
            except ValueError:
                continue

        # Fallback to now
        return datetime.now(tz=TIMEZONE)


def fetch_tech_blog_posts(
    days: int = 7,
    limit_per_source: int = 3,
    sources: list[str] | None = None,
) -> list[BlogPost]:
    """
    Convenience function to fetch recent tech blog posts.

    Args:
        days: Only return posts from last N days
        limit_per_source: Maximum posts per source
        sources: Specific sources to fetch (None = all)

    Returns:
        List of BlogPost objects sorted by date
    """
    client = TechBlogClient()
    return client.fetch_recent_posts(days, limit_per_source, sources)
