# AI Digest 收藏与笔记系统

纯前端架构的 AI 日报收藏与笔记系统，所有逻辑在浏览器运行，数据存储在 GitHub 私有仓库。

## 架构

```
┌─────────────────────────┐      ┌──────────────────────┐
│      GitHub Pages       │      │    私有数据仓库       │
│   (React 纯前端应用)     │◄────►│  ai-daily-digest-data │
├─────────────────────────┤      ├──────────────────────┤
│  Device Flow 认证        │      │  data/stars.json     │
│  GitHub API 读写         │─────►│  data/notes.json     │
└─────────────────────────┘      └──────────────────────┘
```

**特点：**
- **零后端**：所有逻辑在浏览器运行，不依赖 Vercel/Cloudflare
- **零平台配置**：纯代码控制，无需配置 serverless functions
- **自动部署**：GitHub Actions 自动部署到 GitHub Pages
- **数据私有**：使用 GitHub Device Flow 认证，数据存储在用户私有仓库

## 快速开始

### 1. Fork 公开仓库

Fork 本仓库到你自己的账号下

### 2. 创建 GitHub OAuth App

1. 访问 https://github.com/settings/applications/new
2. 创建一个新的 OAuth App：
   - **Application name**: `AI Daily Digest`
   - **Homepage URL**: `https://yourusername.github.io/ai-daily-digest`
   - **Authorization callback URL**: `https://yourusername.github.io/ai-daily-digest`
3. 保存 **Client ID**（不需要 Client Secret）

### 3. 配置 Client ID

编辑 `web/src/config.ts`，替换为你的 Client ID：

```typescript
export const config = {
  githubClientId: "YOUR_GITHUB_CLIENT_ID",  // 替换为你的 Client ID
  basePath: "/ai-daily-digest",
  dataRepoName: "ai-daily-digest-data",
  // ...
};
```

### 4. 启用 GitHub Pages

1. 进入仓库 Settings → Pages
2. Source 选择 "GitHub Actions"
3. 推送代码到 main 分支，自动触发部署

### 5. 访问应用

部署完成后，访问：`https://yourusername.github.io/ai-daily-digest`

首次使用会要求：
1. 点击登录按钮
2. 在 GitHub 输入设备代码授权
3. 自动创建私有数据仓库 `ai-daily-digest-data`

## 目录结构

```
web/
├── public/           # 静态资源
│   └── 404.html      # SPA 路由支持
├── src/
│   ├── config.ts     # 配置文件
│   ├── lib/          # 核心库
│   │   ├── github-auth.ts     # Device Flow 认证
│   │   └── github-storage.ts  # GitHub API 数据操作
│   ├── pages/        # 页面组件
│   │   ├── Home.tsx  # 收藏列表
│   │   ├── Login.tsx # 登录页面
│   │   ├── Star.tsx  # 收藏确认
│   │   └── Note.tsx  # 笔记编辑
│   ├── App.tsx       # 路由配置
│   └── main.tsx      # 应用入口
└── vite.config.ts    # Vite 配置
```

## 数据格式

### stars.json

```json
[
  {
    "id": "github-torvalds-linux",
    "title": "linux",
    "url": "https://github.com/torvalds/linux",
    "type": "github",
    "date": "2024-02-10",
    "starred_at": "2024-02-10T08:35:21Z",
    "tags": ["kernel", "c"],
    "note_id": "note_1234567890"
  }
]
```

### notes.json

```json
[
  {
    "id": "note_1234567890",
    "content_id": "github-torvalds-linux",
    "content_title": "linux",
    "content_url": "https://github.com/torvalds/linux",
    "content_type": "github",
    "date": "2024-02-10",
    "created_at": "2024-02-10T08:35:21Z",
    "updated_at": "2024-02-10T08:35:21Z",
    "ai_enhanced": false,
    "thoughts": "...",
    "questions": "...",
    "todos": "..."
  }
]
```

## 从旧架构迁移

如果你之前使用 Vercel + Serverless 架构：

1. 备份原有 `data/stars.json` 和 `data/notes/` 中的数据
2. 部署新的纯前端版本
3. 登录后会自动创建新的数据仓库
4. 手动将旧数据迁移到新的格式（或重新收藏）

**数据格式变化：**
- Stars: 从 `{version, updated_at, items: [...]}` 变为直接 `[...]`
- Notes: 从单独的 `.md` 文件变为 `notes.json` 数组

## 安全说明

- Token 存储在浏览器 localStorage 中（纯前端无法使用 httpOnly cookie）
- 每个用户只能访问自己的私有仓库数据
- 使用 GitHub Device Flow，不暴露 Client Secret
- 建议仅在个人设备上使用，避免在公共电脑登录

## 本地开发

```bash
cd web
npm install
npm run dev
```

本地开发时同样需要配置 Client ID。

## 许可证

MIT
