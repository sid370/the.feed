// Generated from db/queries/*.sql by scripts/gen_queries.mjs. Do not edit.
export type QueryName =
  | "admin_totals"
  | "admin_recent_ticks"
  | "admin_usage"
  | "admin_characters"
  | "feed"
  | "thread"
  | "post_likes"
  | "heat"
  | "human_posts_today"
  | "poke_target"
  | "insert_human_post"
  | "bump_reply_count"
  | "insert_human_notification"
  | "profile"
  | "profile_posts"
  | "followers"
  | "following"
  | "last_finished_tick"
  | "post_count"
  | "active_character_count"
  | "character_list";

export const SQL: Record<QueryName, { text: string; params: string[] }> = {
  admin_totals: { text: "SELECT (SELECT count(*) FROM posts WHERE world_id = $1) AS posts,\n       (SELECT count(*) FROM likes) AS likes,\n       (SELECT count(*) FROM characters\n         WHERE status = 'active' AND world_id = $1) AS active,\n       (SELECT count(*) FROM batches WHERE status = 'submitted') AS open_batches,\n       (SELECT count(*) FROM headlines WHERE safe IS FALSE) AS blocked_headlines", params: ["world"] },
  admin_recent_ticks: { text: "SELECT id, turns_sent, posts_written, news_share, started_at, error\n  FROM ticks ORDER BY id DESC LIMIT 10", params: [] },
  admin_usage: { text: "SELECT coalesce(sum(input_tokens), 0)       AS input_tokens,\n       coalesce(sum(output_tokens), 0)      AS output_tokens,\n       coalesce(sum(cache_read_tokens), 0)  AS cache_read_tokens,\n       coalesce(sum(cache_write_tokens), 0) AS cache_write_tokens,\n       count(*) FILTER (WHERE status = 'failed') AS failed_batches\n  FROM batches", params: [] },
  admin_characters: { text: "SELECT id, handle, name, status, persona_card, engagement_profile\n  FROM characters WHERE world_id = $1 ORDER BY created_at DESC", params: ["world"] },
  feed: { text: "SELECT p.id, p.body, p.created_at, p.like_count, p.reply_count, p.heat,\n       p.parent_id, p.quote_of_id,\n       c.handle, c.name, c.avatar_seed, c.avatar_url, c.is_real_person,\n       h.title AS headline_title, h.url AS headline_url\n  FROM posts p\n  LEFT JOIN characters c ON c.id = p.character_id\n  LEFT JOIN headlines h  ON h.id = p.headline_id\n WHERE p.world_id = $1 AND p.parent_id IS NULL\n ORDER BY p.heat / (1 + extract(epoch FROM now() - p.created_at) / 3600.0) DESC,\n          p.created_at DESC\n LIMIT $2 OFFSET $3", params: ["world","limit","offset"] },
  thread: { text: "SELECT p.id, p.body, p.created_at, p.like_count, p.reply_count, p.parent_id,\n       coalesce(pc.handle, parent.author_human) AS replying_to,\n       c.handle, c.name, c.avatar_seed, c.avatar_url, c.is_real_person,\n       h.title AS headline_title, h.url AS headline_url\n  FROM posts p\n  LEFT JOIN characters c ON c.id = p.character_id\n  LEFT JOIN posts parent ON parent.id = p.parent_id\n  LEFT JOIN characters pc ON pc.id = parent.character_id\n  LEFT JOIN headlines h  ON h.id = p.headline_id\n WHERE coalesce(p.root_id, p.id) = (SELECT coalesce(root_id, id) FROM posts WHERE id = $1)\n ORDER BY p.created_at", params: ["post"] },
  post_likes: { text: "SELECT c.handle, c.name, c.avatar_seed, c.avatar_url, l.created_at\n  FROM likes l\n  JOIN characters c ON c.id = l.character_id\n WHERE l.post_id = $1\n ORDER BY l.created_at DESC\n LIMIT $2", params: ["post","limit"] },
  heat: { text: "SELECT a.name AS a_name, b.name AS b_name, r.heat, r.sentiment,\n       coalesce(argued.root_id, liked.root_id) AS thread_id\n  FROM relations r\n  JOIN characters a ON a.id = r.character_id\n  JOIN characters b ON b.id = r.other_id\n  -- The hottest thread both of them actually posted in: the argument itself.\n  LEFT JOIN LATERAL (\n      SELECT coalesce(p.root_id, p.id) AS root_id\n        FROM posts p\n       WHERE p.world_id = a.world_id\n         AND p.character_id IN (r.character_id, r.other_id)\n       GROUP BY coalesce(p.root_id, p.id)\n      HAVING bool_or(p.character_id = r.character_id)\n         AND bool_or(p.character_id = r.other_id)\n       ORDER BY max(p.heat) DESC\n       LIMIT 1\n  ) argued ON true\n  -- Heat also rises on a like alone, so a pair can be hot with nothing said between them.\n  LEFT JOIN LATERAL (\n      SELECT coalesce(p.root_id, p.id) AS root_id\n        FROM posts p\n        JOIN likes l ON l.post_id = p.id AND l.character_id = r.character_id\n       WHERE p.character_id = r.other_id\n       ORDER BY p.heat DESC\n       LIMIT 1\n  ) liked ON true\n WHERE r.heat > 0.2 AND a.world_id = $1\n ORDER BY r.heat DESC LIMIT $2", params: ["world","limit"] },
  human_posts_today: { text: "SELECT count(*) AS n FROM posts\n WHERE author_human IS NOT NULL AND created_at > now() - interval '1 day'", params: [] },
  poke_target: { text: "SELECT character_id, coalesce(root_id, id) AS root FROM posts WHERE id = $1", params: ["post"] },
  insert_human_post: { text: "INSERT INTO posts (world_id, author_human, body, parent_id, root_id)\nVALUES ($1, $2, $3, $4, $5) RETURNING id", params: ["world","author","body","parent","root"] },
  bump_reply_count: { text: "UPDATE posts SET reply_count = reply_count + 1 WHERE id = $1", params: ["post"] },
  insert_human_notification: { text: "INSERT INTO notifications (character_id, post_id, kind) VALUES ($1, $2, 'human')", params: ["character","post"] },
  profile: { text: "SELECT c.handle, c.name, c.avatar_seed, c.avatar_url, c.is_real_person, c.status,\n       c.persona_card->>'bio' AS bio,\n       (c.engagement_profile->>'opens_per_day')::float AS opens_per_day,\n       coalesce(c.activated_at, c.created_at) AS joined_at,\n       (SELECT count(*) FROM posts p\n         WHERE p.character_id = c.id AND p.parent_id IS NULL)     AS post_count,\n       (SELECT count(*) FROM posts p\n         WHERE p.character_id = c.id AND p.parent_id IS NOT NULL) AS reply_count,\n       (SELECT coalesce(sum(p.like_count), 0) FROM posts p\n         WHERE p.character_id = c.id)                             AS likes_received,\n       (SELECT count(*) FROM follows f WHERE f.followee_id = c.id) AS follower_count,\n       (SELECT count(*) FROM follows f WHERE f.follower_id = c.id) AS following_count\n  FROM characters c\n WHERE c.handle = $1 AND c.world_id = $2 AND c.status <> 'draft'", params: ["handle","world"] },
  profile_posts: { text: "SELECT p.id, p.body, p.created_at, p.like_count, p.reply_count, p.parent_id,\n       coalesce(pc.handle, parent.author_human) AS replying_to,\n       c.handle, c.name, c.avatar_seed, c.avatar_url, c.is_real_person,\n       h.title AS headline_title, h.url AS headline_url\n  FROM posts p\n  JOIN characters c ON c.id = p.character_id\n  LEFT JOIN posts parent  ON parent.id = p.parent_id\n  LEFT JOIN characters pc ON pc.id = parent.character_id\n  LEFT JOIN headlines h   ON h.id = p.headline_id\n WHERE c.handle = $1 AND p.world_id = $2\n   AND (p.parent_id IS NULL) = $3\n ORDER BY p.created_at DESC\n LIMIT $4", params: ["handle","world","top_level","limit"] },
  followers: { text: "SELECT c.handle, c.name, c.avatar_seed, c.avatar_url, c.persona_card->>'bio' AS bio\n  FROM follows f\n  JOIN characters anchor ON anchor.id = f.followee_id\n  JOIN characters c      ON c.id = f.follower_id\n WHERE anchor.handle = $1 AND anchor.world_id = $2 AND c.status <> 'draft'\n ORDER BY f.created_at DESC\n LIMIT $3", params: ["handle","world","limit"] },
  following: { text: "SELECT c.handle, c.name, c.avatar_seed, c.avatar_url, c.persona_card->>'bio' AS bio\n  FROM follows f\n  JOIN characters anchor ON anchor.id = f.follower_id\n  JOIN characters c      ON c.id = f.followee_id\n WHERE anchor.handle = $1 AND anchor.world_id = $2 AND c.status <> 'draft'\n ORDER BY f.created_at DESC\n LIMIT $3", params: ["handle","world","limit"] },
  last_finished_tick: { text: "SELECT id, started_at FROM ticks WHERE finished_at IS NOT NULL ORDER BY id DESC LIMIT 1", params: [] },
  post_count: { text: "SELECT count(*) AS n FROM posts WHERE world_id = $1", params: ["world"] },
  active_character_count: { text: "SELECT count(*) AS n FROM characters WHERE status = 'active' AND world_id = $1", params: ["world"] },
  character_list: { text: "SELECT c.handle, c.name, c.avatar_seed, c.avatar_url, c.status,\n       c.persona_card->>'bio' AS bio,\n       (c.engagement_profile->>'opens_per_day')::float AS opens_per_day,\n       (SELECT count(*) FROM posts p WHERE p.character_id = c.id) AS post_count,\n       (SELECT count(*) FROM follows f WHERE f.followee_id = c.id) AS follower_count\n  FROM characters c\n WHERE c.world_id = $1 AND c.status <> 'draft'\n ORDER BY follower_count DESC", params: ["world"] },
};
