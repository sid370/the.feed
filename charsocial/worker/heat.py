"""Heat — one mechanic at two scopes.

On relations it picks WHO talks to whom: interacting raises heat, high heat raises the
chance of interacting again, so a beef becomes an attractor state that forms on its own.
On posts it picks WHERE attention goes, producing one thread with thirty replies and ten
with none.

Decay is what stops either from ossifying. Without it, the first two characters to clash
lock the feed forever.
"""
from charsocial import db
from charsocial.config import CONFIG


def bump_relation(
    cur: db.Cursor, character_id, other_id, feeling_delta: int = 0, note: str | None = None
) -> None:
    """`note` is the character's own read on the other person — deliberately their belief,
    not the truth. A written-down wrong belief is what lets a misunderstanding persist
    across ticks instead of resetting, which is the whole engine of a running joke."""
    if character_id is None or other_id is None or character_id == other_id:
        return
    clean = (note or "").strip()[:140] or None
    cur.execute(
        """
        INSERT INTO relations (character_id, other_id, heat, sentiment, note, last_interaction)
        VALUES (%(me)s, %(them)s, %(gain)s, %(delta)s, %(note)s, now())
        ON CONFLICT (character_id, other_id) DO UPDATE
           SET heat = least(relations.heat + %(gain)s, %(ceiling)s),
               sentiment = greatest(-5, least(5, relations.sentiment + %(delta)s)),
               note = coalesce(%(note)s, relations.note),
               last_interaction = now()
        """,
        {
            "me": character_id,
            "them": other_id,
            "gain": CONFIG.relation_heat_gain,
            "delta": feeling_delta,
            "note": clean,
            "ceiling": CONFIG.relation_heat_ceiling,
        },
    )


def bump_post(cur: db.Cursor, post_id, count_reply: bool = True) -> None:
    """A quote raises attention but creates no child post, so it must not inflate
    reply_count — the UI renders that number literally."""
    if post_id is None:
        return
    if count_reply:
        cur.execute(
            "UPDATE posts SET heat = heat + %s, reply_count = reply_count + 1 WHERE id = %s",
            (CONFIG.post_heat_gain, post_id),
        )
    else:
        cur.execute(
            "UPDATE posts SET heat = heat + %s WHERE id = %s", (CONFIG.post_heat_gain, post_id)
        )


def decay(cur: db.Cursor) -> None:
    cur.execute("UPDATE relations SET heat = heat * %s WHERE heat > 0.01", (CONFIG.relation_heat_decay,))
    cur.execute("UPDATE relations SET heat = 0 WHERE heat <= 0.01")
    cur.execute(
        "UPDATE posts SET heat = heat * %s WHERE heat > 0.01 AND created_at > now() - interval '7 days'",
        (CONFIG.post_heat_decay,),
    )
