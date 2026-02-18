"""Lightweight content processing using DeepSeek API."""

import json
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

    def _fallback_scoring(
        self, contents: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Fallback scoring when AI scoring fails.

        Uses rule-based scoring based on engagement metrics.
        Base score: 5, with bonuses for stars and content type.

        Args:
            contents: List of content dicts with type, title, stars, etc.

        Returns:
            Contents with score, tag, and reason added.
        """
        results = []
        for item in contents:
            score = 5  # Base score
            content_type = item.get("type", "")
            stars = item.get("stars", 0) or 0

            # GitHub stars bonus
            if content_type == "github":
                if stars > 500:
                    score += 3
                elif stars > 100:
                    score += 1

            # arXiv papers get a small bonus for academic depth
            if content_type == "arxiv":
                score += 1

            # Cap at 10
            score = min(score, 10)

            # Assign tag based on score
            if score >= 8:
                tag = "🔥 必看"
            elif score >= 5:
                tag = "📖 深度"
            else:
                tag = "⚡ 速览"

            # Use first 40 chars of description as reason
            description = item.get("description", "")
            reason = description[:40] + "..." if len(description) > 40 else description
            if not reason:
                reason = "值得关注的内容"

            # Copy and add scoring fields
            item_copy = item.copy()
            item_copy["score"] = score
            item_copy["tag"] = tag
            item_copy["reason"] = reason
            results.append(item_copy)

        logger.warning(f"Fallback scoring applied to {len(contents)} items (AI scoring failed)")
        return results

    def score_and_tag_contents(
        self, contents: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Score and tag content items using AI or fallback rules.

        Uses DeepSeek AI to score each item 1-10 based on:
        - 30% popularity (stars, citations)
        - 30% novelty (new concepts/projects)
        - 40% practical value (usable tools > theory)

        Tags: 🔥必看 (≥8), 📖深度 (5-7), ⚡速览 (<5)

        Args:
            contents: List of content dicts with type, title, stars, description

        Returns:
            Contents with score, tag, and reason fields added
        """
        if not contents:
            return []

        # Build indexed content list for AI
        content_lines = []
        for i, item in enumerate(contents, 1):
            content_type = item.get("type", "unknown")
            title = item.get("title", "")
            stars = item.get("stars", "")
            description = item.get("description", "")[:200]  # Truncate for tokens
            content_lines.append(
                f"{i}. [{content_type}] {title} (stars: {stars})\n   {description}"
            )

        content_text = "\n\n".join(content_lines)

        history = [
            {
                "role": "system",
                "content": (
                    "你是 AI 资讯筛选助手。请对以下内容逐条打分和标签。\n\n"
                    "打分规则（1-10）：\n"
                    "- 热度（star数、引用量）占 30%\n"
                    "- 新颖度（首次出现的新项目/概念）占 30%\n"
                    "- 实用价值（可直接使用的工具 > 纯理论研究）占 40%\n\n"
                    "标签规则：\n"
                    "- 🔥 必看：≥ 8 分，重大突破或超高热度\n"
                    "- 📖 深度：5-7 分，值得深入了解\n"
                    "- ⚡ 速览：< 5 分，了解即可\n\n"
                    "输出格式（严格 JSON）：\n"
                    '[{"index": 1, "score": 8, "tag": "🔥 必看", "reason": "一句话推荐理由"}, ...]'
                ),
            },
            {
                "role": "user",
                "content": f"请对以下内容逐条打分（共 {len(contents)} 条）：\n\n{content_text}\n\n请返回 JSON 数组：",
            },
        ]

        try:
            response = self._get_client()._call_openai(history)

            # Parse JSON response
            try:
                # Extract JSON from response (handle markdown code blocks)
                json_str = response.strip()
                if "```json" in json_str:
                    parts = json_str.split("```json")
                    if len(parts) > 1:
                        inner = parts[1]
                        json_str = inner.split("```")[0] if "```" in inner else inner
                elif "```" in json_str:
                    parts = json_str.split("```")
                    if len(parts) > 1:
                        json_str = parts[1]

                scores_data = json.loads(json_str.strip())

                # Validate and apply scores
                if isinstance(scores_data, list) and len(scores_data) == len(contents):
                    results = []
                    for i, (item, score_info) in enumerate(zip(contents, scores_data), 1):
                        # Validate index matches expected position
                        if score_info.get("index") != i:
                            logger.debug(f"Index mismatch at position {i}: expected {i}, got {score_info.get('index')}")
                        item_copy = item.copy()
                        item_copy["score"] = score_info.get("score", 5)
                        item_copy["tag"] = score_info.get("tag", "📖 深度")
                        item_copy["reason"] = score_info.get(
                            "reason", "值得关注的内容"
                        )
                        results.append(item_copy)
                    return results
                else:
                    logger.warning(
                        f"AI scoring returned invalid format or length mismatch, using fallback"
                    )
                    return self._fallback_scoring(contents)

            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to parse AI scoring response: {e}")
                return self._fallback_scoring(contents)

        except Exception as e:
            logger.warning(f"AI scoring API call failed: {e}")
            return self._fallback_scoring(contents)

    def generate_daily_insight(self, top3_context: str) -> str:
        """
        Generate a brief daily insight based on top 3 content items.

        Focuses on the most important items only, keeping output under 80 chars.

        Args:
            top3_context: Formatted string of top 3 content items by importance

        Returns:
            Brief insight string (max ~80 chars)
        """
        if not top3_context:
            return "今日 AI 领域稳步发展。"

        history = [
            {
                "role": "system",
                "content": (
                    "你是 AI 晨报编辑。请生成今日洞察，要求：\n"
                    "1. 第一句：今天最重要的一件事（加粗处理）\n"
                    "2. 第二句：为什么重要 / 对开发者意味着什么\n"
                    "3. 第三句（可选）：另一个值得关注的动向\n\n"
                    "规则：\n"
                    "- 总共不超过 80 字\n"
                    '- 不要用"今日AI领域"这样的套话开头\n'
                    "- 直接说事，像发给朋友的消息一样\n"
                    "- 用中文"
                ),
            },
            {
                "role": "user",
                "content": f"以下是今日 Top 3 内容（已按重要性排序）：\n{top3_context}\n\n请生成洞察：",
            },
        ]

        try:
            insight = self._get_client()._call_openai(history)
            return insight.strip() if insight else "今日 AI 领域有新动态值得关注。"
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
                "content": (
                    "你是学术论文助手。用 1-2 句话概括论文核心贡献。\n"
                    "规则：\n"
                    "- 控制在 60 字以内\n"
                    '- 第一句说"做了什么"，第二句说"效果如何"\n'
                    '- 不要用"本文""该研究"等学术套话'
                ),
            },
            {
                "role": "user",
                "content": f"标题: {title}\n\n摘要: {truncated}\n\n一句话概括:",
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
                    "你是 AI 晨报编辑。基于以下 Top 3 内容生成今日洞察：\n\n"
                    "规则：\n"
                    "- 总共不超过 80 字\n"
                    "- 第一句直接说今天最重要的事\n"
                    "- 不要罗列每个源的内容，而是提炼一个核心主题\n"
                    "- 像发给朋友的消息，不要用套话"
                ),
            },
            {
                "role": "user",
                "content": f"今日 Top 3 内容：\n{context}\n\n请提炼洞察：",
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
