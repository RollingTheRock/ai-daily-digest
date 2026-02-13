---
title: Twitter and YouTube Content Aggregation Implementation
category: integration-patterns
component: sources
date: 2026-02-13
source_type: feature-implementation
---

# Twitter and YouTube Content Aggregation Implementation

## Overview

Implementation of two new content sources for the AI Daily Digest system:
1. **Twitter/X API** - Aggregating tweets from core AI researchers and practitioners
2. **YouTube Data API** - Aggregating videos from curated AI channels

## Architecture Decisions

### 1. Unified Content Model

Created `ContentItem` Pydantic model to standardize all content sources:

```python
class ContentItem(BaseModel):
    id: str
    title: str
    source: str              # Source name (@username or channel name)
    source_type: Literal["arxiv", "blog", "twitter", "youtube"]
    url: str
    published_on: datetime
    author: str
    summary: str = ""
    content: str = ""
    engagement_score: int = 0    # Likes, views, etc.
    metadata: dict = {}
```

**Rationale**: Enables consistent handling across the pipeline - filtering, sorting, formatting.

### 2. Lazy Initialization Pattern

Both clients use lazy initialization to avoid import-time API client creation:

```python
class TwitterClient:
    def __init__(self, bearer_token: str | None = None):
        self._client = None

    def _get_client(self):
        if self._client is None:
            import tweepy
            self._client = tweepy.Client(bearer_token=self.bearer_token)
        return self._client
```

**Benefits**:
- Avoids module import errors when API keys not configured
- Allows graceful degradation if dependencies not installed
- Follows existing pattern in `ContentProcessor`

### 3. Optional Dependencies Design

Added optional dependencies in `pyproject.toml`:

```toml
[project.optional-dependencies]
twitter = ["tweepy>=4.14.0"]
youtube = ["google-api-python-client>=2.100.0"]
all = ["tweepy>=4.14.0", "google-api-python-client>=2.100.0"]
```

Usage:
```bash
pip install arxiv-sanity-bot[twitter,youtube]
# or
pip install arxiv-sanity-bot[all]
```

**Benefits**: Users without Twitter/YouTube API access don't need to install unused dependencies.

## Implementation Details

### Twitter Client

**Target Accounts** (5 core accounts as specified by user):
- `_akhaliq` - AK (AI news aggregator)
- `karpathy` - Andrej Karpathy
- `goodside` - Riley Goodside (Prompt Engineering)
- `ylecun` - Yann LeCun
- `ai__pub` - AI Pub

**Filtering Strategy**:
```python
def fetch_recent_tweets(
    min_likes: int = 100,      # High threshold for quality
    exclude_replies: bool = True,
    max_tweets_per_user: int = 5,
)
```

**Key Design**:
- Excludes replies to reduce noise
- Filters by engagement threshold (default 100 likes)
- Extracts referenced URLs for link-sharing tweets

### YouTube Client

**Target Channels** (6 curated high-quality channels):
- Two Minute Papers
- Yannic Kilcher
- AI Explained
- David Shapiro
- DeepLearningAI
- Lex Fridman

**Lightweight Approach**:
- Only fetches video metadata (title, description, views)
- No video download or processing
- Filters by keywords, duration (min 5 min), and view count

```python
def fetch_recent_videos(
    min_views: int = 10000,
    min_duration_minutes: int = 5,
    keywords: list[str] = AI_KEYWORDS,  # LLM, multimodal, agents, etc.
)
```

## Content Filtering Pipeline

### 1. Keyword Filtering

```python
CONTENT_KEYWORDS = {
    "core": ["LLM", "GPT", "transformer", "large language model"],
    "multimodal": ["vision-language", "diffusion", "image generation"],
    "agents": ["agent", "RAG", "tool use", "autonomous"],
    "training": ["fine-tuning", "RLHF", "alignment"],
}
```

### 2. Engagement-Based Filtering

Different thresholds per source type:
- **Twitter**: min_likes = 100
- **YouTube**: min_views = 10,000
- **Blog/ArXiv**: no threshold

### 3. LLM Relevance Check (Optional)

For high-stakes filtering, use LLM to verify relevance:

```python
def llm_relevance_check(item: ContentItem, topic: str) -> bool:
    # Skip for long social content (too expensive)
    if len(item.content) > 500:
        return True

    # Prompt: "Is this content about {topic}? Answer YES or NO"
    response = llm.ask(relevance_prompt)
    return "YES" in response.upper()
```

## Error Handling Strategy

**Principle**: Single source failure should not crash the entire pipeline.

```python
all_content = []
for source in enabled_sources:
    try:
        content = source.fetch_recent()
        all_content.extend(content)
    except Exception as e:
        logger.error(f"Source {source} failed: {e}")
        # Continue with other sources
        continue
```

**Retry Logic**: Uses `tenacity` library for exponential backoff:

```python
@retry(
    retry=retry_if_exception_type((TwitterError, Exception)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=20),
)
def fetch_recent_tweets(...):
    ...
```

## Configuration

### Environment Variables

```bash
# Twitter
export TWITTER_BEARER_TOKEN="your_bearer_token"

# YouTube
export YOUTUBE_API_KEY="your_api_key"

# Content source selection (comma-separated)
export CONTENT_SOURCES="arxiv,blog,twitter,youtube"
```

### Programmatic Configuration

```python
from arxiv_sanity_bot.sources import TwitterClient, YouTubeClient

# Twitter with custom settings
twitter = TwitterClient()
tweets = twitter.fetch_recent_tweets(
    usernames=["karpathy", "ylecun"],
    min_likes=200,  # Higher threshold
    days=3,
)

# YouTube with custom settings
youtube = YouTubeClient()
videos = youtube.fetch_recent_videos(
    channel_ids=["UCXUPKJOdoz9XylBV4T2hpdQ"],
    min_views=50000,
)
```

## Lessons Learned

### 1. API Rate Limits

- **Twitter**: 300 requests per 15 minutes (Basic tier)
- **YouTube**: 10,000 units per day

**Mitigation**: Fetch extra items initially, then filter locally rather than making multiple API calls.

### 2. Content Quality over Quantity

Initially considered fetching more accounts/channels. User feedback:
> "精简到 5-8 个足矣"

Quality sources with high engagement thresholds produce better digests than many low-signal sources.

### 3. Lightweight YouTube Approach

User explicitly requested:
> "YouTube - 只抓标题和摘要，不要处理视频内容（太重）"

Fetching only metadata via YouTube Data API is fast and cost-effective. Video processing would require significant infrastructure.

### 4. Unified Model Benefits

The `ContentItem` model simplified downstream code:
- Single sorting/filtering logic
- Consistent email formatting
- Easy to add new sources in the future

## API Key Setup

### Twitter/X API

1. Apply at https://developer.twitter.com
2. Subscribe to Basic tier ($100/month) or use Free tier (limited)
3. Create app and generate Bearer Token
4. Set `TWITTER_BEARER_TOKEN` environment variable

### YouTube Data API

1. Go to https://console.cloud.google.com
2. Create project and enable YouTube Data API v3
3. Create API credentials (API Key)
4. Set `YOUTUBE_API_KEY` environment variable
5. Free tier: 10,000 quota units per day

## Future Improvements

- [ ] Add LinkedIn content source
- [ ] Implement caching layer to reduce API calls
- [ ] Add sentiment analysis for social content
- [ ] Auto-detect trending topics across sources
- [ ] Support video transcript extraction (if needed)

## References

- `arxiv_sanity_bot/sources/twitter_source.py`
- `arxiv_sanity_bot/sources/youtube_source.py`
- `arxiv_sanity_bot/schemas.py` (ContentItem model)
- `arxiv_sanity_bot/config.py` (Configuration options)

---

**Tags**: #twitter-api #youtube-api #content-aggregation #social-media #integration
