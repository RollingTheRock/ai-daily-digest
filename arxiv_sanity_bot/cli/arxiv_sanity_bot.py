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

    # Merge all content into unified format for AI scoring
    all_contents = []

    # GitHub repos
    for repo in github_repos:
        all_contents.append({
            "type": "github",
            "title": repo.name,
            "stars": repo.stars_total or 0,
            "description": (repo.description or "")[:200],
            "_original": repo,
        })

    # HF Models
    for model in hf_models:
        all_contents.append({
            "type": "hf_model",
            "title": model.name,
            "stars": model.downloads or model.likes or 0,
            "description": (model.description or "")[:200],
            "_original": model,
        })

    # HF Datasets
    for dataset in hf_datasets:
        all_contents.append({
            "type": "hf_dataset",
            "title": dataset.name,
            "stars": dataset.downloads or dataset.likes or 0,
            "description": (dataset.description or "")[:200],
            "_original": dataset,
        })

    # HF Spaces
    for space in hf_spaces:
        all_contents.append({
            "type": "hf_space",
            "title": space.name,
            "stars": space.likes or 0,
            "description": (space.description or "")[:200],
            "_original": space,
        })

    # arXiv papers
    for paper in arxiv_papers:
        all_contents.append({
            "type": "arxiv",
            "title": paper.get("title", ""),
            "stars": paper.get("score", 0),
            "description": (paper.get("abstract", ""))[:200],
            "_original": paper,
        })

    # Blog posts
    for post in blog_posts:
        all_contents.append({
            "type": "blog",
            "title": post.title,
            "stars": 0,
            "description": (post.summary or "")[:200],
            "_original": post,
        })

    # Tweets
    for tweet in tweets:
        all_contents.append({
            "type": "twitter",
            "title": tweet.title or f"@{tweet.source}",
            "stars": tweet.engagement_score or 0,
            "description": (tweet.content or tweet.summary or "")[:200],
            "_original": tweet,
        })

    # YouTube videos
    for video in videos:
        view_count = 0
        if video.metadata and "view_count" in video.metadata:
            view_count = int(video.metadata.get("view_count", 0))
        all_contents.append({
            "type": "youtube",
            "title": video.title,
            "stars": view_count,
            "description": (video.summary or "")[:200],
            "_original": video,
        })

    logger.info(f"Merged {len(all_contents)} items for AI scoring")

    # AI scoring
    if all_contents:
        logger.info("Starting AI scoring...")
        tagged_contents = processor.score_and_tag_contents(all_contents)
        logger.info(f"AI scoring complete for {len(tagged_contents)} items")

        # Sort by score descending
        tagged_contents.sort(key=lambda x: x.get("score", 0), reverse=True)

        # Global Top 3
        global_top3 = tagged_contents[:3]
        logger.info(
            "Global Top 3 selected",
            extra={
                "top3": [
                    {"title": c.get("title", "")[:50], "score": c.get("score"), "tag": c.get("tag")}
                    for c in global_top3
                ]
            },
        )

        # Extract Top 3 by type
        def get_top3_by_type(contents: list[dict], content_type: str) -> list:
            items = [c for c in contents if c.get("type") == content_type]
            return [c.get("_original") for c in items[:3] if c.get("_original")]

        github_top3 = get_top3_by_type(tagged_contents, "github")
        hf_models_top3 = get_top3_by_type(tagged_contents, "hf_model")
        hf_datasets_top3 = get_top3_by_type(tagged_contents, "hf_dataset")
        hf_spaces_top3 = get_top3_by_type(tagged_contents, "hf_space")
        arxiv_top3_raw = get_top3_by_type(tagged_contents, "arxiv")
        blog_top3 = get_top3_by_type(tagged_contents, "blog")
        tweets_top3 = get_top3_by_type(tagged_contents, "twitter")
        videos_top3 = get_top3_by_type(tagged_contents, "youtube")

        # Convert arXiv back to dict format
        arxiv_top3 = [item if isinstance(item, dict) else {"arxiv": "", "title": "", "abstract": ""} for item in arxiv_top3_raw]

        logger.info(
            "Top 3 by type extracted",
            extra={
                "github": len(github_top3),
                "hf_models": len(hf_models_top3),
                "hf_datasets": len(hf_datasets_top3),
                "hf_spaces": len(hf_spaces_top3),
                "arxiv": len(arxiv_top3),
                "blog": len(blog_top3),
                "tweets": len(tweets_top3),
                "videos": len(videos_top3),
            },
        )
    else:
        tagged_contents = []
        global_top3 = []
        github_top3 = github_repos[:3]
        hf_models_top3 = hf_models[:3]
        hf_datasets_top3 = hf_datasets[:3]
        hf_spaces_top3 = hf_spaces[:3]
        arxiv_top3 = arxiv_papers[:3]
        blog_top3 = blog_posts[:3]
        tweets_top3 = tweets[:3]
        videos_top3 = videos[:3]

    if not dry and arxiv_top3:
        logger.info("Generating paper summaries with DeepSeek...")
        arxiv_top3 = processor.batch_summarize_papers(arxiv_top3)

    logger.info("Generating daily insight...")
    # Build top3_context from global top 3
    if global_top3:
        top3_context = "\n".join([
            f"- [{c.get('tag', '')}] {c.get('title', '')}: {c.get('reason', '')}"
            for c in global_top3
        ])
    else:
        top3_context = ""

    daily_insight = processor.generate_daily_insight(top3_context)
    logger.info(f"Daily insight: {daily_insight[:100]}...")

    if dry:
        logger.info("DRY RUN: Would send email with collected data")
        _print_digest_summary(
            github_top3, hf_models_top3, hf_datasets_top3, hf_spaces_top3,
            arxiv_top3, blog_top3, tweets_top3, videos_top3
        )
        # Generate HTML preview for testing
        _generate_html_preview(
            github_top3, hf_models_top3, hf_datasets_top3, hf_spaces_top3,
            arxiv_top3, blog_top3, tweets_top3, videos_top3,
            daily_insight, tagged_contents, global_top3
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
        github_repos=github_top3,
        hf_models=hf_models_top3,
        hf_datasets=hf_datasets_top3,
        hf_spaces=hf_spaces_top3,
        arxiv_papers=arxiv_top3,
        blog_posts=blog_top3,
        to_email=to_email,
        from_email=from_email,
        daily_insight=daily_insight,
        tweets=tweets_top3,
        videos=videos_top3,
        all_scored_contents=tagged_contents,
        global_top3=global_top3,
    )

    if success:
        logger.info("Daily Digest sent successfully")
    else:
        logger.error("Failed to send Daily Digest")

    # Notion Output (optional, parallel to email)
    _send_to_notion_if_enabled(
        daily_insight=daily_insight,
        global_top3=global_top3,
        tagged_contents=tagged_contents,
    )

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


def _send_to_notion_if_enabled(
    daily_insight: str,
    global_top3: list[dict],
    tagged_contents: list[dict],
) -> None:
    """Send daily digest to Notion if OUTPUT_NOTION is enabled.

    This function is called after email sending. Notion failures are logged
    but do not affect the email sending flow.

    Args:
        daily_insight: AI-generated daily insight summary
        global_top3: Global Top 3 contents across all types
        tagged_contents: All scored and tagged contents (dict format with type, title, url, tag, reason, score)
    """
    # Debug: Log environment variable status
    output_notion_val = os.environ.get("OUTPUT_NOTION", "")
    logger.info(f"[Notion] Checking configuration: OUTPUT_NOTION={repr(output_notion_val)}")
    logger.info(f"[Notion] NOTION_TOKEN configured: {bool(os.environ.get('NOTION_TOKEN'))}")
    logger.info(f"[Notion] NOTION_DATABASE_ID configured: {bool(os.environ.get('NOTION_DATABASE_ID'))}")

    if output_notion_val.lower() != "true":
        logger.info(f"[Notion] Skipping Notion output: OUTPUT_NOTION is not 'true' (value: {repr(output_notion_val)})")
        return

    logger.info("[Notion] Notion output is enabled, proceeding...")

    notion_token = os.environ.get("NOTION_TOKEN", "").strip()
    notion_database_id = os.environ.get("NOTION_DATABASE_ID", "").strip()

    if not notion_token or not notion_database_id:
        logger.warning(
            "Notion output enabled but NOTION_TOKEN or NOTION_DATABASE_ID not set"
        )
        return

    try:
        from arxiv_sanity_bot.notion import NotionSender

        notion_sender = NotionSender(
            token=notion_token,
            database_id=notion_database_id,
        )

        today_str = datetime.now(tz=TIMEZONE).strftime("%Y-%m-%d")

        # Extract Top 3 by type from tagged_contents (dict format)
        # tagged_contents contains scored dicts with type, title, url, tag, reason, score
        github_top3_dict = sorted(
            [c for c in tagged_contents if c.get("type") == "github"],
            key=lambda x: x.get("score", 0),
            reverse=True
        )[:3]

        hf_top3_dict = sorted(
            [c for c in tagged_contents if c.get("type") in ("hf_model", "hf_dataset", "hf_space")],
            key=lambda x: x.get("score", 0),
            reverse=True
        )[:3]

        arxiv_top3_dict = sorted(
            [c for c in tagged_contents if c.get("type") == "arxiv"],
            key=lambda x: x.get("score", 0),
            reverse=True
        )[:3]

        blog_top3_dict = sorted(
            [c for c in tagged_contents if c.get("type") == "blog"],
            key=lambda x: x.get("score", 0),
            reverse=True
        )[:3]

        logger.info(f"[Notion] Extracted from tagged_contents: GitHub={len(github_top3_dict)}, HF={len(hf_top3_dict)}, arXiv={len(arxiv_top3_dict)}, Blog={len(blog_top3_dict)}")

        digest_data = {
            "date": today_str,
            "daily_insight": daily_insight,
            "top3": global_top3,
            "github_top3": github_top3_dict,
            "hf_top3": hf_top3_dict,
            "arxiv_top3": arxiv_top3_dict,
            "blog_top3": blog_top3_dict,
            "all_scored_contents": tagged_contents,
        }

        page_url = notion_sender.send_daily_digest(digest_data)
        logger.info(f"Notion page created: {page_url}")

    except Exception as e:
        logger.error(f"Notion output failed: {e}", exc_info=True)
        # Notion failure does not affect email sending


if __name__ == "__main__":
    cli()
