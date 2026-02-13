---
title: 修复收藏夹和记笔记功能
type: fix
date: 2026-02-14
---

# 修复收藏夹和记笔记功能

## 概述

Web 收藏夹的收藏功能和笔记功能需要修复。代码结构完整，但可能存在运行时问题导致功能无法正常工作。

## 问题分析

基于代码审查，发现以下潜在问题：

### 1. 严重：GitHub API 错误处理不完善
**位置**: `web/src/lib/github-storage.ts:299-324`

`getStars()` 函数在 `ensureDataRepo()` 之后才尝试从缓存读取，如果用户未认证，会抛出错误而不是返回缓存数据。

```typescript
// 问题代码
export async function getStars(): Promise<StarItem[]> {
  // 先尝试从缓存读取
  const cached = getCachedStars();
  if (cached) {
    console.log("[getStars] Returning cached data:", cached.length, "items");
  }

  await ensureDataRepo(); // 如果未认证，这里会抛出错误
  // ...
}
```

### 2. 严重：API 调用缺少错误边界
**位置**: `web/src/lib/github-storage.ts:186-204`

`readFile` 函数在 401/403 错误时没有特殊处理，可能导致认证问题被掩盖。

### 3. 中等：缓存更新时机问题
**位置**: `web/src/lib/github-storage.ts:230-237`

缓存只在成功获取服务器数据后更新，如果首次加载失败，用户体验不佳。

### 4. 轻微：Home.tsx 加载状态管理
**位置**: `web/src/pages/Home.tsx:50-72`

`loadData()` 并行请求所有数据，如果其中一个失败，整个页面显示错误。

### 5. 轻微：Base64 编码问题
**位置**: `web/src/lib/github-storage.ts:151-156`

自定义的 Base64 编码实现可能在某些字符上存在问题。

## 修复方案

### 任务 1: 改进错误处理和用户提示
- [ ] 在 `github-storage.ts` 中添加更详细的错误分类
- [ ] 区分网络错误、认证错误、API 限制错误
- [ ] 添加中文错误提示

### 任务 2: 修复认证流程
- [ ] 确保未认证时优雅降级（显示缓存或提示登录）
- [ ] 修复 `getStars()` 和 `getNotes()` 的错误处理
- [ ] 添加 token 过期检测

### 任务 3: 改进数据加载策略
- [ ] 先显示缓存数据，后台刷新
- [ ] 添加单个请求失败的重试机制
- [ ] 改进加载状态显示

### 任务 4: 修复 UI 交互问题
- [ ] 检查收藏/取消收藏的即时反馈
- [ ] 检查笔记保存后的跳转逻辑
- [ ] 添加操作成功提示

### 任务 5: 添加调试和日志
- [ ] 添加开发模式日志
- [ ] 添加错误上报（可选）

## 实现文件

### web/src/lib/github-storage.ts
修复错误处理，添加优雅降级。

### web/src/lib/github-auth.ts
添加 token 验证和过期检测。

### web/src/pages/Home.tsx
改进加载策略和错误显示。

### web/src/pages/Star.tsx
添加更好的错误提示。

### web/src/pages/Note.tsx
添加保存状态提示。

## 测试计划

1. **未登录状态**: 访问收藏夹应提示登录
2. **添加收藏**: 从邮件链接点击收藏，验证数据保存
3. **添加笔记**: 验证笔记关联到收藏
4. **取消收藏**: 验证 UI 更新和数据同步
5. **Token 过期**: 模拟 401 错误，验证重新登录提示

## 验收标准

- [ ] 未登录用户看到友好的登录提示
- [ ] 登录后可以正常添加收藏
- [ ] 收藏后可以添加笔记
- [ ] 笔记正确关联到收藏
- [ ] 取消收藏后笔记仍然保留（仅笔记状态）
- [ ] Token 过期时提示重新登录
- [ ] 网络错误时有重试选项
- [ ] 修复后提供 HTML 预览
