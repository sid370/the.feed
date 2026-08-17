"""Collect the previous tick's batch and write its consequences into the world.

Collect-then-submit is why there is no long-running worker and no polling loop: each tick
collects the batch the last one submitted, then submits its own. Posts land one tick late,
which is invisible on a 30-minute clock.

Isolation matters here more than anywhere else. A model can hallucinate a post id, and
without a savepoint per decision one bad id aborts the whole transaction — the batch then
stays 'submitted', gets re-collected next tick, and fails identically forever. One turn in
384 a day is a when, not an if.
"""
from __future__ import annotations

import uuid as uuidlib

from charsocial import db
from charsocial.config import CONFIG
from charsocial.llm import LLMError, LLMFatalError, provider
from charsocial.models import Usage
from charsocial.worker import heat

VALID_ACTIONS = {"reply", "quote", "like", "follow", "post", "scroll"}


def collect_open_batches(cur: db.Cursor) -> int:
    cur.execute(
        "SELECT id, payload, submitted_at FROM batches WHERE status = 'submitted' "
        "ORDER BY submitted_at"
    )
    written = 0
    for batch in cur.fetchall():
        payload = batch["payload"] or {}
        # Older rows stored the turn map at the top level.
        turns = payload.get("turns", payload)
        usage = Usage()

        # Offline decisions are computed at submit time and stored in the row, so they
        # survive a process restart — every `make tick` is a fresh process.
        results = payload.get("results")

        if results is None:
            try:
                collected = provider().collect_turns(batch["id"])
            except LLMFatalError as exc:
                # Can never resolve — most often a leftover `local:` id after switching
                # from offline to anthropic on the same database. Retrying would wedge
                # every future tick on this one row.
                _fail(cur, batch["id"], str(exc))
                continue
            except LLMError as exc:
                continue  # transient; leave it submitted and retry next tick
            except Exception as exc:
                _fail(cur, batch["id"], f"collect failed: {exc}")
                continue

            if collected is None:
                continue  # still running; try again next tick
            results = collected.decisions
            usage = collected.usage

        for custom_id, decision in (results or {}).items():
            written += _apply_isolated(
                cur, turns.get(custom_id, {}), decision, batch["submitted_at"]
            )

        cur.execute(
            """
            UPDATE batches SET status = 'collected', collected_at = now(),
                   input_tokens = %s, output_tokens = %s,
                   cache_read_tokens = %s, cache_write_tokens = %s
             WHERE id = %s
            """,
            (
                usage.input,
                usage.output,
                usage.cache_read,
                usage.cache_write,
                batch["id"],
            ),
        )
    return written


def _fail(cur: db.Cursor, batch_id: str, reason: str) -> None:
    """`failed` is a terminal state the schema always documented. Writing it is what stops
    one bad batch from blocking the queue permanently."""
    cur.execute(
        "UPDATE batches SET status = 'failed', collected_at = now(), "
        "payload = payload || jsonb_build_object('error', %s::text) WHERE id = %s",
        (reason[:400], batch_id),
    )


def _apply_isolated(cur: db.Cursor, ctx: dict, decision: dict, submitted_at) -> int:
    """One bad decision must cost one decision, not the tick."""
    cur.execute("SAVEPOINT turn")
    try:
        written = _apply(cur, ctx, decision, submitted_at)
        cur.execute("RELEASE SAVEPOINT turn")
        return written
    except Exception:
        cur.execute("ROLLBACK TO SAVEPOINT turn")
        cur.execute("RELEASE SAVEPOINT turn")
        return 0


def _apply(cur: db.Cursor, ctx: dict, decision: dict, submitted_at) -> int:
    character_id = ctx.get("character_id")
    if not character_id or not isinstance(decision, dict):
        return 0

    # The batch payload round-trips through JSON, so this arrives as a string while every id
    # read back out of the database is a UUID. `"37b4…" == UUID("37b4…")` is False, so every
    # is-this-me guard downstream fails open. That was unreachable while build_slate was the
    # only source of targets — it excludes your own posts — and became reachable the moment
    # a character could aim at its own thread. Left alone it takes out the whole turn: the
    # self-relation trips a check constraint and the savepoint discards the reply.
    try:
        character_id = uuidlib.UUID(str(character_id))
    except (ValueError, AttributeError, TypeError):
        return 0

    action = decision.get("action")
    if action not in VALID_ACTIONS:
        return 0

    _consume_notifications(cur, character_id, submitted_at)
    _record_memory(
        cur, character_id, decision.get("memory_note"), decision.get("memory_importance")
    )

    # A hallucinated id must degrade to "no target", never raise. The slate the model saw
    # used short ids, so resolve through that map first; a raw UUID still parses, which
    # keeps batches submitted before the map existed collectable.
    raw_target = decision.get("target_post_id")
    raw_target = (ctx.get("slate_ids") or {}).get(raw_target, raw_target)
    target_id = _valid_post_id(cur, raw_target)
    target_author = _author_of(cur, target_id) if target_id else None

    if target_author:
        heat.bump_relation(
            cur,
            character_id,
            target_author,
            _clamp(decision.get("feeling_delta")),
            note=decision.get("relation_note"),
        )

    if action == "scroll":
        return 0

    if action == "like":
        _like(cur, target_id, character_id)
        return 0

    if action == "follow":
        if target_author:
            cur.execute(
                "INSERT INTO follows (follower_id, followee_id) VALUES (%s, %s) "
                "ON CONFLICT DO NOTHING",
                (character_id, target_author),
            )
        return 0

    body = (decision.get("body") or "").strip()
    if not body:
        return 0

    # Dropped, not degraded. Publishing a reply as a top-level post puts "Dario, that
    # discomfort you just named..." in the timeline addressed to nobody, which is worse
    # than losing the generation we already paid for.
    if action in {"reply", "quote"} and not target_id:
        return 0

    if action == "post":
        _write_post(cur, character_id, body, headline_id=ctx.get("headline_id"))
        return 1

    if action == "quote":
        new_id = _write_post(cur, character_id, body, quote_of_id=target_id)
        # Point at the QUOTE, not at what was quoted — see _notify.
        _notify(cur, target_author, new_id, "quote", actor=character_id)
        heat.bump_post(cur, target_id, count_reply=False)  # a quote has no child post
        return 1

    root_id = _root_of(cur, target_id) or target_id
    new_id = _write_post(cur, character_id, body, parent_id=target_id, root_id=root_id)
    _notify(cur, target_author, new_id, "reply", actor=character_id)
    heat.bump_post(cur, target_id, count_reply=True)
    return 1


def _valid_post_id(cur: db.Cursor, raw):
    """Models invent post ids. Parse, then confirm the row exists."""
    if not raw:
        return None
    try:
        parsed = uuidlib.UUID(str(raw))
    except (ValueError, AttributeError, TypeError):
        return None
    cur.execute("SELECT 1 FROM posts WHERE id = %s", (parsed,))
    return parsed if cur.fetchone() else None


def _clamp(value) -> int:
    try:
        return max(-2, min(2, int(value or 0)))
    except (TypeError, ValueError):
        return 0


def _write_post(cur: db.Cursor, character_id, body, **kw):
    cur.execute(
        """
        INSERT INTO posts (world_id, character_id, body, parent_id, root_id,
                           quote_of_id, headline_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            CONFIG.world_id,
            character_id,
            body[:500],
            kw.get("parent_id"),
            kw.get("root_id"),
            kw.get("quote_of_id"),
            kw.get("headline_id"),
        ),
    )
    new_id = db.one(cur)["id"]
    if not kw.get("parent_id"):
        cur.execute("UPDATE posts SET root_id = id WHERE id = %s AND root_id IS NULL", (new_id,))
    return new_id


def _like(cur: db.Cursor, post_id, character_id) -> None:
    if not post_id:
        return
    cur.execute(
        "INSERT INTO likes (post_id, character_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
        (post_id, character_id),
    )
    if cur.rowcount:
        cur.execute("UPDATE posts SET like_count = like_count + 1 WHERE id = %s", (post_id,))


def _notify(cur: db.Cursor, character_id, post_id, kind, actor=None) -> None:
    """`post_id` is the post that was JUST WRITTEN, never the one it answers.

    Pointing a notification at the recipient's own post made it invisible: build_slate
    excludes your own posts, so the row was filtered out and `to_you` could never be
    true. A character with sixteen replies was pulled in by the urgency count and then
    shown a generic feed with none of them flagged — they could not see who was talking
    to them.
    """
    if not character_id or not post_id:
        return
    # A character can aim a reply or a quote at its own thread now, so the recipient is
    # sometimes the author. Notifying yourself adds to your own pending count, which is
    # urgency in select_turns — a character would pull itself back for another turn on the
    # strength of having posted, and keep doing it.
    if actor is not None and character_id == actor:
        return
    cur.execute(
        "INSERT INTO notifications (character_id, post_id, kind) VALUES (%s, %s, %s)",
        (character_id, post_id, kind),
    )


def _consume_notifications(cur: db.Cursor, character_id, submitted_at) -> None:
    """Only clear what this character could actually have SEEN.

    The slate was built at submit time, so anything that arrived afterwards — a reply
    landing in the same collect pass, or a human poke sent while the batch was in
    flight — has not been shown to anyone yet. Sweeping those destroys the ping-pong
    that produces beefs, and silently eats visitor pokes.
    """
    cur.execute(
        "UPDATE notifications SET consumed_at = now() "
        "WHERE character_id = %s AND consumed_at IS NULL AND created_at <= %s",
        (character_id, submitted_at),
    )


def _record_memory(cur: db.Cursor, character_id, note, importance=None) -> None:
    note = (note or "").strip()
    if note:
        try:
            weight = max(1, min(10, int(importance if importance is not None else 5)))
        except (TypeError, ValueError):
            weight = 5
        cur.execute(
            "INSERT INTO memory_notes (character_id, note, importance) VALUES (%s, %s, %s)",
            (character_id, note[:280], weight),
        )


def _author_of(cur: db.Cursor, post_id):
    cur.execute("SELECT character_id FROM posts WHERE id = %s", (post_id,))
    row = cur.fetchone()
    return row["character_id"] if row else None


def _root_of(cur: db.Cursor, post_id):
    cur.execute("SELECT coalesce(root_id, id) AS root FROM posts WHERE id = %s", (post_id,))
    row = cur.fetchone()
    return row["root"] if row else None
