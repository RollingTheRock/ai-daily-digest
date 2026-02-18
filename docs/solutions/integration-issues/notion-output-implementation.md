---
title: "Notion 输出模块实现经验"
description: "AI Daily Digest 项目添加 Notion API 输出渠道的完整开发经验，包含数据格式、API 限制、调试技巧"
category: integration-issues
date: 2026-02-19
author: Claude
related:
  - ../ui-bugs/notion-inspired-email-template-redesign.md
  - ../architecture/three-layer-email-refactoring.md
tags:
  - notion
  - api-integration
  - data-format
  - debugging
---

# Notion 输出模块实现经验

## 问题背景

AI Daily Digest 项目需要将每日晨报同时输出到**邮件**和 **Notion 数据库**两个渠道。邮件输出已完成改造（三层结构），需要新增 Notion API 集成作为并行输出通道。

## 开发过程

### Phase 1: 核心实现

创建 `NotionSender` 类封装 Notion API：

```python
class NotionSender:
    def send_daily_digest(self, digest_data: dict) -> str
    def _extract_tags(self, contents: list[dict]) -> list[str]
    def _calculate_importance(self, top3: list[dict]) -> str
```

**关键设计决策**：
- 使用 `dict` 格式传递数据（包含 `type`, `title`, `url`, `tag`, `reason`, `score`）
- 自动标签提取（AI/LLM/安全/Agent/多模态/工具/论文/开源）
- 重要程度计算（平均分 ≥8 为 🔥）
- API 限制处理（rich_text 2000 字符，blocks 100 个/次）

### Phase 2: 遇到的问题

#### 问题 1: 完全没有 Notion 日志输出

**现象**: Workflow 成功运行，但日志中没有 `[Notion]` 相关内容

**排查过程**:
1. 检查 workflow 文件 - 发现缺少 Notion 环境变量传递
2. 添加 `NOTION_TOKEN`, `NOTION_DATABASE_ID`, `OUTPUT_NOTION` 到 workflow
3. 添加调试日志确认环境变量读取

**修复代码**:
```yaml
# .github/workflows/daily-digest.yml
env:
  NOTION_TOKEN: ${{ secrets.NOTION_TOKEN }}
  NOTION_DATABASE_ID: ${{ secrets.NOTION_DATABASE_ID }}
  OUTPUT_NOTION: ${{ secrets.OUTPUT_NOTION || 'false' }}
```

#### 问题 2: 'GitHubRepo' object has no attribute 'get'

**现象**: 报错显示传入的数据是模型对象而非 dict

**根因分析**:
- 邮件发送使用原始数据模型（`GitHubRepo`, `HFModel` 等）
- Notion 模块期望的是打分后的 dict（包含 `score`, `tag`, `reason`）
- `_send_to_notion_if_enabled()` 直接传入了原始对象列表

**修复方案**:
从 `tagged_contents`（已打分的 dict 列表）中按类型筛选：

```python
# 正确做法：从 tagged_contents 中筛选 dict
github_top3_dict = sorted(
    [c for c in tagged_contents if c.get("type") == "github"],
    key=lambda x: x.get("score", 0),
    reverse=True
)[:3]

digest_data = {
    "github_top3": github_top3_dict,  # dict 列表
    "hf_top3": hf_top3_dict,
    ...
}
```

**错误做法**:
```python
# 错误：传入原始模型对象
digest_data = {
    "github_top3": github_top3,  # GitHubRepo 对象列表 ❌
}
```

### Phase 3: 数据流梳理

**清晰的数据流设计**：

```
数据采集
    ↓
[GitHubRepo, HFModel, ArxivPaper, BlogPost]  ← 原始模型对象
    ↓ 转换为统一 dict + AI 打分
tagged_contents: list[dict]  ← 包含 score/tag/reason
    ↓
邮件发送 ← 使用原始对象（兼容旧代码）
Notion 输出 ← 从 tagged_contents 筛选 dict
```

## 关键经验

### 1. 数据格式一致性

当多个输出渠道需要不同数据格式时：
- **明确每个渠道的数据需求**（模型对象 vs dict）
- **在转换层统一处理**，不要混用
- **添加类型检查或调试日志**确认数据格式

### 2. API 集成调试技巧

**环境变量问题排查**:
```python
# 在函数入口添加无条件日志
logger.info(f"[Notion] OUTPUT_NOTION={repr(os.getenv('OUTPUT_NOTION'))}")
logger.info(f"[Notion] Token configured: {bool(os.getenv('NOTION_TOKEN'))}")
```

**静默失败问题**:
```python
# 错误：静默返回
if os.environ.get("OUTPUT_NOTION") != "true":
    return  # 没有任何日志！

# 正确：添加日志
if os.environ.get("OUTPUT_NOTION", "").lower() != "true":
    logger.info(f"[Notion] Skipping: OUTPUT_NOTION={repr(os.getenv('OUTPUT_NOTION'))}")
    return
```

### 3. Notion API 限制

| 限制 | 值 | 处理方式 |
|------|-----|----------|
| rich_text 长度 | 2000 字符 | `_truncate_text()` |
| blocks/次 | 100 个 | 分批追加 |
| toggle children | 建议 50 个 | `MAX_TOGGLE_CHILDREN` |

### 4. 正则表达式陷阱

**中文单词边界问题**:
```python
# 错误：\b 不支持中文
(r"\b安全\b", "安全")  # 可能匹配失败

# 正确：移除 \b
(r"(安全|guard)", "安全")  # 可靠匹配
```

## 最终代码结构

```
arxiv_sanity_bot/
├── notion/
│   ├── __init__.py
│   └── notion_sender.py      # 500+ 行，完整实现
├── cli/
│   └── arxiv_sanity_bot.py   # 集成点（简化参数）
└── ...
```

**集成点代码**:
```python
def _send_to_notion_if_enabled(
    daily_insight: str,
    global_top3: list[dict],
    tagged_contents: list[dict],  # 关键：使用打分后的 dict
) -> None:
    """从 tagged_contents 筛选各类别 Top 3"""
    github_top3 = [c for c in tagged_contents if c.get("type") == "github"][:3]
    # ... 其他类型
```

## 验证清单

- [x] Workflow 环境变量配置正确
- [x] Notion Integration 已连接到数据库
- [x] `tagged_contents` 传入的是 dict 列表
- [x] 各类别 Top 3 从 `tagged_contents` 筛选
- [x] API 限制处理（截断、分批）
- [x] 异常隔离（Notion 失败不影响邮件）

## 相关提交

- `a5b94b2` - Add Notion output module for daily digest
- `e51a102` - 修复代码审查发现的问题
- `d6161ca` - 添加 Notion 输出模块解决方案文档
- `7fc80f0` - 添加 Notion 环境变量到 workflow
- `72b3b4c` - 添加 Notion 调试日志
- `5676129` - 修复 Notion 数据格式问题

## 参考资源

- [Notion API 官方文档](https://developers.notion.com/)
- [notion-client Python SDK](https://github.com/ramnes/notion-sdk-py)
- 本项目 `docs/solutions/integrations/notion-output.md`
