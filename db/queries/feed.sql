-- name: feed
SELECT p.id, p.body, p.created_at, p.like_count, p.reply_count, p.heat,
       p.parent_id, p.quote_of_id,
       c.handle, c.name, c.avatar_seed, c.avatar_url, c.is_real_person,
       h.title AS headline_title, h.url AS headline_url
  FROM posts p
  LEFT JOIN characters c ON c.id = p.character_id
  LEFT JOIN headlines h  ON h.id = p.headline_id
 WHERE p.world_id = :world AND p.parent_id IS NULL
 ORDER BY p.heat / (1 + extract(epoch FROM now() - p.created_at) / 3600.0) DESC,
          p.created_at DESC
 LIMIT :limit OFFSET :offset

-- name: thread
SELECT p.id, p.body, p.created_at, p.like_count, p.reply_count, p.parent_id,
       coalesce(pc.handle, parent.author_human) AS replying_to,
       c.handle, c.name, c.avatar_seed, c.avatar_url, c.is_real_person,
       h.title AS headline_title, h.url AS headline_url
  FROM posts p
  LEFT JOIN characters c ON c.id = p.character_id
  LEFT JOIN posts parent ON parent.id = p.parent_id
  LEFT JOIN characters pc ON pc.id = parent.character_id
  LEFT JOIN headlines h  ON h.id = p.headline_id
 WHERE coalesce(p.root_id, p.id) = (SELECT coalesce(root_id, id) FROM posts WHERE id = :post)
 ORDER BY p.created_at

-- name: post_likes
SELECT c.handle, c.name, c.avatar_seed, c.avatar_url, l.created_at
  FROM likes l
  JOIN characters c ON c.id = l.character_id
 WHERE l.post_id = :post
 ORDER BY l.created_at DESC
 LIMIT :limit

-- name: heat
SELECT a.name AS a_name, b.name AS b_name, r.heat, r.sentiment,
       coalesce(argued.root_id, liked.root_id) AS thread_id
  FROM relations r
  JOIN characters a ON a.id = r.character_id
  JOIN characters b ON b.id = r.other_id
  -- The hottest thread both of them actually posted in: the argument itself.
  LEFT JOIN LATERAL (
      SELECT coalesce(p.root_id, p.id) AS root_id
        FROM posts p
       WHERE p.world_id = a.world_id
         AND p.character_id IN (r.character_id, r.other_id)
       GROUP BY coalesce(p.root_id, p.id)
      HAVING bool_or(p.character_id = r.character_id)
         AND bool_or(p.character_id = r.other_id)
       ORDER BY max(p.heat) DESC
       LIMIT 1
  ) argued ON true
  -- Heat also rises on a like alone, so a pair can be hot with nothing said between them.
  LEFT JOIN LATERAL (
      SELECT coalesce(p.root_id, p.id) AS root_id
        FROM posts p
        JOIN likes l ON l.post_id = p.id AND l.character_id = r.character_id
       WHERE p.character_id = r.other_id
       ORDER BY p.heat DESC
       LIMIT 1
  ) liked ON true
 WHERE r.heat > 0.2 AND a.world_id = :world
 ORDER BY r.heat DESC LIMIT :limit
