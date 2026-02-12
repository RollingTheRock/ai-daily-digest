# AI 日报 - 每日 AI 资讯自动推送

[![AI Daily Digest](https://github.com/RollingTheRock/ai-daily-digest/actions/workflows/daily-digest.yml/badge.svg)](https://github.com/RollingTheRock/ai-daily-digest/actions/workflows/daily-digest.yml)

每天早上 8 点，自动收集并发送 AI 领域最新动态到你的邮箱。同时提供 Web 收藏夹功能，方便管理和记录学习笔记。

> **致谢**：本项目基于 [giacomov/arxiv-sanity-bot](https://github.com/giacomov/arxiv-sanity-bot) 原版项目改造而成，感谢原作者的开源贡献。

---

## 功能特性

### 日报邮件
- **GitHub 热门仓库** - 追踪每日最受欢迎的 AI 开源项目
- **HuggingFace 趋势** - 热门模型、数据集和 Spaces
- **arXiv 论文精选** - AI 领域最新研究论文及中文摘要
- **技术博客** - OpenAI、Anthropic 等公司最新博客文章
- **AI 生成洞察** - 使用 DeepSeek AI 生成每日趋势总结

### Web 收藏夹
- **内容收藏** - 收藏感兴趣的 GitHub 仓库、论文、模型和博客
- **标签管理** - 为收藏添加自定义标签，方便分类
- **学习笔记** - 记录想法、疑问和 TODO，支持独立保存
- **离线查看** - 本地缓存，快速访问已收藏内容
- **数据私有** - 所有数据存储在你的 GitHub 私有仓库中

---

## 快速开始

### 方法一：订阅现成的服务（推荐非技术用户）

如果你只是想接收日报邮件，可以直接：

1. 发送邮件至 **2891887360@qq.com** 申请订阅
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

---

## Web 收藏夹使用指南

### 访问地址

部署完成后，访问：`https://你的用户名.github.io/ai-daily-digest`

### 首次使用

1. **创建 GitHub OAuth App**
   - 访问 https://github.com/settings/applications/new
   - Application name: `AI Daily Digest`
   - Homepage URL: `https://你的用户名.github.io/ai-daily-digest`
   - Authorization callback URL: `https://你的用户名.github.io/ai-daily-digest`
   - 保存生成的 Client ID

2. **配置 Client ID**
   - 编辑 `web/src/config.ts`
   - 将 `githubClientId` 替换为你的 Client ID
   - 提交并推送，自动重新部署

3. **登录**
   - 访问 Web 收藏夹页面
   - 使用 Personal Access Token 登录
   - Token 需要 `repo` 权限（访问私有仓库）

### 使用方法

**收藏内容：**
- 在日报邮件中点击收藏链接
- 或直接访问带参数的 URL：
  ```
  https://你的用户名.github.io/ai-daily-digest/star?id=内容ID&title=标题&url=链接&type=类型&date=日期
  ```

**添加笔记：**
- 点击收藏项的 ✏️ 按钮
- 填写想法、疑问、TODO
- 保存后自动关联到收藏

**查看笔记：**
- 点击收藏项的 📝 按钮
- 在弹窗中查看完整笔记
- 点击"编辑笔记"修改内容

**管理标签：**
- 收藏时可添加标签
- 按标签筛选收藏内容

---

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

编辑 workflow 文件中的 `args` 部分：

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

---

## 技术架构

### 日报系统

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

### Web 收藏夹

```
┌─────────────────────────┐      ┌──────────────────────┐
│      GitHub Pages       │      │    私有数据仓库       │
│   (React 纯前端应用)     │◄────►│  ai-daily-digest-data │
├─────────────────────────┤      ├──────────────────────┤
│  Device Flow 认证        │      │  data/stars.json     │
│  GitHub API 读写         │─────►│  data/notes.json     │
│  LocalStorage 缓存       │      └──────────────────────┘
└─────────────────────────┘
```

---

## 项目结构

```
ai-daily-digest/
├── .github/workflows/
│   ├── daily-digest.yml          # 日报邮件工作流
│   ├── deploy-web.yml            # Web 部署工作流
│   └── run-arxiv-sanity-bot.yml  # 原 Twitter Bot
│
├── arxiv_sanity_bot/             # Python 后端（日报生成）
│   ├── sources/                  # 数据源模块
│   │   ├── github_trending.py
│   │   ├── huggingface_extended.py
│   │   └── tech_blogs.py
│   ├── email/                    # 邮件发送模块
│   │   ├── email_sender.py
│   │   └── smtp_sender.py
│   └── models/                   # AI 模型
│       ├── openai.py
│       └── content_processor.py
│
├── web/                          # React 前端（收藏夹）
│   ├── src/
│   │   ├── pages/                # 页面组件
│   │   │   ├── Home.tsx          # 收藏夹主页
│   │   │   ├── Star.tsx          # 添加收藏
│   │   │   ├── Note.tsx          # 添加笔记
│   │   │   └── Login.tsx         # 登录页面
│   │   ├── lib/                  # 核心库
│   │   │   ├── github-auth.ts    # GitHub 认证
│   │   │   └── github-storage.ts # 数据操作
│   │   └── config.ts             # 配置文件
│   └── package.json
│
├── docs/
│   └── dev-log.md                # 开发日志
│
└── README.md                     # 本文件
```

---

## 本地开发

### 后端（日报系统）

**环境要求：**
- Python 3.12+
- [uv](https://github.com/astral-sh/uv) 包管理器

**安装依赖：**
```bash
uv sync
```

**本地测试（不发送邮件）：**
```bash
uv run arxiv-sanity-bot daily-digest --dry
```

**本地运行（真实发送）：**
```bash
export LLM_PROVIDER=deepseek
export DEEPSEEK_API_KEY=sk-xxx
export SMTP_HOST=smtp.qq.com
export SMTP_USER=your@qq.com
export SMTP_PASS=xxx
export FROM_EMAIL=your@qq.com
export TO_EMAIL=recipient@example.com

uv run arxiv-sanity-bot daily-digest
```

### 前端（收藏夹）

**环境要求：**
- Node.js 20+
- npm 或 yarn

**安装依赖：**
```bash
cd web
npm install
```

**本地开发：**
```bash
npm run dev
```

**构建：**
```bash
npm run build
```

---

## 常见问题

### 日报邮件

**Q: 邮件发送失败？**
A: 检查 SMTP_PASS 是否使用的是授权码而非邮箱密码。QQ 邮箱需要在设置中开启 SMTP 并获取授权码。

**Q: DeepSeek API 报错？**
A: 确认 `LLM_PROVIDER` 设置为 `deepseek`（小写），且 `DEEPSEEK_API_KEY` 正确设置。

**Q: 如何关闭自动发送？**
A: 进入仓库 Settings → Actions → General → 选择 "Disable Actions"。

### Web 收藏夹

**Q: 登录时提示 Token 无效？**
A: 确保 Token 有 `repo` 权限。在 GitHub → Settings → Developer settings → Personal access tokens 中检查。

**Q: 收藏后没有显示？**
A: 检查浏览器控制台是否有错误。可能是 GitHub API 限制，请稍后再试。

**Q: 数据存储在哪里？**
A: 数据存储在你的 GitHub 账号下的私有仓库 `ai-daily-digest-data` 中，包含 `data/stars.json` 和 `data/notes.json` 两个文件。

**Q: 可以在多台设备上使用吗？**
A: 可以。数据存储在 GitHub 上，任何设备登录后都能看到相同的数据。

**Q: 取消收藏后笔记会丢失吗？**
A: 不会。笔记和收藏是独立的，取消收藏后笔记仍然保留，会显示为"仅笔记"状态。

---

## 费用说明

- **GitHub Actions**: 免费版每月 2000 分钟，本项目每次运行约 5-10 分钟，完全够用
- **GitHub Pages**: 免费托管静态网站
- **DeepSeek API**: 按 token 计费，每日约消耗 5000-10000 tokens，费用极低（约 0.01-0.02 元/天）
- **邮件发送**: 使用自己的邮箱，无额外费用

---

## 隐私声明

- API Key 和邮箱信息仅存储在你的 GitHub Secrets 中
- 收藏和笔记数据存储在你的私有 GitHub 仓库中
- 我们不会收集或存储你的任何数据
- 所有数据处理在 GitHub Actions 运行器或你的浏览器中完成

---

## 致谢

本项目基于 **[giacomov/arxiv-sanity-bot](https://github.com/giacomov/arxiv-sanity-bot)** 改造而来，感谢原作者的开源贡献！

原项目功能：
- 从 AlphaXiv 和 HuggingFace 获取 trending papers
- 使用 OpenAI API 生成推文摘要
- 自动发布到 X/Twitter

---

## 贡献代码

欢迎提交 Issue 和 Pull Request！

开发日志请查看 [docs/dev-log.md](./docs/dev-log.md)

---

## 许可证

MIT License

---

有问题？欢迎提交 [Issue](https://github.com/RollingTheRock/ai-daily-digest/issues) 或联系维护者。
