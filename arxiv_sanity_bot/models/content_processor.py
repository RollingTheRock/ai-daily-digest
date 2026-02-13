"""Lightweight content processing using DeepSeek API."""

import os
from typing import Any

from arxiv_sanity_bot.logger import get_logger
from arxiv_sanity_bot.models.openai import OpenAI
from arxiv_sanity_bot.schemas import ContentItem
from arxiv_sanity_bot.config import CONTENT_KEYWORDS

logger = get_logger(__name__)


class ContentProcessor:
    """Process content with LLM for summaries and insights (lightweight, token-efficient)."""

    def __init__(self):
        self._client: OpenAI | None = None
        self._provider = os.environ.get("LLM_PROVIDER", "openai").lower()

    def _get_client(self) -> OpenAI:
        """Lazy initialization of OpenAI client."""
        if self._client is None:
            self._client = OpenAI()
        return self._client

    def generate_daily_insight(
        self,
        github_repos: list[Any],
        hf_models: list[Any],
        blog_posts: list[Any],
    ) -> str:
        """
        Generate a brief daily insight based on trending content.
        Lightweight - uses minimal tokens.
        """
        # Build a concise context
        context_parts = []

        if github_repos:
            repo_names = [r.name for r in github_repos[:3]]
            context_parts.append(f"GitHub热门: {', '.join(repo_names)}")

        if hf_models:
            model_names = [m.name.split("/")[-1] for m in hf_models[:2]]
            context_parts.append(f"HF模型: {', '.join(model_names)}")

        if blog_posts:
            blog_titles = [b.title[:30] for b in blog_posts[:2]]
            context_parts.append(f"博客: {'; '.join(blog_titles)}")

        if not context_parts:
            return "今日 AI 领域稳步发展，各平台均有新动态。"

        context = "\n".join(context_parts)

        history = [
            {
                "role": "system",
                "content": "你是一位资深AI资讯编辑。请用2-3句话总结今日AI领域的主要趋势和亮点，语气自然、专业，像晨报导语。可以适当展开，控制在150字以内。",
            },
            {
                "role": "user",
                "content": f"基于以下信息生成今日洞察（丰富但不冗长）：\n{context}",
            },
        ]

        try:
            insight = self._get_client()._call_openai(history)
            return insight.strip() if insight else "今日 AI 领域呈现多元发展态势。"
        except Exception as e:
            logger.warning(f"Failed to generate daily insight: {e}")
            return "今日 AI 领域持续活跃，值得关注。"

    def summarize_paper(self, title: str, abstract: str) -> str:
        """
        Generate a concise paper summary in Chinese.
        Token-efficient: keeps abstracts truncated and summaries brief.
        """
        # Truncate abstract to save tokens
        truncated = abstract[:800] if len(abstract) > 800 else abstract

        history = [
            {
                "role": "system",
                "content": "你是学术论文助手。用2-3句话概括论文核心贡献，面向技术读者，突出创新点。控制在100字以内，语言自然。",
            },
            {
                "role": "user",
                "content": f"标题: {title}\n\n摘要: {truncated}\n\n请生成简洁中文摘要:",
            },
        ]

        try:
            summary = self._get_client()._call_openai(history)
            return summary.strip() if summary else ""
        except Exception as e:
            logger.warning(f"Failed to summarize paper: {e}")
            return ""

    def batch_summarize_papers(
        self, papers: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Summarize multiple papers with rate limiting to control costs.
        Only summarize top papers to save tokens.
        """
        max_papers = 3  # Limit to save tokens
        results = []

        for i, paper in enumerate(papers[:max_papers]):
            logger.info(f"Summarizing paper {i+1}/{min(len(papers), max_papers)}")

            summary = self.summarize_paper(
                paper.get("title", ""), paper.get("abstract", "")
            )

            paper_copy = paper.copy()
            paper_copy["summary"] = summary
            results.append(paper_copy)

        # Add remaining papers without summary
        for paper in papers[max_papers:]:
            paper_copy = paper.copy()
            paper_copy["summary"] = ""
            results.append(paper_copy)

        return results

    def filter_by_keywords(
        self,
        items: list[ContentItem],
        keywords: dict[str, list[str]] | None = None,
        require_match: bool = True,
    ) -> list[ContentItem]:
        """
        Filter content items by keyword relevance.

        Args:
            items: List of ContentItem to filter
            keywords: Keyword categories (defaults to CONTENT_KEYWORDS config)
            require_match: If True, only return items matching keywords

        Returns:
            Filtered list of items
        """
        if keywords is None:
            keywords = CONTENT_KEYWORDS

        all_keywords = []
        for category_keywords in keywords.values():
            all_keywords.extend(category_keywords)

        filtered: list[ContentItem] = []
        for item in items:
            # Combine title and content for matching
            text = f"{item.title} {item.content} {item.summary}".lower()

            # Check if any keyword matches
            matches = any(kw.lower() in text for kw in all_keywords)

            if matches or not require_match:
                filtered.append(item)

        logger.info(f"Keyword filter: {len(filtered)}/{len(items)} items matched")
        return filtered

    def filter_by_engagement(
        self,
        items: list[ContentItem],
        min_score: int | None = None,
    ) -> list[ContentItem]:
        """
        Filter content items by engagement score.

        Args:
            items: List of ContentItem to filter
            min_score: Minimum engagement score (varies by source type)

        Returns:
            Filtered list of items
        """
        if min_score is None:
            # Default thresholds per source type
            min_score_by_type = {
                "twitter": 100,  # min likes + retweets*2
                "youtube": 10000,  # min views
                "blog": 0,
                "arxiv": 0,
            }
        else:
            min_score_by_type = {t: min_score for t in ["twitter", "youtube", "blog", "arxiv"]}

        filtered: list[ContentItem] = []
        for item in items:
            threshold = min_score_by_type.get(item.source_type, 0)
            if item.engagement_score >= threshold:
                filtered.append(item)

        logger.info(f"Engagement filter: {len(filtered)}/{len(items)} items passed")
        return filtered

    def generate_mixed_content_digest(
        self,
        papers: list[ContentItem],
        blogs: list[ContentItem],
        tweets: list[ContentItem],
        videos: list[ContentItem],
    ) -> str:
        """
        Generate a comprehensive daily digest from mixed content sources.

        Args:
            papers: ArXiv papers
            blogs: Blog posts
            tweets: Twitter content
            videos: YouTube videos

        Returns:
            Formatted digest string
        """
        sections = []

        # Papers section
        if papers:
            paper_titles = [p.title[:50] for p in papers[:3]]
            sections.append(f"📄 论文: {', '.join(paper_titles)}")

        # Blogs section
        if blogs:
            blog_titles = [b.title[:40] for b in blogs[:2]]
            sections.append(f"📝 博客: {', '.join(blog_titles)}")

        # Twitter section
        if tweets:
            top_tweet = tweets[0]
            sections.append(f"🐦 Twitter: @{top_tweet.source} 分享热门内容")

        # YouTube section
        if videos:
            top_video = videos[0]
            sections.append(f"📺 视频: {top_video.title[:40]}...")

        if not sections:
            return "今日 AI 领域稳步发展。"

        context = "\n".join(sections)

        history = [
            {
                "role": "system",
                "content": (
                    "你是一位资深AI资讯编辑。基于以下多源内容生成今日洞察：\n"
                    "- 概括主要趋势和热点\n"
                    "- 提及重要论文、博客、社交媒体讨论\n"
                    "- 语气自然专业，控制在200字以内"
                ),
            },
            {
                "role": "user",
                "content": f"今日内容汇总：\n{context}\n\n生成洞察：",
            },
        ]

        try:
            digest = self._get_client()._call_openai(history)
            return digest.strip() if digest else "今日 AI 领域持续活跃。"
        except Exception as e:
            logger.warning(f"Failed to generate mixed digest: {e}")
            return "今日 AI 领域多元发展，值得关注。"

    def llm_relevance_check(
        self,
        item: ContentItem,
        topic: str = "AI/ML research and developments",
    ) -> bool:
        """
        Use LLM to check if content is relevant to specified topic.
        More accurate than keyword matching but costs tokens.

        Args:
            item: ContentItem to check
            topic: Topic to check relevance against

        Returns:
            True if relevant, False otherwise
        """
        # Skip LLM check for certain sources (too expensive)
        if item.source_type in ["twitter", "youtube"] and len(item.content) > 500:
            # Use keyword fallback for long social content
            return True

        content = item.content or item.summary or item.title
        if len(content) > 1000:
            content = content[:1000] + "..."

        history = [
            {
                "role": "system",
                "content": (
                    f"判断以下内容是否与 '{topic}' 相关。\n"
                    "只回答 'YES' 或 'NO'，不要有其他内容。"
                ),
            },
            {
                "role": "user",
                "content": f"标题: {item.title}\n\n内容: {content}\n\n相关吗？",
            },
        ]

        try:
            response = self._get_client()._call_openai(history)
            is_relevant: bool = bool(response and "YES" in response.upper())
            logger.debug(f"LLM relevance check for '{item.title[:30]}...': {is_relevant}")
            return is_relevant
        except Exception as e:
            logger.warning(f"LLM relevance check failed: {e}")
            # Default to keeping content if check fails
            return True
