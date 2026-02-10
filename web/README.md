# AI Digest 收藏与笔记系统

基于双仓库架构的AI日报收藏与笔记系统，数据存储在私有仓库，前端部署在GitHub Pages或Vercel。

## 架构

```
┌─────────────────┐      ┌──────────────────┐
│  公开仓库        │      │  私有仓库         │
│  (代码 + 前端)   │◄────►│  (收藏 + 笔记)    │
├─────────────────┤      ├──────────────────┤
│  GitHub Pages   │      │  data/stars.json │
│  Vercel API     │─────►│  data/notes/     │
└─────────────────┘      └──────────────────┘
```

## 快速开始

### 1. Fork 公开仓库

Fork 本仓库到你自己的账号下（例如 `yourusername/ai-digest`）

### 2. 创建私有数据仓库

创建一个新的**私有**仓库（例如 `yourusername/ai-digest-data`）

### 3. 配置 GitHub OAuth App

1. 访问 https://github.com/settings/applications/new
2. 创建一个新的 OAuth App：
   - Application name: `AI Digest`
   - Homepage URL: `https://yourusername.github.io/ai-digest`
   - Authorization callback URL: `https://ai-digest-yourusername.vercel.app/api/auth/callback`
3. 保存 `Client ID` 和 `Client Secret`

### 4. 部署到 Vercel

1. 在 Vercel 导入你的 fork 仓库
2. 配置环境变量：
   - `GITHUB_CLIENT_ID`: 你的 GitHub OAuth Client ID
   - `GITHUB_CLIENT_SECRET`: 你的 GitHub OAuth Client Secret
   - `DATA_REPO`: 你的私有数据仓库（格式：`username/repo`）
   - `SECRET_KEY`: 随机密钥（生成：`openssl rand -hex 32`）

### 5. 配置原仓库（发送邮件）

在原 `arxiv-sanity-bot` 仓库中添加环境变量：

```bash
DIGEST_WEB_URL=https://yourusername.github.io/ai-digest
SECRET_KEY=与Vercel相同的密钥
```

## 目录结构

```
web/
├── api/              # Vercel Functions
│   ├── _lib/         # 共享库
│   ├── auth/         # OAuth 相关
│   ├── star.ts       # 保存收藏
│   ├── note.ts       # 保存笔记
│   └── list.ts       # 获取列表
├── src/              # React 前端
│   ├── components/   # 组件
│   ├── pages/        # 页面
│   └── utils/        # 工具函数
└── public/           # 静态资源
```

## API 端点

| 端点 | 方法 | 描述 |
|-----|------|-----|
| `/api/auth/login` | GET | GitHub OAuth 登录 |
| `/api/auth/callback` | GET | OAuth 回调 |
| `/api/auth/logout` | POST | 退出登录 |
| `/api/auth/me` | GET | 获取当前用户 |
| `/api/star` | POST | 添加收藏 |
| `/api/unstar` | POST | 取消收藏 |
| `/api/note` | POST | 保存笔记 |
| `/api/list` | GET | 获取收藏和笔记列表 |

## 数据格式

### stars.json

```json
{
  "version": "1.0",
  "updated_at": "2024-02-10T08:35:21Z",
  "items": [
    {
      "id": "github-torvalds-linux",
      "title": "linux",
      "url": "https://github.com/torvalds/linux",
      "type": "github",
      "date": "2024-02-10",
      "starred_at": "2024-02-10T08:35:21Z",
      "tags": ["kernel", "c"],
      "note_id": "note-20240210-1"
    }
  ]
}
```

### 笔记 Markdown

```markdown
---
id: note-20240210-1
content_id: github-torvalds-linux
content_title: linux
content_url: https://github.com/torvalds/linux
content_type: github
date: 2024-02-10
created_at: 2024-02-10T08:35:21Z
ai_enhanced: false
---

## 💭 想法
...

## ❓ 疑问
...

## ✅ TODO
- [ ] ...

---

## 🤖 AI 增强
待处理...
```

## 安全说明

- OAuth token 存储在 httpOnly cookie 中
- URL 签名使用 HMAC-SHA256 防止恶意构造
- 每个用户只能访问自己的私有仓库数据
- CORS 仅允许特定域名

## 许可证

MIT
