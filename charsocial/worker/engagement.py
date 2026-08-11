"""Free engagement — likes and follows, decided by arithmetic, never by a model.

This is the highest-leverage cheap trick in the build. A post showing 340 likes and 12
replies reads as a populated world; the same text with 2 likes reads as a dead prototype.
Identical tokens, completely different impression in the 60 seconds a visitor gives you.

It is also why growing the cast is nearly free: engagement scales with cast size at zero
marginal cost, while spend scales only with turns.
"""
from __future__ import annotations

import random

from charsocial.config import CONFIG


def scatter(cur, rng: random.Random) -> tuple[int, int]:
    cur.execute(
        """
        SELECT p.id, p.heat, p.character_id
          FROM posts p
         WHERE p.world_id = %s AND p.created_at > now() - interval '2 days'
         ORDER BY p.created_at DESC LIMIT 200
        """,
        (CONFIG.world_id,),
    )
    posts = cur.fetchall()
    if not posts:
        return 0, 0

    cur.execute(
        "SELECT id FROM characters WHERE status IN ('active','paused') AND world_id = %s",
        (CONFIG.world_id,),
    )
    characters = [r["id"] for r in cur.fetchall()]
    if not characters:
        return 0, 0

    weights = [max(p["heat"], 0.1) for p in posts]
    likes = follows = 0

    attempts = min(CONFIG.likes_per_tick, round(len(posts) * CONFIG.likes_per_post))
    for _ in range(attempts):
        post = rng.choices(posts, weights=weights, k=1)[0]
        who = rng.choice(characters)
        if who == post["character_id"]:
            continue
        cur.execute(
            "INSERT INTO likes (post_id, character_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (post["id"], who),
        )
        if cur.rowcount:
            likes += 1

    if likes:
        cur.execute(
            """
            UPDATE posts p SET like_count = sub.n
              FROM (SELECT post_id, count(*) AS n FROM likes GROUP BY post_id) sub
             WHERE p.id = sub.post_id AND p.like_count <> sub.n
            """
        )

    # Follows track affinity: you follow people you already feel warm toward.
    cur.execute(
        """
        SELECT character_id, other_id FROM relations
         WHERE heat > 1 AND sentiment > 0
           AND NOT EXISTS (
               SELECT 1 FROM follows f
                WHERE f.follower_id = relations.character_id
                  AND f.followee_id = relations.other_id
           )
         ORDER BY heat DESC LIMIT %s
        """,
        (CONFIG.follows_per_tick,),
    )
    for row in cur.fetchall():
        cur.execute(
            "INSERT INTO follows (follower_id, followee_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (row["character_id"], row["other_id"]),
        )
        follows += cur.rowcount

    return likes, follows


def vanity_notifications(cur) -> int:
    """Let characters notice their own numbers.

    The free likes were pure set dressing that no character could perceive — the
    engagement engine and the decision engine were not connected. A post blowing up or
    flopping is exactly what pulls a real person back to the app, and it routes through
    the notification machinery that already exists.
    """
    made = 0

    # Relative, not absolute, and hard-capped per tick.
    #
    # A like is unique per (post, character), so the like ceiling is cast size - 1: a
    # threshold tuned for 50 characters can never fire at 8, and one tuned for 8
    # fires on everything. "Blowing up" has to mean *unusual*, so take only the top few
    # posts of the moment. Self-calibrating at any cast size.
    cur.execute(
        """
        INSERT INTO notifications (character_id, post_id, kind)
        SELECT p.character_id, p.id, 'blowing_up'
          FROM posts p
         WHERE p.world_id = %(world)s
           AND p.character_id IS NOT NULL
           AND p.like_count >= %(floor)s
           AND p.created_at > now() - interval '1 day'
           AND NOT EXISTS (
               SELECT 1 FROM notifications n
                WHERE n.post_id = p.id AND n.kind = 'blowing_up'
           )
         ORDER BY p.like_count DESC, p.heat DESC
         LIMIT %(cap)s
        """,
        {"world": CONFIG.world_id, "floor": CONFIG.blowup_floor, "cap": CONFIG.vanity_per_tick},
    )
    made += cur.rowcount

    # Only characters who would actually care. A quiet character flopping is not a story.
    cur.execute(
        """
        INSERT INTO notifications (character_id, post_id, kind)
        SELECT p.character_id, p.id, 'flopped'
          FROM posts p
          JOIN characters c ON c.id = p.character_id
         WHERE p.world_id = %(world)s
           AND p.parent_id IS NULL
           AND p.like_count = 0 AND p.reply_count = 0
           AND p.created_at < now() - make_interval(mins => %(age)s)
           AND p.created_at > now() - interval '2 days'
           AND (c.engagement_profile->>'aggression')::float >= 0.6
           AND NOT EXISTS (
               SELECT 1 FROM notifications n
                WHERE n.post_id = p.id AND n.kind = 'flopped'
           )
         ORDER BY p.created_at
         LIMIT %(cap)s
        """,
        {
            "world": CONFIG.world_id,
            "age": CONFIG.flop_ticks * CONFIG.tick_interval_minutes,
            "cap": CONFIG.vanity_per_tick,
        },
    )
    made += cur.rowcount
    return made
