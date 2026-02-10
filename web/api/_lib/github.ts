/** GitHub API client for data repository operations */

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

export interface StarsData {
  version: string;
  updated_at: string;
  items: StarItem[];
}

const DATA_REPO = process.env.DATA_REPO || "";
const DATA_BRANCH = process.env.DATA_BRANCH || "main";

export class GitHubDataClient {
  private token: string;

  constructor(token: string) {
    this.token = token;
  }

  private async request(path: string, options: RequestInit = {}): Promise<any> {
    const url = `https://api.github.com${path}`;
    const response = await fetch(url, {
      ...options,
      headers: {
        Authorization: `Bearer ${this.token}`,
        Accept: "application/vnd.github.v3+json",
        "User-Agent": "ai-digest-web",
        ...options.headers,
      },
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`GitHub API error: ${response.status} ${error}`);
    }

    return response.json();
  }

  async getStars(): Promise<StarsData> {
    try {
      const content = await this.request(
        `/repos/${DATA_REPO}/contents/data/stars.json?ref=${DATA_BRANCH}`
      );
      const decoded = Buffer.from(content.content, "base64").toString("utf-8");
      return JSON.parse(decoded);
    } catch (error) {
      // Return empty data if file doesn't exist
      return {
        version: "1.0",
        updated_at: new Date().toISOString(),
        items: [],
      };
    }
  }

  async saveStars(data: StarsData): Promise<void> {
    const content = Buffer.from(JSON.stringify(data, null, 2)).toString("base64");

    // Get existing file SHA if it exists
    let sha: string | undefined;
    try {
      const existing = await this.request(
        `/repos/${DATA_REPO}/contents/data/stars.json?ref=${DATA_BRANCH}`
      );
      sha = existing.sha;
    } catch {
      // File doesn't exist yet
    }

    await this.request(`/repos/${DATA_REPO}/contents/data/stars.json`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: `Update stars: ${data.updated_at}`,
        content,
        branch: DATA_BRANCH,
        ...(sha && { sha }),
      }),
    });
  }

  async addStar(item: Omit<StarItem, "starred_at">): Promise<void> {
    const data = await this.getStars();

    // Check if already starred
    const existingIndex = data.items.findIndex((i) => i.id === item.id);
    const starredItem: StarItem = {
      ...item,
      starred_at: new Date().toISOString(),
    };

    if (existingIndex >= 0) {
      data.items[existingIndex] = starredItem;
    } else {
      data.items.unshift(starredItem);
    }

    data.updated_at = new Date().toISOString();
    await this.saveStars(data);
  }

  async removeStar(id: string): Promise<void> {
    const data = await this.getStars();
    data.items = data.items.filter((i) => i.id !== id);
    data.updated_at = new Date().toISOString();
    await this.saveStars(data);
  }

  async getNote(noteId: string): Promise<NoteItem | null> {
    try {
      const content = await this.request(
        `/repos/${DATA_REPO}/contents/data/notes/${noteId}.md?ref=${DATA_BRANCH}`
      );
      const decoded = Buffer.from(content.content, "base64").toString("utf-8");
      return this.parseNoteMarkdown(noteId, decoded);
    } catch {
      return null;
    }
  }

  async saveNote(note: NoteItem): Promise<void> {
    const markdown = this.buildNoteMarkdown(note);
    const content = Buffer.from(markdown).toString("base64");
    const filename = `${note.id}.md`;

    // Get existing file SHA if it exists
    let sha: string | undefined;
    try {
      const existing = await this.request(
        `/repos/${DATA_REPO}/contents/data/notes/${filename}?ref=${DATA_BRANCH}`
      );
      sha = existing.sha;
    } catch {
      // File doesn't exist yet
    }

    await this.request(`/repos/${DATA_REPO}/contents/data/notes/${filename}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: `Update note: ${note.content_title}`,
        content,
        branch: DATA_BRANCH,
        ...(sha && { sha }),
      }),
    });
  }

  async listNotes(): Promise<NoteItem[]> {
    try {
      const contents = await this.request(
        `/repos/${DATA_REPO}/contents/data/notes?ref=${DATA_BRANCH}`
      );

      const notes: NoteItem[] = [];
      for (const file of contents) {
        if (file.name.endsWith(".md")) {
          const noteId = file.name.replace(".md", "");
          const note = await this.getNote(noteId);
          if (note) notes.push(note);
        }
      }

      return notes.sort(
        (a, b) =>
          new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );
    } catch {
      return [];
    }
  }

  private parseNoteMarkdown(noteId: string, markdown: string): NoteItem {
    // Extract YAML frontmatter
    const match = markdown.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/);
    if (!match) {
      throw new Error("Invalid note format");
    }

    const frontmatter = match[1];
    const content = match[2].trim();

    const meta: Record<string, string> = {};
    for (const line of frontmatter.split("\n")) {
      const [key, ...valueParts] = line.split(":");
      if (key && valueParts.length > 0) {
        meta[key.trim()] = valueParts.join(":").trim();
      }
    }

    return {
      id: noteId,
      content_id: meta.content_id || "",
      content_title: meta.content_title || "",
      content_url: meta.content_url || "",
      content_type: meta.content_type || "",
      date: meta.date || "",
      created_at: meta.created_at || new Date().toISOString(),
      ai_enhanced: meta.ai_enhanced === "true",
      content,
    };
  }

  private buildNoteMarkdown(note: NoteItem): string {
    return `---
id: ${note.id}
content_id: ${note.content_id}
content_title: ${note.content_title}
content_url: ${note.content_url}
content_type: ${note.content_type}
date: ${note.date}
created_at: ${note.created_at}
ai_enhanced: ${note.ai_enhanced}
---

${note.content}
`;
  }
}
