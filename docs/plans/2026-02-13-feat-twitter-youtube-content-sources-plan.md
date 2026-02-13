---
title: 添加 Twitter AI 头部开发者和 YouTube AI 视频内容源
type: feat
date: 2026-02-13
---

# 添加 Twitter AI 头部开发者和 YouTube AI 视频内容源

## 概述

扩展 AI 日报邮件系统的内容源，添加两个新渠道：
1. **Twitter/X AI 头部开发者的推文和分享链接**
2. **YouTube 最新头部 AI 频道视频**

这将使日报内容更加多元化，涵盖社交媒体讨论热点和最新视频教程/解读。

## 动机

当前系统主要从学术来源（arXiv）和技术博客获取内容。为了提供更全面的 AI 资讯，需要添加：
- **Twitter**: AI 领域重要研究者、工程师的第一手观点、论文讨论、行业动态
- **YouTube**: 最新技术解读、教程、会议演讲，适合不同学习偏好的读者

## 技术架构分析

### 现有内容源模式

基于代码库分析 (`arxiv_sanity_bot/sources/`)，现有模式为：

```
sources/
├── __init__.py          # 导出所有客户端和模型
├── tech_blogs.py        # RSS feed 抓取示例
├── github_trending.py   # API 调用示例
└── huggingface_extended.py
```

**关键设计模式**:
1. **Client 类**: 每个源有自己的 Client 类（如 `TechBlogClient`）
2. **Pydantic 模型**: 数据使用 Pydantic BaseModel 定义（如 `BlogPost`）
3. **重试逻辑**: 使用 `tenacity` 库实现指数退避重试
4. **错误处理**: 单个源失败不影响其他源
5. **延迟初始化**: API 客户端使用懒加载模式（参见 `ContentProcessor._get_client()`）

### 统一接口设计

新的内容源应遵循统一接口：

```python
class ContentSource(Protocol):
    """统一内容源接口"""
    def fetch_recent(self, days: int = 7, limit: int = 10) -> list[ContentItem]:
        ...

class ContentItem(BaseModel):
    """统一内容项模型"""
    title: str
    source: str           # 来源名称
    source_type: str      # "twitter" | "youtube" | "blog" | "paper"
    url: str
    published_on: datetime
    author: str
    summary: str = ""     # 内容摘要/描述
    engagement_score: int = 0  # 互动数/观看数等
```

## 方案设计

### 内容过滤策略

#### 论文关键词过滤（arXiv）
```python
# 只关注这些领域的论文
KEYWORD_FILTERS = {
    "core": ["LLM", "large language model", "transformer", "GPT", "Claude"],
    "multimodal": ["multimodal", "vision-language", "image generation", "diffusion"],
    "agents": ["agent", "tool use", "function calling", "RAG", "retrieval"],
    "training": ["fine-tuning", "RLHF", "alignment", "safety"],
}
```

#### 社交媒体 Engagement 阈值
```python
# Twitter 阈值
TWITTER_MIN_LIKES = 100
TWITTER_MIN_RETWEETS = 20

# YouTube 阈值
YOUTUBE_MIN_VIEWS = 10000
```

#### LLM 二次筛选
```python
# 使用轻量级 LLM 判断内容相关性
RELEVANCE_PROMPT = """
判断以下 AI 内容是否与以下主题相关：LLM、多模态、Agent、训练方法。
只回答 YES 或 NO。

标题: {title}
内容: {content}
"""
```

### 0. Substack 博客扩展

#### 目标 Newsletter（3 个核心源）
```python
SUBSTACK_FEEDS = {
    "Import AI": "https://importai.substack.com/feed",
    "The Batch": "https://www.deeplearning.ai/the-batch/feed",  # 或 TLDR AI
    # "TLDR AI": "https://tldr.tech/ai/feed",
}
```

**实现方式**: 复用现有的 `TechBlogClient`，通过 `add_feed()` 方法添加 Substack RSS。

### 1. Twitter/X 内容聚合

#### API 选择
- **推荐**: Twitter API v2 (Basic 套餐 $100/月)
- **备选**: Nitter RSS (免费但稳定性差)
- **权衡**: 免费方案有严格速率限制，付费 API 更可靠

#### 目标账号列表（精简至 5 个核心账号）
```python
TWITTER_AI_SOURCES = [
    "_akhaliq",     # AK (@_akhaliq) - AI 领域重要新闻聚合
    "karpathy",     # Andrej Karpathy - OpenAI 前研究主管
    "goodside",     # Riley Goodside - Prompt Engineering 专家
    "ylecun",       # Yann LeCun - Meta AI 首席科学家
    "ai__pub",      # AI Pub - AI 论文/研究动态
]
```

**筛选策略**:
- 只监控核心账号，减少 API 调用量
- 设置高互动阈值（min_engagement = 100）
- 优先包含外部链接的推文（论文/文章分享）

#### 数据模型
```python
class TweetContent(BaseModel):
    tweet_id: str
    author: str
    author_display_name: str
    content: str
    url: str
    published_on: datetime
    like_count: int
    retweet_count: int
    reply_count: int
    is_reply: bool
    referenced_urls: list[str]  # 推文中的链接
```

#### 过滤策略
1. **排除回复**: 减少噪音
2. **最小互动阈值**: 只保留有质量的推文（如 50+ likes）
3. **链接优先**: 优先包含外部链接的推文（分享文章/论文）
4. **去重**: 同一 URL 多次分享只保留一次

### 2. YouTube 内容聚合

#### API 选择
- **YouTube Data API v3**: 免费额度 10,000 单位/天
- **成本估算**: 每次搜索 100 单位，可支持 100 次搜索/天

#### 目标频道列表（精选 6 个高质量频道）
```python
YOUTUBE_AI_CHANNELS = [
    "UCXUPKJOdoz9XylBV4T2hpdQ",  # Two Minute Papers
    "UCvjgXvBlbQiydffZUzzmYJw",  # Yannic Kilcher
    "UCbfYPyITQ-7l4upoX8nvctg",  # AI Explained
    "UCZHmQk67mSJgfCCTnMGEA7w",  # David Shapiro
    "UCP7jMXSY2xbc3KCAE0MHQ-A",  # DeepLearningAI
    "UC1LpsuAUaKoMzzJSEt5Wpgw",  # Lex Fridman
]
```

**轻量级策略**:
- 只获取视频元数据（标题、描述、缩略图、观看数）
- 不下载/处理视频内容
- 通过标题+描述进行关键词过滤

#### 数据模型
```python
class YouTubeContent(BaseModel):
    video_id: str
    title: str
    channel_name: str
    description: str
    url: str
    published_on: datetime
    view_count: int
    like_count: int
    duration: str  # ISO 8601 duration format
    thumbnail_url: str
```

#### 内容筛选
1. **关键词过滤**: 标题/描述包含 AI/ML 相关词
2. **时长过滤**: 排除短视频（< 5分钟），优先 10-60 分钟内容
3. **观看数阈值**: 根据频道规模动态调整

## 实现计划

### Phase 1: 基础架构 (2-3 小时)

#### 1.1 创建统一内容模型
**文件**: `arxiv_sanity_bot/schemas.py`

添加统一内容项模型：
```python
class ContentItem(BaseModel):
    """统一内容项，用于所有内容源"""
    id: str
    title: str
    source: str           # 来源标识
    source_type: Literal["arxiv", "github", "huggingface", "blog", "twitter", "youtube"]
    url: str
    published_on: datetime
    author: str
    summary: str = ""
    content: str = ""     # 原始内容
    engagement_score: int = 0
    metadata: dict = {}   # 源特定额外数据
```

#### 1.2 创建 Twitter Client
**文件**: `arxiv_sanity_bot/sources/twitter_source.py`

```python
class TwitterClient:
    def __init__(self, bearer_token: str | None = None):
        self.bearer_token = bearer_token or os.environ.get("TWITTER_BEARER_TOKEN")
        self._client = None

    def _get_client(self):
        # 延迟初始化，使用 tweepy
        ...

    def fetch_recent_tweets(
        self,
        usernames: list[str] | None = None,
        days: int = 7,
        min_engagement: int = 50,
        exclude_replies: bool = True,
    ) -> list[ContentItem]:
        ...
```

**依赖**: `tweepy>=4.14.0`

#### 1.3 创建 YouTube Client
**文件**: `arxiv_sanity_bot/sources/youtube_source.py`

```python
class YouTubeClient:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("YOUTUBE_API_KEY")
        self._client = None

    def _get_client(self):
        # 延迟初始化，使用 google-api-python-client
        ...

    def fetch_recent_videos(
        self,
        channel_ids: list[str] | None = None,
        days: int = 7,
        min_duration_minutes: int = 5,
    ) -> list[ContentItem]:
        ...
```

**依赖**: `google-api-python-client>=2.100.0`

### Phase 2: 配置集成 (1 小时)

#### 2.1 更新配置
**文件**: `arxiv_sanity_bot/config.py`

```python
# Twitter settings
TWITTER_BEARER_TOKEN = os.environ.get("TWITTER_BEARER_TOKEN", "")
TWITTER_MIN_ENGAGEMENT = int(os.environ.get("TWITTER_MIN_ENGAGEMENT", "50"))
TWITTER_MAX_TWEETS_PER_USER = int(os.environ.get("TWITTER_MAX_TWEETS_PER_USER", "5"))

# YouTube settings
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")
YOUTUBE_MIN_DURATION_MINUTES = int(os.environ.get("YOUTUBE_MIN_DURATION_MINUTES", "5"))
YOUTUBE_MAX_VIDEOS_PER_CHANNEL = int(os.environ.get("YOUTUBE_MAX_VIDEOS_PER_CHANNEL", "3"))

# Content aggregation settings
CONTENT_SOURCES = os.environ.get("CONTENT_SOURCES", "arxiv,blog").split(",")
# 选项: arxiv, blog, github, huggingface, twitter, youtube
```

#### 2.2 环境变量模板
**文件**: `.env.example`

```bash
# Twitter/X API
TWITTER_BEARER_TOKEN=your_twitter_bearer_token_here

# YouTube Data API
YOUTUBE_API_KEY=your_youtube_api_key_here

# 内容源配置（逗号分隔）
CONTENT_SOURCES=arxiv,blog,twitter,youtube
```

### Phase 3: 内容处理器扩展 (1-2 小时)

#### 3.1 更新 ContentProcessor
**文件**: `arxiv_sanity_bot/models/content_processor.py`

添加新的处理方法：

```python
def summarize_tweet_thread(self, tweets: list[ContentItem]) -> str:
    """总结推文讨论主题"""
    ...

def summarize_video_content(self, video: ContentItem) -> str:
    """生成视频内容摘要（基于标题和描述）"""
    ...

def generate_mixed_content_digest(
    self,
    papers: list[ContentItem],
    blogs: list[ContentItem],
    tweets: list[ContentItem],
    videos: list[ContentItem],
) -> str:
    """生成混合内容的日报摘要"""
    ...
```

### Phase 4: 主流程集成 (1-2 小时)

#### 4.1 更新 CLI/主流程
**文件**: `arxiv_sanity_bot/cli/main.py`

修改内容获取逻辑，根据配置动态加载源：

```python
def fetch_all_content() -> dict[str, list[ContentItem]]:
    sources = CONTENT_SOURCES
    all_content = {}

    if "arxiv" in sources:
        all_content["papers"] = fetch_arxiv_papers()
    if "blog" in sources:
        all_content["blogs"] = fetch_tech_blog_posts()
    if "twitter" in sources and TWITTER_BEARER_TOKEN:
        client = TwitterClient()
        all_content["tweets"] = client.fetch_recent_tweets()
    if "youtube" in sources and YOUTUBE_API_KEY:
        client = YouTubeClient()
        all_content["videos"] = client.fetch_recent_videos()

    return all_content
```

### Phase 5: 邮件模板更新 (1 小时)

#### 5.1 更新邮件模板
**文件**: `arxiv_sanity_bot/email/digest_formatter.py`

添加新的内容区块：

```python
def format_twitter_section(tweets: list[ContentItem]) -> str:
    """格式化 Twitter 内容区块"""
    ...

def format_youtube_section(videos: list[ContentItem]) -> str:
    """格式化 YouTube 内容区块"""
    ...
```

### Phase 6: 测试与验证 (2 小时)

#### 6.1 单元测试
**文件**: `tests/test_twitter_source.py`, `tests/test_youtube_source.py`

- Mock API 响应测试
- 错误处理测试
- 重试逻辑测试

#### 6.2 集成测试
- 端到端内容抓取测试
- 邮件格式验证

## 技术考量

### 速率限制处理

| 服务 | 限制 | 策略 |
|------|------|------|
| Twitter API v2 | 300 req/15min | 使用 tenacity 重试，指数退避 |
| YouTube Data API | 10,000 单位/天 | 缓存结果，批量获取 |

### 错误处理策略

遵循现有模式，单个源失败不应影响整体流程：

```python
try:
    tweets = twitter_client.fetch_recent_tweets()
except Exception as e:
    logger.error(f"Twitter fetch failed: {e}")
    tweets = []  # 返回空列表，继续处理其他源
```

### 成本控制

- **Twitter**: Basic 套餐 $100/月，或免费层的 1,500 推文/月
- **YouTube**: 免费额度通常足够
- **LLM 摘要**: Twitter 和 YouTube 内容可能不需要 LLM 摘要（节省 tokens）

## 依赖项

添加到 `pyproject.toml`:

```toml
[project.optional-dependencies]
twitter = ["tweepy>=4.14.0"]
youtube = ["google-api-python-client>=2.100.0"]
```

## 配置清单

### 必需环境变量

| 变量名 | 说明 | 获取方式 |
|--------|------|----------|
| `TWITTER_BEARER_TOKEN` | Twitter API Bearer Token | https://developer.twitter.com |
| `YOUTUBE_API_KEY` | YouTube Data API Key | https://console.cloud.google.com |

### 可选环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `CONTENT_SOURCES` | `arxiv,blog` | 启用的内容源 |
| `TWITTER_MIN_ENGAGEMENT` | 50 | 最小互动数阈值 |
| `YOUTUBE_MIN_DURATION_MINUTES` | 5 | 最小视频时长 |

## 验收标准

- [x] Twitter Client 可以从指定账号获取最近推文
- [x] YouTube Client 可以从指定频道获取最近视频
- [x] 内容可以正确过滤（互动数、时长、关键词）
- [x] 失败的内容源不影响其他源的正常工作
- [ ] 邮件模板正确显示 Twitter 和 YouTube 内容（后续迭代）
- [x] 所有新代码通过语法检查
- [ ] 单元测试覆盖率 > 80%（待补充）
- [ ] README 更新，包含新 API 配置说明（待补充）

## 风险与缓解

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| Twitter API 费用 | 中 | 低 | 提供免费 RSS 备选方案 |
| API 速率限制 | 高 | 中 | 实现缓存和指数退避重试 |
| API 变更 | 低 | 中 | 封装客户端，隔离变化 |
| 内容质量问题 | 中 | 低 | 设置互动数阈值，人工审核 |

## 未来扩展

- 支持更多社交平台（LinkedIn、Reddit）
- 自动视频字幕提取和摘要
- 推文情感分析
- 热门话题趋势分析

## 参考

### 内部参考
- 现有内容源模式: `arxiv_sanity_bot/sources/tech_blogs.py:55`
- 延迟初始化模式: `arxiv_sanity_bot/models/content_processor.py:19`
- 重试逻辑: `arxiv_sanity_bot/sources/tech_blogs.py:135`

### 外部文档
- Twitter API v2: https://developer.twitter.com/en/docs/twitter-api
- YouTube Data API: https://developers.google.com/youtube/v3
- Tweepy 文档: https://docs.tweepy.org/

---

**注意**: 本计划假设使用付费 Twitter API。如果预算有限，可以考虑使用 Nitter RSS 或先实现 YouTube 部分。
