import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { isLoggedIn, getCurrentUser, logout, type GitHubUser } from "../lib/github-auth";
import { getStars, removeStar, getStats, getNotes, invalidateStarsCache, getNoteByContentId, type StarItem, type NoteItem } from "../lib/github-storage";

export default function Home() {
  const navigate = useNavigate();
  const [user, setUser] = useState<GitHubUser | null>(null);
  const [stars, setStars] = useState<StarItem[]>([]);
  const [stats, setStats] = useState({ total_stars: 0, total_notes: 0, pending_ai: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("all");
  const [viewingNote, setViewingNote] = useState<NoteItem | null>(null);
  const [loadingNote, setLoadingNote] = useState(false);
  const [orphanNotes, setOrphanNotes] = useState<NoteItem[]>([]); // 没有收藏的笔记

  useEffect(() => {
    checkAuthAndLoadData();

    // 页面重新获得焦点时刷新数据（从其他页面返回时）
    const handleFocus = () => {
      if (isLoggedIn()) {
        loadData();
      }
    };

    window.addEventListener("focus", handleFocus);
    return () => window.removeEventListener("focus", handleFocus);
  }, []);

  const checkAuthAndLoadData = async () => {
    if (!isLoggedIn()) {
      setLoading(false);
      return;
    }

    try {
      const userData = await getCurrentUser();
      setUser(userData);
      if (userData) {
        await loadData();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "认证失败");
      setLoading(false);
    }
  };

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);

      const [starsData, statsData, notesData] = await Promise.all([
        getStars(),
        getStats(),
        getNotes()
      ]);
      setStars(starsData);
      setStats(statsData);

      // 找出没有对应收藏的笔记（孤立笔记）
      const starIds = new Set(starsData.map(s => s.id));
      const orphanNotesData = notesData.filter(n => !starIds.has(n.content_id));
      setOrphanNotes(orphanNotesData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载数据失败");
    } finally {
      setLoading(false);
    }
  };

  const handleUnstar = async (id: string) => {
    try {
      await removeStar(id);
      setStars((prev) => prev.filter((s) => s.id !== id));
      setStats((prev) => ({ ...prev, total_stars: prev.total_stars - 1 }));
    } catch (err) {
      alert(err instanceof Error ? err.message : "取消收藏失败");
    }
  };

  const handleLogout = () => {
    logout();
  };

  const handleViewNote = async (star: StarItem) => {
    if (!star.note_id) return;

    try {
      setLoadingNote(true);
      const note = await getNoteByContentId(star.id);
      if (note) {
        setViewingNote(note);
      } else {
        alert("笔记未找到");
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : "加载笔记失败");
    } finally {
      setLoadingNote(false);
    }
  };

  const filteredStars = stars.filter((star) => {
    if (filter === "all") return true;
    if (filter === "github") return star.type === "github";
    if (filter === "arxiv") return star.type === "arxiv";
    if (filter === "huggingface") return star.type === "huggingface";
    if (filter === "blog") return star.type === "blog";
    if (filter === "with_notes") return star.note_id;
    return true;
  });

  // 将孤儿笔记转换为虚拟 StarItem 以便统一渲染
  const orphanNotesAsStars: StarItem[] = orphanNotes.map(note => ({
    id: note.content_id,
    title: note.content_title,
    url: note.content_url,
    type: note.content_type,
    date: note.date,
    starred_at: note.created_at,
    tags: [],
    note_id: note.id,
  }));

  // 合并收藏和孤儿笔记
  const allItems = [...filteredStars, ...orphanNotesAsStars];

  // 过滤孤儿笔记（只在 "all" 或 "with_notes" 筛选器下显示）
  const filteredItems = allItems.filter(item => {
    if (filter === 'all') return true;
    if (filter === 'with_notes') return item.note_id;
    // 孤儿笔记没有 star，所以不显示在其他类型筛选下
    if (orphanNotesAsStars.some(o => o.id === item.id)) {
      return filter === 'all' || filter === 'with_notes';
    }
    return true;
  });

  // Group by date
  const groupedItems = filteredItems.reduce((acc, item) => {
    const date = item.date;
    if (!acc[date]) acc[date] = [];
    acc[date].push(item);
    return acc;
  }, {} as Record<string, StarItem[]>);

  const sortedDates = Object.keys(groupedItems).sort().reverse();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-notion-muted">加载中...</div>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center p-4">
        <div className="text-4xl mb-4">🔖</div>
        <h1 className="text-2xl font-semibold mb-2">AI Digest 收藏夹</h1>
        <p className="text-notion-muted mb-8 text-center max-w-md">
          收藏和整理你的AI日报内容，随时记录想法和笔记
        </p>
        <button onClick={() => navigate("/login")} className="btn-primary">
          使用 GitHub 登录
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <span className="text-2xl">🔖</span>
          <h1 className="text-xl font-semibold">AI Digest 收藏夹</h1>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-notion-muted hidden sm:inline">
            {user.login}
          </span>
          <button onClick={handleLogout} className="text-sm text-notion-muted hover:text-notion-text">
            退出
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="bg-white rounded-lg border border-notion-border p-4 mb-6">
        <div className="flex items-center justify-between">
          <div className="flex gap-6 text-sm">
          <div>
            <span className="text-2xl font-semibold">{stats.total_stars}</span>
            <span className="text-notion-muted ml-1">收藏</span>
          </div>
          <div>
            <span className="text-2xl font-semibold">{stats.total_notes}</span>
            <span className="text-notion-muted ml-1">笔记</span>
          </div>
          {stats.pending_ai > 0 && (
            <div>
              <span className="text-2xl font-semibold text-amber-600">{stats.pending_ai}</span>
              <span className="text-notion-muted ml-1">待AI增强</span>
            </div>
          )}
          </div>
          <button
            onClick={loadData}
            disabled={loading}
            className="text-sm text-notion-muted hover:text-notion-text px-2 py-1 rounded"
            title="刷新"
          >
            {loading ? "⟳" : "🔄"}
          </button>
          <button
            onClick={() => {
              invalidateStarsCache();
              loadData();
            }}
            disabled={loading}
            className="text-sm text-notion-muted hover:text-notion-text px-2 py-1 rounded ml-2"
            title="强制刷新（清除缓存）"
          >
            {loading ? "⟳" : "🔄💥"}
          </button>
        </div>
      </div>

      {/* Filter */}
      <div className="flex gap-2 mb-4 overflow-x-auto pb-2">
        {[
          { key: "all", label: "全部" },
          { key: "github", label: "GitHub" },
          { key: "arxiv", label: "论文" },
          { key: "huggingface", label: "HF" },
          { key: "blog", label: "博客" },
          { key: "with_notes", label: "有笔记" },
        ].map((f) => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`px-3 py-1 rounded-full text-sm whitespace-nowrap ${
              filter === f.key
                ? "bg-notion-text text-white"
                : "bg-white border border-notion-border text-notion-muted hover:text-notion-text"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-4 mb-4">
          {error}
        </div>
      )}

      {/* Content */}
      {sortedDates.length === 0 ? (
        <div className="text-center py-12 text-notion-muted">
          暂无收藏内容
        </div>
      ) : (
        <div className="space-y-6">
          {sortedDates.map((date) => (
            <div key={date}>
              <div className="text-sm text-notion-muted mb-3">
                📅 {date}
              </div>
              <div className="space-y-3">
                {groupedItems[date].map((star) => (
                  <div key={star.id} className="card">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <a
                          href={star.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="font-medium text-notion-text hover:underline truncate block"
                        >
                          {star.title}
                        </a>
                        <div className="flex items-center gap-2 mt-2 text-xs text-notion-muted">
                          <span className="tag">{star.type}</span>
                          {star.note_id && (
                            <span className="text-amber-600">📝 有笔记</span>
                          )}
                          {star.tags?.map((tag) => (
                            <span key={tag} className="tag">{tag}</span>
                          ))}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {star.note_id ? (
                          <button
                            onClick={() => handleViewNote(star)}
                            disabled={loadingNote}
                            className="text-amber-500 hover:text-amber-600"
                            title="查看笔记"
                          >
                            📝
                          </button>
                        ) : (
                          <button
                            onClick={() => navigate(`/note?id=${encodeURIComponent(star.id)}&title=${encodeURIComponent(star.title)}&url=${encodeURIComponent(star.url)}&type=${star.type}&date=${star.date}`)}
                            className="text-notion-muted hover:text-notion-text"
                            title="添加笔记"
                          >
                            ✏️
                          </button>
                        )}
                        {stars.some(s => s.id === star.id) ? (
                          <button
                            onClick={() => handleUnstar(star.id)}
                            className="text-notion-muted hover:text-red-500"
                            title="取消收藏"
                          >
                            ⭐
                          </button>
                        ) : (
                          <span className="text-xs text-amber-600 px-2 py-1 bg-amber-50 rounded" title="仅笔记（未收藏）">
                            仅笔记
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Note Detail Modal */}
      {viewingNote && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg max-w-2xl w-full max-h-[80vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-semibold">📝 笔记详情</h2>
                <button
                  onClick={() => setViewingNote(null)}
                  className="text-notion-muted hover:text-notion-text"
                >
                  ✕
                </button>
              </div>

              <div className="bg-notion-bg rounded-lg p-4 mb-6">
                <div className="text-sm text-notion-muted mb-1">关联内容</div>
                <a
                  href={viewingNote.content_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-medium hover:underline"
                >
                  {viewingNote.content_title}
                </a>
              </div>

              <div className="space-y-4">
                {viewingNote.thoughts && (
                  <div>
                    <h3 className="text-sm font-medium text-notion-muted mb-2">💭 想法</h3>
                    <div className="bg-gray-50 rounded-lg p-3 whitespace-pre-wrap">{viewingNote.thoughts}</div>
                  </div>
                )}

                {viewingNote.questions && (
                  <div>
                    <h3 className="text-sm font-medium text-notion-muted mb-2">❓ 疑问</h3>
                    <div className="bg-gray-50 rounded-lg p-3 whitespace-pre-wrap">{viewingNote.questions}</div>
                  </div>
                )}

                {viewingNote.todos && (
                  <div>
                    <h3 className="text-sm font-medium text-notion-muted mb-2">✅ TODO</h3>
                    <div className="bg-gray-50 rounded-lg p-3 whitespace-pre-wrap">{viewingNote.todos}</div>
                  </div>
                )}
              </div>

              <div className="mt-6 text-xs text-notion-muted">
                创建于 {new Date(viewingNote.created_at).toLocaleString()}
                {viewingNote.updated_at !== viewingNote.created_at && (
                  <span> · 更新于 {new Date(viewingNote.updated_at).toLocaleString()}</span>
                )}
              </div>

              <div className="mt-6 flex gap-3">
                <button
                  onClick={() => setViewingNote(null)}
                  className="btn-secondary flex-1"
                >
                  关闭
                </button>
                <button
                  onClick={() => {
                    setViewingNote(null);
                    navigate(`/note?id=${encodeURIComponent(viewingNote.content_id)}&title=${encodeURIComponent(viewingNote.content_title)}&url=${encodeURIComponent(viewingNote.content_url)}&type=${viewingNote.content_type}&date=${viewingNote.date}`);
                  }}
                  className="btn-primary flex-1"
                >
                  ✏️ 编辑笔记
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
