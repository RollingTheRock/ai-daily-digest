/** List all stars and notes */

import type { VercelRequest, VercelResponse } from "@vercel/node";
import { GitHubDataClient } from "./_lib/github";

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
  if (req.method !== "GET") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const token = getTokenFromCookie(req);
  if (!token) {
    return res.status(401).json({ error: "Not authenticated" });
  }

  try {
    const client = new GitHubDataClient(token);

    const [stars, notes] = await Promise.all([client.getStars(), client.listNotes()]);

    const pendingAi = notes.filter((n) => !n.ai_enhanced).length;

    res.status(200).json({
      stars: stars.items,
      notes,
      stats: {
        total_stars: stars.items.length,
        total_notes: notes.length,
        pending_ai: pendingAi,
      },
    });
  } catch (error) {
    console.error("Error listing data:", error);
    res.status(500).json({ error: "Failed to list data" });
  }
}
