const API_BASE = "/api";

export interface StarItem {
  id: string;
  title: string;
  url: string;
  type: string;
  date: string;
  starred_at: string;
  tags: string[];
  note_id?: string;
}

export interface NoteItem {
  id: string;
  content_id: string;
  content_title: string;
  content_url: string;
  content_type: string;
  date: string;
  created_at: string;
  ai_enhanced: boolean;
  content: string;
}

export interface ListResponse {
  stars: StarItem[];
  notes: NoteItem[];
  stats: {
    total_stars: number;
    total_notes: number;
    pending_ai: number;
  };
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
    credentials: "include",
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(error || `Request failed: ${response.status}`);
  }

  return response.json();
}

export const api = {
  auth: {
    me: () => request<{ login: string; avatar_url: string; name: string }>("/auth/me"),
    login: (redirect?: string) => {
      window.location.href = `${API_BASE}/auth/login${redirect ? `?redirect=${encodeURIComponent(redirect)}` : ""}`;
    },
    logout: () => request("/auth/logout", { method: "POST" }),
  },
  stars: {
    list: () => request<ListResponse>("/list"),
    add: (data: {
      id: string;
      title: string;
      url: string;
      type: string;
      date: string;
      t: string;
      tags?: string[];
    }) => request("/star", { method: "POST", body: JSON.stringify(data) }),
    remove: (id: string) =>
      request("/unstar", { method: "POST", body: JSON.stringify({ id }) }),
  },
  notes: {
    save: (data: {
      content_id: string;
      content_title: string;
      content_url: string;
      content_type: string;
      date: string;
      t: string;
      thoughts: string;
      questions: string;
      todos: string;
      request_ai: boolean;
    }) => request("/note", { method: "POST", body: JSON.stringify(data) }),
  },
};
