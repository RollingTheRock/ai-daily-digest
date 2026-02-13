"""SendGrid email sender for AI Daily Digest."""

import os
from datetime import datetime
from typing import Any
from urllib.parse import quote

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from arxiv_sanity_bot.logger import get_logger
from arxiv_sanity_bot.config import TIMEZONE
from arxiv_sanity_bot.sources import GitHubRepo, HFModel, BlogPost
from arxiv_sanity_bot.schemas import ContentItem
from arxiv_sanity_bot.signature import generate_signature

logger = get_logger(__name__)


class EmailSender:
    """Base class for email senders."""

    def send_digest(
        self,
        github_repos: list[GitHubRepo],
        hf_models: list[HFModel],
        hf_datasets: list[HFModel],
        hf_spaces: list[HFModel],
        arxiv_papers: list[dict[str, Any]],
        blog_posts: list[BlogPost],
        to_email: str,
        from_email: str,
        subject: str | None = None,
        daily_insight: str = "",
        tweets: list[ContentItem] | None = None,
        videos: list[ContentItem] | None = None,
    ) -> bool:
        """
        Send a daily digest email.

        Args:
            github_repos: List of trending GitHub repos
            hf_models: List of trending HF models
            hf_datasets: List of trending HF datasets
            hf_spaces: List of trending HF spaces
            arxiv_papers: List of arXiv papers with summaries
            blog_posts: List of recent blog posts
            to_email: Recipient email address
            from_email: Sender email address
            subject: Email subject (optional)
            daily_insight: Daily insight summary from LLM (optional)
            tweets: List of Twitter content items (optional)
            videos: List of YouTube content items (optional)

        Returns:
            True if sent successfully, False otherwise
        """
        raise NotImplementedError


class SendGridEmailSender(EmailSender):
    """SendGrid implementation of email sender."""

    def __init__(self, api_key: str | None = None):
        """
        Initialize SendGrid email sender.

        Args:
            api_key: SendGrid API key (or from SENDGRID_API_KEY env var)
        """
        self.api_key = api_key or os.environ.get("SENDGRID_API_KEY")
        if not self.api_key:
            raise ValueError(
                "SendGrid API key required. Set SENDGRID_API_KEY environment variable."
            )

        self._client = SendGridAPIClient(self.api_key)

    def send_digest(
        self,
        github_repos: list[GitHubRepo],
        hf_models: list[HFModel],
        hf_datasets: list[HFModel],
        hf_spaces: list[HFModel],
        arxiv_papers: list[dict[str, Any]],
        blog_posts: list[BlogPost],
        to_email: str,
        from_email: str,
        subject: str | None = None,
        daily_insight: str = "",
        tweets: list[ContentItem] | None = None,
        videos: list[ContentItem] | None = None,
    ) -> bool:
        """
        Send a daily digest email via SendGrid.

        Args:
            github_repos: List of trending GitHub repos
            hf_models: List of trending HF models
            hf_datasets: List of trending HF datasets
            hf_spaces: List of trending HF spaces
            arxiv_papers: List of arXiv papers with summaries
            blog_posts: List of recent blog posts
            to_email: Recipient email address
            from_email: Sender email address
            subject: Email subject (optional)
            daily_insight: Daily insight summary from LLM
            tweets: List of Twitter content items (optional)
            videos: List of YouTube content items (optional)

        Returns:
            True if sent successfully, False otherwise
        """
        if not subject:
            today = datetime.now(tz=TIMEZONE).strftime("%Y-%m-%d")
            subject = f"🤖 AI Daily Digest - {today}"

        # SendGrid uses simplified template (Twitter/YouTube not yet supported)
        html_content = self._build_html_email(
            github_repos=github_repos,
            hf_models=hf_models,
            hf_datasets=hf_datasets,
            hf_spaces=hf_spaces,
            arxiv_papers=arxiv_papers,
            blog_posts=blog_posts,
        )

        try:
            mail = Mail(
                from_email=from_email,
                to_emails=to_email,
                subject=subject,
                html_content=html_content,
            )

            response = self._client.send(mail)

            if response.status_code in (200, 201, 202):
                logger.info(
                    "Email sent successfully",
                    extra={
                        "to": to_email,
                        "from": from_email,
                        "status_code": response.status_code,
                    },
                )
                return True
            else:
                logger.error(
                    "Failed to send email",
                    extra={
                        "to": to_email,
                        "status_code": response.status_code,
                        "body": response.body,
                    },
                )
                return False

        except Exception as e:
            logger.error(
                f"Exception sending email: {e}",
                exc_info=True,
                extra={"to": to_email, "from": from_email},
            )
            return False

    def _build_html_email(
        self,
        github_repos: list[GitHubRepo],
        hf_models: list[HFModel],
        hf_datasets: list[HFModel],
        hf_spaces: list[HFModel],
        arxiv_papers: list[dict[str, Any]],
        blog_posts: list[BlogPost],
    ) -> str:
        """Build HTML email content."""
        today = datetime.now(tz=TIMEZONE).strftime("%Y-%m-%d %A")

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Daily Digest</title>
    <style>
        body {{
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background-color: #f6f8fa;
            color: #24292e;
            line-height: 1.6;
        }}
        .container {{
            max-width: 680px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
            border-radius: 8px 8px 0 0;
        }}
        .header h1 {{
            margin: 0;
            font-size: 28px;
            font-weight: 600;
        }}
        .header .date {{
            margin-top: 10px;
            opacity: 0.9;
            font-size: 14px;
        }}
        .content {{
            background: white;
            padding: 30px;
            border-radius: 0 0 8px 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        .section {{
            margin-bottom: 30px;
        }}
        .section:last-child {{
            margin-bottom: 0;
        }}
        .section-header {{
            display: flex;
            align-items: center;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #e1e4e8;
        }}
        .section-icon {{
            font-size: 24px;
            margin-right: 10px;
        }}
        .section-title {{
            font-size: 20px;
            font-weight: 600;
            color: #2f363d;
            margin: 0;
        }}
        .card {{
            background: #fafbfc;
            border: 1px solid #e1e4e8;
            border-radius: 6px;
            padding: 15px;
            margin-bottom: 12px;
            transition: border-color 0.2s;
        }}
        .card:hover {{
            border-color: #0366d6;
        }}
        .card-title {{
            font-size: 16px;
            font-weight: 600;
            margin: 0 0 8px 0;
        }}
        .card-title a {{
            color: #0366d6;
            text-decoration: none;
        }}
        .card-title a:hover {{
            text-decoration: underline;
        }}
        .card-description {{
            color: #586069;
            font-size: 14px;
            margin: 0 0 10px 0;
            line-height: 1.5;
        }}
        .card-meta {{
            font-size: 12px;
            color: #6a737d;
        }}
        .card-meta span {{
            margin-right: 12px;
        }}
        .tag {{
            display: inline-block;
            padding: 2px 8px;
            background: #e1e4e8;
            border-radius: 12px;
            font-size: 11px;
            color: #586069;
            margin-right: 5px;
        }}
        .card-actions {{
            margin-top: 12px;
            padding-top: 12px;
            border-top: 1px solid #e1e4e8;
        }}
        .btn {{
            display: inline-block;
            padding: 5px 12px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 500;
            text-decoration: none;
            margin-right: 8px;
        }}
        .btn-star {{
            background: #fff3cd;
            color: #856404;
            border: 1px solid #ffeaa7;
        }}
        .btn-star:hover {{
            background: #ffeaa7;
        }}
        .btn-note {{
            background: #d1ecf1;
            color: #0c5460;
            border: 1px solid #bee5eb;
        }}
        .btn-note:hover {{
            background: #bee5eb;
        }}
        .star-icon {{
            color: #f9a825;
        }}
        .footer {{
            text-align: center;
            padding: 20px;
            color: #6a737d;
            font-size: 12px;
        }}
        .footer a {{
            color: #0366d6;
        }}
        .empty-state {{
            color: #6a737d;
            font-style: italic;
            padding: 20px;
            text-align: center;
        }}
        @media (max-width: 600px) {{
            .container {{
                padding: 10px;
            }}
            .header, .content {{
                padding: 20px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 AI Daily Digest</h1>
            <div class="date">{today}</div>
        </div>
        <div class="content">
"""

        # GitHub Trending Section
        html += self._build_github_section(github_repos)

        # HuggingFace Section
        html += self._build_huggingface_section(hf_models, hf_datasets, hf_spaces)

        # arXiv Papers Section
        html += self._build_arxiv_section(arxiv_papers)

        # Tech Blogs Section
        html += self._build_blog_section(blog_posts)

        html += """
        </div>
        <div class="footer">
            <p>AI Daily Digest - Automated with 🤖</p>
            <p>Sent by arxiv-sanity-bot</p>
        </div>
    </div>
</body>
</html>
"""

        return html

    def _build_action_buttons(
        self,
        content_id: str,
        title: str,
        url: str,
        content_type: str,
        date: str,
    ) -> str:
        """Build action buttons (star/note) for a content card."""
        base_url = os.environ.get("DIGEST_WEB_URL", "").rstrip("/")
        if not base_url:
            return ""  # No web URL configured, skip buttons

        try:
            signature = generate_signature(content_id, date)

            star_url = f"{base_url}/star?id={quote(content_id, safe='')}&title={quote(title, safe='')}&url={quote(url, safe='')}&type={content_type}&date={date}&t={signature}"
            note_url = f"{base_url}/note?id={quote(content_id, safe='')}&title={quote(title, safe='')}&url={quote(url, safe='')}&type={content_type}&date={date}&t={signature}"

            return f'''
                <div class="card-actions">
                    <a href="{star_url}" class="btn btn-star" target="_blank">&#9733; Star</a>
                    <a href="{note_url}" class="btn btn-note" target="_blank">&#9998; Note</a>
                </div>
            '''
        except Exception as e:
            logger.warning(f"Failed to generate action buttons: {e}")
            return ""

    def _build_github_section(self, repos: list[GitHubRepo]) -> str:
        """Build GitHub trending section HTML."""
        html = """
            <div class="section">
                <div class="section-header">
                    <span class="section-icon">⭐</span>
                    <h2 class="section-title">GitHub Trending</h2>
                </div>
"""

        if not repos:
            html += (
                '<div class="empty-state">No trending repositories found today.</div>'
            )
        else:
            today = datetime.now(tz=TIMEZONE).strftime("%Y-%m-%d")
            for repo in repos:
                stars_today = f"+{repo.stars_today} today" if repo.stars_today else ""
                language = (
                    f'<span class="tag">{repo.language}</span>' if repo.language else ""
                )
                content_id = f"github-{repo.name.replace('/', '-')}"
                action_buttons = self._build_action_buttons(
                    content_id=content_id,
                    title=repo.name,
                    url=repo.url,
                    content_type="github",
                    date=today,
                )

                html += f"""
                <div class="card">
                    <h3 class="card-title"><a href="{repo.url}">{repo.name}</a></h3>
                    <p class="card-description">{self._escape_html(repo.description)}</p>
                    <div class="card-meta">
                        <span class="star-icon">★</span> {repo.stars_total:,} stars
                        {f'<span>{stars_today}</span>' if stars_today else ""}
                        {language}
                    </div>
                    {action_buttons}
                </div>
"""

        html += "</div>"
        return html

    def _build_huggingface_section(
        self,
        models: list[HFModel],
        datasets: list[HFModel],
        spaces: list[HFModel],
    ) -> str:
        """Build HuggingFace trending section HTML."""
        html = """
            <div class="section">
                <div class="section-header">
                    <span class="section-icon">🤗</span>
                    <h2 class="section-title">HuggingFace Trending</h2>
                </div>
"""

        today = datetime.now(tz=TIMEZONE).strftime("%Y-%m-%d")

        # Models subsection
        if models:
            html += '<h3 style="font-size: 14px; color: #586069; margin: 15px 0 10px;">🔥 Models</h3>'
            for model in models:
                tags = "".join(f'<span class="tag">{t}</span>' for t in model.tags[:3])
                content_id = f"hf-model-{model.name.replace('/', '-')}"
                action_buttons = self._build_action_buttons(
                    content_id=content_id,
                    title=model.name,
                    url=model.url,
                    content_type="huggingface",
                    date=today,
                )
                html += f"""
                <div class="card">
                    <h3 class="card-title"><a href="{model.url}">{model.name}</a></h3>
                    <p class="card-description">{self._escape_html(model.description)}</p>
                    <div class="card-meta">
                        <span>⬇️ {model.downloads:,} downloads</span>
                        <span>❤️ {model.likes:,} likes</span>
                        {tags}
                    </div>
                    {action_buttons}
                </div>
"""

        # Datasets subsection
        if datasets:
            html += '<h3 style="font-size: 14px; color: #586069; margin: 15px 0 10px;">📊 Datasets</h3>'
            for dataset in datasets:
                content_id = f"hf-dataset-{dataset.name.replace('/', '-')}"
                action_buttons = self._build_action_buttons(
                    content_id=content_id,
                    title=dataset.name,
                    url=dataset.url,
                    content_type="huggingface",
                    date=today,
                )
                html += f"""
                <div class="card">
                    <h3 class="card-title"><a href="{dataset.url}">{dataset.name}</a></h3>
                    <p class="card-description">{self._escape_html(dataset.description)}</p>
                    <div class="card-meta">
                        <span>⬇️ {dataset.downloads:,} downloads</span>
                        <span>❤️ {dataset.likes:,} likes</span>
                    </div>
                    {action_buttons}
                </div>
"""

        # Spaces subsection
        if spaces:
            html += '<h3 style="font-size: 14px; color: #586069; margin: 15px 0 10px;">🚀 Spaces</h3>'
            for space in spaces:
                content_id = f"hf-space-{space.name.replace('/', '-')}"
                action_buttons = self._build_action_buttons(
                    content_id=content_id,
                    title=space.name,
                    url=space.url,
                    content_type="huggingface",
                    date=today,
                )
                html += f"""
                <div class="card">
                    <h3 class="card-title"><a href="{space.url}">{space.name}</a></h3>
                    <p class="card-description">{self._escape_html(space.description)}</p>
                    <div class="card-meta">
                        <span>❤️ {space.likes:,} likes</span>
                    </div>
                    {action_buttons}
                </div>
"""

        if not models and not datasets and not spaces:
            html += '<div class="empty-state">No trending HuggingFace content found today.</div>'

        html += "</div>"
        return html

    def _build_arxiv_section(self, papers: list[dict[str, Any]]) -> str:
        """Build arXiv papers section HTML."""
        html = """
            <div class="section">
                <div class="section-header">
                    <span class="section-icon">📄</span>
                    <h2 class="section-title">arXiv Papers</h2>
                </div>
"""

        today = datetime.now(tz=TIMEZONE).strftime("%Y-%m-%d")

        if not papers:
            html += '<div class="empty-state">No arXiv papers found today.</div>'
        else:
            for paper in papers:
                title = paper.get("title", "Untitled")
                arxiv_id = paper.get("arxiv", "")
                summary = paper.get("summary", paper.get("abstract", ""))
                url = paper.get("url", f"https://arxiv.org/abs/{arxiv_id}")
                paper_date = paper.get("date", today)

                # Truncate summary
                if len(summary) > 300:
                    summary = summary[:297] + "..."

                content_id = f"arxiv-{arxiv_id}"
                action_buttons = self._build_action_buttons(
                    content_id=content_id,
                    title=title,
                    url=url,
                    content_type="arxiv",
                    date=paper_date,
                )

                html += f"""
                <div class="card">
                    <h3 class="card-title"><a href="{url}">{self._escape_html(title)}</a></h3>
                    <p class="card-description">{self._escape_html(summary)}</p>
                    <div class="card-meta">
                        <span>arXiv:{arxiv_id}</span>
                    </div>
                    {action_buttons}
                </div>
"""

        html += "</div>"
        return html

    def _build_blog_section(self, posts: list[BlogPost]) -> str:
        """Build tech blogs section HTML."""
        html = """
            <div class="section">
                <div class="section-header">
                    <span class="section-icon">📝</span>
                    <h2 class="section-title">Tech Blogs</h2>
                </div>
"""

        if not posts:
            html += '<div class="empty-state">No recent blog posts found.</div>'
        else:
            for post in posts:
                date_str = post.published_on.strftime("%b %d")
                author = f"by {post.author}" if post.author else ""
                post_date = post.published_on.strftime("%Y-%m-%d")
                content_id = f"blog-{post.source.lower().replace(' ', '-')}-{post.title[:30].lower().replace(' ', '-')}"
                action_buttons = self._build_action_buttons(
                    content_id=content_id,
                    title=post.title,
                    url=post.url,
                    content_type="blog",
                    date=post_date,
                )

                html += f"""
                <div class="card">
                    <h3 class="card-title"><a href="{post.url}">{self._escape_html(post.title)}</a></h3>
                    <p class="card-description">{self._escape_html(post.summary)}</p>
                    <div class="card-meta">
                        <span class="tag">{post.source}</span>
                        <span>{date_str}</span>
                        {f'<span>{author}</span>' if author else ""}
                    </div>
                    {action_buttons}
                </div>
"""

        html += "</div>"
        return html

    @staticmethod
    def _escape_html(text: str) -> str:
        """Escape HTML special characters."""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )


def send_daily_digest(
    github_repos: list[GitHubRepo],
    hf_models: list[HFModel],
    hf_datasets: list[HFModel],
    hf_spaces: list[HFModel],
    arxiv_papers: list[dict[str, Any]],
    blog_posts: list[BlogPost],
    to_email: str | None = None,
    from_email: str | None = None,
) -> bool:
    """
    Convenience function to send daily digest via SendGrid.

    Args:
        github_repos: List of trending GitHub repos
        hf_models: List of trending HF models
        hf_datasets: List of trending HF datasets
        hf_spaces: List of trending HF spaces
        arxiv_papers: List of arXiv papers
        blog_posts: List of recent blog posts
        to_email: Recipient email (or from TO_EMAIL env var)
        from_email: Sender email (or from FROM_EMAIL env var)

    Returns:
        True if sent successfully, False otherwise
    """
    to_email = to_email or os.environ.get("TO_EMAIL")
    from_email = from_email or os.environ.get("FROM_EMAIL")

    if not to_email or not from_email:
        logger.error("TO_EMAIL and FROM_EMAIL required")
        return False

    sender = SendGridEmailSender()
    return sender.send_digest(
        github_repos=github_repos,
        hf_models=hf_models,
        hf_datasets=hf_datasets,
        hf_spaces=hf_spaces,
        arxiv_papers=arxiv_papers,
        blog_posts=blog_posts,
        to_email=to_email,
        from_email=from_email,
    )
