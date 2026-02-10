/** Star/save content to favorites */

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

  const { id, title, url, type, date, t: signature, tags = [] } = req.body;

  if (!id || !title || !url || !type || !date || !signature) {
    return res.status(400).json({ error: "Missing required fields" });
  }

  // Verify signature
  if (!verifySignature(id, date, signature)) {
    return res.status(403).json({ error: "Invalid signature" });
  }

  try {
    const client = new GitHubDataClient(token);
    await client.addStar({
      id,
      title,
      url,
      type,
      date,
      tags,
    });

    res.status(200).json({ success: true });
  } catch (error) {
    console.error("Error saving star:", error);
    res.status(500).json({ error: "Failed to save star" });
  }
}
