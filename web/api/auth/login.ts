/** GitHub OAuth login endpoint */

import type { VercelRequest, VercelResponse } from "@vercel/node";

const GITHUB_CLIENT_ID = process.env.GITHUB_CLIENT_ID || "";

export default function handler(req: VercelRequest, res: VercelResponse) {
  if (req.method !== "GET") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const { redirect } = req.query;
  const state = redirect && typeof redirect === "string" ? redirect : "/";

  // 优先使用 REDIRECT_URI 环境变量，否则根据 VERCEL_URL 生成
  const redirectUri = process.env.REDIRECT_URI
    ? process.env.REDIRECT_URI
    : process.env.VERCEL_URL
    ? `https://${process.env.VERCEL_URL}/api/auth/callback`
    : "http://localhost:3000/api/auth/callback";

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
