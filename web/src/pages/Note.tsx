import { useState, useEffect } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { isLoggedIn, getCurrentUser, type GitHubUser } from "../lib/github-auth";
import { addNote, addStar, type StarItem } from "../lib/github-storage";
import { config } from "../config";

export default function Note() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const id = searchParams.get("id") || "";
  const title = searchParams.get("title") || "";
  const url = searchParams.get("url") || "";
  const type = searchParams.get("type") || "";
  const date = searchParams.get("date") || "";

  const [user, setUser] = useState<GitHubUser | null>(null);
  const [checkingAuth, setCheckingAuth] = useState(true);
  const [thoughts, setThoughts] = useState("");
  const [questions, setQuestions] = useState("");
  const [todos, setTodos] = useState("");
  const [requestAi, setRequestAi] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    checkAuth();
  }, []);

  const checkAuth = async () => {
    if (!isLoggedIn()) {
      setCheckingAuth(false);
      return;
    }

    try {
      const userData = await getCurrentUser();
      setUser(userData);
    } catch {
      // 认证失败，会在渲染时处理
    } finally {
      setCheckingAuth(false);
    }
  };

  if (checkingAuth) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-notion-muted">加载中...</div>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center p-4">
        <div className="text-4xl mb-4">📝</div>
        <h1 className="text-xl font-semibold mb-2">需要登录</h1>
        <p className="text-notion-muted mb-6 text-center max-w-md">
          请先登录后再添加笔记
        </p>
        <button onClick={() => navigate("/login")} className="btn-primary">
          去登录
        </button>
      </div>
    );
  }

  if (!id || !title || !url) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <div className="text-center">
          <div className="text-4xl mb-4">⚠️</div>
          <h1 className="text-xl font-semibold mb-2">无效的链接</h1>
          <p className="text-notion-muted">缺少必要的参数</p>
        </div>
      </div>
    );
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    try {
      setLoading(true);
      setError(null);

      // 先添加收藏（如果不存在）
      const starData: Omit<StarItem, "starred_at"> = {
        id,
        title,
        url,
        type,
        date,
        tags: [],
      };
      await addStar(starData);

      // 再添加笔记
      await addNote(
        id,
        title,
        url,
        type,
        date,
        thoughts,
        questions,
        todos
      );

      setSuccess(true);
      setTimeout(() => {
        navigate("/");
      }, 1500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存笔记失败");
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <div className="text-center">
          <div className="text-4xl mb-4">✅</div>
          <h1 className="text-xl font-semibold mb-2">笔记已保存</h1>
          <p className="text-notion-muted">正在跳转到收藏夹...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-4">
      <div className="max-w-2xl mx-auto">
        <div className="card">
          <div className="mb-6">
            <div className="flex items-center gap-2 mb-4">
              <span className="text-2xl">📝</span>
              <h1 className="text-xl font-semibold">写笔记</h1>
            </div>

            <div className="bg-notion-bg rounded-lg p-4">
              <div className="text-sm text-notion-muted mb-1">正在为</div>
              <h2 className="font-medium mb-1 truncate" title={title}>
                {title}
              </h2>
              <a
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-blue-600 hover:underline truncate block"
              >
                {url.replace(/^https?:\/\//, "").slice(0, 50)}...
              </a>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Thoughts */}
            <div>
              <label className="block text-sm font-medium mb-2">
                💭 想法
              </label>
              <textarea
                value={thoughts}
                onChange={(e) => setThoughts(e.target.value)}
                placeholder="记录下你的想法、见解..."
                className="textarea"
                rows={4}
              />
            </div>

            {/* Questions */}
            <div>
              <label className="block text-sm font-medium mb-2">
                ❓ 疑问
              </label>
              <textarea
                value={questions}
                onChange={(e) => setQuestions(e.target.value)}
                placeholder="有什么不理解的地方？"
                className="textarea"
                rows={3}
              />
            </div>

            {/* TODOs */}
            <div>
              <label className="block text-sm font-medium mb-2">
                ✅ TODO
              </label>
              <textarea
                value={todos}
                onChange={(e) => setTodos(e.target.value)}
                placeholder="- [ ] 阅读文档\n- [ ] 尝试运行"
                className="textarea"
                rows={3}
              />
            </div>

            {/* AI Enhancement - 仅在功能开启时显示 */}
            {config.features.aiEnhancement && (
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="requestAi"
                  checked={requestAi}
                  onChange={(e) => setRequestAi(e.target.checked)}
                  className="w-4 h-4 rounded border-notion-border"
                />
                <label htmlFor="requestAi" className="text-sm cursor-pointer">
                  <span className="font-medium">🤖 AI 增强</span>
                  <span className="text-notion-muted ml-1">
                    （润色内容、延伸调研、行动建议）
                  </span>
                </label>
              </div>
            )}

            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 text-sm">
                <div className="flex items-center gap-2">
                  <span>⚠️</span>
                  <span>{error}</span>
                </div>
                {error.includes("重新登录") && (
                  <button
                    onClick={() => navigate("/login")}
                    className="mt-2 text-sm underline hover:text-red-800"
                  >
                    去登录页面
                  </button>
                )}
              </div>
            )}

            <div className="flex gap-3 pt-4">
              <button
                type="button"
                onClick={() => navigate("/")}
                className="btn-secondary flex-1"
              >
                取消
              </button>
              <button
                type="submit"
                disabled={loading}
                className="btn-primary flex-1"
              >
                {loading ? "保存中..." : "💾 保存笔记"}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
