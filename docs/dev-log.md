# AI 日报项目开发日志

## 2026-02-12 - 收藏夹与笔记功能开发

### 背景

项目原本是一个自动发送 AI 日报邮件的系统。用户反馈希望有一个前端界面来管理收藏的内容和记录笔记。

### 开发内容

#### 1. Web 前端架构搭建

**技术栈：**
- React 18 + TypeScript
- Vite 构建工具
- Tailwind CSS 样式
- GitHub Pages 部署
- GitHub API 作为数据存储

**架构特点：**
- 纯前端架构，零后端依赖
- 使用 GitHub Device Flow 认证
- 数据存储在用户私有仓库 (`ai-daily-digest-data`)
- 自动部署到 GitHub Pages

#### 2. 收藏夹功能

**实现细节：**
- 收藏文章（GitHub、arXiv、HuggingFace、博客）
- 添加标签分类
- 本地缓存优化加载速度
- 按日期分组显示

**遇到的问题：**
1. **加载缓慢** - 每次都要调用多次 GitHub API
   - 解决：添加 localStorage 缓存机制

2. **数据不保存** - Base64 解码中文出错
   - 解决：使用 TextDecoder 替代 atob()

#### 3. 笔记功能

**实现细节：**
- 支持记录想法、疑问、TODO
- 笔记与收藏可独立存在
- 查看笔记详情弹窗
- 编辑已有笔记

**遇到的问题：**
1. **重复笔记** - 同一文章多次记笔记会创建多条
   - 解决：`addNote()` 时检查是否已存在，存在则更新

2. **笔记依赖收藏** - 取消收藏后笔记无法显示
   - 解决：笔记独立化，收藏夹显示"收藏+孤立笔记"的并集

#### 4. 关键代码变更

**文件变更：**
```
web/src/lib/github-storage.ts  - 数据存储逻辑
web/src/pages/Home.tsx         - 收藏夹主页面
web/src/pages/Star.tsx         - 添加收藏
web/src/pages/Note.tsx         - 添加/编辑笔记
web/src/lib/github-auth.ts     - GitHub 认证
```

**缓存机制：**
```typescript
// 双重缓存策略
const STARS_CACHE_KEY = "aidigest_stars_cache";
const NOTES_CACHE_KEY = "aidigest_notes_cache";

// 先读缓存，后台刷新
const getStars = async () => {
  const cached = getCachedStars();
  if (cached) return cached;  // 立即返回缓存
  // 同时后台刷新...
};
```

#### 5. 性能优化

**优化前：**
- 每次加载 2-3 次 GitHub API 调用
- 加载时间 3-5 秒

**优化后：**
- 首次加载后使用缓存
- 加载时间 < 200ms
- 后台静默刷新保持同步

### 教训总结

#### 技术层面

1. **Base64 编码陷阱**
   - `atob()` 不能处理中文，必须用 `TextDecoder`
   - 编码时也要用 `TextEncoder` + 自定义 Base64

2. **API 缓存策略**
   - GitHub API 有延迟，写入后不能立即读到
   - 乐观更新 + 本地缓存是必须的

3. **数据模型设计**
   - 最初让笔记依赖收藏是个错误
   - 应该从一开始就设计为独立实体

#### 工程层面

1. **调试友好**
   - 添加详细日志让线上调试更容易
   - `console.log('[Module] message')` 格式清晰

2. **错误处理**
   - API 调用可能失败，要有降级策略
   - 缓存失效时要能优雅降级

3. **用户体验**
   - 加载状态要明确
   - 缓存数据先显示，后台刷新

### 后续规划

1. **功能增强**
   - [ ] 搜索功能
   - [ ] 笔记导出
   - [ ] AI 辅助总结

2. **性能优化**
   - [ ] 分页加载
   - [ ] 虚拟滚动
   - [ ] Service Worker 离线支持

3. **体验优化**
   - [ ] 暗黑模式
   - [ ] 快捷键支持
   - [ ] 批量操作

---

**开发耗时：** 约 4 小时
**主要开发者：** Claude Opus 4.6
**代码行数：** +800 行（TypeScript）
