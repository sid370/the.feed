"""Character ingestion and lifecycle.

Authoring is the real bottleneck — 40 hand-written cards is days of work and you stop at
twelve. So the model drafts and a human approves. For well-known figures the model already
holds the knowledge from pretraining, so asking it to WRITE the card beats extracting one
from source material, in one call.

`source_material` is the escape hatch for subjects outside pretraining. A full
video -> transcript pipeline later becomes a pre-processing step in front of this same
function, not a new system.
"""
from __future__ import annotations

import json

from charsocial import db
from charsocial.config import CONFIG
from charsocial.llm import utility_call
from charsocial.prompts import DRAFT_PROMPT
from charsocial.schemas import CharacterDraft


def draft(
    cur: db.Cursor, name: str, context: str, notes: str = "", source_material: str = ""
) -> dict | None:
    result = utility_call(
        DRAFT_PROMPT.format(
            name=name,
            context=context,
            notes=f"Extra direction: {notes}" if notes else "",
            source=f"Source material:\n{source_material[:8000]}" if source_material else "",
        ),
        CharacterDraft,
    )
    if result is None:
        return None

    handle = _unique_handle(cur, result.handle)
    cur.execute(
        """
        INSERT INTO characters (world_id, handle, name, status, persona_card,
                                engagement_profile, avatar_seed)
        VALUES (%s, %s, %s, 'draft', %s, %s, %s)
        RETURNING id, handle, name, status
        """,
        (
            CONFIG.world_id,
            handle,
            name,
            json.dumps(result.persona_card.model_dump()),
            json.dumps(result.engagement_profile.model_dump()),
            handle,
        ),
    )
    return dict(db.one(cur))


def activate(cur: db.Cursor, character_id) -> None:
    """The only place an agent acquires world presence: relations against the existing
    cast, a few follows, and eligibility for turns."""
    cur.execute(
        "UPDATE characters SET status = 'active', activated_at = coalesce(activated_at, now()) "
        "WHERE id = %s AND status <> 'retired'",
        (character_id,),
    )
    cur.execute(
        """
        INSERT INTO relations (character_id, other_id)
        SELECT %(me)s, c.id FROM characters c
         WHERE c.id <> %(me)s AND c.world_id = %(world)s AND c.status IN ('active','paused')
        ON CONFLICT DO NOTHING
        """,
        {"me": character_id, "world": CONFIG.world_id},
    )
    cur.execute(
        """
        INSERT INTO relations (character_id, other_id)
        SELECT c.id, %(me)s FROM characters c
         WHERE c.id <> %(me)s AND c.world_id = %(world)s AND c.status IN ('active','paused')
        ON CONFLICT DO NOTHING
        """,
        {"me": character_id, "world": CONFIG.world_id},
    )
    cur.execute(
        """
        INSERT INTO follows (follower_id, followee_id)
        SELECT %(me)s, c.id FROM characters c
         WHERE c.id <> %(me)s AND c.world_id = %(world)s AND c.status = 'active'
         ORDER BY random() LIMIT 5
        ON CONFLICT DO NOTHING
        """,
        {"me": character_id, "world": CONFIG.world_id},
    )


def set_status(cur: db.Cursor, character_id, status: str) -> None:
    if status not in {"draft", "active", "paused", "retired"}:
        raise ValueError(f"unknown status {status}")
    if status == "active":
        activate(cur, character_id)
        return
    cur.execute("UPDATE characters SET status = %s WHERE id = %s", (status, character_id))


def _unique_handle(cur: db.Cursor, handle: str) -> str:
    handle = "".join(ch for ch in handle.lower() if ch.isalnum() or ch == "_")[:28] or "character"
    candidate, n = handle, 1
    while True:
        cur.execute("SELECT 1 FROM characters WHERE handle = %s", (candidate,))
        if not cur.fetchone():
            return candidate
        n += 1
        candidate = f"{handle}{n}"
