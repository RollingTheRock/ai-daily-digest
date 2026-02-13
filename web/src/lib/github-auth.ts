import { config } from "../config";

const STORAGE_KEY = "github_token";
const USER_KEY = "github_user";

export interface GitHubUser {
  login: string;
  avatar_url: string;
  name: string;
}

export interface DeviceFlowResponse {
  device_code: string;
  user_code: string;
  verification_uri: string;
  expires_in: number;
  interval: number;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  scope: string;
}

/**
 * 开始 Device Flow 认证
 */
export async function startDeviceFlow(): Promise<DeviceFlowResponse> {
  try {
    const response = await fetch("https://github.com/login/device/code", {
      method: "POST",
      mode: "cors",
      headers: {
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: new URLSearchParams({
        client_id: config.githubClientId,
        scope: "repo",
      }),
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`HTTP ${response.status}: ${error}`);
    }

    return response.json();
  } catch (error) {
    console.error("Device Flow Error:", error);
    if (error instanceof TypeError && error.message === "Failed to fetch") {
      throw new Error(
        "无法连接到 GitHub (Failed to fetch)。\n\n" +
        "可能原因：\n" +
        "1. 浏览器隐私模式阻止了跨域请求\n" +
        "2. 需要允许第三方 Cookie\n" +
        "3. 浏览器扩展阻止\n\n" +
        "请尝试：\n" +
        "• 关闭隐私/无痕模式\n" +
        "• 允许此网站的第三方 Cookie\n" +
        "• 禁用广告拦截器后重试"
      );
    }
    throw error;
  }
}

/**
 * 轮询获取 Token
 */
export async function pollForToken(
  deviceCode: string,
  _interval: number
): Promise<TokenResponse> {
  const response = await fetch("https://github.com/login/oauth/access_token", {
    method: "POST",
    mode: "cors",
    headers: {
      "Accept": "application/json",
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: new URLSearchParams({
      client_id: config.githubClientId,
      device_code: deviceCode,
      grant_type: "urn:ietf:params:oauth:grant-type:device_code",
    }),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Token poll failed: ${error}`);
  }

  const data = await response.json();

  // 处理错误状态
  if (data.error) {
    if (data.error === "authorization_pending") {
      return { access_token: "", token_type: "", scope: "" };
    }
    if (data.error === "slow_down") {
      // 需要降低轮询频率
      await new Promise((resolve) => setTimeout(resolve, 5000));
      return { access_token: "", token_type: "", scope: "" };
    }
    throw new Error(`OAuth error: ${data.error}`);
  }

  return data;
}

/**
 * 等待用户授权（带轮询）
 */
export async function waitForAuthorization(
  deviceCode: string,
  interval: number,
  expiresIn: number,
  onProgress?: () => void
): Promise<TokenResponse> {
  const startTime = Date.now();
  const maxTime = expiresIn * 1000;

  while (Date.now() - startTime < maxTime) {
    await new Promise((resolve) => setTimeout(resolve, interval * 1000));

    const token = await pollForToken(deviceCode, interval);

    if (token.access_token) {
      return token;
    }

    onProgress?.();
  }

  throw new Error("Device code expired");
}

/**
 * 保存 Token
 */
export function saveToken(token: string): void {
  localStorage.setItem(STORAGE_KEY, token);
}

/**
 * 获取 Token
 */
export function getToken(): string | null {
  return localStorage.getItem(STORAGE_KEY);
}

/**
 * 检查是否已登录
 */
export function isLoggedIn(): boolean {
  return !!getToken();
}

/**
 * 登出
 */
export function logout(): void {
  localStorage.removeItem(STORAGE_KEY);
  localStorage.removeItem(USER_KEY);
  window.location.href = "/ai-daily-digest/";
}

/**
 * 验证 Token 是否有效
 */
export async function validateToken(): Promise<boolean> {
  const token = getToken();
  if (!token) return false;

  try {
    const response = await fetch("https://api.github.com/user", {
      headers: {
        "Authorization": `Bearer ${token}`,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
      },
    });

    if (response.status === 401) {
      // Token 已过期，清理本地存储
      localStorage.removeItem(STORAGE_KEY);
      localStorage.removeItem(USER_KEY);
      return false;
    }

    return response.ok;
  } catch {
    return false;
  }
}

/**
 * 获取当前用户信息（带缓存）
 */
export async function getCurrentUser(): Promise<GitHubUser | null> {
  const token = getToken();
  if (!token) return null;

  // 检查缓存
  const cached = localStorage.getItem(USER_KEY);
  if (cached) {
    try {
      return JSON.parse(cached);
    } catch {
      // 缓存损坏，继续获取新数据
    }
  }

  const response = await fetch("https://api.github.com/user", {
    headers: {
      "Authorization": `Bearer ${token}`,
      "Accept": "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
    },
  });

  if (!response.ok) {
    if (response.status === 401) {
      // Token 无效或过期
      localStorage.removeItem(STORAGE_KEY);
      localStorage.removeItem(USER_KEY);
      throw new Error("GitHub Token 已过期或无效，请重新登录");
    }
    if (response.status === 403) {
      throw new Error("GitHub API 访问受限，请检查 Token 权限");
    }
    throw new Error(`获取用户信息失败: ${response.status} ${response.statusText}`);
  }

  const user: GitHubUser = await response.json();
  localStorage.setItem(USER_KEY, JSON.stringify(user));
  return user;
}

/**
 * 获取认证头
 */
export function getAuthHeaders(): Record<string, string> {
  const token = getToken();
  return {
    "Authorization": `Bearer ${token}`,
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
  };
}
