"""Data source modules for AI Daily Digest."""

from arxiv_sanity_bot.sources.github_trending import GitHubTrendingClient, GitHubRepo
from arxiv_sanity_bot.sources.huggingface_extended import (
    HuggingFaceExtendedClient,
    HFModel,
)
from arxiv_sanity_bot.sources.tech_blogs import TechBlogClient, BlogPost
from arxiv_sanity_bot.sources.twitter_source import (
    TwitterClient,
    fetch_twitter_content,
    DEFAULT_TWITTER_SOURCES,
)
from arxiv_sanity_bot.sources.youtube_source import (
    YouTubeClient,
    fetch_youtube_content,
    DEFAULT_YOUTUBE_CHANNELS,
)

__all__ = [
    "GitHubTrendingClient",
    "GitHubRepo",
    "HuggingFaceExtendedClient",
    "HFModel",
    "TechBlogClient",
    "BlogPost",
    "TwitterClient",
    "fetch_twitter_content",
    "DEFAULT_TWITTER_SOURCES",
    "YouTubeClient",
    "fetch_youtube_content",
    "DEFAULT_YOUTUBE_CHANNELS",
]
