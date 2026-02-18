"""SMTP email sender for AI Daily Digest (supports QQ Mail, Gmail, etc.)."""

import os
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Any

from arxiv_sanity_bot.logger import get_logger
from arxiv_sanity_bot.config import TIMEZONE
from arxiv_sanity_bot.sources import GitHubRepo, HFModel, BlogPost
from arxiv_sanity_bot.email.email_sender import EmailSender
from arxiv_sanity_bot.schemas import ContentItem
from arxiv_sanity_bot.signature import generate_signature
from urllib.parse import quote

logger = get_logger(__name__)


class SmtpEmailSender(EmailSender):
    """SMTP implementation of email sender (supports QQ Mail, Gmail, etc.)."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        user: str | None = None,
        password: str | None = None,
        use_tls: bool = True,
    ):
        """
        Initialize SMTP email sender.

        Args:
            host: SMTP server host (or from SMTP_HOST env var)
            port: SMTP server port (or from SMTP_PORT env var)
            user: SMTP username/email (or from SMTP_USER env var)
            password: SMTP password/auth code (or from SMTP_PASS env var)
            use_tls: Use TLS encryption (default True)
        """
        self.host: str = host or os.environ.get("SMTP_HOST") or "smtp.qq.com"
        self.port: int = port or int(os.environ.get("SMTP_PORT") or "465")
        self.user: str | None = user or os.environ.get("SMTP_USER")
        self.password: str | None = password or os.environ.get("SMTP_PASS")
        self.use_tls = use_tls

        if not self.user or not self.password:
            raise ValueError(
                "SMTP user and password required. "
                "Set SMTP_USER and SMTP_PASS environment variables."
            )

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
        all_scored_contents: list[dict[str, Any]] | None = None,
        global_top3: list[dict[str, Any]] | None = None,
    ) -> bool:
        """
        Send a daily digest email via SMTP.

        Args:
            github_repos: List of trending GitHub repos (filtered to Top 3)
            hf_models: List of trending HF models (filtered to Top 3)
            hf_datasets: List of trending HF datasets (filtered to Top 3)
            hf_spaces: List of trending HF spaces (filtered to Top 3)
            arxiv_papers: List of arXiv papers with summaries (filtered to Top 3)
            blog_posts: List of recent blog posts (filtered to Top 3)
            to_email: Recipient email address
            from_email: Sender email address
            subject: Email subject (optional)
            daily_insight: Daily insight summary from LLM
            tweets: List of Twitter content items (filtered to Top 3, optional)
            videos: List of YouTube content items (filtered to Top 3, optional)
            all_scored_contents: All contents with AI scores (optional)
            global_top3: Global Top 3 contents across all types (optional)

        Returns:
            True if sent successfully, False otherwise
        """
        if not subject:
            today = datetime.now(tz=TIMEZONE).strftime("%m月%d日")
            weekday = datetime.now(tz=TIMEZONE).strftime("%A")
            weekday_cn = {
                "Monday": "周一",
                "Tuesday": "周二",
                "Wednesday": "周三",
                "Thursday": "周四",
                "Friday": "周五",
                "Saturday": "周六",
                "Sunday": "周日",
            }.get(weekday, weekday)
            subject = f"AI 晨报 · {today} {weekday_cn}"

        html_content = self._build_html_email(
            github_repos=github_repos,
            hf_models=hf_models,
            hf_datasets=hf_datasets,
            hf_spaces=hf_spaces,
            arxiv_papers=arxiv_papers,
            blog_posts=blog_posts,
            daily_insight=daily_insight,
            tweets=tweets or [],
            videos=videos or [],
            all_scored_contents=all_scored_contents,
            global_top3=global_top3,
        )

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = from_email
            msg["To"] = to_email
            msg.attach(MIMEText(html_content, "html", "utf-8"))

            server: smtplib.SMTP_SSL | smtplib.SMTP
            if self.port == 465:
                server = smtplib.SMTP_SSL(self.host, self.port, timeout=30)
            else:
                server = smtplib.SMTP(self.host, self.port, timeout=30)
                server.starttls()

            assert self.user is not None
            assert self.password is not None
            with server:
                server.login(self.user, self.password)
                server.sendmail(from_email, to_email, msg.as_string())

            logger.info(
                "Email sent successfully via SMTP",
                extra={"to": to_email, "from": from_email, "smtp_host": self.host},
            )
            return True

        except Exception as e:
            logger.error(
                f"Failed to send email via SMTP: {e}",
                exc_info=True,
                extra={"to": to_email, "from": from_email, "smtp_host": self.host},
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
        daily_insight: str = "",
        tweets: list[ContentItem] | None = None,
        videos: list[ContentItem] | None = None,
        all_scored_contents: list[dict[str, Any]] | None = None,
        global_top3: list[dict[str, Any]] | None = None,
    ) -> str:
        """Build HTML email content with Notion-inspired design."""
        tweets = tweets or []
        videos = videos or []
        all_scored_contents = all_scored_contents or []
        global_top3 = global_top3 or []
        today = datetime.now(tz=TIMEZONE).strftime("%m月%d日")
        weekday = datetime.now(tz=TIMEZONE).strftime("%A")
        weekday_cn = {
            "Monday": "周一",
            "Tuesday": "周二",
            "Wednesday": "周三",
            "Thursday": "周四",
            "Friday": "周五",
            "Saturday": "周六",
            "Sunday": "周日",
        }.get(weekday, weekday)

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI 晨报</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: #ffffff;
            color: #37352f;
            line-height: 1.6;
            -webkit-font-smoothing: antialiased;
        }}

        .container {{
            max-width: 720px;
            margin: 0 auto;
            padding: 48px 24px;
        }}

        /* Header */
        .header {{
            text-align: center;
            margin-bottom: 40px;
        }}

        .header-icon {{
            font-size: 36px;
            margin-bottom: 16px;
        }}

        .header h1 {{
            font-size: 28px;
            font-weight: 600;
            color: #37352f;
            margin-bottom: 8px;
            letter-spacing: -0.5px;
        }}

        .header .subtitle {{
            font-size: 15px;
            color: #6b6b6b;
            font-weight: 400;
            margin-bottom: 4px;
        }}

        .header .date {{
            font-size: 14px;
            color: #9b9b9b;
        }}

        /* Insight Box */
        .insight-box {{
            background: #f7f7f5;
            border-radius: 6px;
            padding: 24px;
            margin-bottom: 40px;
        }}

        .insight-label {{
            font-size: 12px;
            font-weight: 600;
            color: #2383e2;
            margin-bottom: 12px;
        }}

        .insight-text {{
            font-size: 15px;
            color: #37352f;
            line-height: 1.7;
        }}

        /* Section */
        .section {{
            margin-bottom: 40px;
        }}

        .section-title {{
            font-size: 20px;
            font-weight: 600;
            color: #37352f;
            margin-bottom: 16px;
            padding-bottom: 12px;
            border-bottom: 1px solid #f0f0f0;
        }}

        /* Content Card - Notion Style */
        .content-card {{
            background: #f7f7f5;
            border-radius: 6px;
            padding: 20px 24px;
            margin-bottom: 12px;
            transition: background 0.15s ease;
        }}

        .content-card:hover {{
            background: #f0f0ee;
        }}

        .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
            flex-wrap: wrap;
            gap: 8px;
        }}

        /* Source Tags */
        .source-tag {{
            font-size: 12px;
            font-weight: 500;
            padding: 3px 10px;
            border-radius: 4px;
            display: inline-block;
        }}

        .source-tag.github {{
            color: #2383e2;
            background: rgba(35, 131, 226, 0.1);
        }}

        .source-tag.hf {{
            color: #ff6b00;
            background: rgba(255, 107, 0, 0.1);
        }}

        .source-tag.arxiv {{
            color: #b31b1b;
            background: rgba(179, 27, 27, 0.08);
        }}

        .source-tag.blog {{
            color: #f97316;
            background: rgba(249, 115, 22, 0.1);
        }}

        .source-tag.twitter {{
            color: #1da1f2;
            background: rgba(29, 161, 242, 0.1);
        }}

        .source-tag.youtube {{
            color: #ff0000;
            background: rgba(255, 0, 0, 0.08);
        }}

        /* Featured Card Styles */
        .featured-card {{
            background: #f7f7f5;
            border-radius: 6px;
            padding: 14px 16px;
            margin-bottom: 8px;
        }}

        .featured-header {{
            margin-bottom: 8px;
        }}

        /* Tag Styles */
        .tag-must-read {{
            display: inline-block;
            font-size: 11px;
            font-weight: 500;
            padding: 2px 8px;
            border-radius: 4px;
            background: #fff3e0;
            color: #e65100;
            margin-right: 8px;
        }}

        .tag-deep {{
            display: inline-block;
            font-size: 11px;
            font-weight: 500;
            padding: 2px 8px;
            border-radius: 4px;
            background: #e3f2fd;
            color: #1565c0;
            margin-right: 8px;
        }}

        .tag-quick {{
            display: inline-block;
            font-size: 11px;
            font-weight: 500;
            padding: 2px 8px;
            border-radius: 4px;
            background: #f5f5f5;
            color: #757575;
            margin-right: 8px;
        }}

        /* Featured Title */
        .featured-title {{
            font-size: 14px;
            font-weight: 600;
            margin: 8px 0;
            line-height: 1.4;
        }}

        .featured-title a {{
            color: #37352f;
            text-decoration: none;
        }}

        .featured-title a:hover {{
            color: #2383e2;
            text-decoration: underline;
        }}

        /* Featured Reason */
        .featured-reason {{
            font-size: 13px;
            color: #6b6b6b;
            margin: 0 0 8px 0;
            line-height: 1.5;
        }}

        /* More Section */
        .more-section {{
            margin-top: 32px;
            padding-top: 24px;
            border-top: 1px solid #e8e8e8;
        }}

        .more-title {{
            font-size: 16px;
            font-weight: 600;
            color: #37352f;
            margin-bottom: 12px;
        }}

        .more-item {{
            padding: 10px 0;
            border-bottom: 1px solid #f0f0f0;
        }}

        .more-item a {{
            color: #37352f;
            text-decoration: none;
            font-size: 13px;
        }}

        .more-item a:hover {{
            color: #2383e2;
        }}

        .more-count {{
            color: #9b9b9b;
            font-size: 13px;
        }}

        /* Card Title - Clickable */
        .card-title {{
            font-size: 17px;
            font-weight: 600;
            margin: 0 0 8px 0;
            line-height: 1.4;
        }}

        .card-title a {{
            color: #37352f;
            text-decoration: none;
            transition: color 0.15s ease;
        }}

        .card-title a:hover {{
            color: #2383e2;
            text-decoration: underline;
        }}

        /* Card Content */
        .card-desc,
        .card-summary {{
            font-size: 15px;
            color: #6b6b6b;
            margin: 0 0 8px 0;
            line-height: 1.6;
        }}

        .card-content {{
            font-size: 15px;
            color: #37352f;
            margin: 0 0 8px 0;
            line-height: 1.6;
        }}

        .card-content a {{
            color: #2383e2;
            text-decoration: none;
        }}

        .card-content a:hover {{
            text-decoration: underline;
        }}

        /* Meta Info */
        .card-meta,
        .meta,
        .engagement {{
            font-size: 13px;
            color: #9b9b9b;
        }}

        .author {{
            font-size: 13px;
            color: #6b6b6b;
        }}

        /* Card Footer */
        .card-footer {{
            margin-top: 12px;
            padding-top: 12px;
            border-top: 1px solid rgba(0,0,0,0.05);
        }}

        /* Action Buttons */
        .card-actions {{
            margin-top: 12px;
            padding-top: 12px;
            border-top: 1px solid rgba(0,0,0,0.05);
            display: flex;
            gap: 8px;
        }}
        .btn {{
            display: inline-block;
            padding: 6px 12px;
            border-radius: 4px;
            font-size: 13px;
            font-weight: 500;
            text-decoration: none;
            cursor: pointer;
        }}
        .btn-star {{
            background: #fef3c7;
            color: #92400e;
            border: 1px solid #fcd34d;
        }}
        .btn-note {{
            background: #e0f2fe;
            color: #0369a1;
            border: 1px solid #7dd3fc;
        }}

        /* Empty State */
        .empty-state {{
            color: #9b9b9b;
            font-style: italic;
            padding: 24px;
            text-align: center;
            font-size: 14px;
            background: #f7f7f5;
            border-radius: 6px;
        }}

        /* Footer */
        .footer {{
            text-align: center;
            padding: 32px 24px;
            color: #9b9b9b;
            font-size: 13px;
            border-top: 1px solid #f0f0f0;
            margin-top: 16px;
        }}

        .footer p {{
            margin: 4px 0;
        }}

        /* Mobile */
        @media (max-width: 480px) {{
            .container {{
                padding: 24px 16px;
            }}

            .content-card {{
                padding: 16px 20px;
            }}

            .header h1 {{
                font-size: 24px;
            }}

            .section-title {{
                font-size: 18px;
            }}

            .card-title {{
                font-size: 16px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="header-icon">&#129302;</div>
            <h1>AI 晨报</h1>
            <div class="subtitle">每日 AI 要点，2 分钟速览</div>
            <div class="date">{today} · {weekday_cn}</div>
        </div>
"""

        # Daily insight section
        if daily_insight:
            html += f"""
        <div class="insight-box">
            <div class="insight-label">&#10024; 今日洞察</div>
            <div class="insight-text">{self._escape_html(daily_insight)}</div>
        </div>
"""

        # Featured Section (Global Top 3)
        html += self._build_featured_section(global_top3)

        # More Section (Category Links)
        html += self._build_more_section(all_scored_contents)

        html += """
        <div class="footer">
            <p>AI 晨报 · 为你精选每日 AI 资讯</p>
            <p>由 arxiv-sanity-bot 自动生成</p>
        </div>
    </div>
</body>
</html>
"""

        return html

    def _build_trending_section(
        self,
        repos: list[GitHubRepo],
        models: list[HFModel],
        datasets: list[HFModel],
        spaces: list[HFModel],
    ) -> str:
        """Build trending section with GitHub and HuggingFace content."""
        has_content = repos or models or datasets or spaces
        if not has_content:
            return ""

        html = """
        <div class="section">
            <h2 class="section-title">&#128293; 热门项目</h2>
"""

        today = datetime.now(tz=TIMEZONE).strftime("%Y-%m-%d")

        # GitHub repos
        for repo in repos:
            stars = f"&#11088; {repo.stars_total:,} stars" if repo.stars_total else ""
            content_id = f"github-{repo.name.replace('/', '-')}"
            buttons = self._build_action_buttons(content_id, repo.name, repo.url, "github", today)
            html += f"""
            <div class="content-card">
                <div class="card-header">
                    <span class="source-tag github">GitHub</span>
                    <span class="meta">{stars}</span>
                </div>
                <h3 class="card-title"><a href="{repo.url}">{repo.name}</a></h3>
                <p class="card-desc">{self._escape_html(repo.description or "")}</p>
                {buttons}
            </div>
"""

        # HuggingFace models
        for model in models:
            downloads = f"&#128229; {model.downloads:,}" if model.downloads else ""
            content_id = f"hf-model-{model.name.replace('/', '-')}"
            buttons = self._build_action_buttons(content_id, model.name, model.url, "huggingface", today)
            html += f"""
            <div class="content-card">
                <div class="card-header">
                    <span class="source-tag hf">&#129303; HuggingFace</span>
                    <span class="meta">{downloads}</span>
                </div>
                <h3 class="card-title"><a href="{model.url}">{model.name}</a></h3>
                <p class="card-desc">{self._escape_html(model.description or "")}</p>
                {buttons}
            </div>
"""

        # HuggingFace datasets
        for dataset in datasets:
            downloads = f"&#128229; {dataset.downloads:,}" if dataset.downloads else ""
            content_id = f"hf-dataset-{dataset.name.replace('/', '-')}"
            buttons = self._build_action_buttons(content_id, dataset.name, dataset.url, "huggingface", today)
            html += f"""
            <div class="content-card">
                <div class="card-header">
                    <span class="source-tag hf">&#129303; Dataset</span>
                    <span class="meta">{downloads}</span>
                </div>
                <h3 class="card-title"><a href="{dataset.url}">{dataset.name}</a></h3>
                <p class="card-desc">{self._escape_html(dataset.description or "")}</p>
                {buttons}
            </div>
"""

        # HuggingFace spaces
        for space in spaces:
            likes = f"&#10084; {space.likes:,}" if space.likes else ""
            content_id = f"hf-space-{space.name.replace('/', '-')}"
            buttons = self._build_action_buttons(content_id, space.name, space.url, "huggingface", today)
            html += f"""
            <div class="content-card">
                <div class="card-header">
                    <span class="source-tag hf">&#129303; Space</span>
                    <span class="meta">{likes}</span>
                </div>
                <h3 class="card-title"><a href="{space.url}">{space.name}</a></h3>
                <p class="card-desc">{self._escape_html(space.description or "")}</p>
                {buttons}
            </div>
"""

        html += "</div>"
        return html

    def _build_reading_section(
        self,
        papers: list[dict[str, Any]],
        posts: list[BlogPost],
    ) -> str:
        """Build reading section with arXiv papers and blog posts."""
        has_content = papers or posts
        if not has_content:
            return ""

        today = datetime.now(tz=TIMEZONE).strftime("%Y-%m-%d")

        html = """
        <div class="section">
            <h2 class="section-title">&#128221; 深度阅读</h2>
"""

        # arXiv papers
        for paper in papers:
            title = paper.get("title", "未命名")
            arxiv_id = paper.get("arxiv", "")
            summary = paper.get("summary", "")
            url = paper.get("url", f"https://arxiv.org/abs/{arxiv_id}")
            summary_html = f'<p class="card-summary">{self._escape_html(summary)}</p>' if summary else ""
            content_id = f"arxiv-{arxiv_id}"
            buttons = self._build_action_buttons(content_id, title, url, "arxiv", today)
            html += f"""
            <div class="content-card">
                <div class="card-header">
                    <span class="source-tag arxiv">arXiv</span>
                    <span class="meta">{arxiv_id}</span>
                </div>
                <h3 class="card-title"><a href="{url}">{self._escape_html(title)}</a></h3>
                {summary_html}
                {buttons}
            </div>
"""

        # Blog posts
        for post in posts:
            date_str = post.published_on.strftime("%m/%d")
            content_id = f"blog-{post.source.lower().replace(' ', '-')}-{post.title[:30].lower().replace(' ', '-')}"
            buttons = self._build_action_buttons(content_id, post.title, post.url, "blog", today)
            html += f"""
            <div class="content-card">
                <div class="card-header">
                    <span class="source-tag blog">{post.source}</span>
                    <span class="meta">{date_str}</span>
                </div>
                <h3 class="card-title"><a href="{post.url}">{self._escape_html(post.title)}</a></h3>
                <p class="card-desc">{self._escape_html(post.summary or "")}</p>
                {buttons}
            </div>
"""

        html += "</div>"
        return html

    def _build_social_section(
        self,
        tweets: list[ContentItem],
        videos: list[ContentItem],
    ) -> str:
        """Build social section with Twitter and YouTube content."""
        has_content = tweets or videos
        if not has_content:
            return ""

        html = """
        <div class="section">
            <h2 class="section-title">&#128172; 社交动态</h2>
"""

        # Twitter tweets
        for tweet in tweets:
            time_str = ""
            if tweet.published_on:
                time_str = tweet.published_on.strftime("%m月%d日")

            engagement = ""
            if tweet.engagement_score:
                engagement = f"&#10084; {tweet.engagement_score:,}"

            content = tweet.content or tweet.summary or ""
            # Truncate long content
            if len(content) > 200:
                content = content[:200] + "..."

            html += f"""
            <div class="content-card">
                <div class="card-header">
                    <span class="source-tag twitter">&#128038; Twitter</span>
                    <span class="meta">@{tweet.source} · {time_str}</span>
                </div>
                <p class="card-content">{self._escape_html(content)} <a href="{tweet.url}">查看 →</a></p>
                <div class="card-footer">
                    <span class="engagement">{engagement}</span>
                </div>
            </div>
"""

        # YouTube videos
        for video in videos:
            time_str = ""
            if video.published_on:
                time_str = video.published_on.strftime("%m月%d日")

            views = video.metadata.get("view_count", 0) if video.metadata else 0
            views_str = f"&#128064; {int(views):,} views" if views else ""

            html += f"""
            <div class="content-card">
                <div class="card-header">
                    <span class="source-tag youtube">&#127909; YouTube</span>
                    <span class="meta">{video.source} · {time_str}</span>
                </div>
                <h3 class="card-title"><a href="{video.url}">{self._escape_html(video.title)}</a></h3>
                <p class="card-desc">{self._escape_html(video.summary or "")}</p>
                <div class="card-footer">
                    <span class="engagement">{views_str}</span>
                </div>
            </div>
"""

        html += "</div>"
        return html

    def _build_featured_section(self, global_top3: list[dict[str, Any]]) -> str:
        """Build featured section with global top 3 content."""
        if not global_top3:
            return ""

        html = """
        <div class="section">
            <h2 class="section-title">&#128293; 今日精选</h2>
"""

        today = datetime.now(tz=TIMEZONE).strftime("%Y-%m-%d")

        for item in global_top3:
            tag = item.get("tag", "")
            title = item.get("title", "")
            url = item.get("url", "")
            reason = item.get("reason", "")
            content_type = item.get("type", "")

            # Determine tag class
            tag_class = "tag-quick"
            if "必看" in tag:
                tag_class = "tag-must-read"
            elif "深度" in tag:
                tag_class = "tag-deep"

            # Determine source tag class
            source_class = ""
            source_label = ""
            if content_type == "github":
                source_class = "github"
                source_label = "GitHub"
            elif content_type in ("hf_model", "hf_dataset", "hf_space"):
                source_class = "hf"
                source_label = "HuggingFace"
            elif content_type == "arxiv":
                source_class = "arxiv"
                source_label = "arXiv"
            elif content_type == "blog":
                source_class = "blog"
                source_label = "Blog"
            elif content_type == "twitter":
                source_class = "twitter"
                source_label = "Twitter"
            elif content_type == "youtube":
                source_class = "youtube"
                source_label = "YouTube"

            # Generate action buttons
            content_id = f"{content_type}-{title[:30].replace(' ', '-')}"
            buttons = self._build_action_buttons(content_id, title, url, content_type, today)

            html += f"""
            <div class="featured-card">
                <div class="featured-header">
                    <span class="{tag_class}">{tag}</span>
                    <span class="source-tag {source_class}">{source_label}</span>
                </div>
                <h3 class="featured-title"><a href="{url}">{self._escape_html(title)}</a></h3>
                <p class="featured-reason">{self._escape_html(reason)}</p>
                {buttons}
            </div>
"""

        html += "</div>"
        return html

    def _build_more_section(self, all_scored_contents: list[dict[str, Any]]) -> str:
        """Build more section with category links."""
        if not all_scored_contents:
            return ""

        # Count by category
        github_count = sum(1 for c in all_scored_contents if c.get("type") == "github")
        hf_count = sum(1 for c in all_scored_contents if c.get("type") in ("hf_model", "hf_dataset", "hf_space"))
        arxiv_count = sum(1 for c in all_scored_contents if c.get("type") == "arxiv")
        blog_count = sum(1 for c in all_scored_contents if c.get("type") == "blog")
        social_count = sum(1 for c in all_scored_contents if c.get("type") in ("twitter", "youtube"))

        base_url = os.environ.get("DIGEST_WEB_URL", "").rstrip("/")

        html = """
        <div class="more-section">
            <h2 class="more-title">&#128194; 更多内容</h2>
"""

        if github_count > 0 and base_url:
            html += f"""
            <div class="more-item">
                <a href="{base_url}/github">GitHub 热门仓库 <span class="more-count">{github_count} 个项目 &rarr;</span></a>
            </div>
"""
        elif github_count > 0:
            html += f"""
            <div class="more-item">
                <span>GitHub 热门仓库 <span class="more-count">{github_count} 个项目</span></span>
            </div>
"""

        if hf_count > 0 and base_url:
            html += f"""
            <div class="more-item">
                <a href="{base_url}/huggingface">HuggingFace 趋势 <span class="more-count">{hf_count} 个模型 &rarr;</span></a>
            </div>
"""
        elif hf_count > 0:
            html += f"""
            <div class="more-item">
                <span>HuggingFace 趋势 <span class="more-count">{hf_count} 个模型</span></span>
            </div>
"""

        if arxiv_count > 0 and base_url:
            html += f"""
            <div class="more-item">
                <a href="{base_url}/arxiv">arXiv 论文精选 <span class="more-count">{arxiv_count} 篇论文 &rarr;</span></a>
            </div>
"""
        elif arxiv_count > 0:
            html += f"""
            <div class="more-item">
                <span>arXiv 论文精选 <span class="more-count">{arxiv_count} 篇论文</span></span>
            </div>
"""

        if blog_count > 0 and base_url:
            html += f"""
            <div class="more-item">
                <a href="{base_url}/blog">技术博客 <span class="more-count">{blog_count} 篇文章 &rarr;</span></a>
            </div>
"""
        elif blog_count > 0:
            html += f"""
            <div class="more-item">
                <span>技术博客 <span class="more-count">{blog_count} 篇文章</span></span>
            </div>
"""

        if social_count > 0 and base_url:
            html += f"""
            <div class="more-item">
                <a href="{base_url}/social">社交动态 <span class="more-count">{social_count} 条 &rarr;</span></a>
            </div>
"""
        elif social_count > 0:
            html += f"""
            <div class="more-item">
                <span>社交动态 <span class="more-count">{social_count} 条</span></span>
            </div>
"""

        html += "</div>"
        return html

    def _build_action_buttons(self, content_id: str, title: str, url: str, content_type: str, date: str) -> str:
        base_url = os.environ.get("DIGEST_WEB_URL", "").rstrip("/")
        if not base_url:
            return ""
        try:
            signature = generate_signature(content_id, date)
            star_url = f"{base_url}/star?id={quote(content_id)}&title={quote(title)}&url={quote(url)}&type={content_type}&date={date}&t={signature}"
            note_url = f"{base_url}/note?id={quote(content_id)}&title={quote(title)}&url={quote(url)}&type={content_type}&date={date}&t={signature}"
            return f'<div class="card-actions"><a href="{star_url}" class="btn btn-star" target="_blank">Star</a><a href="{note_url}" class="btn btn-note" target="_blank">Note</a></div>'
        except Exception as e:
            logger.warning(f"Failed to generate action buttons: {e}")
            return ""

    def _build_featured_section(self, global_top3: list[dict[str, Any]]) -> str:
        """Build featured section with global top 3 content."""
        if not global_top3:
            return ""

        html = """
        <div class="section">
            <h2 class="section-title">&#128293; 今日精选</h2>
"""

        today = datetime.now(tz=TIMEZONE).strftime("%Y-%m-%d")

        for item in global_top3:
            tag = item.get("tag", "")
            title = item.get("title", "")
            url = item.get("url", "")
            reason = item.get("reason", "")
            content_type = item.get("type", "")

            # Determine tag class
            tag_class = "tag-quick"
            if "必看" in tag:
                tag_class = "tag-must-read"
            elif "深度" in tag:
                tag_class = "tag-deep"

            # Determine source tag class
            source_class = ""
            source_label = ""
            if content_type == "github":
                source_class = "github"
                source_label = "GitHub"
            elif content_type in ("hf_model", "hf_dataset", "hf_space"):
                source_class = "hf"
                source_label = "HuggingFace"
            elif content_type == "arxiv":
                source_class = "arxiv"
                source_label = "arXiv"
            elif content_type == "blog":
                source_class = "blog"
                source_label = "Blog"
            elif content_type == "twitter":
                source_class = "twitter"
                source_label = "Twitter"
            elif content_type == "youtube":
                source_class = "youtube"
                source_label = "YouTube"

            # Generate action buttons
            content_id = f"{content_type}-{title[:30].replace(' ', '-')}"
            buttons = self._build_action_buttons(content_id, title, url, content_type, today)

            html += f"""
            <div class="featured-card">
                <div class="featured-header">
                    <span class="{tag_class}">{tag}</span>
                    <span class="source-tag {source_class}">{source_label}</span>
                </div>
                <h3 class="featured-title"><a href="{url}">{self._escape_html(title)}</a></h3>
                <p class="featured-reason">{self._escape_html(reason)}</p>
                {buttons}
            </div>
"""

        html += "</div>"
        return html

    def _build_more_section(self, all_scored_contents: list[dict[str, Any]]) -> str:
        """Build more section with category links."""
        if not all_scored_contents:
            return ""

        # Count by category
        github_count = sum(1 for c in all_scored_contents if c.get("type") == "github")
        hf_count = sum(1 for c in all_scored_contents if c.get("type") in ("hf_model", "hf_dataset", "hf_space"))
        arxiv_count = sum(1 for c in all_scored_contents if c.get("type") == "arxiv")
        blog_count = sum(1 for c in all_scored_contents if c.get("type") == "blog")
        social_count = sum(1 for c in all_scored_contents if c.get("type") in ("twitter", "youtube"))

        base_url = os.environ.get("DIGEST_WEB_URL", "").rstrip("/")

        html = """
        <div class="more-section">
            <h2 class="more-title">&#128194; 更多内容</h2>
"""

        if github_count > 0 and base_url:
            html += f"""
            <div class="more-item">
                <a href="{base_url}/github">GitHub 热门仓库 <span class="more-count">{github_count} 个项目 &rarr;</span></a>
            </div>
"""
        elif github_count > 0:
            html += f"""
            <div class="more-item">
                <span>GitHub 热门仓库 <span class="more-count">{github_count} 个项目</span></span>
            </div>
"""

        if hf_count > 0 and base_url:
            html += f"""
            <div class="more-item">
                <a href="{base_url}/huggingface">HuggingFace 趋势 <span class="more-count">{hf_count} 个模型 &rarr;</span></a>
            </div>
"""
        elif hf_count > 0:
            html += f"""
            <div class="more-item">
                <span>HuggingFace 趋势 <span class="more-count">{hf_count} 个模型</span></span>
            </div>
"""

        if arxiv_count > 0 and base_url:
            html += f"""
            <div class="more-item">
                <a href="{base_url}/arxiv">arXiv 论文精选 <span class="more-count">{arxiv_count} 篇论文 &rarr;</span></a>
            </div>
"""
        elif arxiv_count > 0:
            html += f"""
            <div class="more-item">
                <span>arXiv 论文精选 <span class="more-count">{arxiv_count} 篇论文</span></span>
            </div>
"""

        if blog_count > 0 and base_url:
            html += f"""
            <div class="more-item">
                <a href="{base_url}/blog">技术博客 <span class="more-count">{blog_count} 篇文章 &rarr;</span></a>
            </div>
"""
        elif blog_count > 0:
            html += f"""
            <div class="more-item">
                <span>技术博客 <span class="more-count">{blog_count} 篇文章</span></span>
            </div>
"""

        if social_count > 0 and base_url:
            html += f"""
            <div class="more-item">
                <a href="{base_url}/social">社交动态 <span class="more-count">{social_count} 条 &rarr;</span></a>
            </div>
"""
        elif social_count > 0:
            html += f"""
            <div class="more-item">
                <span>社交动态 <span class="more-count">{social_count} 条</span></span>
            </div>
"""

        html += "</div>"
        return html

    @staticmethod
    def _escape_html(text: str) -> str:
        if not text:
            return ""
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
