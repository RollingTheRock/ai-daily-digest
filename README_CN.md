# AI 日报 - 每日 AI 资讯自动推送

[![AI Daily Digest](https://github.com/RollingTheRock/ai-daily-digest/actions/workflows/daily-digest.yml/badge.svg)](https://github.com/RollingTheRock/ai-daily-digest/actions/workflows/daily-digest.yml)

每天早上 8 点，自动收集并发送 AI 领域最新动态到你的邮箱。

## 功能特性

- **GitHub 热门仓库** - 追踪每日最受欢迎的 AI 开源项目
- **HuggingFace 趋势** - 热门模型、数据集和 Spaces
- **arXiv 论文精选** - AI 领域最新研究论文及中文摘要
- **技术博客** - OpenAI、Anthropic 等公司最新博客文章
- **AI 生成洞察** - 使用 DeepSeek AI 生成每日趋势总结

## 邮件样式

采用 Notion 风格的简洁设计，支持手机/平板/电脑自适应显示。

## 快速开始

### 方法一：使用现成的服务（推荐非技术用户）

如果你只是想接收日报邮件，可以直接：

1. 发送邮件至 xxx@example.com 申请订阅
2. 等待确认邮件
3. 每天早上 8 点自动接收 AI 日报

### 方法二：自行部署（适合开发者）

#### 1. Fork 本仓库

点击右上角 "Fork" 按钮，将本项目复制到你的 GitHub 账号下。

#### 2. 配置 Secrets

进入你 Fork 的仓库 → Settings → Secrets and variables → Actions，添加以下 Secrets：

| Secret 名称 | 说明 | 示例 |
|------------|------|------|
| `LLM_PROVIDER` | AI 服务提供商 | `deepseek` |
| `DEEPSEEK_API_KEY` | DeepSeek API Key | `sk-xxxxxxxx` |
| `SMTP_HOST` | 邮件服务器地址 | `smtp.qq.com` |
| `SMTP_PORT` | 邮件服务器端口 | `465` |
| `SMTP_USER` | 邮箱用户名 | `yourname@qq.com` |
| `SMTP_PASS` | 邮箱授权码（非密码）| `xxxxxxxx` |
| `FROM_EMAIL` | 发件人邮箱 | `yourname@qq.com` |
| `TO_EMAIL` | 收件人邮箱 | `yourname@example.com` |

**如何获取：**

- **DeepSeek API Key**: 访问 [DeepSeek 开放平台](https://platform.deepseek.com/) 注册并创建 API Key
- **QQ 邮箱授权码**: 登录 QQ 邮箱 → 设置 → 账户 → 开启 SMTP 服务 → 获取授权码

#### 3. 启用 Workflow

进入 Actions 页面，点击 "I understand my workflows, go ahead and enable them" 启用 Actions。

#### 4. 测试运行

进入 Actions → AI Daily Digest → Run workflow → 点击 "Run workflow" 手动触发一次测试。

#### 5. 完成

如果收到邮件，说明配置成功。系统会每天早上 8 点自动发送日报。

## 自定义配置

### 修改发送时间

编辑 `.github/workflows/daily-digest.yml`：

```yaml
schedule:
  - cron: "0 0 * * *"  # UTC 时间，北京时间 = UTC + 8
```

常见时间：
- `0 0 * * *` - 每天早上 8 点（默认）
- `0 22 * * *` - 每天早上 6 点
- `0 14 * * *` - 每天晚上 10 点

### 调整内容数量

编辑 workflow 文件中的 `env` 部分：

```yaml
args: |
  --github-limit 5      # GitHub 仓库数量
  --hf-models-limit 5   # HuggingFace 模型数量
  --arxiv-limit 5       # arXiv 论文数量
```

### 使用 OpenAI 替代 DeepSeek

1. 将 `LLM_PROVIDER` 改为 `openai`
2. 添加 `OPENAI_API_KEY` Secret
3. （可选）添加 `OPENAI_MODEL` 指定模型，如 `gpt-4o-mini`

## 技术架构

```
┌─────────────────┐
│  GitHub Actions │
│  (定时触发)      │
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌────────┐ ┌──────────┐
│  arXiv │ │  GitHub  │
└────────┘ └──────────┘
┌────────┐ ┌──────────┐
│   HF   │ │   RSS    │
└────────┘ └──────────┘
    │         │
    └────┬────┘
         ▼
┌─────────────────┐
│ DeepSeek AI     │
│ (摘要生成)       │
└────────┬────────┘
         ▼
┌─────────────────┐
│   SMTP/QQ邮箱   │
│  (邮件发送)      │
└─────────────────┘
```

## 项目结构

```
arxiv-sanity-bot/
├── .github/workflows/
│   ├── daily-digest.yml      # 日报工作流
│   └── run-arxiv-sanity-bot.yml  # 原 Twitter Bot
├── arxiv_sanity_bot/
│   ├── sources/              # 数据源模块
│   │   ├── github_trending.py
│   │   ├── huggingface_extended.py
│   │   └── tech_blogs.py
│   ├── email/                # 邮件发送模块
│   │   ├── email_sender.py
│   │   └── smtp_sender.py
│   ├── models/               # AI 模型
│   │   ├── openai.py         # DeepSeek/OpenAI 支持
│   │   └── content_processor.py
│   └── cli/                  # 命令行入口
└── README_CN.md              # 本文件
```

## 本地开发

### 环境要求

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) 包管理器

### 安装依赖

```bash
uv sync
```

### 本地测试（不发送邮件）

```bash
uv run arxiv-sanity-bot daily-digest --dry
```

### 本地运行（真实发送）

```bash
# 设置环境变量
export LLM_PROVIDER=deepseek
export DEEPSEEK_API_KEY=sk-xxx
export SMTP_HOST=smtp.qq.com
export SMTP_USER=your@qq.com
export SMTP_PASS=xxx
export FROM_EMAIL=your@qq.com
export TO_EMAIL=recipient@example.com

# 运行
uv run arxiv-sanity-bot daily-digest
```

## 常见问题

**Q: 邮件发送失败？**
A: 检查 SMTP_PASS 是否使用的是授权码而非邮箱密码。QQ 邮箱需要在设置中开启 SMTP 并获取授权码。

**Q: DeepSeek API 报错？**
A: 确认 `LLM_PROVIDER` 设置为 `deepseek`（小写），且 `DEEPSEEK_API_KEY` 正确设置。

**Q: 如何关闭自动发送？**
A: 进入仓库 Settings → Actions → General → 选择 "Disable Actions"。

**Q: 可以发送到多个邮箱吗？**
A: 目前只支持单个收件人。如需多人接收，可以设置邮件转发规则，或 Fork 多个仓库分别配置。

**Q: 能自定义邮件内容吗？**
A: 可以修改 `arxiv_sanity_bot/email/smtp_sender.py` 中的 HTML 模板。

## 费用说明

- **GitHub Actions**: 免费版每月 2000 分钟，本项目每次运行约 5-10 分钟，完全够用
- **DeepSeek API**: 按 token 计费，每日约消耗 5000-10000 tokens，费用极低（约 0.01-0.02 元/天）
- **邮件发送**: 使用自己的邮箱，无额外费用

## 隐私声明

- API Key 和邮箱信息仅存储在你的 GitHub Secrets 中
- 我们不会收集或存储你的邮件内容
- 所有数据处理在 GitHub Actions 运行器中完成，完成后即销毁

## 贡献代码

欢迎提交 Issue 和 Pull Request！

## 许可证

MIT License

---

有问题？欢迎提交 [Issue](https://github.com/RollingTheRock/ai-daily-digest/issues) 或联系维护者。