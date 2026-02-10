/** Get current user info from cookie */

import type { VercelRequest, VercelResponse } from "@vercel/node";

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
    const userResponse = await fetch("https://api.github.com/user", {
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github.v3+json",
        "User-Agent": "ai-digest-web",
      },
    });

    if (!userResponse.ok) {
      return res.status(401).json({ error: "Invalid token" });
    }

    const userData = await userResponse.json();
    res.status(200).json({
      login: userData.login,
      avatar_url: userData.avatar_url,
      name: userData.name,
    });
  } catch (error) {
    console.error("Error fetching user:", error);
    res.status(500).json({ error: "Failed to fetch user" });
  }
}
