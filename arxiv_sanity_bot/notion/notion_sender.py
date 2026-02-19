"""Notion output module for AI Daily Digest.

This module provides functionality to send daily digest content to a Notion database,
parallel to the existing email output channel.
"""

import re
from typing import Any

from notion_client import Client
from notion_client.errors import APIResponseError

from arxiv_sanity_bot.logger import get_logger

logger = get_logger(__name__)

# Notion API limits
MAX_RICH_TEXT_LENGTH = 2000
MAX_BLOCKS_PER_REQUEST = 100
MAX_TOGGLE_CHILDREN = 50  # Limit children in toggle blocks to avoid too many blocks

# Tag extraction rules
# Note: \b (word boundary) only works for ASCII characters, not Chinese
TAG_RULES = [
    (r"\b(LLM|language model|GPT|Claude|LLaMA|Qwen|Mixtral)\b", "LLM"),
    (
        r"(safe|安全|alignment|guard|护栏|对齐)",
        "安全",
    ),  # Removed \b for Chinese support
    (r"\b(agent|Agent|智能体|autonomous)\b", "Agent"),
    (
        r"(multimodal|多模态|vision|image|diffusion|Stable Diffusion)",
        "多模态",
    ),  # Fixed: removed space and \b
    (r"\b(tool|工具|framework|library|SDK|API)\b", "工具"),
]


class NotionSender:
    """Sender for writing daily digest to Notion database.

    This class handles the creation of Notion pages with daily digest content,
    including automatic tag extraction and importance calculation.
    """

    def __init__(self, token: str, database_id: str):
        """Initialize Notion client.

        Args:
            token: Notion integration token (starts with 'secret_')
            database_id: Notion database ID to write pages to
        """
        self.notion = Client(auth=token)
        self.database_id = database_id
        logger.info(f"NotionSender initialized with database: {database_id}")

    def send_daily_digest(self, digest_data: dict[str, Any]) -> str:
        """Send daily digest to Notion database.

        Creates a new page in the configured Notion database with all digest
        content organized in structured blocks.

        Args:
            digest_data: Dictionary containing:
                - date: str, date in "YYYY-MM-DD" format
                - daily_insight: str, AI-generated TL;DR summary
                - top3: list[dict], global Top 3 contents across all types
                - github_top3: list[dict], Top 3 GitHub repositories
                - hf_top3: list[dict], Top 3 HuggingFace items
                - arxiv_top3: list[dict], Top 3 arXiv papers
                - blog_top3: list[dict], Top 3 blog posts
                - all_scored_contents: list[dict], all contents with AI scores

        Returns:
            URL of the created Notion page

        Raises:
            APIResponseError: If Notion API returns an error
        """
        logger.info("Starting Notion daily digest creation")

        # Extract data
        date = digest_data["date"]
        daily_insight = digest_data.get("daily_insight", "")
        top3 = digest_data.get("top3", [])
        github_top3 = digest_data.get("github_top3", [])
        hf_top3 = digest_data.get("hf_top3", [])
        arxiv_top3 = digest_data.get("arxiv_top3", [])
        blog_top3 = digest_data.get("blog_top3", [])
        all_scored_contents = digest_data.get("all_scored_contents", [])

        # Calculate derived fields
        tags = self._extract_tags(top3)
        importance = self._calculate_importance(top3)

        # Format property content
        hot_projects = self._format_property_content(github_top3 + hf_top3)
        papers = self._format_property_content(arxiv_top3)
        blogs = self._format_property_content(blog_top3)

        # Create page properties
        properties = {
            "标题": {"title": [{"text": {"content": f"{date} AI 晨报"}}]},
            "日期": {"date": {"start": date}},
            "今日洞察": {
                "rich_text": [
                    {
                        "text": {
                            "content": self._truncate_text(
                                daily_insight, MAX_RICH_TEXT_LENGTH
                            )
                        }
                    }
                ]
            },
            "热门项目": {"rich_text": [{"text": {"content": hot_projects}}]},
            "论文精选": {"rich_text": [{"text": {"content": papers}}]},
            "博客速递": {"rich_text": [{"text": {"content": blogs}}]},
            "我的笔记": {"rich_text": []},
            "标签": {"multi_select": [{"name": tag} for tag in tags]},
            "重要程度": {"select": {"name": importance}},
        }

        # Create the page
        try:
            page = self._create_page(properties)
            page_id = page["id"]
            page_url = page["url"]
            logger.info(f"Notion page created: {page_url}")
        except APIResponseError as e:
            logger.error(f"Failed to create Notion page: {e}")
            raise

        # Build and append blocks
        blocks = self._build_blocks(digest_data)
        try:
            self._append_blocks(page_id, blocks)
            logger.info(f"Appended {len(blocks)} blocks to Notion page")
        except APIResponseError as e:
            logger.error(f"Failed to append blocks: {e}")
            # Page was created, return URL anyway

        return page_url

    def _extract_tags(self, contents: list[dict]) -> list[str]:
        """Extract tags from content titles and descriptions.

        Args:
            contents: List of content items with 'title' and optionally 'description'

        Returns:
            List of extracted tag names (unique, sorted)
        """
        tags = set()
        text_to_scan = ""

        for item in contents:
            title = item.get("title", "")
            description = item.get("description", "")
            content_type = item.get("type", "")
            text_to_scan += f" {title} {description}"

            # Type-based tags
            if content_type == "arxiv":
                tags.add("论文")
            if content_type == "github":
                # Check for open source indicators
                text_lower = f"{title} {description}".lower()
                if any(
                    word in text_lower
                    for word in ["open source", "github", "license", "mit", "apache"]
                ):
                    tags.add("开源")

        # Apply regex rules
        for pattern, tag_name in TAG_RULES:
            if re.search(pattern, text_to_scan, re.IGNORECASE):
                tags.add(tag_name)

        # Default tag
        tags.add("AI")

        return sorted(tags)

    def _calculate_importance(self, top3: list[dict]) -> str:
        """Calculate importance level based on top 3 average score.

        Args:
            top3: List of top 3 content items with 'score' field

        Returns:
            Importance level string: "🔥 重要", "⭐ 一般", or "💤 低优"
        """
        if not top3:
            return "💤 低优"

        scores = [item.get("score", 0) for item in top3]
        avg_score = sum(scores) / len(scores)

        if avg_score >= 8:
            return "🔥 重要"
        elif avg_score >= 5:
            return "⭐ 一般"
        else:
            return "💤 低优"

    def _format_property_content(self, items: list[dict]) -> str:
        """Format content items for rich_text property.

        Args:
            items: List of content items

        Returns:
            Formatted text string, truncated to MAX_RICH_TEXT_LENGTH
        """
        if not items:
            return ""

        lines = []
        for item in items:
            tag = item.get("tag", "")
            title = item.get("title", "")
            reason = item.get("reason", "")
            stars = item.get("stars", 0)
            # Support both "url" and "link" fields for compatibility
            url = item.get("url", "") or item.get("link", "")

            if stars:
                line = f"{tag} {title} | ⭐ {stars} | {reason}"
            else:
                line = f"{tag} {title} | {reason}"

            # Append URL if available
            if url:
                line += f"\n🔗 {url}"

            lines.append(line)

        content = "\n\n".join(lines)
        return self._truncate_text(content, MAX_RICH_TEXT_LENGTH)

    def _truncate_text(self, text: str, max_length: int) -> str:
        """Truncate text to max length with ellipsis.

        Args:
            text: Input text
            max_length: Maximum allowed length

        Returns:
            Truncated text with "..." if needed
        """
        if len(text) <= max_length:
            return text
        return text[: max_length - 3] + "..."

    def _build_blocks(self, digest_data: dict[str, Any]) -> list[dict]:
        """Build Notion blocks for page content.

        Args:
            digest_data: Dictionary with all digest data

        Returns:
            List of Notion block objects
        """
        blocks = []

        # Section: Daily Insight
        blocks.append(
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": "✨ 今日洞察"}}]
                },
            }
        )

        daily_insight = digest_data.get("daily_insight", "")
        if daily_insight:
            # Truncate to avoid Notion API limits
            truncated_insight = self._truncate_text(daily_insight, MAX_RICH_TEXT_LENGTH)
            blocks.append(
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            {"type": "text", "text": {"content": truncated_insight}}
                        ]
                    },
                }
            )

        blocks.append({"object": "block", "type": "divider", "divider": {}})

        # Section: Top 3
        blocks.append(
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [
                        {"type": "text", "text": {"content": "🔥 今日精选 Top 3"}}
                    ]
                },
            }
        )

        top3 = digest_data.get("top3", [])
        for item in top3:
            tag = item.get("tag", "")
            content_type = item.get("type", "")
            title = item.get("title", "")
            reason = item.get("reason", "")
            # Support both "url" and "link" fields for compatibility
            url = item.get("url", "") or item.get("link", "")

            # Heading
            blocks.append(
                {
                    "object": "block",
                    "type": "heading_3",
                    "heading_3": {
                        "rich_text": [
                            {
                                "type": "text",
                                "text": {"content": f"{tag} [{content_type}] {title}"},
                            }
                        ]
                    },
                }
            )

            # Reason (truncated to avoid API limits)
            if reason:
                truncated_reason = self._truncate_text(reason, MAX_RICH_TEXT_LENGTH)
                blocks.append(
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [
                                {"type": "text", "text": {"content": truncated_reason}}
                            ]
                        },
                    }
                )

            # URL with link - "🔗 查看原文" format
            if url:
                blocks.append(
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [
                                {
                                    "type": "text",
                                    "text": {
                                        "content": "🔗 查看原文",
                                        "link": {"url": url},
                                    },
                                }
                            ]
                        },
                    }
                )

        blocks.append({"object": "block", "type": "divider", "divider": {}})

        # Section: Full Content
        blocks.append(
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": "📂 完整内容"}}]
                },
            }
        )

        # Group by type
        all_contents = digest_data.get("all_scored_contents", [])
        type_groups = self._group_by_type(all_contents)

        for type_name, items in type_groups.items():
            if not items:
                continue

            # Toggle heading with count
            toggle_blocks = []
            for item in items:
                score = item.get("score", 0)
                title = item.get("title", "")
                # Support both "url" and "link" fields for compatibility
                item_url = item.get("url", "") or item.get("link", "")

                # First paragraph: tag, title and score
                item_text = f"{item.get('tag', '')} {title} | ⭐ {score} 分"
                toggle_blocks.append(
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [
                                {"type": "text", "text": {"content": item_text}}
                            ]
                        },
                    }
                )

                # Second paragraph: URL link if available
                if item_url:
                    toggle_blocks.append(
                        {
                            "object": "block",
                            "type": "paragraph",
                            "paragraph": {
                                "rich_text": [
                                    {"type": "text", "text": {"content": "🔗 "}},
                                    {
                                        "type": "text",
                                        "text": {
                                            "content": item_url,
                                            "link": {"url": item_url},
                                        },
                                    },
                                ]
                            },
                        }
                    )

            # Add toggle block
            blocks.append(
                {
                    "object": "block",
                    "type": "toggle",
                    "toggle": {
                        "rich_text": [
                            {
                                "type": "text",
                                "text": {"content": f"{type_name} ({len(items)})"},
                            }
                        ],
                        "children": toggle_blocks[:MAX_TOGGLE_CHILDREN],
                    },
                }
            )

        return blocks

    def _group_by_type(self, contents: list[dict]) -> dict[str, list[dict]]:
        """Group contents by their type.

        Args:
            contents: List of content items

        Returns:
            Dictionary mapping type names to lists of items
        """
        groups: dict[str, list[dict]] = {
            "GitHub": [],
            "HuggingFace": [],
            "arXiv": [],
            "Blog": [],
            "Twitter": [],
            "YouTube": [],
        }

        for item in contents:
            content_type = item.get("type", "")

            if content_type == "github":
                groups["GitHub"].append(item)
            elif content_type in ("hf_model", "hf_dataset", "hf_space"):
                groups["HuggingFace"].append(item)
            elif content_type == "arxiv":
                groups["arXiv"].append(item)
            elif content_type == "blog":
                groups["Blog"].append(item)
            elif content_type == "twitter":
                groups["Twitter"].append(item)
            elif content_type == "youtube":
                groups["YouTube"].append(item)

        # Remove empty groups
        return {k: v for k, v in groups.items() if v}

    def _create_page(self, properties: dict[str, Any]) -> dict[str, Any]:
        """Create a new page in the Notion database.

        Args:
            properties: Page properties dictionary

        Returns:
            Created page object from Notion API
        """
        return self.notion.pages.create(
            parent={"database_id": self.database_id}, properties=properties
        )

    def _append_blocks(self, page_id: str, blocks: list[dict]) -> None:
        """Append blocks to a Notion page.

        Handles batching to respect the 100 blocks per request limit.

        Args:
            page_id: Notion page ID to append blocks to
            blocks: List of block objects to append
        """
        for i in range(0, len(blocks), MAX_BLOCKS_PER_REQUEST):
            batch = blocks[i : i + MAX_BLOCKS_PER_REQUEST]
            self.notion.blocks.children.append(block_id=page_id, children=batch)
            logger.debug(f"Appended batch of {len(batch)} blocks")
