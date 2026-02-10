/** Logout endpoint - clears cookies */

import type { VercelRequest, VercelResponse } from "@vercel/node";

export default function handler(req: VercelRequest, res: VercelResponse) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const isProduction = process.env.NODE_ENV === "production";

  res.setHeader("Set-Cookie", [
    `github_token=; HttpOnly; Path=/; Max-Age=0; ${isProduction ? "Secure; SameSite=None" : "SameSite=Lax"}`,
    `user_login=; Path=/; Max-Age=0; ${isProduction ? "Secure; SameSite=None" : "SameSite=Lax"}`,
  ]);

  res.status(200).json({ success: true });
}
