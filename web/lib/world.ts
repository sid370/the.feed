import "server-only";
import { query, queryOne } from "./db";
import type { Character, Liker, Person, Post, Profile } from "./api";

// The read layer. Everything here runs on the server against db/queries/*.sql — the same
// files charsocial/api/main.py loads — and shapes rows into the types the components
// already take, so the client half of the app did not have to change.
//
// Two coercions are not optional. Postgres count()/sum() are bigint and arrive as strings,
// and TIMESTAMPTZ arrives as a Date; the FastAPI responses these replace were numbers and
// ISO strings. Skip either and the difference shows up as "[object Object]" in a timestamp
// or a follower count that sorts lexicographically.
const WORLD = process.env.WORLD_ID ?? "main";

const num = (v: unknown): number => Number(v ?? 0);
const iso = (v: unknown): string => (v instanceof Date ? v.toISOString() : String(v));

export type Pair = {
  a: string;
  b: string;
  heat: number;
  share: number;
  mood: string;
  threadId: string | null;
};

export type World = {
  tick: number;
  lastTickAt: string | null;
  intervalMinutes: number;
  posts: number;
  characters: number;
};

function toPost(row: any): Post {
  return {
    id: String(row.id),
    body: row.body,
    createdAt: iso(row.created_at),
    likeCount: num(row.like_count),
    replyCount: num(row.reply_count),
    parentId: row.parent_id ? String(row.parent_id) : null,
    replyingTo: row.replying_to ?? null,
    author: {
      handle: row.handle ?? "guest",
      name: row.name ?? "Guest",
      avatarSeed: row.avatar_seed ?? "guest",
      avatarUrl: row.avatar_url ?? null,
      // A human poke has no character row, so there is no profile to open.
      isCharacter: row.handle != null,
      isRealPerson: Boolean(row.is_real_person),
    },
    headline: row.headline_title
      ? { title: row.headline_title, url: row.headline_url }
      : null,
  };
}

export async function getFeed(limit = 40, offset = 0): Promise<Post[]> {
  const rows = await query("feed", { world: WORLD, limit: Math.min(limit, 100), offset });
  return rows.map(toPost);
}

export async function getThread(post: string): Promise<Post[]> {
  return (await query("thread", { post })).map(toPost);
}

export async function getLikes(post: string, limit = 50): Promise<Liker[]> {
  const rows = await query<any>("post_likes", { post, limit: Math.min(limit, 200) });
  return rows.map((r) => ({
    handle: r.handle,
    name: r.name,
    avatarSeed: r.avatar_seed,
    avatarUrl: r.avatar_url,
    likedAt: iso(r.created_at),
  }));
}

export async function getHeat(limit = 8): Promise<Pair[]> {
  const rows = await query<any>("heat", { world: WORLD, limit: Math.min(limit, 20) });
  const top = Math.max(...rows.map((r) => num(r.heat)), 1) || 1;
  return rows.map((r) => ({
    a: r.a_name,
    b: r.b_name,
    heat: Math.round(num(r.heat) * 100) / 100,
    share: Math.round((num(r.heat) / top) * 1000) / 1000,
    mood: num(r.sentiment) < -1 ? "hostile" : num(r.sentiment) > 1 ? "warm" : "neutral",
    threadId: r.thread_id ? String(r.thread_id) : null,
  }));
}

export async function getWorld(): Promise<World> {
  const [last, posts, active] = await Promise.all([
    queryOne<any>("last_finished_tick"),
    queryOne<any>("post_count", { world: WORLD }),
    queryOne<any>("active_character_count", { world: WORLD }),
  ]);
  return {
    tick: last ? num(last.id) : 0,
    lastTickAt: last ? iso(last.started_at) : null,
    intervalMinutes: num(process.env.TICK_INTERVAL_MINUTES ?? 30),
    posts: num(posts?.n),
    characters: num(active?.n),
  };
}

export async function getCharacters(): Promise<Character[]> {
  const rows = await query<any>("character_list", { world: WORLD });
  return rows.map((r) => ({
    handle: r.handle,
    name: r.name,
    avatar_seed: r.avatar_seed,
    avatar_url: r.avatar_url,
    bio: r.bio,
    status: r.status,
    opens_per_day: r.opens_per_day,
    post_count: num(r.post_count),
    follower_count: num(r.follower_count),
  }));
}

/** The header alone. The follow pages need a name and nothing else — running the two post
 *  queries for them would be two cold-render queries per handle for a string. */
export async function getProfileHeader(raw: string): Promise<Profile | null> {
  const handle = raw.replace(/^@/, "").toLowerCase();
  const row = await queryOne<any>("profile", { handle, world: WORLD });
  return row ? toProfile(row) : null;
}

export async function getProfile(
  raw: string,
): Promise<{ profile: Profile; posts: Post[]; replies: Post[] } | null> {
  const handle = raw.replace(/^@/, "").toLowerCase();
  const args = { handle, world: WORLD, limit: 50 };
  const row = await queryOne<any>("profile", { handle, world: WORLD });
  if (!row) return null;

  // Both tabs come from the same rows, so switching between them shouldn't hit the network.
  const [posts, replies] = await Promise.all([
    query("profile_posts", { ...args, top_level: true }),
    query("profile_posts", { ...args, top_level: false }),
  ]);

  return { profile: toProfile(row), posts: posts.map(toPost), replies: replies.map(toPost) };
}

function toProfile(row: any): Profile {
  return {
    handle: row.handle,
    name: row.name,
    avatarSeed: row.avatar_seed,
    avatarUrl: row.avatar_url,
    isRealPerson: row.is_real_person,
    status: row.status,
    bio: row.bio,
    opensPerDay: row.opens_per_day,
    joinedAt: row.joined_at ? iso(row.joined_at) : null,
    postCount: num(row.post_count),
    replyCount: num(row.reply_count),
    likesReceived: num(row.likes_received),
    followerCount: num(row.follower_count),
    followingCount: num(row.following_count),
  };
}

export async function getFollows(
  raw: string,
  direction: "followers" | "following",
  limit = 100,
): Promise<Person[]> {
  const handle = raw.replace(/^@/, "").toLowerCase();
  const rows = await query<any>(direction, {
    handle,
    world: WORLD,
    limit: Math.min(limit, 200),
  });
  return rows.map((r) => ({
    handle: r.handle,
    name: r.name,
    avatarSeed: r.avatar_seed,
    avatarUrl: r.avatar_url,
    bio: r.bio,
  }));
}
