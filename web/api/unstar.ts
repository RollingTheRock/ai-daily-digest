/** Remove a star */

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
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const token = getTokenFromCookie(req);
  if (!token) {
    return res.status(401).json({ error: "Not authenticated" });
  }

  const { id } = req.body;

  if (!id) {
    return res.status(400).json({ error: "Missing id" });
  }

  try {
    const client = new GitHubDataClient(token);
    await client.removeStar(id);

    res.status(200).json({ success: true });
  } catch (error) {
    console.error("Error removing star:", error);
    res.status(500).json({ error: "Failed to remove star" });
  }
}
