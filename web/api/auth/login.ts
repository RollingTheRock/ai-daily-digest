/** GitHub OAuth login endpoint */

import type { VercelRequest, VercelResponse } from "@vercel/node";

const GITHUB_CLIENT_ID = process.env.GITHUB_CLIENT_ID || "";

export default function handler(req: VercelRequest, res: VercelResponse) {
  if (req.method !== "GET") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const { redirect } = req.query;
  const state = redirect && typeof redirect === "string" ? redirect : "/";

  // 必须使用与 GitHub OAuth App 中设置的完全一致的 callback URL
  // 请确保在 Vercel 环境变量中设置 REDIRECT_URI
  const redirectUri = process.env.REDIRECT_URI
    || "https://ai-daily-digest-89phfxl8p-rollingtherocks-projects.vercel.app/api/auth/callback";

  // eslint-disable-next-line no-console
  console.log("[OAuth Login] redirect_uri:", redirectUri);

  const githubAuthUrl =
    `https://github.com/login/oauth/authorize?` +
    `client_id=${GITHUB_CLIENT_ID}` +
    `&redirect_uri=${encodeURIComponent(redirectUri)}` +
    `&scope=repo` +
    `&state=${encodeURIComponent(state)}`;

  res.redirect(302, githubAuthUrl);
}
