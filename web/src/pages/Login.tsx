import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { startDeviceFlow, waitForAuthorization, saveToken } from "../lib/github-auth";

export default function Login() {
  const navigate = useNavigate();
  const [deviceCode, setDeviceCode] = useState("");
  const [, setVerificationUri] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [, setPolling] = useState(false);

  const handleLogin = async () => {
    try {
      setLoading(true);
      setError(null);

      const deviceData = await startDeviceFlow();
      setDeviceCode(deviceData.user_code);
      setVerificationUri(deviceData.verification_uri);
      setPolling(true);

      // 自动打开验证页面
      window.open(deviceData.verification_uri, "_blank");

      // 开始轮询
      const token = await waitForAuthorization(
        deviceData.device_code,
        deviceData.interval,
        deviceData.expires_in,
        () => {
          // 轮询进度回调（可选）
        }
      );

      if (token.access_token) {
        saveToken(token.access_token);
        navigate("/");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "登录失败");
      setPolling(false);
    } finally {
      setLoading(false);
    }
  };

  const copyCode = () => {
    navigator.clipboard.writeText(deviceCode);
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-4">
      <div className="text-4xl mb-4">🔖</div>
      <h1 className="text-2xl font-semibold mb-2">AI Digest 收藏夹</h1>
      <p className="text-notion-muted mb-8 text-center max-w-md">
        收藏和整理你的AI日报内容，随时记录想法和笔记
      </p>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-4 mb-6 max-w-sm whitespace-pre-wrap text-sm">
          {error}
          <div className="mt-3 pt-3 border-t border-red-200">
            <button
              onClick={() => setError(null)}
              className="text-sm underline hover:text-red-800"
            >
              清除错误，重试
            </button>
          </div>
        </div>
      )}

      {!deviceCode ? (
        <button
          onClick={handleLogin}
          disabled={loading}
          className="btn-primary flex items-center gap-2"
        >
          {loading ? (
            <>
              <span className="animate-spin">⏳</span>
              准备中...
            </>
          ) : (
            <>
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
              </svg>
              使用 GitHub 登录
            </>
          )}
        </button>
      ) : (
        <div className="card max-w-sm w-full text-center">
          <div className="text-3xl mb-4">🔐</div>
          <h2 className="text-lg font-semibold mb-4">在 GitHub 上验证</h2>

          <div className="bg-notion-bg rounded-lg p-4 mb-4">
            <div className="text-sm text-notion-muted mb-2">输入此代码</div>
            <div className="flex items-center justify-center gap-2">
              <code className="text-2xl font-mono bg-white px-4 py-2 rounded border border-notion-border">
                {deviceCode}
              </code>
              <button
                onClick={copyCode}
                className="p-2 text-notion-muted hover:text-notion-text"
                title="复制"
              >
                📋
              </button>
            </div>
          </div>

          <p className="text-sm text-notion-muted mb-4">
            请在打开的 GitHub 页面中输入上方代码完成授权
          </p>

          <div className="flex items-center justify-center gap-2 text-notion-muted">
            <span className="animate-spin">⏳</span>
            等待授权...
          </div>
        </div>
      )}
    </div>
  );
}
