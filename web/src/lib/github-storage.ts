import { config } from "../config";
import { getToken, getAuthHeaders, getCurrentUser } from "./github-auth";

// 本地缓存键
const STARS_CACHE_KEY = "aidigest_stars_cache";
const STARS_CACHE_TIME_KEY = "aidigest_stars_cache_time";
const NOTES_CACHE_KEY = "aidigest_notes_cache";
const NOTES_CACHE_TIME_KEY = "aidigest_notes_cache_time";
const CACHE_VALIDITY_MS = 5 * 60 * 1000; // 5分钟缓存有效期

// 数据类型定义
export interface StarItem {
  id: string;
  title: string;
  url: string;
  type: string;
  date: string;
  starred_at: string;
  tags: string[];
  note_id?: string;
}

export interface NoteItem {
  id: string;
  content_id: string;
  content_title: string;
  content_url: string;
  content_type: string;
  date: string;
  created_at: string;
  updated_at: string;
  ai_enhanced: boolean;
  thoughts: string;
  questions: string;
  todos: string;
}

// GitHub API 基础 URL
const GITHUB_API = "https://api.github.com";

/**
 * 获取数据仓库的完整名称 (owner/repo)
 */
async function getRepoFullName(): Promise<string> {
  const user = await getCurrentUser();
  if (!user) throw new Error("Not authenticated");
  return `${user.login}/${config.dataRepoName}`;
}

/**
 * 确保数据仓库存在，不存在则创建
 */
export async function ensureDataRepo(): Promise<void> {
  const token = getToken();
  if (!token) throw new Error("Not authenticated");

  const user = await getCurrentUser();
  if (!user) throw new Error("Not authenticated");

  // 检查仓库是否存在
  const response = await fetch(`${GITHUB_API}/repos/${user.login}/${config.dataRepoName}`, {
    headers: getAuthHeaders(),
  });

  if (response.status === 404) {
    // 创建仓库
    const createResponse = await fetch(`${GITHUB_API}/user/repos`, {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({
        name: config.dataRepoName,
        description: "AI Daily Digest 数据存储",
        private: true,
        auto_init: true,
      }),
    });

    if (!createResponse.ok) {
      const errorText = await createResponse.text();
      // 422 表示仓库已存在（可能是并发创建或其他原因）
      if (createResponse.status === 422 && errorText.includes("already exists")) {
        // 仓库已存在，继续初始化
        console.log("Repository already exists, skipping creation");
      } else {
        throw new Error(`Failed to create repo: ${errorText}`);
      }
    }

    // 等待仓库初始化
    await new Promise((resolve) => setTimeout(resolve, 2000));

    // 初始化数据文件
    await initDataFiles();
  } else if (!response.ok) {
    // 其他错误（401, 403等）
    throw new Error(`Failed to check repo: ${response.status} ${response.statusText}`);
  }

  // 仓库已存在，检查数据文件是否存在（仅在必要时初始化）
  const repo = `${user.login}/${config.dataRepoName}`;
  const starsExist = await readFile(repo, "data/stars.json");
  if (starsExist === null) {
    console.log("Data files not found, initializing...");
    await initDataFiles();
  }
}

/**
 * 初始化数据文件
 */
async function initDataFiles(): Promise<void> {
  const repo = await getRepoFullName();

  // 创建空的 stars.json
  await createOrUpdateFile(repo, "data/stars.json", JSON.stringify([], null, 2), "Initialize stars data");

  // 创建空的 notes.json
  await createOrUpdateFile(repo, "data/notes.json", JSON.stringify([], null, 2), "Initialize notes data");
}

/**
 * 创建或更新文件
 */
async function createOrUpdateFile(
  repo: string,
  path: string,
  content: string,
  message: string
): Promise<void> {
  const token = getToken();
  if (!token) throw new Error("Not authenticated");

  console.log(`[createOrUpdateFile] ${path} in ${repo}`);

  // 检查文件是否存在以获取 SHA
  const existingResponse = await fetch(`${GITHUB_API}/repos/${repo}/contents/${path}`, {
    headers: getAuthHeaders(),
  });

  let sha: string | undefined;
  if (existingResponse.ok) {
    const existing = await existingResponse.json();
    sha = existing.sha;
    console.log(`[createOrUpdateFile] File exists, sha: ${sha?.substring(0, 8)}...`);
  } else if (existingResponse.status === 404) {
    console.log(`[createOrUpdateFile] File does not exist, will create new`);
  } else {
    console.error(`[createOrUpdateFile] Error checking file: ${existingResponse.status}`);
  }

  // 使用支持 Unicode 的 Base64 编码
  const base64Content = (() => {
    const utf8Bytes = new TextEncoder().encode(content);
    const binaryString = Array.from(utf8Bytes, (byte) => String.fromCharCode(byte)).join("");
    return btoa(binaryString);
  })();

  const body: Record<string, unknown> = {
    message,
    content: base64Content,
  };

  if (sha) {
    body.sha = sha;
  }

  console.log(`[createOrUpdateFile] Sending PUT request...`);
  const response = await fetch(`${GITHUB_API}/repos/${repo}/contents/${path}`, {
    method: "PUT",
    headers: getAuthHeaders(),
    body: JSON.stringify(body),
  });

  if (response.status === 401) {
    throw new Error("GitHub 认证已过期，请重新登录");
  }

  if (response.status === 403) {
    throw new Error("没有权限写入仓库，请检查 Token 是否有 repo 权限");
  }

  if (response.status === 409) {
    throw new Error("文件冲突，请刷新页面后重试");
  }

  if (!response.ok) {
    const error = await response.text();
    console.error(`[createOrUpdateFile] Failed: ${response.status} ${error}`);
    throw new Error(`保存失败: ${response.status} ${error}`);
  }

  console.log(`[createOrUpdateFile] Success: ${response.status}`);
}

/**
 * 读取文件内容
 */
async function readFile(repo: string, path: string): Promise<string | null> {
  const response = await fetch(`${GITHUB_API}/repos/${repo}/contents/${path}`, {
    headers: getAuthHeaders(),
  });

  if (response.status === 404) {
    return null;
  }

  if (response.status === 401) {
    throw new Error("GitHub 认证已过期，请重新登录");
  }

  if (response.status === 403) {
    const rateLimitRemaining = response.headers.get("X-RateLimit-Remaining");
    if (rateLimitRemaining === "0") {
      throw new Error("GitHub API 速率限制已达上限，请稍后再试");
    }
    throw new Error("没有权限访问该仓库，请检查 Token 是否有 repo 权限");
  }

  if (!response.ok) {
    const errorText = await response.text().catch(() => response.statusText);
    throw new Error(`读取文件失败: ${response.status} ${errorText}`);
  }

  const data = await response.json();
  // 使用支持 Unicode 的 Base64 解码
  const base64Content = data.content.replace(/\s/g, "");
  const utf8Bytes = Uint8Array.from(atob(base64Content), (c) => c.charCodeAt(0));
  return new TextDecoder().decode(utf8Bytes);
}

// ==================== Cache API ====================

/**
 * 从本地缓存获取 stars
 */
function getCachedStars(): StarItem[] | null {
  try {
    const cached = localStorage.getItem(STARS_CACHE_KEY);
    const cachedTime = localStorage.getItem(STARS_CACHE_TIME_KEY);

    if (!cached || !cachedTime) return null;

    const age = Date.now() - parseInt(cachedTime, 10);
    if (age > CACHE_VALIDITY_MS) return null;

    return JSON.parse(cached);
  } catch {
    return null;
  }
}

/**
 * 保存 stars 到本地缓存
 */
function setCachedStars(stars: StarItem[]): void {
  try {
    localStorage.setItem(STARS_CACHE_KEY, JSON.stringify(stars));
    localStorage.setItem(STARS_CACHE_TIME_KEY, Date.now().toString());
  } catch {
    // 忽略缓存错误
  }
}

/**
 * 清除 stars 缓存
 */
export function invalidateStarsCache(): void {
  try {
    localStorage.removeItem(STARS_CACHE_KEY);
    localStorage.removeItem(STARS_CACHE_TIME_KEY);
  } catch {
    // 忽略错误
  }
}

/**
 * 从本地缓存获取 notes
 */
function getCachedNotes(): NoteItem[] | null {
  try {
    const cached = localStorage.getItem(NOTES_CACHE_KEY);
    const cachedTime = localStorage.getItem(NOTES_CACHE_TIME_KEY);

    if (!cached || !cachedTime) return null;

    const age = Date.now() - parseInt(cachedTime, 10);
    if (age > CACHE_VALIDITY_MS) return null;

    return JSON.parse(cached);
  } catch {
    return null;
  }
}

/**
 * 保存 notes 到本地缓存
 */
function setCachedNotes(notes: NoteItem[]): void {
  try {
    localStorage.setItem(NOTES_CACHE_KEY, JSON.stringify(notes));
    localStorage.setItem(NOTES_CACHE_TIME_KEY, Date.now().toString());
  } catch {
    // 忽略缓存错误
  }
}

/**
 * 清除 notes 缓存
 */
export function invalidateNotesCache(): void {
  try {
    localStorage.removeItem(NOTES_CACHE_KEY);
    localStorage.removeItem(NOTES_CACHE_TIME_KEY);
  } catch {
    // 忽略错误
  }
}

// ==================== Stars API ====================

/**
 * 获取所有收藏（优先从缓存读取，支持优雅降级）
 */
export async function getStars(): Promise<StarItem[]> {
  // 先尝试从缓存读取
  const cached = getCachedStars();
  if (cached) {
    console.log("[getStars] Returning cached data:", cached.length, "items");
  }

  try {
    await ensureDataRepo();
    const repo = await getRepoFullName();

    const content = await readFile(repo, "data/stars.json");
    if (!content) {
      console.log("[getStars] No content from server");
      return cached || [];
    }

    try {
      const stars = JSON.parse(content) as StarItem[];
      console.log("[getStars] From server:", stars.length, "items");
      // 更新缓存
      setCachedStars(stars);
      return stars;
    } catch (e) {
      console.error("[getStars] Parse error:", e);
      return cached || [];
    }
  } catch (error) {
    // 认证错误或其他错误时，返回缓存数据
    console.error("[getStars] Error fetching from server:", error);
    if (cached) {
      console.log("[getStars] Returning cached data due to error");
      return cached;
    }
    throw error;
  }
}

/**
 * 添加收藏
 */
export async function addStar(star: Omit<StarItem, "starred_at">): Promise<StarItem> {
  console.log("[addStar] Starting...", star);
  await ensureDataRepo();
  const repo = await getRepoFullName();
  console.log("[addStar] Repo:", repo);

  const stars = await getStars();
  console.log("[addStar] Existing stars count:", stars.length);

  const newStar: StarItem = {
    ...star,
    starred_at: new Date().toISOString(),
  };

  // 检查是否已存在
  const existingIndex = stars.findIndex((s) => s.id === star.id);
  if (existingIndex >= 0) {
    stars[existingIndex] = { ...stars[existingIndex], ...newStar };
  } else {
    stars.unshift(newStar);
  }

  console.log("[addStar] Writing to file, total stars:", stars.length);
  await createOrUpdateFile(repo, "data/stars.json", JSON.stringify(stars, null, 2), `Add star: ${star.title}`);
  console.log("[addStar] File written successfully");

  // 更新本地缓存
  setCachedStars(stars);
  console.log("[addStar] Cache updated");

  return newStar;
}

/**
 * 移除收藏
 */
export async function removeStar(id: string): Promise<void> {
  await ensureDataRepo();
  const repo = await getRepoFullName();

  const stars = await getStars();
  const filtered = stars.filter((s) => s.id !== id);

  if (filtered.length === stars.length) {
    throw new Error("Star not found");
  }

  await createOrUpdateFile(repo, "data/stars.json", JSON.stringify(filtered, null, 2), `Remove star: ${id}`);

  // 更新本地缓存
  setCachedStars(filtered);
}

/**
 * 检查是否已收藏
 */
export async function isStarred(id: string): Promise<boolean> {
  const stars = await getStars();
  return stars.some((s) => s.id === id);
}

/**
 * 更新收藏标签
 */
export async function updateStarTags(id: string, tags: string[]): Promise<void> {
  await ensureDataRepo();
  const repo = await getRepoFullName();

  const stars = await getStars();
  const star = stars.find((s) => s.id === id);

  if (!star) {
    throw new Error("Star not found");
  }

  star.tags = tags;
  await createOrUpdateFile(repo, "data/stars.json", JSON.stringify(stars, null, 2), `Update tags for: ${star.title}`);
}

// ==================== Notes API ====================

/**
 * 获取所有笔记（优先从缓存读取，支持优雅降级）
 */
export async function getNotes(): Promise<NoteItem[]> {
  // 先尝试从缓存读取
  const cached = getCachedNotes();
  if (cached) {
    console.log("[getNotes] Returning cached data:", cached.length, "items");
  }

  try {
    await ensureDataRepo();
    const repo = await getRepoFullName();

    const content = await readFile(repo, "data/notes.json");
    if (!content) {
      console.log("[getNotes] No content from server");
      return cached || [];
    }

    try {
      const notes = JSON.parse(content) as NoteItem[];
      console.log("[getNotes] From server:", notes.length, "items");
      // 更新缓存
      setCachedNotes(notes);
      return notes;
    } catch (e) {
      console.error("[getNotes] Parse error:", e);
      return cached || [];
    }
  } catch (error) {
    // 认证错误或其他错误时，返回缓存数据
    console.error("[getNotes] Error fetching from server:", error);
    if (cached) {
      console.log("[getNotes] Returning cached data due to error");
      return cached;
    }
    throw error;
  }
}

/**
 * 根据内容 ID 获取笔记
 */
export async function getNoteByContentId(contentId: string): Promise<NoteItem | null> {
  const notes = await getNotes();
  return notes.find((n) => n.content_id === contentId) || null;
}

/**
 * 添加笔记（如果已存在则更新）
 */
export async function addNote(
  contentId: string,
  contentTitle: string,
  contentUrl: string,
  contentType: string,
  date: string,
  thoughts: string,
  questions: string,
  todos: string
): Promise<NoteItem> {
  await ensureDataRepo();
  const repo = await getRepoFullName();

  const notes = await getNotes();

  // 检查是否已有该内容的笔记
  const existingIndex = notes.findIndex((n) => n.content_id === contentId);

  if (existingIndex >= 0) {
    // 更新现有笔记
    notes[existingIndex] = {
      ...notes[existingIndex],
      thoughts,
      questions,
      todos,
      updated_at: new Date().toISOString(),
    };

    await createOrUpdateFile(
      repo,
      "data/notes.json",
      JSON.stringify(notes, null, 2),
      `Update note for: ${contentTitle}`
    );

    // 更新 star 的 note_id（如果存在）
    const stars = await getStars();
    const star = stars.find((s) => s.id === contentId);
    if (star && !star.note_id) {
      star.note_id = notes[existingIndex].id;
      await createOrUpdateFile(
        repo,
        "data/stars.json",
        JSON.stringify(stars, null, 2),
        `Link note to star: ${contentTitle}`
      );
    }

    // 更新笔记缓存
    setCachedNotes(notes);

    return notes[existingIndex];
  }

  // 创建新笔记
  const now = new Date().toISOString();
  const newNote: NoteItem = {
    id: `note_${Date.now()}`,
    content_id: contentId,
    content_title: contentTitle,
    content_url: contentUrl,
    content_type: contentType,
    date,
    created_at: now,
    updated_at: now,
    ai_enhanced: false,
    thoughts,
    questions,
    todos,
  };

  notes.unshift(newNote);

  await createOrUpdateFile(repo, "data/notes.json", JSON.stringify(notes, null, 2), `Add note for: ${contentTitle}`);

  // 同时更新 star 的 note_id
  const stars = await getStars();
  const star = stars.find((s) => s.id === contentId);
  if (star) {
    star.note_id = newNote.id;
    await createOrUpdateFile(repo, "data/stars.json", JSON.stringify(stars, null, 2), `Link note to star: ${contentTitle}`);
  }

  // 更新笔记缓存
  setCachedNotes(notes);

  return newNote;
}

/**
 * 更新笔记
 */
export async function updateNote(
  noteId: string,
  updates: Partial<Omit<NoteItem, "id" | "content_id" | "created_at">>
): Promise<NoteItem> {
  await ensureDataRepo();
  const repo = await getRepoFullName();

  const notes = await getNotes();
  const noteIndex = notes.findIndex((n) => n.id === noteId);

  if (noteIndex === -1) {
    throw new Error("Note not found");
  }

  notes[noteIndex] = {
    ...notes[noteIndex],
    ...updates,
    updated_at: new Date().toISOString(),
  };

  await createOrUpdateFile(
    repo,
    "data/notes.json",
    JSON.stringify(notes, null, 2),
    `Update note: ${notes[noteIndex].content_title}`
  );

  // 更新笔记缓存
  setCachedNotes(notes);

  return notes[noteIndex];
}

/**
 * 删除笔记
 */
export async function deleteNote(noteId: string): Promise<void> {
  await ensureDataRepo();
  const repo = await getRepoFullName();

  const notes = await getNotes();
  const note = notes.find((n) => n.id === noteId);

  if (!note) {
    throw new Error("Note not found");
  }

  const filtered = notes.filter((n) => n.id !== noteId);

  await createOrUpdateFile(repo, "data/notes.json", JSON.stringify(filtered, null, 2), `Delete note: ${note.content_title}`);

  // 同时移除 star 的 note_id
  const stars = await getStars();
  const star = stars.find((s) => s.id === note.content_id);
  if (star) {
    delete star.note_id;
    await createOrUpdateFile(repo, "data/stars.json", JSON.stringify(stars, null, 2), `Unlink note from star: ${star.title}`);
  }

  // 更新笔记缓存
  setCachedNotes(filtered);
}

// ==================== Stats API ====================

/**
 * 获取统计信息
 */
export async function getStats(): Promise<{
  total_stars: number;
  total_notes: number;
  pending_ai: number;
}> {
  const [stars, notes] = await Promise.all([getStars(), getNotes()]);

  return {
    total_stars: stars.length,
    total_notes: notes.length,
    pending_ai: notes.filter((n) => !n.ai_enhanced).length,
  };
}
