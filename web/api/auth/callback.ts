/** GitHub OAuth callback handler */

import type { VercelRequest, VercelResponse } from "@vercel/node";

const GITHUB_CLIENT_ID = process.env.GITHUB_CLIENT_ID || "";
const GITHUB_CLIENT_SECRET = process.env.GITHUB_CLIENT_SECRET || "";
// 优先使用 REDIRECT_URI 环境变量，否则根据 VERCEL_URL 生成
const REDIRECT_URI = process.env.REDIRECT_URI
  ? process.env.REDIRECT_URI
  : process.env.VERCEL_URL
  ? `https://${process.env.VERCEL_URL}/api/auth/callback`
  : "http://localhost:3000/api/auth/callback";

export default async function handler(req: VercelRequest, res: VercelResponse) {
  // eslint-disable-next-line no-console
  console.log("[OAuth Callback] handler called, path:", req.url);
  // eslint-disable-next-line no-console
  console.log("[OAuth Callback] redirect_uri:", REDIRECT_URI);

  if (req.method !== "GET") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const { code, state } = req.query;

  if (!code || typeof code !== "string") {
    return res.status(400).json({ error: "Missing authorization code" });
  }

  try {
    // Exchange code for access token
    const tokenResponse = await fetch(
      "https://github.com/login/oauth/access_token",
      {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          client_id: GITHUB_CLIENT_ID,
          client_secret: GITHUB_CLIENT_SECRET,
          code,
          redirect_uri: REDIRECT_URI,
        }),
      }
    );

    const tokenData = await tokenResponse.json();

    if (tokenData.error) {
      console.error("OAuth error:", tokenData);
      return res.status(400).json({ error: tokenData.error_description });
    }

    const accessToken = tokenData.access_token;

    // Get user info
    const userResponse = await fetch("https://api.github.com/user", {
      headers: {
        Authorization: `Bearer ${accessToken}`,
        Accept: "application/vnd.github.v3+json",
        "User-Agent": "ai-digest-web",
      },
    });

    const userData = await userResponse.json();

    // Set httpOnly cookie with token
    const cookieValue = Buffer.from(accessToken).toString("base64");
    const isProduction = process.env.NODE_ENV === "production";

    res.setHeader("Set-Cookie", [
      `github_token=${cookieValue}; HttpOnly; Path=/; Max-Age=604800; ${isProduction ? "Secure; SameSite=None" : "SameSite=Lax"}`,
      `user_login=${userData.login}; Path=/; Max-Age=604800; ${isProduction ? "Secure; SameSite=None" : "SameSite=Lax"}`,
    ]);

    // Redirect back to the app
    const redirectPath = state && typeof state === "string" ? state : "/";
    res.redirect(302, redirectPath);
  } catch (error) {
    console.error("Auth callback error:", error);
    res.status(500).json({ error: "Authentication failed" });
  }
}
