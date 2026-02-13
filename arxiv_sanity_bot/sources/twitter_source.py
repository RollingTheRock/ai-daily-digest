"""Twitter/X content source for AI Daily Digest."""

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

# Core AI Twitter accounts to monitor (as specified by user)
DEFAULT_TWITTER_SOURCES = [
    "_akhaliq",     # AK - AI news aggregator
    "karpathy",     # Andrej Karpathy
    "goodside",     # Riley Goodside - Prompt Engineering
    "ylecun",       # Yann LeCun
    "ai__pub",      # AI Pub
]

DEFAULT_NUM_RETRIES = 3
DEFAULT_WAIT_TIME = 20
DEFAULT_MIN_LIKES = 100
DEFAULT_MAX_TWEETS_PER_USER = 5


class TwitterError(Exception):
    """Exception raised for Twitter API errors."""
    pass


class TwitterClient:
    """Client for fetching AI-related tweets from specified accounts."""

    def __init__(
        self,
        bearer_token: str | None = None,
        num_retries: int = DEFAULT_NUM_RETRIES,
        wait_time: int = DEFAULT_WAIT_TIME,
    ):
        """
        Initialize the Twitter client.

        Args:
            bearer_token: Twitter API Bearer Token (from env TWITTER_BEARER_TOKEN)
            num_retries: Number of retry attempts per API call
            wait_time: Maximum wait time between retries
        """
        self.bearer_token = bearer_token
        self.num_retries = num_retries
        self.wait_time = wait_time
        self._client: Any | None = None

    def _get_client(self) -> Any:
        """Lazy initialization of Tweepy client."""
        if self._client is None:
            try:
                import tweepy
            except ImportError:
                raise TwitterError(
                    "tweepy is required for Twitter support. "
                    "Install with: pip install arxiv-sanity-bot[twitter]"
                )

            token = self.bearer_token
            if not token:
                import os
                token = os.environ.get("TWITTER_BEARER_TOKEN", "")

            if not token:
                raise TwitterError(
                    "Twitter Bearer Token not provided. "
                    "Set TWITTER_BEARER_TOKEN environment variable."
                )

            self._client = tweepy.Client(
                bearer_token=token,
                wait_on_rate_limit=True,
            )
            logger.debug("Initialized Tweepy client")

        return self._client

    @retry(
        retry=retry_if_exception_type((TwitterError, Exception)),
        stop=stop_after_attempt(DEFAULT_NUM_RETRIES),
        wait=wait_exponential(multiplier=1, min=1, max=DEFAULT_WAIT_TIME),
        reraise=True,
    )
    def fetch_recent_tweets(
        self,
        usernames: list[str] | None = None,
        days: int = 7,
        min_likes: int = DEFAULT_MIN_LIKES,
        max_tweets_per_user: int = DEFAULT_MAX_TWEETS_PER_USER,
        exclude_replies: bool = True,
    ) -> list[ContentItem]:
        """
        Fetch recent tweets from specified AI accounts.

        Args:
            usernames: List of Twitter usernames (without @). Defaults to core AI accounts.
            days: Only return tweets from last N days
            min_likes: Minimum like count threshold
            max_tweets_per_user: Maximum tweets to fetch per user
            exclude_replies: Whether to exclude reply tweets

        Returns:
            List of ContentItem objects sorted by engagement (highest first)
        """
        accounts = usernames if usernames else DEFAULT_TWITTER_SOURCES
        all_tweets: list[ContentItem] = []
        cutoff_date = datetime.now(tz=TIMEZONE) - timedelta(days=days)

        client = self._get_client()

        for username in accounts:
            try:
                tweets = self._fetch_user_tweets(
                    client=client,
                    username=username,
                    cutoff_date=cutoff_date,
                    min_likes=min_likes,
                    max_results=max_tweets_per_user,
                    exclude_replies=exclude_replies,
                )
                all_tweets.extend(tweets)
                logger.info(f"Fetched {len(tweets)} tweets from @{username}")
            except Exception as e:
                logger.error(
                    f"Failed to fetch tweets for @{username}: {e}",
                    exc_info=True,
                    extra={"username": username},
                )
                continue

        # Sort by engagement score (likes), highest first
        all_tweets.sort(key=lambda t: t.engagement_score, reverse=True)

        logger.info(f"Total tweets fetched: {len(all_tweets)} from {len(accounts)} accounts")
        return all_tweets

    def _fetch_user_tweets(
        self,
        client: Any,
        username: str,
        cutoff_date: datetime,
        min_likes: int,
        max_results: int,
        exclude_replies: bool,
    ) -> list[ContentItem]:
        """Fetch tweets from a single user."""
        try:
            # Get user ID from username
            user_response = client.get_user(username=username.replace("@", ""))
            if not user_response or not user_response.data:
                logger.warning(f"User @{username} not found")
                return []

            user_id = user_response.data.id
            user_display_name = user_response.data.name

            # Fetch recent tweets
            tweets_response = client.get_users_tweets(
                id=user_id,
                max_results=min(max_results * 2, 20),  # Fetch extra to filter
                tweet_fields=["created_at", "public_metrics", "referenced_tweets", "entities"],
                exclude=["retweets"] if exclude_replies else None,
            )

            if not tweets_response or not tweets_response.data:
                return []

            tweets: list[ContentItem] = []
            for tweet in tweets_response.data:
                try:
                    # Parse tweet data
                    content_item = self._parse_tweet(
                        tweet=tweet,
                        username=username,
                        user_display_name=user_display_name,
                        cutoff_date=cutoff_date,
                        min_likes=min_likes,
                    )
                    if content_item:
                        tweets.append(content_item)
                except ValidationError as e:
                    logger.warning(f"Failed to parse tweet from @{username}: {e}")
                    continue
                except Exception as e:
                    logger.warning(f"Unexpected error parsing tweet: {e}")
                    continue

            return tweets[:max_results]

        except Exception as e:
            logger.error(f"Error fetching tweets for @{username}: {e}")
            raise

    def _parse_tweet(
        self,
        tweet: Any,
        username: str,
        user_display_name: str,
        cutoff_date: datetime,
        min_likes: int,
    ) -> ContentItem | None:
        """Parse a single tweet into ContentItem."""
        # Check date
        created_at = tweet.created_at
        if created_at:
            if isinstance(created_at, str):
                from dateutil import parser
                created_at = parser.isoparse(created_at)
            if created_at.replace(tzinfo=TIMEZONE) < cutoff_date:
                return None

        # Get metrics
        metrics = tweet.public_metrics or {}
        like_count = metrics.get("like_count", 0)
        retweet_count = metrics.get("retweet_count", 0)
        reply_count = metrics.get("reply_count", 0)

        # Filter by engagement
        if like_count < min_likes:
            return None

        # Extract referenced URLs from tweet text
        referenced_urls: list[str] = []
        if tweet.entities and "urls" in tweet.entities:
            for url_obj in tweet.entities["urls"]:
                expanded_url = url_obj.get("expanded_url", "")
                if expanded_url and not expanded_url.startswith("https://twitter.com/"):
                    referenced_urls.append(expanded_url)

        # Build tweet URL
        tweet_url = f"https://twitter.com/{username}/status/{tweet.id}"

        # Calculate engagement score (weighted likes + retweets)
        engagement_score = like_count + (retweet_count * 2)

        return ContentItem(
            id=str(tweet.id),
            title=f"Tweet by @{username}",
            source=f"@{username}",
            source_type="twitter",
            url=tweet_url,
            published_on=created_at.replace(tzinfo=TIMEZONE) if created_at else datetime.now(tz=TIMEZONE),
            author=user_display_name,
            summary=tweet.text[:200] + "..." if len(tweet.text) > 200 else tweet.text,
            content=tweet.text,
            engagement_score=engagement_score,
            metadata={
                "like_count": like_count,
                "retweet_count": retweet_count,
                "reply_count": reply_count,
                "referenced_urls": referenced_urls,
            },
        )


def fetch_twitter_content(
    usernames: list[str] | None = None,
    days: int = 7,
    min_likes: int = DEFAULT_MIN_LIKES,
    max_tweets_per_user: int = DEFAULT_MAX_TWEETS_PER_USER,
) -> list[ContentItem]:
    """
    Convenience function to fetch recent tweets from AI accounts.

    Args:
        usernames: Specific accounts to fetch (None = default AI accounts)
        days: Only return tweets from last N days
        min_likes: Minimum like count threshold
        max_tweets_per_user: Maximum tweets per account

    Returns:
        List of ContentItem objects
    """
    client = TwitterClient()
    return client.fetch_recent_tweets(
        usernames=usernames,
        days=days,
        min_likes=min_likes,
        max_tweets_per_user=max_tweets_per_user,
    )
