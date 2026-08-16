-- name: profile
SELECT c.handle, c.name, c.avatar_seed, c.avatar_url, c.is_real_person, c.status,
       c.persona_card->>'bio' AS bio,
       (c.engagement_profile->>'opens_per_day')::float AS opens_per_day,
       coalesce(c.activated_at, c.created_at) AS joined_at,
       (SELECT count(*) FROM posts p
         WHERE p.character_id = c.id AND p.parent_id IS NULL)     AS post_count,
       (SELECT count(*) FROM posts p
         WHERE p.character_id = c.id AND p.parent_id IS NOT NULL) AS reply_count,
       (SELECT coalesce(sum(p.like_count), 0) FROM posts p
         WHERE p.character_id = c.id)                             AS likes_received,
       (SELECT count(*) FROM follows f WHERE f.followee_id = c.id) AS follower_count,
       (SELECT count(*) FROM follows f WHERE f.follower_id = c.id) AS following_count
  FROM characters c
 WHERE c.handle = :handle AND c.world_id = :world AND c.status <> 'draft'

-- One query for both tabs; the boolean picks which side of the parent_id split to return.
-- name: profile_posts
SELECT p.id, p.body, p.created_at, p.like_count, p.reply_count, p.parent_id,
       coalesce(pc.handle, parent.author_human) AS replying_to,
       c.handle, c.name, c.avatar_seed, c.avatar_url, c.is_real_person,
       h.title AS headline_title, h.url AS headline_url
  FROM posts p
  JOIN characters c ON c.id = p.character_id
  LEFT JOIN posts parent  ON parent.id = p.parent_id
  LEFT JOIN characters pc ON pc.id = parent.character_id
  LEFT JOIN headlines h   ON h.id = p.headline_id
 WHERE c.handle = :handle AND p.world_id = :world
   AND (p.parent_id IS NULL) = :top_level
 ORDER BY p.created_at DESC
 LIMIT :limit

-- followers and following differ only in which side of the edge the profile sits on. They
-- were one .format()'d template with the column names interpolated; two named queries say
-- the same thing without a string that can be built wrong.
-- name: followers
SELECT c.handle, c.name, c.avatar_seed, c.avatar_url, c.persona_card->>'bio' AS bio
  FROM follows f
  JOIN characters anchor ON anchor.id = f.followee_id
  JOIN characters c      ON c.id = f.follower_id
 WHERE anchor.handle = :handle AND anchor.world_id = :world AND c.status <> 'draft'
 ORDER BY f.created_at DESC
 LIMIT :limit

-- name: following
SELECT c.handle, c.name, c.avatar_seed, c.avatar_url, c.persona_card->>'bio' AS bio
  FROM follows f
  JOIN characters anchor ON anchor.id = f.follower_id
  JOIN characters c      ON c.id = f.followee_id
 WHERE anchor.handle = :handle AND anchor.world_id = :world AND c.status <> 'draft'
 ORDER BY f.created_at DESC
 LIMIT :limit
