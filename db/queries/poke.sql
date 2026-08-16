-- name: human_posts_today
SELECT count(*) AS n FROM posts
 WHERE author_human IS NOT NULL AND created_at > now() - interval '1 day'

-- name: poke_target
SELECT character_id, coalesce(root_id, id) AS root FROM posts WHERE id = :post

-- The post, the parent's reply count and the character's notification are one statement so
-- they are one transaction. Neon's HTTP driver has no interactive transaction, and three
-- separate round trips could leave a post whose parent never counted it.
-- name: insert_human_poke
WITH new_post AS (
    INSERT INTO posts (world_id, author_human, body, parent_id, root_id)
    VALUES (:world, :author, :body, :parent, :root)
    RETURNING id
), bumped AS (
    UPDATE posts SET reply_count = reply_count + 1 WHERE id = :parent
), notified AS (
    INSERT INTO notifications (character_id, post_id, kind)
    SELECT CAST(:character AS uuid), new_post.id, 'human'
      FROM new_post
     WHERE CAST(:character AS uuid) IS NOT NULL
)
SELECT id FROM new_post
