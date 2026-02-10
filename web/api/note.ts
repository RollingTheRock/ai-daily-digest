/** Save/update a note */

import type { VercelRequest, VercelResponse } from "@vercel/node";
import { GitHubDataClient } from "./_lib/github";
import { verifySignature } from "./_lib/crypto";

function getTokenFromCookie(req: VercelRequest): string | null {
  const cookie = req.headers.cookie;
  if (!cookie) return null;

  const match = cookie.match(/github_token=([^;]+)/);
  if (!match) return null;

  try {
    return Buffer.from(decodeURIComponent(match[1]), "base64").toString("utf-8");
  } catch {
    return null;
  }
}

export default async function handler(req: VercelRequest, res: VercelResponse) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const token = getTokenFromCookie(req);
  if (!token) {
    return res.status(401).json({ error: "Not authenticated" });
  }

  const {
    content_id,
    content_title,
    content_url,
    content_type,
    date,
    t: signature,
    thoughts = "",
    questions = "",
    todos = "",
    request_ai = false,
  } = req.body;

  if (!content_id || !content_title || !content_url || !content_type || !date || !signature) {
    return res.status(400).json({ error: "Missing required fields" });
  }

  // Verify signature
  if (!verifySignature(content_id, date, signature)) {
    return res.status(403).json({ error: "Invalid signature" });
  }

  try {
    const client = new GitHubDataClient(token);

    const noteId = `note-${date.replace(/-/g, "")}-${content_id.replace(/[^a-zA-Z0-9]/g, "-").slice(0, 30)}`;

    // Build note content
    const noteContent = `## 💭 想法
${thoughts || "无"}

## ❓ 疑问
${questions || "无"}

## ✅ TODO
${todos || "- [ ] "}

---

## 🤖 AI 增强

${request_ai ? "待处理..." : "未请求"}
`;

    const now = new Date().toISOString();

    await client.saveNote({
      id: noteId,
      content_id,
      content_title,
      content_url,
      content_type,
      date,
      created_at: now,
      ai_enhanced: false,
      content: noteContent,
    });

    // Also star the content
    await client.addStar({
      id: content_id,
      title: content_title,
      url: content_url,
      type: content_type,
      date,
      tags: [],
      note_id: noteId,
    });

    res.status(200).json({
      success: true,
      note_id: noteId,
      ai_enhanced: request_ai,
    });
  } catch (error) {
    console.error("Error saving note:", error);
    res.status(500).json({ error: "Failed to save note" });
  }
}
