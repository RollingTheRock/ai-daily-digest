"""GitHub Trending scraper for AI Daily Digest."""

from typing import Any

import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from arxiv_sanity_bot.logger import get_logger

logger = get_logger(__name__)

DEFAULT_NUM_RETRIES = 3
DEFAULT_WAIT_TIME = 20


class GitHubRepo(BaseModel):
    """Model for a GitHub trending repository."""

    name: str = Field(..., description="Repository name in format 'owner/repo'")
    description: str = Field(..., description="Repository description")
    stars_today: int = Field(0, description="Stars gained today")
    stars_total: int = Field(0, description="Total star count")
    language: str | None = Field(None, description="Primary programming language")
    url: str = Field(..., description="Repository URL")


class GitHubTrendingError(Exception):
    """Exception raised for GitHub trending fetch errors."""

    pass


class GitHubTrendingClient:
    """Client for fetching GitHub Trending repositories."""

    BASE_URL = "https://github.com/trending"

    def __init__(
        self,
        language: str | None = None,
        since: str = "daily",
        num_retries: int = DEFAULT_NUM_RETRIES,
        wait_time: int = DEFAULT_WAIT_TIME,
    ):
        """
        Initialize the GitHub Trending client.

        Args:
            language: Filter by programming language (e.g., 'python', 'javascript')
            since: Time period - 'daily', 'weekly', or 'monthly'
            num_retries: Number of retry attempts
            wait_time: Maximum wait time between retries
        """
        self.language = language
        self.since = since
        self.num_retries = num_retries
        self.wait_time = wait_time

    def fetch_trending(self, limit: int = 10) -> list[GitHubRepo]:
        """
        Fetch trending repositories from GitHub.

        Args:
            limit: Maximum number of repositories to return

        Returns:
            List of GitHubRepo objects
        """
        try:
            repos = self._fetch_with_retry()
            return repos[:limit]
        except Exception as e:
            logger.error(
                f"Failed to fetch GitHub trending: {e}",
                exc_info=True,
                extra={"language": self.language, "since": self.since},
            )
            return []

    @retry(
        retry=retry_if_exception_type((requests.RequestException, GitHubTrendingError)),
        stop=stop_after_attempt(DEFAULT_NUM_RETRIES),
        wait=wait_exponential(multiplier=1, min=1, max=DEFAULT_WAIT_TIME),
        reraise=True,
    )
    def _fetch_with_retry(self) -> list[GitHubRepo]:
        """Fetch trending repos with retry logic."""
        url = self._build_url()
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
        }

        logger.debug("Fetching GitHub trending", extra={"url": url})

        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        repos = self._parse_html(response.text)

        logger.info(f"Fetched {len(repos)} trending repositories from GitHub")
        return repos

    def _build_url(self) -> str:
        """Build the GitHub trending URL."""
        url = self.BASE_URL
        if self.language:
            url = f"{url}/{self.language}"
        url = f"{url}?since={self.since}"
        return url

    def _parse_html(self, html: str) -> list[GitHubRepo]:
        """Parse GitHub trending HTML to extract repository data."""
        soup = BeautifulSoup(html, "html.parser")
        repos: list[GitHubRepo] = []

        # Find all article elements that contain repository data
        articles = soup.find_all("article", class_="Box-row")

        for article in articles:
            try:
                repo = self._parse_repo_article(article)
                if repo:
                    repos.append(repo)
            except Exception as e:
                logger.warning(f"Failed to parse repository article: {e}")
                continue

        return repos

    def _parse_repo_article(self, article: Any) -> GitHubRepo | None:
        """Parse a single repository article element."""
        # Extract repository name from h2 > a
        link_elem = article.find("h2")
        if not link_elem:
            return None

        a_elem = link_elem.find("a")
        if not a_elem:
            return None

        href = a_elem.get("href", "")
        if not href:
            return None

        # Clean up the name (remove whitespace)
        name = href.strip("/")
        url = f"https://github.com/{name}"

        # Extract description
        description = ""
        desc_elem = article.find("p", class_="col-9")
        if desc_elem:
            description = desc_elem.get_text(strip=True)

        # Extract language
        language = None
        lang_elem = article.find("span", itemprop="programmingLanguage")
        if lang_elem:
            language = lang_elem.get_text(strip=True)

        # Extract star counts
        stars_total = 0
        stars_today = 0

        # Find all link elements that might contain star counts
        link_elems = article.find_all(
            "a", class_="Link Link--muted d-inline-block mr-3"
        )
        for elem in link_elems:
            text = elem.get_text(strip=True)
            if (
                "star" in text.lower()
                or text.replace(",", "").replace(".", "").isdigit()
            ):
                # This is likely the star count
                stars_text = (
                    text.replace(",", "").replace("k", "000").replace("K", "000")
                )
                try:
                    # Handle '1.2k' format
                    if "." in stars_text and "000" in stars_text:
                        stars_text = stars_text.replace("000", "00")
                    stars_total = int(float(stars_text))
                except ValueError:
                    pass

        # Look for "stars today" or similar text
        today_elem = article.find("span", class_="d-inline-block float-sm-right")
        if today_elem:
            today_text = today_elem.get_text(strip=True)
            # Parse something like "123 stars today"
            try:
                today_parts = today_text.replace(",", "").split()
                if today_parts:
                    stars_today = int(today_parts[0])
            except (ValueError, IndexError):
                pass

        return GitHubRepo(
            name=name,
            description=description,
            stars_today=stars_today,
            stars_total=stars_total,
            language=language,
            url=url,
        )


def fetch_github_trending(
    language: str | None = None,
    since: str = "daily",
    limit: int = 10,
) -> list[GitHubRepo]:
    """
    Convenience function to fetch GitHub trending repositories.

    Args:
        language: Filter by programming language
        since: Time period - 'daily', 'weekly', or 'monthly'
        limit: Maximum number of repositories to return

    Returns:
        List of GitHubRepo objects
    """
    client = GitHubTrendingClient(language=language, since=since)
    return client.fetch_trending(limit=limit)
