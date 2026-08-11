"""Build this tick's turns and submit them as one batch.

This is the only place in the entire system that spends money. That is the invariant the
whole design rests on: one chokepoint means the budget is actually enforceable.
"""
from __future__ import annotations

import json
import uuid

from charsocial import db
from charsocial.llm import LLMError, provider
from charsocial.models import ActingCharacter, Assignment, Submission
from charsocial.prompts import system_blocks, turn_prompt
from charsocial.schemas import Decision, json_schema
from charsocial.worker import scheduler

DECISION_SCHEMA = json_schema(Decision)


def submit_turns(
    cur,
    characters: list[ActingCharacter],
    assignments: list[Assignment],
    tick_id: int,
) -> tuple[str | None, int]:
    if not characters:
        return None, 0

    by_handle = {a.handle: a for a in assignments}
    turns, payload = [], {}

    for character in characters:
        assignment = by_handle.pop(character.handle, None)
        ctx = scheduler.build_context(
            cur, character, assignment=assignment.text if assignment else None
        )
        custom_id = f"turn-{uuid.uuid4().hex[:16]}"

        turns.append(
            {
                "custom_id": custom_id,
                "prompt": turn_prompt(ctx),
                "schema": DECISION_SCHEMA,
                "model": character.model,
                # offline provider reads these to pick a canned decision in the
                # character's own voice rather than inventing filler
                "name": character.name,
                "slate": [s.model_dump(mode="json") for s in ctx.slate],
                "samples": (ctx.persona_card or {}).get("samples") or {},
            }
        )
        payload[custom_id] = {
            "character_id": str(character.id),
            "headline_id": str(assignment.headline_id) if assignment else None,
            "intent": character.intent,
        }

    try:
        submission = provider().submit_turns(turns, system_blocks())
    except LLMError:
        return None, 0

    _record_batch(submission, tick_id, payload, len(turns))
    return submission.batch_id, len(turns)


def _record_batch(
    submission: Submission, tick_id: int, payload: dict, turn_count: int
) -> None:
    """Committed on its own connection, immediately.

    `submit_turns` already spent money. If the row recording the batch id rode the tick's
    transaction it would sit uncommitted through engagement writes and the final update —
    and a crash in that window would orphan a paid batch with no way to find it again.
    """
    body = {"turns": payload}
    if submission.inline_results is not None:
        body["results"] = submission.inline_results

    with db.connect() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO batches (id, tick_id, turn_count, payload) VALUES (%s, %s, %s, %s)",
            (submission.batch_id, tick_id, turn_count, json.dumps(body)),
        )
        conn.commit()
