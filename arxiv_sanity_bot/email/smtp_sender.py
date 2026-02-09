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
    ) -> bool:
        """
        Send a daily digest email via SMTP.

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
    ) -> str:
        """Build HTML email content with Notion-inspired design."""
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
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: #f7f6f3;
            color: #37352f;
            line-height: 1.6;
            -webkit-font-smoothing: antialiased;
        }}

        .container {{
            max-width: 640px;
            margin: 0 auto;
            padding: 40px 20px;
        }}

        .header {{
            text-align: center;
            margin-bottom: 32px;
            padding: 0 20px;
        }}

        .header-icon {{
            font-size: 32px;
            margin-bottom: 12px;
            opacity: 0.8;
        }}

        .header h1 {{
            font-size: 26px;
            font-weight: 600;
            color: #37352f;
            margin-bottom: 6px;
            letter-spacing: -0.5px;
        }}

        .header .date {{
            font-size: 14px;
            color: #6b6b6b;
            font-weight: 400;
        }}

        .insight-box {{
            background: #ffffff;
            border-radius: 8px;
            padding: 20px 24px;
            margin-bottom: 24px;
            box-shadow: 0 1px 2px rgba(0,0,0,0.04), 0 2px 4px rgba(0,0,0,0.02);
            border: 1px solid #e9e9e7;
        }}

        .insight-label {{
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: #9ca3af;
            margin-bottom: 8px;
            font-weight: 500;
        }}

        .insight-text {{
            font-size: 15px;
            color: #4b5563;
            line-height: 1.7;
        }}

        .section {{
            margin-bottom: 28px;
        }}

        .section-header {{
            display: flex;
            align-items: center;
            margin-bottom: 16px;
            padding: 0 4px;
        }}

        .section-icon {{
            width: 22px;
            height: 22px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: #f4f4f4;
            border-radius: 5px;
            margin-right: 10px;
            font-size: 12px;
        }}

        .section-title {{
            font-size: 14px;
            font-weight: 600;
            color: #6b6b6b;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .card {{
            background: #ffffff;
            border-radius: 8px;
            padding: 16px 20px;
            margin-bottom: 8px;
            box-shadow: 0 1px 2px rgba(0,0,0,0.04);
            border: 1px solid #e9e9e7;
            transition: all 0.15s ease;
        }}

        .card:hover {{
            box-shadow: 0 2px 4px rgba(0,0,0,0.06);
            transform: translateY(-1px);
        }}

        .card-title {{
            font-size: 15px;
            font-weight: 500;
            margin-bottom: 6px;
            color: #37352f;
        }}

        .card-title a {{
            color: #37352f;
            text-decoration: none;
            border-bottom: 1px solid #e9e9e7;
            transition: border-color 0.15s;
        }}

        .card-title a:hover {{
            border-color: #37352f;
        }}

        .card-description {{
            font-size: 13px;
            color: #6b6b6b;
            line-height: 1.6;
            margin-bottom: 10px;
        }}

        .card-summary {{
            font-size: 13px;
            color: #4b5563;
            line-height: 1.6;
            padding: 10px 12px;
            background: #f9f9f8;
            border-radius: 6px;
            margin-top: 10px;
            border-left: 3px solid #d1d5db;
        }}

        .card-meta {{
            font-size: 12px;
            color: #9ca3af;
            display: flex;
            align-items: center;
            gap: 12px;
            flex-wrap: wrap;
        }}

        .tag {{
            display: inline-flex;
            align-items: center;
            padding: 2px 8px;
            background: #f4f4f4;
            border-radius: 4px;
            font-size: 11px;
            color: #6b6b6b;
            font-weight: 500;
        }}

        .divider {{
            height: 1px;
            background: #e9e9e7;
            margin: 24px 0;
        }}

        .footer {{
            text-align: center;
            padding: 24px;
            color: #9ca3af;
            font-size: 12px;
        }}

        .footer p {{
            margin: 4px 0;
        }}

        .empty-state {{
            color: #9ca3af;
            font-style: italic;
            padding: 16px 20px;
            text-align: center;
            font-size: 13px;
            background: #ffffff;
            border-radius: 8px;
            border: 1px solid #e9e9e7;
        }}

        @media (max-width: 480px) {{
            .container {{
                padding: 20px 16px;
            }}

            .card {{
                padding: 14px 16px;
            }}

            .header h1 {{
                font-size: 22px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="header-icon">&#127774;</div>
            <h1>AI 晨报</h1>
            <div class="date">{today} · {weekday_cn}</div>
        </div>
"""

        # Daily insight section
        if daily_insight:
            html += f"""
        <div class="insight-box">
            <div class="insight-label">今日洞察</div>
            <div class="insight-text">{self._escape_html(daily_insight)}</div>
        </div>
"""

        # GitHub Section
        html += self._build_github_section(github_repos)

        # HuggingFace Section
        html += self._build_huggingface_section(hf_models, hf_datasets, hf_spaces)

        # arXiv Section
        html += self._build_arxiv_section(arxiv_papers)

        # Blog Section
        html += self._build_blog_section(blog_posts)

        html += """
        <div class="divider"></div>

        <div class="footer">
            <p>AI 晨报 · 为你精选每日 AI 资讯</p>
            <p>由 arxiv-sanity-bot 自动发送</p>
        </div>
    </div>
</body>
</html>
"""

        return html

    def _build_github_section(self, repos: list[GitHubRepo]) -> str:
        """Build GitHub trending section."""
        html = """
        <div class="section">
            <div class="section-header">
                <div class="section-icon">&#9733;</div>
                <div class="section-title">GitHub 热门</div>
            </div>
"""

        if not repos:
            html += '<div class="empty-state">今日暂无热门仓库</div>'
        else:
            for repo in repos:
                stars = f"{repo.stars_total:,} stars" if repo.stars_total else ""
                lang = (
                    f'<span class="tag">{repo.language}</span>' if repo.language else ""
                )

                html += f"""
            <div class="card">
                <div class="card-title"><a href="{repo.url}">{repo.name}</a></div>
                <div class="card-description">{self._escape_html(repo.description)}</div>
                <div class="card-meta">
                    {f'<span>{stars}</span>' if stars else ""}
                    {lang}
                </div>
            </div>
"""

        html += "</div>"
        return html

    def _build_huggingface_section(
        self, models: list[HFModel], datasets: list[HFModel], spaces: list[HFModel]
    ) -> str:
        """Build HuggingFace trending section."""
        has_content = models or datasets or spaces
        if not has_content:
            return ""

        html = """
        <div class="section">
            <div class="section-header">
                <div class="section-icon">&#10084;</div>
                <div class="section-title">HuggingFace 趋势</div>
            </div>
"""

        # Models
        if models:
            html += '<div style="margin-bottom: 12px;"><span class="tag" style="margin-bottom: 8px; display: inline-block;">模型</span></div>'
            for model in models:
                tags = "".join(f'<span class="tag">{t}</span>' for t in model.tags[:2])
                html += f"""
            <div class="card">
                <div class="card-title"><a href="{model.url}">{model.name}</a></div>
                <div class="card-description">{self._escape_html(model.description)}</div>
                <div class="card-meta">
                    <span>下载: {model.downloads:,}</span>
                    <span>喜欢: {model.likes:,}</span>
                    {tags}
                </div>
            </div>
"""

        # Datasets
        if datasets:
            html += '<div style="margin: 16px 0 12px;"><span class="tag" style="margin-bottom: 8px; display: inline-block;">数据集</span></div>'
            for dataset in datasets:
                html += f"""
            <div class="card">
                <div class="card-title"><a href="{dataset.url}">{dataset.name}</a></div>
                <div class="card-description">{self._escape_html(dataset.description)}</div>
                <div class="card-meta">
                    <span>下载: {dataset.downloads:,}</span>
                    <span>喜欢: {dataset.likes:,}</span>
                </div>
            </div>
"""

        # Spaces
        if spaces:
            html += '<div style="margin: 16px 0 12px;"><span class="tag" style="margin-bottom: 8px; display: inline-block;">Spaces</span></div>'
            for space in spaces:
                html += f"""
            <div class="card">
                <div class="card-title"><a href="{space.url}">{space.name}</a></div>
                <div class="card-description">{self._escape_html(space.description)}</div>
                <div class="card-meta">
                    <span>喜欢: {space.likes:,}</span>
                </div>
            </div>
"""

        html += "</div>"
        return html

    def _build_arxiv_section(self, papers: list[dict[str, Any]]) -> str:
        """Build arXiv papers section."""
        if not papers:
            return ""

        html = """
        <div class="section">
            <div class="section-header">
                <div class="section-icon">&#8473;</div>
                <div class="section-title">论文精选</div>
            </div>
"""

        for paper in papers:
            title = paper.get("title", "未命名")
            arxiv_id = paper.get("arxiv", "")
            summary = paper.get("summary", "")
            url = paper.get("url", f"https://arxiv.org/abs/{arxiv_id}")

            summary_html = (
                f'<div class="card-summary">{self._escape_html(summary)}</div>'
                if summary
                else ""
            )

            html += f"""
            <div class="card">
                <div class="card-title"><a href="{url}">{self._escape_html(title)}</a></div>
                {summary_html}
                <div class="card-meta">
                    <span>arXiv:{arxiv_id}</span>
                </div>
            </div>
"""

        html += "</div>"
        return html

    def _build_blog_section(self, posts: list[BlogPost]) -> str:
        """Build tech blogs section."""
        if not posts:
            return ""

        html = """
        <div class="section">
            <div class="section-header">
                <div class="section-icon">&#9998;</div>
                <div class="section-title">技术博客</div>
            </div>
"""

        for post in posts:
            date_str = post.published_on.strftime("%m月%d日")

            html += f"""
            <div class="card">
                <div class="card-title"><a href="{post.url}">{self._escape_html(post.title)}</a></div>
                <div class="card-description">{self._escape_html(post.summary)}</div>
                <div class="card-meta">
                    <span class="tag">{post.source}</span>
                    <span>{date_str}</span>
                </div>
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
