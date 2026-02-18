# Notion 输出模块实现计划

**日期**: 2026-02-18
**类型**: Feature
**模块**: notion-output
**状态**: Planning

---

## 1. 目标与背景

### 1.1 目标
为 ai-daily-digest 项目新增 Notion API 输出模块，实现将每日晨报自动写入 Notion 数据库，作为邮件之外的并行输出渠道。

### 1.2 背景
- 邮件输出已完成格式精简（三层结构）
- 用户需要 Notion 作为第二输出渠道
- 现有数据采集和评分流程保持不变

---

## 2. 需求分析

### 2.1 功能需求

#### 必须实现 (MVP)
- [ ] 创建 `NotionSender` 类封装 Notion API 调用
- [ ] 创建 Notion 数据库页面，填充所有属性字段
- [ ] 在页面 body 中写入详细内容（今日洞察、Top 3、完整内容）
- [ ] 自动提取标签（AI、LLM、安全、工具、论文、开源、多模态、Agent）
- [ ] 根据 Top 3 平均分判断重要程度
- [ ] 添加 notion-client 依赖
- [ ] 配置环境变量（NOTION_TOKEN, NOTION_DATABASE_ID, OUTPUT_NOTION）
- [ ] 在主流程中接入 Notion 输出（邮件之后，异常不影响邮件）

#### 技术约束
- Notion rich_text 限制 2000 字符，需要截断处理
- Notion blocks API 单次最多 100 个 block，需要分批
- 所有 API 调用必须异常处理
- 保持现有代码风格

### 2.2 数据库 Schema

| 属性名 | 类型 | 说明 |
|--------|------|------|
| 标题 | title | "YYYY-MM-DD AI 晨报" |
| 日期 | date | 晨报日期 |
| 今日洞察 | rich_text | AI 生成的 TL;DR（≤2000字符） |
| 热门项目 | rich_text | Top 3 GitHub/HF 项目摘要 |
| 论文精选 | rich_text | Top 3 arXiv 论文摘要 |
| 博客速递 | rich_text | Top 3 技术博客摘要 |
| 我的笔记 | rich_text | 留空供手动填写 |
| 标签 | multi_select | AI/LLM/安全/工具/论文/开源/多模态/Agent |
| 重要程度 | select | 🔥重要/⭐一般/💤低优 |

### 2.3 页面结构

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
  [toggle heading_3] GitHub ({count})
    [paragraph] [{score}] {title} | {url}
  [toggle heading_3] HuggingFace ({count})
    ...
  [toggle heading_3] arXiv ({count})
    ...
  [toggle heading_3] Blog ({count})
    ...
```

---

## 3. 技术方案

### 3.1 架构设计

```
arxiv_sanity_bot/
├── notion/
│   ├── __init__.py          # 导出 NotionSender
│   └── notion_sender.py     # 核心实现
├── cli/
│   └── arxiv_sanity_bot.py  # 主流程接入点（修改）
└── config.py                # 配置加载（修改）
```

### 3.2 类设计

```python
class NotionSender:
    def __init__(self, token: str, database_id: str)
    def send_daily_digest(self, digest_data: dict) -> str
    def _extract_tags(self, contents: list[dict]) -> list[str]
    def _calculate_importance(self, top3: list[dict]) -> str
    def _format_property_content(self, items: list[dict]) -> str
    def _build_blocks(self, digest_data: dict) -> list[dict]
    def _create_page(self, properties: dict) -> dict
    def _append_blocks(self, page_id: str, blocks: list[dict])
```

### 3.3 集成点

在 `daily_digest()` 函数中，邮件发送后添加：

```python
# Notion 输出（新增）
if os.environ.get("OUTPUT_NOTION", "").lower() == "true":
    try:
        from arxiv_sanity_bot.notion import NotionSender
        notion_sender = NotionSender(
            token=os.environ["NOTION_TOKEN"],
            database_id=os.environ["NOTION_DATABASE_ID"]
        )
        digest_data = {...}  # 构建数据
        page_url = notion_sender.send_daily_digest(digest_data)
        logger.info(f"Notion 页面已创建: {page_url}")
    except Exception as e:
        logger.error(f"Notion 输出失败: {e}")
        # Notion 失败不影响邮件发送
```

### 3.4 标签提取规则

| 关键词 | 标签 |
|--------|------|
| LLM, language model, GPT, Claude | LLM |
| safe, 安全, alignment, guard | 安全 |
| agent, Agent, 智能体 | Agent |
| multimodal, 多模态, vision, image | 多模态 |
| tool, 工具, framework, library | 工具 |
| type == arxiv | 论文 |
| type == github + license 相关 | 开源 |
| 默认 | AI |

### 3.5 重要程度计算

```python
avg_score = sum(item.get("score", 0) for item in top3) / len(top3)
if avg_score >= 8:
    return "🔥 重要"
elif avg_score >= 5:
    return "⭐ 一般"
else:
    return "💤 低优"
```

---

## 4. 实施步骤

### Step 1: 创建 notion 模块目录结构
- [ ] 创建 `arxiv_sanity_bot/notion/` 目录
- [ ] 创建 `arxiv_sanity_bot/notion/__init__.py`
- [ ] 创建 `arxiv_sanity_bot/notion/notion_sender.py`

### Step 2: 实现 NotionSender 类
- [ ] `__init__` 初始化 Notion 客户端
- [ ] `send_daily_digest` 主入口方法
- [ ] `_extract_tags` 自动标签提取
- [ ] `_calculate_importance` 重要程度计算
- [ ] `_format_property_content` 格式化属性内容（处理 2000 字符限制）
- [ ] `_build_blocks` 构建页面 blocks
- [ ] `_create_page` 创建数据库页面
- [ ] `_append_blocks` 分批追加 blocks

### Step 3: 添加依赖
- [ ] 在 `pyproject.toml` 中添加 `notion-client>=2.0.0`
- [ ] 运行 `uv sync` 更新依赖

### Step 4: 添加配置
- [ ] 更新 `.env.example` 添加 NOTION_TOKEN, NOTION_DATABASE_ID, OUTPUT_NOTION
- [ ] （如有 config.py）添加配置项读取

### Step 5: 主流程集成
- [ ] 在 `arxiv_sanity_bot.py` 中导入 NotionSender
- [ ] 在邮件发送后添加 Notion 输出逻辑
- [ ] 确保异常处理不影响邮件发送

### Step 6: 测试
- [ ] 单元测试：验证标签提取逻辑
- [ ] 单元测试：验证重要程度计算
- [ ] 单元测试：验证字符截断逻辑
- [ ] 集成测试：验证完整流程

---

## 5. 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| Notion API 限流 | 中 | 实现重试机制，降低请求频率 |
| rich_text 超限 | 中 | 截断处理，添加省略号提示 |
| blocks 数量超限 | 低 | 分批追加，每批最多 100 个 |
| Token 泄露 | 高 | 通过环境变量传入，不硬编码 |
| 网络超时 | 中 | 设置合理超时时间，异常捕获 |

---

## 6. 验收标准

- [ ] `NotionSender` 类完整实现所有方法
- [ ] 成功创建 Notion 页面并填充所有属性
- [ ] 页面 body 结构符合设计要求
- [ ] 标签自动提取准确
- [ ] 重要程度计算正确
- [ ] notion-client 依赖正确添加
- [ ] 环境变量配置完整
- [ ] 主流程集成成功
- [ ] Notion 失败不影响邮件发送
- [ ] 所有边界情况处理（字符超限、blocks 超限）

---

## 7. 相关文件

### 新建文件
- `arxiv_sanity_bot/notion/__init__.py`
- `arxiv_sanity_bot/notion/notion_sender.py`

### 修改文件
- `pyproject.toml` - 添加依赖
- `.env.example` - 添加配置示例
- `arxiv_sanity_bot/cli/arxiv_sanity_bot.py` - 主流程集成

---

## 8. 参考资料

- [Notion API 文档](https://developers.notion.com/)
- [notion-client Python 库](https://github.com/ramnes/notion-sdk-py)
- 项目现有代码风格（参考 email/smtp_sender.py）
