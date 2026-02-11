import { config } from "../config";
import { getToken, getAuthHeaders, getCurrentUser } from "./github-auth";

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

  // 仓库已存在，确保数据文件也存在
  // 等待一下确保仓库完全可用
  await new Promise((resolve) => setTimeout(resolve, 500));
  await initDataFiles().catch(() => {
    // 忽略初始化错误（文件可能已存在）
  });
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

  // 检查文件是否存在以获取 SHA
  const existingResponse = await fetch(`${GITHUB_API}/repos/${repo}/contents/${path}`, {
    headers: getAuthHeaders(),
  });

  let sha: string | undefined;
  if (existingResponse.ok) {
    const existing = await existingResponse.json();
    sha = existing.sha;
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

  const response = await fetch(`${GITHUB_API}/repos/${repo}/contents/${path}`, {
    method: "PUT",
    headers: getAuthHeaders(),
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Failed to save file: ${error}`);
  }
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

  if (!response.ok) {
    throw new Error(`Failed to read file: ${response.statusText}`);
  }

  const data = await response.json();
  return atob(data.content);
}

// ==================== Stars API ====================

/**
 * 获取所有收藏
 */
export async function getStars(): Promise<StarItem[]> {
  await ensureDataRepo();
  const repo = await getRepoFullName();

  const content = await readFile(repo, "data/stars.json");
  if (!content) return [];

  try {
    return JSON.parse(content);
  } catch {
    return [];
  }
}

/**
 * 添加收藏
 */
export async function addStar(star: Omit<StarItem, "starred_at">): Promise<StarItem> {
  await ensureDataRepo();
  const repo = await getRepoFullName();

  const stars = await getStars();

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

  await createOrUpdateFile(repo, "data/stars.json", JSON.stringify(stars, null, 2), `Add star: ${star.title}`);

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
 * 获取所有笔记
 */
export async function getNotes(): Promise<NoteItem[]> {
  await ensureDataRepo();
  const repo = await getRepoFullName();

  const content = await readFile(repo, "data/notes.json");
  if (!content) return [];

  try {
    return JSON.parse(content);
  } catch {
    return [];
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
 * 添加笔记
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
