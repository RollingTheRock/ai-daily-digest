# Notion 输出模块实现方案

**日期**: 2026-02-18
**分类**: Integrations
**相关项目**: ai-daily-digest

---

## 问题背景

AI Daily Digest 项目需要将每日晨报内容同时输出到邮件和 Notion 数据库两个渠道。邮件输出已完成改造，需要新增 Notion API 集成作为并行输出通道。

## 解决方案概述

创建独立的 `NotionSender` 模块，在邮件发送后异步写入 Notion 数据库。实现内容包括：

1. **NotionSender 类**: 封装 Notion API 调用
2. **自动标签提取**: 从内容中识别 8 个类别标签
3. **重要程度计算**: 基于 Top 3 平均分自动判断
4. **内容格式化**: 处理数据库属性和页面 blocks
5. **主流程集成**: 邮件后并行执行，失败隔离

---

## 实现细节

### 1. 模块结构

```
arxiv_sanity_bot/
├── notion/
│   ├── __init__.py          # 导出 NotionSender
│   └── notion_sender.py     # 核心实现 (500+ 行)
```

### 2. NotionSender 类设计

```python
class NotionSender:
    def __init__(self, token: str, database_id: str)
    def send_daily_digest(self, digest_data: dict) -> str  # 返回页面 URL
    def _extract_tags(self, contents: list[dict]) -> list[str]
    def _calculate_importance(self, top3: list[dict]) -> str
    def _format_property_content(self, items: list[dict]) -> str
    def _build_blocks(self, digest_data: dict) -> list[dict]
    def _create_page(self, properties: dict) -> dict
    def _append_blocks(self, page_id: str, blocks: list[dict])
```

### 3. 数据库属性映射

| Notion 属性 | 类型 | 数据来源 |
|------------|------|----------|
| 标题 | title | `{date} AI 晨报` |
| 日期 | date | `digest_data["date"]` |
| 今日洞察 | rich_text | `daily_insight` (截断 2000 字符) |
| 热门项目 | rich_text | GitHub + HuggingFace Top 3 |
| 论文精选 | rich_text | arXiv Top 3 |
| 博客速递 | rich_text | Blog Top 3 |
| 我的笔记 | rich_text | 留空 |
| 标签 | multi_select | 自动提取 (AI/LLM/安全等) |
| 重要程度 | select | 平均分 ≥8 🔥/≥5 ⭐/<5 💤 |

### 4. 页面结构 (Blocks)

```
✨ 今日洞察
  [daily_insight 文本]
---
🔥 今日精选 Top 3
  [heading_3] {tag} [{type}] {title}
  [paragraph] {reason}
  [paragraph] {url}
---
📂 完整内容
  [toggle] GitHub ({count})
    [paragraph] [{score}] {title} | {url}
  [toggle] HuggingFace ({count})
    ...
```

### 5. 标签提取规则

```python
TAG_RULES = [
    (r"\b(LLM|GPT|Claude)\b", "LLM"),           # 英文用 \b
    (r"(安全|alignment|guard)", "安全"),        # 中文不用 \b
    (r"\b(agent|Agent)\b", "Agent"),
    (r"(多模态|vision|diffusion)", "多模态"),
    (r"\b(tool|SDK|API)\b", "工具"),
]
# 默认标签: AI
# 类型标签: 论文 (arxiv), 开源 (github+license)
```

**关键经验**: 正则 `\b` (单词边界) **不支持中文字符**，对中文匹配需要移除 `\b`。

### 6. API 限制处理

```python
# 常量定义
MAX_RICH_TEXT_LENGTH = 2000    # rich_text 字符限制
MAX_BLOCKS_PER_REQUEST = 100   # blocks API 单次限制
MAX_TOGGLE_CHILDREN = 50       # toggle 内子 block 限制

# 截断处理
def _truncate_text(self, text: str, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."

# 分批处理 blocks
for i in range(0, len(blocks), MAX_BLOCKS_PER_REQUEST):
    batch = blocks[i:i + MAX_BLOCKS_PER_REQUEST]
    self.notion.blocks.children.append(...)
```

### 7. 主流程集成

```python
def _send_to_notion_if_enabled(...):
    """邮件发送后调用，异常不影响邮件"""
    if os.environ.get("OUTPUT_NOTION", "").lower() != "true":
        return

    notion_token = os.environ.get("NOTION_TOKEN", "").strip()
    notion_database_id = os.environ.get("NOTION_DATABASE_ID", "").strip()

    try:
        from arxiv_sanity_bot.notion import NotionSender
        notion_sender = NotionSender(token=notion_token, ...)
        page_url = notion_sender.send_daily_digest(digest_data)
        logger.info(f"Notion 页面已创建: {page_url}")
    except Exception as e:
        logger.error(f"Notion 输出失败: {e}", exc_info=True)
        # 失败不抛出，不影响邮件发送
```

**设计原则**: Notion 输出是**增强功能**，失败不应影响核心邮件功能。

---

## 配置说明

### 环境变量

```bash
# 必需
NOTION_TOKEN=secret_xxx              # Notion Integration Token
NOTION_DATABASE_ID=xxx               # 数据库 ID

# 开关
OUTPUT_NOTION=true                   # 启用 Notion 输出
```

### Notion 集成设置

1. 访问 https://www.notion.so/my-integrations
2. 创建新 Integration，复制 Token
3. 在数据库页面点击 "..." → "Add connections" → 选择 Integration
4. 复制数据库 ID（URL 中 `/database_id?v=` 部分）

---

## 踩坑记录

### 1. 正则表达式 `\b` 不支持中文

**问题**: 使用 `r"\b安全\b"` 匹配中文失败
**原因**: `\b` 只识别 ASCII 单词边界
**解决**: 中文字符周围不使用 `\b`：`r"(安全|guard)"`

### 2. rich_text 内容超限

**问题**: Notion API 返回 `validation_error`
**原因**: rich_text 属性值超过 2000 字符
**解决**: 所有写入 rich_text 的内容先经过 `_truncate_text()`

### 3. Blocks API 单次限制

**问题**: 内容多时 API 报错
**原因**: blocks.children.append 单次最多 100 个 blocks
**解决**: 分批追加：`for i in range(0, len(blocks), 100)`

### 4. 环境变量包含空格

**问题**: Notion API 认证失败
**原因**: 环境变量值末尾有换行或空格
**解决**: 读取时添加 `.strip()`：
```python
token = os.environ.get("NOTION_TOKEN", "").strip()
```

---

## 代码审查要点

| 检查项 | 状态 | 说明 |
|--------|------|------|
| API 错误处理 | ✅ | APIResponseError 捕获，其他异常兜底 |
| 字符截断 | ✅ | rich_text 2000 字符，blocks 内容也截断 |
| 分批处理 | ✅ | blocks 按 100 分批，toggle children 限制 50 |
| 标签提取 | ✅ | 中文字符不用 `\b`，英文保留 |
| 安全 | ✅ | 无 XSS 风险，结构化 API |
| 日志 | ✅ | 关键步骤记录，不泄露敏感信息 |
| 类型注解 | ✅ | 使用 `dict[str, Any]` 现代语法 |

---

## 相关文件

- `arxiv_sanity_bot/notion/notion_sender.py` - 核心实现
- `arxiv_sanity_bot/notion/__init__.py` - 模块导出
- `arxiv_sanity_bot/cli/arxiv_sanity_bot.py` - 主流程集成
- `.env.example` - 配置示例
- `pyproject.toml` - 依赖 (notion-client>=2.0.0)

---

## 参考资源

- [Notion API 官方文档](https://developers.notion.com/)
- [notion-client Python SDK](https://github.com/ramnes/notion-sdk-py)
- [Notion API 限制说明](https://developers.notion.com/reference/limits)
