from datetime import datetime
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints


class ArxivPaper(BaseModel):
    arxiv: Annotated[str, StringConstraints(min_length=1)]
    title: Annotated[str, StringConstraints(min_length=1)]
    abstract: Annotated[str, StringConstraints(min_length=1)]
    published_on: datetime
    categories: list[str] = Field(default_factory=list)


class PaperSource(str, Enum):
    ALPHAXIV = "alphaxiv"
    HUGGINGFACE = "hf"
    BOTH = "both"


class BasePaper(BaseModel):
    arxiv_id: Annotated[str, StringConstraints(min_length=1)]
    title: Annotated[str, StringConstraints(min_length=1)]
    abstract: Annotated[str, StringConstraints(min_length=1)]
    published_on: Annotated[str, StringConstraints(min_length=1)]


class RawPaper(BasePaper):
    votes: int | None = None


class RankedPaper(BasePaper):
    score: int = Field(ge=1, le=2)
    alphaxiv_rank: int | None = None
    hf_rank: int | None = None
    source: PaperSource

    @property
    def average_rank(self) -> float:
        ranks = [r for r in [self.alphaxiv_rank, self.hf_rank] if r is not None]
        return sum(ranks) / len(ranks) if ranks else float("inf")

    def sort_key(self) -> tuple[int, float]:
        return (-self.score, self.average_rank)


class ContentItem(BaseModel):
    """统一内容项模型，用于整合所有内容源。

    支持 arXiv 论文、博客文章、Twitter 推文、YouTube 视频等多种内容类型。
    """

    id: str = Field(..., description="内容唯一标识")
    title: str = Field(..., description="内容标题")
    source: str = Field(..., description="来源名称（如 'OpenAI', '@karpathy'）")
    source_type: Literal["arxiv", "github", "huggingface", "blog", "twitter", "youtube"] = Field(
        ..., description="内容类型"
    )
    url: str = Field(..., description="内容链接")
    published_on: datetime = Field(..., description="发布时间")
    author: str = Field(default="", description="作者名称")
    summary: str = Field(default="", description="内容摘要/描述")
    content: str = Field(default="", description="原始内容（推文正文、视频描述等）")
    engagement_score: int = Field(default=0, description="互动分数（点赞/观看/转发数）")
    metadata: dict = Field(default_factory=dict, description="源特定额外数据")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}

    @property
    def display_title(self) -> str:
        """返回适合展示的标题。"""
        if self.source_type == "twitter":
            # 推文内容可能很长，截断显示
            content = self.content or self.summary
            if len(content) > 100:
                return content[:97] + "..."
            return content
        return self.title

    @property
    def engagement_display(self) -> str:
        """返回格式化的互动数显示。"""
        if self.engagement_score == 0:
            return ""
        if self.engagement_score >= 1000000:
            return f"{self.engagement_score / 1000000:.1f}M"
        if self.engagement_score >= 1000:
            return f"{self.engagement_score / 1000:.1f}K"
        return str(self.engagement_score)
