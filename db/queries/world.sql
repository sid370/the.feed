-- name: last_finished_tick
SELECT id, started_at FROM ticks WHERE finished_at IS NOT NULL ORDER BY id DESC LIMIT 1

-- name: post_count
SELECT count(*) AS n FROM posts WHERE world_id = :world

-- name: active_character_count
SELECT count(*) AS n FROM characters WHERE status = 'active' AND world_id = :world

-- name: character_list
SELECT c.handle, c.name, c.avatar_seed, c.avatar_url, c.status,
       c.persona_card->>'bio' AS bio,
       (c.engagement_profile->>'opens_per_day')::float AS opens_per_day,
       (SELECT count(*) FROM posts p WHERE p.character_id = c.id) AS post_count,
       (SELECT count(*) FROM follows f WHERE f.followee_id = c.id) AS follower_count
  FROM characters c
 WHERE c.world_id = :world AND c.status <> 'draft'
 ORDER BY follower_count DESC
