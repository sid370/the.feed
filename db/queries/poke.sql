-- name: human_posts_today
SELECT count(*) AS n FROM posts
 WHERE author_human IS NOT NULL AND created_at > now() - interval '1 day'

-- name: poke_target
SELECT character_id, coalesce(root_id, id) AS root FROM posts WHERE id = :post

-- name: insert_human_post
INSERT INTO posts (world_id, author_human, body, parent_id, root_id)
VALUES (:world, :author, :body, :parent, :root) RETURNING id

-- A poke is a real child post, so the parent's rendered count must include it.
-- name: bump_reply_count
UPDATE posts SET reply_count = reply_count + 1 WHERE id = :post

-- name: insert_human_notification
INSERT INTO notifications (character_id, post_id, kind) VALUES (:character, :post, 'human')
