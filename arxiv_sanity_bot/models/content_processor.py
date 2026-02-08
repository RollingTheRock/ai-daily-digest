"""Lightweight content processing using DeepSeek API."""

import os
from typing import Any

from arxiv_sanity_bot.logger import get_logger
from arxiv_sanity_bot.models.openai import OpenAI

logger = get_logger(__name__)


class ContentProcessor:
    """Process content with LLM for summaries and insights (lightweight, token-efficient)."""

    def __init__(self):
        self._client = OpenAI()
        self._provider = os.environ.get("LLM_PROVIDER", "openai").lower()

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
            model_names = [m.name.split('/')[-1] for m in hf_models[:2]]
            context_parts.append(f"HF模型: {', '.join(model_names)}")

        if blog_posts:
            blog_titles = [b.title[:30] for b in blog_posts[:2]]
            context_parts.append(f"博客: {'; '.join(blog_titles)}")

        if not context_parts:
            return "今日 AI 领域稳步发展，各平台均有新动态。"

        context = " | ".join(context_parts)

        history = [
            {
                "role": "system",
                "content": "你是一位AI资讯编辑。用1-2句话总结今日AI领域的主要趋势，语气自然、专业，像晨报导语。控制在80字以内。"
            },
            {
                "role": "user",
                "content": f"基于以下信息生成今日洞察（简洁自然）：\n{context}"
            }
        ]

        try:
            insight = self._client._call_openai(history)
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
                "content": "你是学术论文助手。用2-3句话概括论文核心贡献，面向技术读者，突出创新点。控制在100字以内，语言自然。"
            },
            {
                "role": "user",
                "content": f"标题: {title}\n\n摘要: {truncated}\n\n请生成简洁中文摘要:"
            }
        ]

        try:
            summary = self._client._call_openai(history)
            return summary.strip() if summary else ""
        except Exception as e:
            logger.warning(f"Failed to summarize paper: {e}")
            return ""

    def batch_summarize_papers(self, papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Summarize multiple papers with rate limiting to control costs.
        Only summarize top papers to save tokens.
        """
        max_papers = 3  # Limit to save tokens
        results = []

        for i, paper in enumerate(papers[:max_papers]):
            logger.info(f"Summarizing paper {i+1}/{min(len(papers), max_papers)}")

            summary = self.summarize_paper(
                paper.get("title", ""),
                paper.get("abstract", "")
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
