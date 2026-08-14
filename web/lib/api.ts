export const API = process.env.NEXT_PUBLIC_API ?? "http://localhost:8000";

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

export const getFeed = () => get<{ posts: Post[] }>("/api/feed");
export const getCharacters = () => get<{ characters: Character[] }>("/api/characters");
export const getThread = (id: string) => get<{ posts: Post[] }>(`/api/thread/${id}`);
export const getLikes = (id: string) => get<{ likers: Liker[] }>(`/api/posts/${id}/likes`);
export const getFollowers = (handle: string) =>
  get<{ people: Person[] }>(`/api/profile/${encodeURIComponent(handle)}/followers`);
export const getFollowing = (handle: string) =>
  get<{ people: Person[] }>(`/api/profile/${encodeURIComponent(handle)}/following`);
export const getProfile = (handle: string) =>
  get<{ profile: Profile; posts: Post[]; replies: Post[] }>(
    `/api/profile/${encodeURIComponent(handle)}`,
  );

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
