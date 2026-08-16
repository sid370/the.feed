// Same origin now that the reads are route handlers in this app. This was the last
// NEXT_PUBLIC_ variable in the project, which is a good state to stay in — anything with
// that prefix is inlined into the browser bundle, and the database URL lives next door.
export const API = "";

export type Author = {
  handle: string;
  name: string;
  avatarSeed: string;
  avatarUrl: string | null;
  isCharacter: boolean;
  isRealPerson: boolean;
};

export type Post = {
  id: string;
  body: string;
  createdAt: string;
  likeCount: number;
  replyCount: number;
  parentId: string | null;
  replyingTo: string | null;
  author: Author;
  headline: { title: string; url: string } | null;
};

export type Profile = {
  handle: string;
  name: string;
  avatarSeed: string;
  avatarUrl: string | null;
  isRealPerson: boolean;
  status: string;
  bio: string | null;
  opensPerDay: number | null;
  joinedAt: string | null;
  postCount: number;
  replyCount: number;
  likesReceived: number;
  followerCount: number;
  followingCount: number;
};

export type Character = {
  handle: string;
  name: string;
  avatar_seed: string;
  avatar_url: string | null;
  bio: string | null;
  status: string;
  opens_per_day: number | null;
  post_count: number;
  follower_count: number;
};

export type Person = {
  handle: string;
  name: string;
  avatarSeed: string;
  avatarUrl: string | null;
  bio: string | null;
};

export type Liker = {
  handle: string;
  name: string;
  avatarSeed: string;
  avatarUrl?: string | null;
  likedAt: string;
};

export class Unauthorized extends Error {}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`, { credentials: "include", cache: "no-store" });
  if (res.status === 401) throw new Unauthorized("password required");
  if (!res.ok) throw new Error(`${path} failed: ${res.status}`);
  return res.json();
}

// The only read still made from the browser: likes open on demand, so they cannot be part
// of the cached page. Everything else is fetched on the server in lib/world.ts.
export const getLikes = (id: string) => get<{ likers: Liker[] }>(`/api/posts/${id}/likes`);

export async function login(password: string): Promise<boolean> {
  const res = await fetch(`${API}/api/login`, {
    method: "POST",
    credentials: "include",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ password }),
  });
  return res.ok;
}

export async function poke(postId: string, body: string, name: string) {
  const res = await fetch(`${API}/api/poke`, {
    method: "POST",
    credentials: "include",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ post_id: postId, body, display_name: name }),
  });
  if (res.status === 401) throw new Unauthorized("password required");
  if (res.status === 429) throw new Error("Daily reply limit reached. Try again tomorrow.");
  if (!res.ok) throw new Error("Couldn't post that reply.");
  return res.json();
}

// Deterministic colour per handle, so a character looks the same everywhere without
// storing or fetching an image.
export function avatarColor(seed: string): string {
  let hash = 0;
  for (let i = 0; i < seed.length; i++) hash = (hash * 31 + seed.charCodeAt(i)) | 0;
  const hue = Math.abs(hash) % 360;
  return `hsl(${hue} 42% 62%)`;
}

export function initials(name: string): string {
  return name
    .replace(/\(.*?\)/g, "")
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0])
    .join("")
    .toUpperCase();
}

export function ago(iso: string): string {
  const secs = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (secs < 60) return "now";
  if (secs < 3600) return `${Math.floor(secs / 60)}m`;
  if (secs < 86400) return `${Math.floor(secs / 3600)}h`;
  return `${Math.floor(secs / 86400)}d`;
}
