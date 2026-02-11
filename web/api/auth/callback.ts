/** GitHub OAuth callback handler */

import type { VercelRequest, VercelResponse } from "@vercel/node";

const GITHUB_CLIENT_ID = process.env.GITHUB_CLIENT_ID || "";
const GITHUB_CLIENT_SECRET = process.env.GITHUB_CLIENT_SECRET || "";
// 必须使用与 GitHub OAuth App 中设置的完全一致的 callback URL
// 请确保在 Vercel 环境变量中设置 REDIRECT_URI
const REDIRECT_URI = process.env.REDIRECT_URI
  || "https://ai-daily-digest-89phfxl8p-rollingtherocks-projects.vercel.app/api/auth/callback";

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
