from datetime import datetime, timedelta
import os
import time
import random
from typing import Any

import click
import numpy as np
import pandas as pd

import dotenv

dotenv.load_dotenv()

from arxiv_sanity_bot.arxiv import arxiv_abstracts  # noqa: E402
from arxiv_sanity_bot.ranking import ranked_papers  # noqa: E402
from arxiv_sanity_bot.arxiv.extract_image import extract_first_image  # noqa: E402
from arxiv_sanity_bot.config import (  # noqa: E402
    WINDOW_START,
    WINDOW_STOP,
    TIMEZONE,
    SOURCE,
    SCORE_THRESHOLD,
    MAX_NUM_PAPERS,
)
from arxiv_sanity_bot.logger import get_logger, FatalError  # noqa: E402
from arxiv_sanity_bot.models.openai import OpenAI  # noqa: E402
from arxiv_sanity_bot.store.store import DocumentStore  # noqa: E402
from arxiv_sanity_bot.twitter.auth import TwitterOAuth1  # noqa: E402
from arxiv_sanity_bot.twitter.send_tweet import send_tweet  # noqa: E402
from arxiv_sanity_bot.sources import (  # noqa: E402
    GitHubTrendingClient,
    HuggingFaceExtendedClient,
    TechBlogClient,
    TwitterClient,
    YouTubeClient,
)
from arxiv_sanity_bot.email import (  # noqa: E402
    EmailSender,
    SendGridEmailSender,
    SmtpEmailSender,
)
from arxiv_sanity_bot.models.content_processor import ContentProcessor  # noqa: E402


logger = get_logger(__name__)


_SOURCES = {
    "arxiv": arxiv_abstracts,
    "ranked": ranked_papers,
}


@click.command()
@click.option("--window_start", default=WINDOW_START, help="Window start", type=int)
@click.option("--window_stop", default=WINDOW_STOP, help="Window stop", type=int)
@click.option("--dry", is_flag=True)
def bot(window_start, window_stop, dry):
    logger.info("Bot starting")

    # This returns all abstracts above the threshold
    abstracts, n_retrieved = _gather_abstracts(window_start, window_stop)

    if abstracts.shape[0] == 0:
        return

    # Summarize the papers above the threshold that have not been summarized
    # before
    doc_store = DocumentStore.from_env_variable()

    filtered_abstracts = _keep_only_new_abstracts(abstracts, doc_store)

    summaries = _summarize_top_abstracts(filtered_abstracts)

    if len(summaries) > 0:
        send_tweets(n_retrieved, summaries, doc_store, dry)

    logger.info("Bot finishing")


def send_tweets(
    n_retrieved: int,
    summaries: list[dict[str, Any]],
    doc_store: DocumentStore,
    dry: bool,
):

    # Send the tweets
    oauth = TwitterOAuth1()

    if dry:

        def tweet_sender(
            tweet: str,
            auth: TwitterOAuth1,
            img_path: str | None = None,
            in_reply_to_tweet_id: int | None = None,
        ) -> tuple[str | None, int | None]:
            return ("https://fake.url", 123456789)

    else:
        tweet_sender = send_tweet

    logger.info("Sending summary tweet")
    summary_tweet = OpenAI().generate_bot_summary(n_retrieved, len(summaries))

    if summary_tweet is None:

        # Error!
        logger.critical("Could not generate summary tweet")
        raise FatalError("Could not generate summary tweet")

    summary_tweet_url, summary_tweet_id = tweet_sender(summary_tweet, auth=oauth)

    for s in summaries[::-1]:
        # Introduce a random delay between the tweets to avoid triggering
        # the Twitter alarm
        delay = random.randint(10, 30)
        logger.info(f"Waiting for {delay} seconds before sending next tweet")
        time.sleep(delay)

        this_url, this_tweet_id = tweet_sender(
            s["tweet"],
            auth=oauth,
            img_path=s["image"],
            in_reply_to_tweet_id=summary_tweet_id,
        )

        if this_url is not None:
            if s["url"]:
                logger.info(f"Sending URL as reply to tweet {this_tweet_id}")
                time.sleep(2)
                tweet_sender(s["url"], auth=oauth, in_reply_to_tweet_id=this_tweet_id)

            doc_store[s["arxiv"]] = {
                "tweet_id": this_tweet_id,
                "tweet_url": this_url,
                "title": s["title"],
                "published_on": s["published_on"],
            }


def _keep_only_new_abstracts(
    abstracts: pd.DataFrame, doc_store: DocumentStore
) -> pd.DataFrame:
    mask = np.ones(len(abstracts), dtype=bool)

    for idx, (_, row) in enumerate(abstracts.iterrows()):
        logger.info(
            f"Checking if paper {row['arxiv']} has been posted before",
            extra={
                "arxiv_id": row["arxiv"],
                "title": row["title"],
                "score": row["score"],
            },
        )
        if row["arxiv"] in doc_store:
            # Yes, we already processed it. Skip it
            logger.info(
                f"Paper {row['arxiv']} has been already summarized in a previous run",
                extra={"title": row["title"], "score": row["score"]},
            )
            mask[idx] = False

    return abstracts[mask].reset_index(drop=True)


def _summarize_top_abstracts(selected_abstracts: pd.DataFrame) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []

    top_papers = selected_abstracts.iloc[:MAX_NUM_PAPERS]

    logger.info(f"Selected {len(top_papers)} papers to summarize")
    for paper_num, (_, row) in enumerate(top_papers.iterrows(), start=1):
        logger.info(
            f"Paper {paper_num}: {row['arxiv']}",
            extra={
                "title": row["title"],
                "score": row["score"],
                "alphaxiv_rank": row.get("alphaxiv_rank"),
                "hf_rank": row.get("hf_rank"),
                "average_rank": row.get("average_rank"),
                "published_on": (
                    row["published_on"].isoformat()
                    if hasattr(row["published_on"], "isoformat")
                    else str(row["published_on"])
                ),
            },
        )

    for i, row in top_papers.iterrows():
        summary, url, img_path = _summarize(row)

        if summary is not None:
            summaries.append(
                {
                    "arxiv": row["arxiv"],
                    "title": row["title"],
                    "score": row["score"],
                    "published_on": row["published_on"],
                    "image": img_path,
                    "tweet": summary,
                    "url": url,
                }
            )

    return summaries


def _summarize(row: pd.Series) -> tuple[str, str, str | None]:
    openai_model = OpenAI()

    summary = openai_model.summarize_abstract(row["abstract"])

    url = _SOURCES[SOURCE].get_url(row["arxiv"])

    logger.info(
        f"Processed abstract for {url}",
        extra={"title": row["title"], "score": row["score"]},
    )

    # Get image from the first page
    img_path = extract_first_image(row["arxiv"])

    return summary, url, img_path


def _gather_abstracts(window_start: int, window_stop: int) -> tuple[pd.DataFrame, int]:
    """
    Get all abstracts from arxiv-sanity from the last 48 hours above the threshold

    :return: a pandas dataframe with the papers ordered by score (best at the top)
    """

    get_all_abstracts_func = _SOURCES[SOURCE].get_all_abstracts

    now = datetime.now(tz=TIMEZONE)
    start = now - timedelta(hours=window_start)
    end = now - timedelta(hours=window_stop)

    logger.info(f"Considering time interval {start} to {end} UTC")

    abstracts, alphaxiv_count = get_all_abstracts_func(after=start, before=end)

    if abstracts.shape[0] == 0:
        logger.info(
            f"No abstract in the time window {start} - {end} before filtering for score."
        )

        return abstracts, alphaxiv_count

    # Threshold on score
    idx = abstracts["score"] >= SCORE_THRESHOLD
    abstracts = abstracts[idx].reset_index(drop=True)

    if abstracts.shape[0] == 0:
        logger.info(
            f"No abstract in the time window {start} - {end} above score {SCORE_THRESHOLD}"
        )
        return abstracts, alphaxiv_count
    else:
        logger.info(
            f"Found {abstracts.shape[0]} abstracts in the time window {start} - {end} above score {SCORE_THRESHOLD}. "
            f"Total AlphaXiv papers considered (before percentile filter): {alphaxiv_count}"
        )

        top_papers = abstracts.head(50)
        papers_list = []
        for _, row in top_papers.iterrows():
            papers_list.append(
                {"arxiv_id": row["arxiv"], "title": row["title"], "score": row["score"]}
            )
        logger.info(
            f"Top {len(papers_list)} papers after ranking",
            extra={"papers": papers_list},
        )

    return abstracts, alphaxiv_count


@click.command()
@click.option("--dry", is_flag=True, help="Dry run - don't actually send email")
@click.option("--github-limit", default=5, help="Number of GitHub repos to include")
@click.option("--hf-models-limit", default=5, help="Number of HF models to include")
@click.option("--hf-datasets-limit", default=3, help="Number of HF datasets to include")
@click.option("--hf-spaces-limit", default=3, help="Number of HF spaces to include")
@click.option("--arxiv-limit", default=5, help="Number of arXiv papers to include")
@click.option("--blog-days", default=7, help="Days of blog posts to include")
@click.option("--blog-limit", default=3, help="Max posts per blog source")
def daily_digest(
    dry: bool,
    github_limit: int,
    hf_models_limit: int,
    hf_datasets_limit: int,
    hf_spaces_limit: int,
    arxiv_limit: int,
    blog_days: int,
    blog_limit: int,
) -> None:
    """Generate and send AI Daily Digest email."""
    logger.info("Daily Digest starting")

    # Collect all data sources
    logger.info("Collecting data from all sources...")

    # GitHub Trending
    github_repos = _fetch_github_trending(github_limit)

    # HuggingFace Trending
    hf_models, hf_datasets, hf_spaces = _fetch_huggingface_trending(
        hf_models_limit, hf_datasets_limit, hf_spaces_limit
    )

    # Initialize content processor early for paper summaries
    processor = ContentProcessor()

    # arXiv Papers
    arxiv_papers = _fetch_arxiv_papers(arxiv_limit)

    # Tech Blog Posts
    blog_posts = _fetch_blog_posts(blog_days, blog_limit)

    # Twitter Content (if enabled)
    tweets = _fetch_twitter_content()

    # YouTube Content (if enabled)
    videos = _fetch_youtube_content()

    logger.info(
        "Data collection complete",
        extra={
            "github_repos": len(github_repos),
            "hf_models": len(hf_models),
            "hf_datasets": len(hf_datasets),
            "hf_spaces": len(hf_spaces),
            "arxiv_papers": len(arxiv_papers),
            "blog_posts": len(blog_posts),
            "tweets": len(tweets),
            "videos": len(videos),
        },
    )

    if not dry and arxiv_papers:
        logger.info("Generating paper summaries with DeepSeek...")
        arxiv_papers = processor.batch_summarize_papers(arxiv_papers)

    logger.info("Generating daily insight...")
    daily_insight = processor.generate_mixed_content_digest(
        arxiv_papers, blog_posts, tweets, videos
    )
    logger.info(f"Daily insight: {daily_insight[:100]}...")

    if dry:
        logger.info("DRY RUN: Would send email with collected data")
        _print_digest_summary(
            github_repos, hf_models, hf_datasets, hf_spaces,
            arxiv_papers, blog_posts, tweets, videos
        )
        return

    # Send email
    to_email = os.environ.get("TO_EMAIL")
    from_email = os.environ.get("FROM_EMAIL")

    if not to_email or not from_email:
        logger.error("TO_EMAIL and FROM_EMAIL environment variables required")
        return

    # Choose sender: SMTP (QQ Mail, etc.) or SendGrid
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")

    sender: EmailSender
    if smtp_host and smtp_user and smtp_pass:
        # Use SMTP (QQ Mail, Gmail, etc.)
        logger.info(f"Using SMTP sender: {smtp_host}")
        sender = SmtpEmailSender()
    elif os.environ.get("SENDGRID_API_KEY"):
        # Use SendGrid
        logger.info("Using SendGrid sender")
        sender = SendGridEmailSender()
    else:
        logger.error(
            "No email sender configured. "
            "Set SMTP_HOST/SMTP_USER/SMTP_PASS for SMTP, "
            "or SENDGRID_API_KEY for SendGrid."
        )
        return

    success = sender.send_digest(
        github_repos=github_repos,
        hf_models=hf_models,
        hf_datasets=hf_datasets,
        hf_spaces=hf_spaces,
        arxiv_papers=arxiv_papers,
        blog_posts=blog_posts,
        to_email=to_email,
        from_email=from_email,
        daily_insight=daily_insight,
    )

    if success:
        logger.info("Daily Digest sent successfully")
    else:
        logger.error("Failed to send Daily Digest")

    logger.info("Daily Digest finishing")


def _fetch_github_trending(limit: int) -> list:
    """Fetch trending GitHub repositories."""
    try:
        client = GitHubTrendingClient(since="daily")
        repos = client.fetch_trending(limit=limit)
        logger.info(f"Fetched {len(repos)} GitHub trending repos")
        return repos
    except Exception as e:
        logger.error(f"GitHub trending fetch failed: {e}", exc_info=True)
        return []


def _fetch_huggingface_trending(
    models_limit: int, datasets_limit: int, spaces_limit: int
) -> tuple[list, list, list]:
    """Fetch trending HuggingFace content."""
    try:
        client = HuggingFaceExtendedClient()
        trending = client.fetch_all_trending(
            models_limit=models_limit,
            datasets_limit=datasets_limit,
            spaces_limit=spaces_limit,
        )
        logger.info(
            f"Fetched HuggingFace content: "
            f"{len(trending['models'])} models, "
            f"{len(trending['datasets'])} datasets, "
            f"{len(trending['spaces'])} spaces"
        )
        return trending["models"], trending["datasets"], trending["spaces"]
    except Exception as e:
        logger.error(f"HuggingFace fetch failed: {e}", exc_info=True)
        return [], [], []


def _fetch_arxiv_papers(limit: int) -> list[dict[str, Any]]:
    """Fetch recent arXiv papers (summaries generated separately)."""
    try:
        # Use arxiv_abstracts directly to avoid HF daily_papers API issues
        now = datetime.now(tz=TIMEZONE)
        start = now - timedelta(hours=WINDOW_START)
        end = now - timedelta(hours=WINDOW_STOP)

        logger.info(f"Fetching arXiv papers from {start} to {end}")
        abstracts, count = arxiv_abstracts.get_all_abstracts(after=start, before=end)

        if abstracts.shape[0] == 0:
            logger.info("No arXiv papers found")
            return []

        # Get top papers
        top_papers = abstracts.iloc[:limit]

        papers = []
        for _, row in top_papers.iterrows():

            url = arxiv_abstracts.get_url(row["arxiv"])

            papers.append(
                {
                    "arxiv": row["arxiv"],
                    "title": row["title"],
                    "abstract": row["abstract"],
                    "summary": "",  # Will be generated by batch_summarize_papers
                    "url": url,
                    "score": row.get("score", 1),
                    "published_on": row["published_on"],
                }
            )

        logger.info(f"Processed {len(papers)} arXiv papers")
        return papers
    except Exception as e:
        logger.error(f"arXiv fetch failed: {e}", exc_info=True)
        return []


def _fetch_blog_posts(days: int, limit_per_source: int) -> list:
    """Fetch recent tech blog posts."""
    try:
        client = TechBlogClient()
        posts = client.fetch_recent_posts(
            days=days,
            limit_per_source=limit_per_source,
        )
        logger.info(f"Fetched {len(posts)} blog posts")
        return posts
    except Exception as e:
        logger.error(f"Blog posts fetch failed: {e}", exc_info=True)
        return []


def _fetch_twitter_content() -> list:
    """Fetch recent tweets from AI accounts (if enabled)."""
    content_sources = os.environ.get("CONTENT_SOURCES", "arxiv,blog").split(",")
    if "twitter" not in content_sources:
        logger.info("Twitter content source disabled")
        return []

    try:
        client = TwitterClient()
        tweets = client.fetch_recent_tweets()
        logger.info(f"Fetched {len(tweets)} tweets")
        return tweets
    except Exception as e:
        logger.error(f"Twitter fetch failed: {e}", exc_info=True)
        return []


def _fetch_youtube_content() -> list:
    """Fetch recent videos from AI channels (if enabled)."""
    content_sources = os.environ.get("CONTENT_SOURCES", "arxiv,blog").split(",")
    if "youtube" not in content_sources:
        logger.info("YouTube content source disabled")
        return []

    try:
        client = YouTubeClient()
        videos = client.fetch_recent_videos()
        logger.info(f"Fetched {len(videos)} videos")
        return videos
    except Exception as e:
        logger.error(f"YouTube fetch failed: {e}", exc_info=True)
        return []


def _print_digest_summary(
    github_repos, hf_models, hf_datasets, hf_spaces, arxiv_papers, blog_posts, tweets=None, videos=None
) -> None:
    """Print summary of digest content for dry run."""
    print("\n" + "=" * 60)
    print("AI DAILY DIGEST - DRY RUN SUMMARY")
    print("=" * 60)

    print(f"\n[GitHub Trending] {len(github_repos)} repos")
    for repo in github_repos[:3]:
        print(f"  - {repo.name}")

    print(f"\n[HuggingFace Models] {len(hf_models)}")
    for model in hf_models[:3]:
        print(f"  - {model.name}")

    print(f"\n[HuggingFace Datasets] {len(hf_datasets)}")
    print(f"[HuggingFace Spaces] {len(hf_spaces)}")

    print(f"\n[arXiv Papers] {len(arxiv_papers)}")
    for paper in arxiv_papers[:3]:
        print(f"  - {paper['title'][:60]}...")

    print(f"\n[Blog Posts] {len(blog_posts)}")
    for post in blog_posts[:3]:
        print(f"  - [{post.source}] {post.title[:50]}...")

    # New content sources
    if tweets is not None:
        print(f"\n[Twitter] {len(tweets)} tweets")
        for tweet in tweets[:3]:
            content = tweet.content[:50] if tweet.content else tweet.title[:50]
            print(f"  - [@{tweet.source}] {content}...")

    if videos is not None:
        print(f"\n[YouTube] {len(videos)} videos")
        for video in videos[:3]:
            print(f"  - [{video.source}] {video.title[:50]}...")

    print("\n" + "=" * 60)


# Create command group for both commands
@click.group()
def cli():
    """arxiv-sanity-bot CLI."""
    pass


cli.add_command(bot)
cli.add_command(daily_digest)


if __name__ == "__main__":
    cli()
