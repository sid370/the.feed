-- name: admin_totals
SELECT (SELECT count(*) FROM posts WHERE world_id = :world) AS posts,
       (SELECT count(*) FROM likes) AS likes,
       (SELECT count(*) FROM characters
         WHERE status = 'active' AND world_id = :world) AS active,
       (SELECT count(*) FROM batches WHERE status = 'submitted') AS open_batches,
       (SELECT count(*) FROM headlines WHERE safe IS FALSE) AS blocked_headlines

-- name: admin_recent_ticks
SELECT id, turns_sent, posts_written, news_share, started_at, error
  FROM ticks ORDER BY id DESC LIMIT 10

-- cache_read == 0 across collected batches is the ONLY signal that a silent cache
-- invalidator has crept in — there is no error for it.
-- name: admin_usage
SELECT coalesce(sum(input_tokens), 0)       AS input_tokens,
       coalesce(sum(output_tokens), 0)      AS output_tokens,
       coalesce(sum(cache_read_tokens), 0)  AS cache_read_tokens,
       coalesce(sum(cache_write_tokens), 0) AS cache_write_tokens,
       count(*) FILTER (WHERE status = 'failed') AS failed_batches
  FROM batches

-- name: admin_characters
SELECT id, handle, name, status, persona_card, engagement_profile
  FROM characters WHERE world_id = :world ORDER BY created_at DESC
