---
title: Notion-style Email Template Redesign
issue_type: ui-redesign
date: 2026-02-13
component: email-system
severity: medium
categories:
  - email-template
  - frontend
  - ux-improvement
affected_files:
  - arxiv_sanity_bot/email/smtp_sender.py
  - arxiv_sanity_bot/email/email_sender.py
  - arxiv_sanity_bot/cli/arxiv_sanity_bot.py
pr: "5"
---

# Notion-style Email Template Redesign

## Problem Symptom

The AI Daily Digest email template suffered from information overload and visual clutter:

- **6 separate sections** (GitHub, HuggingFace Models, HuggingFace Datasets, HuggingFace Spaces, arXiv Papers, Blog Posts) created cognitive fatigue
- **Redundant action buttons** (star/note) on every card distracted from content
- **Bordered card design** created visual noise
- **No support for social media content** (Twitter/YouTube)
- **Inconsistent spacing and typography**

Users reported the template was "too cluttered for daily reading" and information was hard to scan quickly.

## Root Cause Analysis

1. **Information Architecture Issue**: 6 disjointed sections with similar card designs made it difficult to quickly identify relevant content
2. **Visual Design Debt**: Each card had borders, shadows, and action buttons that competed for attention
3. **Missing Content Channels**: No unified way to display social media content alongside academic sources
4. **Lack of Visual Hierarchy**: All content had equal visual weight, making scanning inefficient

## Working Solution

### 1. Section Consolidation (6 → 4)

Consolidated the 6 separate sections into 4 thematic groups:

| Section | Emoji | Content Sources | Purpose |
|---------|-------|-----------------|---------|
| **🔥 热门项目** | Trending | GitHub + HuggingFace (Models/Datasets/Spaces) | Code repositories and ML models |
| **📝 深度阅读** | Reading | arXiv Papers + Blog Posts | Academic and technical content |
| **💬 社交动态** | Social | Twitter + YouTube | Social media discussions and videos |
| **📌 今日洞察** | Insight | LLM-generated | Daily AI trends summary |

**Implementation:**

```python
def _build_html_email(self, ...):
    # Trending Section (GitHub + HuggingFace)
    html += self._build_trending_section(github_repos, hf_models, hf_datasets, hf_spaces)

    # Reading Section (arXiv + Blog)
    html += self._build_reading_section(arxiv_papers, blog_posts)

    # Social Section (Twitter + YouTube)
    html += self._build_social_section(tweets, videos)
```

### 2. Notion-Inspired Visual Design

Adopted Notion's minimalist aesthetic with these key principles:

#### Color Palette

```css
/* Background-colored cards instead of borders */
.content-card {
    background: #f7f7f5;        /* Notion's signature light gray */
    border-radius: 6px;
    padding: 20px 24px;
    margin-bottom: 12px;
    transition: background 0.15s ease;
}

.content-card:hover {
    background: #f0f0ee;        /* Subtle hover feedback */
}
```

#### Source-Specific Color Tags

```css
.source-tag.github   { color: #2383e2; background: rgba(35, 131, 226, 0.1); }
.source-tag.hf       { color: #ff6b00; background: rgba(255, 107, 0, 0.1); }
.source-tag.arxiv    { color: #b31b1b; background: rgba(179, 27, 27, 0.08); }
.source-tag.blog     { color: #f97316; background: rgba(249, 115, 22, 0.1); }
.source-tag.twitter  { color: #1da1f2; background: rgba(29, 161, 242, 0.1); }
.source-tag.youtube  { color: #ff0000; background: rgba(255, 0, 0, 0.08); }
```

#### Typography Hierarchy

```css
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    color: #37352f;
    line-height: 1.6;
}

.section-title { font-size: 20px; font-weight: 600; }
.card-title    { font-size: 17px; font-weight: 600; }
.card-desc     { font-size: 15px; color: #6b6b6b; }
.meta          { font-size: 13px; color: #9b9b9b; }
```

### 3. Button Removal - Clickable Titles

**Before (with buttons):**
```html
<div class="card">
    <h3 class="card-title">{title}</h3>
    <p class="card-description">{description}</p>
    <div class="card-actions">
        <a href="{url}" class="btn">查看详情</a>
    </div>
</div>
```

**After (title is the link):**
```html
<div class="content-card">
    <div class="card-header">
        <span class="source-tag github">GitHub</span>
        <span class="meta">⭐ 2.3k stars</span>
    </div>
    <h3 class="card-title">
        <a href="{url}">{title}</a>
    </h3>
    <p class="card-desc">{description}</p>
</div>
```

With CSS hover effects:
```css
.card-title a {
    color: #37352f;
    text-decoration: none;
    transition: color 0.15s ease;
}

.card-title a:hover {
    color: #2383e2;
    text-decoration: underline;
}
```

### 4. Bug Fix: Mutable Default Arguments

Discovered and fixed a classic Python pitfall:

**Problem (before fix):**
```python
def _build_html_email(
    self,
    ...
    tweets: list[ContentItem] = [],    # DANGER: Mutable default!
    videos: list[ContentItem] = [],
) -> str:
```

**Solution (after fix):**
```python
def _build_html_email(
    self,
    ...
    tweets: list[ContentItem] | None = None,
    videos: list[ContentItem] | None = None,
) -> str:
    tweets = tweets or []
    videos = videos or []
```

## Prevention Strategies

### 1. Avoid Mutable Default Arguments

**Pattern to use:**
```python
# Good: Use None as default
def process_items(items: list[str] | None = None) -> None:
    items = items or []
    # Process items...

# For dataclasses/Pydantic:
from pydantic import Field

class Config(BaseModel):
    tags: list[str] = Field(default_factory=list)
```

### 2. Email Template Design Best Practices

- **Use background colors** instead of borders for card separation
- **Limit sections** to 3-4 thematic groups maximum
- **Remove redundant buttons** - make content itself clickable
- **Color-code content sources** for quick visual identification
- **Test in multiple email clients** (Gmail, Outlook, Apple Mail)

### 3. Code Review Checklist for Email Changes

- [ ] Mutable defaults avoided (`None` + `or []` pattern)
- [ ] All user input HTML-escaped
- [ ] Empty content lists handled gracefully
- [ ] Mobile-responsive breakpoints included
- [ ] Both sender implementations updated (if applicable)

### 4. Maintain Consistency Between Senders

Current SMTP and SendGrid implementations have divergent templates. Future work should:
- Extract template generation into a shared `EmailTemplate` class
- Use a template engine like Jinja2
- Ensure feature parity or explicit documentation of differences

## Test Cases

- [x] Email generates without errors (11,757 bytes output)
- [x] All 4 sections display correctly
- [x] HTML escaping prevents XSS (`<script>` → `&lt;script&gt;`)
- [x] Mobile responsive layout (`@media (max-width: 480px)`)
- [x] Empty sections hidden gracefully
- [x] Chinese characters display correctly
- [ ] Gmail web compatibility (pending real send test)
- [ ] Outlook compatibility (pending real send test)
- [ ] Dark mode compatibility (future enhancement)

## Technical Details

### Affected Files

| File | Lines Changed | Description |
|------|---------------|-------------|
| `smtp_sender.py` | -351, +304 | Complete template rewrite with Notion style |
| `email_sender.py` | -1, +11 | Updated base class signatures |
| `arxiv_sanity_bot.py` | 0, +2 | Pass tweets/videos to sender |

### Key Methods

```python
# Main template builder
_build_html_email(...) -> str

# Section builders
_build_trending_section(repos, models, datasets, spaces) -> str
_build_reading_section(papers, posts) -> str
_build_social_section(tweets, videos) -> str

# Utility
_escape_html(text: str) -> str
```

## Cross-References

- **Plan Document**: [Email Template Refactoring Plan](../../plans/2026-02-13-refactor-simplify-email-template-plan.md)
- **Related Feature**: [Twitter/YouTube Content Sources](../../plans/2026-02-13-feat-twitter-youtube-content-sources-plan.md)
- **Integration Pattern**: [Content Aggregation](../integration-patterns/twitter-youtube-content-aggregation.md)
- **Code**: `arxiv_sanity_bot/email/smtp_sender.py`
- **PR**: #5 - Notion-style email template redesign

## Lessons Learned

1. **Information Architecture Matters**: Consolidating 6 sections into 4 thematic groups dramatically improved scannability
2. **Whitespace is Content**: Notion's generous padding (20-24px) creates breathing room that reduces cognitive load
3. **Buttons are Visual Noise**: Removing redundant action buttons simplified the interface without losing functionality
4. **Mutable Defaults are Tricky**: Even experienced developers can miss this Python gotcha - always use `None` defaults for mutable types
5. **Email Client Compatibility**: CSS support varies widely - use inline styles and table-based layouts for maximum compatibility

## Future Improvements

- [ ] Sync SendGrid template with new Notion style
- [ ] Extract HTML templates to Jinja2 files
- [ ] Add dark mode support (`prefers-color-scheme`)
- [ ] Implement URL validation to prevent injection
- [ ] Add visual regression testing with Playwright
- [ ] Create email preview tool for testing templates

## References

- [Notion Design System](https://www.notion.so/blog/the-notion-design-system)
- [Can I Email - CSS Compatibility](https://www.caniemail.com/)
- [Python Mutable Default Arguments](https://docs.python-guide.org/writing/gotchas/#mutable-default-arguments)
- [Responsive Email Patterns](https://responsiveemailpatterns.com/)
