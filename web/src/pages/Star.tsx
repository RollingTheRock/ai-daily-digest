import { useState, useEffect } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { api } from "../utils/api";

export default function Star() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { user, loading: authLoading, login } = useAuth();

  const id = searchParams.get("id") || "";
  const title = searchParams.get("title") || "";
  const url = searchParams.get("url") || "";
  const type = searchParams.get("type") || "";
  const date = searchParams.get("date") || "";
  const signature = searchParams.get("t") || "";

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [tags, setTags] = useState<string[]>([]);
  const [tagInput, setTagInput] = useState("");

  useEffect(() => {
    if (!authLoading && !user) {
      // Save current path for redirect after login
      login(window.location.pathname + window.location.search);
    }
  }, [authLoading, user, login]);

  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-notion-muted">加载中...</div>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-notion-muted">正在跳转到登录页面...</div>
      </div>
    );
  }

  if (!id || !title || !url || !signature) {
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

  const handleAddTag = () => {
    if (tagInput.trim() && !tags.includes(tagInput.trim())) {
      setTags([...tags, tagInput.trim()]);
      setTagInput("");
    }
  };

  const handleRemoveTag = (tag: string) => {
    setTags(tags.filter((t) => t !== tag));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    try {
      setLoading(true);
      setError(null);

      await api.stars.add({
        id,
        title,
        url,
        type,
        date,
        t: signature,
        tags,
      });

      setSuccess(true);
      setTimeout(() => {
        navigate("/");
      }, 1500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "收藏失败");
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <div className="text-center">
          <div className="text-4xl mb-4">✅</div>
          <h1 className="text-xl font-semibold mb-2">已收藏</h1>
          <p className="text-notion-muted">正在跳转到收藏夹...</p>
        </div>
      </div>
    );
  }

  const getTypeIcon = () => {
    switch (type) {
      case "github":
        return "⭐";
      case "arxiv":
        return "📄";
      case "huggingface":
        return "🤗";
      case "blog":
        return "📝";
      default:
        return "🔖";
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="card">
          <div className="text-center mb-6">
            <div className="text-3xl mb-3">{getTypeIcon()}</div>
            <h1 className="text-xl font-semibold mb-2">确认收藏</h1>
          </div>

          <div className="bg-notion-bg rounded-lg p-4 mb-6">
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
            <div className="flex items-center gap-2 mt-2 text-xs text-notion-muted">
              <span className="tag">{type}</span>
              <span>{date}</span>
            </div>
          </div>

          <form onSubmit={handleSubmit}>
            {/* Tags */}
            <div className="mb-4">
              <label className="block text-sm font-medium mb-2">标签</label>
              <div className="flex gap-2 mb-2">
                <input
                  type="text"
                  value={tagInput}
                  onChange={(e) => setTagInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      handleAddTag();
                    }
                  }}
                  placeholder="添加标签..."
                  className="input flex-1"
                />
                <button
                  type="button"
                  onClick={handleAddTag}
                  className="btn-secondary"
                >
                  添加
                </button>
              </div>
              <div className="flex flex-wrap gap-2">
                {tags.map((tag) => (
                  <span
                    key={tag}
                    className="inline-flex items-center gap-1 px-2 py-1 bg-amber-100 text-amber-800 rounded text-xs"
                  >
                    {tag}
                    <button
                      type="button"
                      onClick={() => handleRemoveTag(tag)}
                      className="hover:text-amber-600"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            </div>

            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 mb-4 text-sm">
                {error}
              </div>
            )}

            <div className="flex gap-3">
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
                className="btn-accent flex-1"
              >
                {loading ? "保存中..." : "⭐ 确认收藏"}
              </button>
            </div>
          </form>

          <div className="mt-4 text-center">
            <a
              href={`/ai-digest/note?id=${encodeURIComponent(id)}&title=${encodeURIComponent(title)}&url=${encodeURIComponent(url)}&type=${type}&date=${date}&t=${signature}`}
              className="text-sm text-notion-muted hover:text-notion-text"
            >
              📝 收藏并记笔记 →
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
