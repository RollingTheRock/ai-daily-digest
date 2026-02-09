"""Data source modules for AI Daily Digest."""

from arxiv_sanity_bot.sources.github_trending import GitHubTrendingClient, GitHubRepo
from arxiv_sanity_bot.sources.huggingface_extended import (
    HuggingFaceExtendedClient,
    HFModel,
)
from arxiv_sanity_bot.sources.tech_blogs import TechBlogClient, BlogPost

__all__ = [
    "GitHubTrendingClient",
    "GitHubRepo",
    "HuggingFaceExtendedClient",
    "HFModel",
    "TechBlogClient",
    "BlogPost",
]
