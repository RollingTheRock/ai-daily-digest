import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { saveToken, getCurrentUser } from "../lib/github-auth";

export default function Login() {
  const navigate = useNavigate();
  const [token, setToken] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleLogin = async () => {
    if (!token.trim()) {
      setError("请输入 Personal Access Token");
      return;
    }

    try {
      setLoading(true);
      setError(null);

      // 验证 token 有效性
      saveToken(token.trim());
      const user = await getCurrentUser();

      if (user) {
        navigate("/");
      } else {
        setError("Token 无效或已过期");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "登录失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-4">
      <div className="text-4xl mb-4">🔖</div>
      <h1 className="text-2xl font-semibold mb-2">AI Digest 收藏夹</h1>
      <p className="text-notion-muted mb-8 text-center max-w-md">
        收藏和整理你的AI日报内容，随时记录想法和笔记
      </p>

      <div className="card max-w-md w-full">
        <h2 className="text-lg font-semibold mb-4">使用 Personal Access Token 登录</h2>

        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 mb-4 text-sm text-amber-800">
          <p className="font-medium mb-1">如何获取 Token：</p>
          <ol className="list-decimal list-inside space-y-1 text-xs">
            <li>访问 <a href="https://github.com/settings/tokens/new" target="_blank" rel="noopener noreferrer" className="underline">github.com/settings/tokens/new</a></li>
            <li>Note 填写 "AI Daily Digest"</li>
            <li>Expiration 选择 "No expiration"</li>
            <li>勾选 "repo" 权限（访问私有仓库）</li>
            <li>点击 Generate token</li>
            <li>复制生成的 token（以 ghp_ 开头）</li>
          </ol>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Personal Access Token</label>
            <input
              type="password"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="ghp_xxxxxxxxxxxxxxxxxxxx"
              className="input w-full"
            />
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 text-sm">
              {error}
            </div>
          )}

          <button
            onClick={handleLogin}
            disabled={loading}
            className="btn-primary w-full flex items-center justify-center gap-2"
          >
            {loading ? (
              <>
                <span className="animate-spin">⏳</span>
                验证中...
              </>
            ) : (
              <>
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
                </svg>
                登录
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
