"""Seed the world with a starting cast.

The cast lives in `characters/*.md`, one file per character: a fenced ```json block
holding the card and engagement profile, with voice notes in prose underneath. Markdown
because `samples` is the single highest-leverage field for voice quality and it is worth
editing somewhere readable. Everyone after this should be drafted by the model through
/api/admin/characters/draft and hand-edited only if they sound generic.

Every card is a performance of a public persona — style, obsessions, register. None
asserts anything factual about a real person's private life, health, family, legal
situation or finances, and `avoid` is where that boundary is enforced per character.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from charsocial import db
from charsocial.config import CONFIG

CHARACTERS_DIR = Path(__file__).resolve().parent.parent / "characters"

JSON_FENCE = re.compile(r"```json\s*\n(.*?)\n```", re.DOTALL)

CARD_FIELDS = {"bio", "voice", "tics", "obsessions", "beefs", "avoid", "samples"}
SAMPLE_GROUPS = {"posts", "replies", "quotes", "subtweets"}
PROFILE_FIELDS = {"opens_per_day", "reply_rate", "aggression",
                  "notification_sensitivity", "triggers"}


def load_cast() -> list[dict]:
    """Parse every character file, failing loudly rather than seeding a malformed card."""
    cast = []
    for path in sorted(CHARACTERS_DIR.glob("*.md")):
        fence = JSON_FENCE.search(path.read_text(encoding="utf-8"))
        if not fence:
            raise ValueError(f"{path.name}: no ```json block")
        try:
            entry = json.loads(fence.group(1))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path.name}: malformed JSON — {exc}") from exc

        missing = {"handle", "name", "real", "card", "profile"} - entry.keys()
        if missing:
            raise ValueError(f"{path.name}: missing {sorted(missing)}")
        if entry["handle"] != path.stem:
            raise ValueError(f"{path.name}: handle is {entry['handle']!r}")
        if CARD_FIELDS - entry["card"].keys():
            raise ValueError(f"{path.name}: card missing "
                             f"{sorted(CARD_FIELDS - entry['card'].keys())}")
        samples = entry["card"]["samples"]
        if not isinstance(samples, dict) or SAMPLE_GROUPS - samples.keys():
            raise ValueError(f"{path.name}: samples must be grouped by "
                             f"{sorted(SAMPLE_GROUPS)}")
        if PROFILE_FIELDS - entry["profile"].keys():
            raise ValueError(f"{path.name}: profile missing "
                             f"{sorted(PROFILE_FIELDS - entry['profile'].keys())}")
        cast.append(entry)

    if not cast:
        raise ValueError(f"no character files in {CHARACTERS_DIR}")
    return cast


def seed() -> None:
    from charsocial.worker import characters as chars

    cast = load_cast()
    db.migrate()
    with db.cursor() as cur:
        created = 0
        for entry in cast:
            cur.execute("SELECT id FROM characters WHERE handle = %s", (entry["handle"],))
            if cur.fetchone():
                continue
            cur.execute(
                """
                INSERT INTO characters (world_id, handle, name, status, is_real_person,
                                        avatar_seed, persona_card, engagement_profile)
                VALUES (%s, %s, %s, 'draft', %s, %s, %s, %s) RETURNING id
                """,
                (
                    CONFIG.world_id,
                    entry["handle"],
                    entry["name"],
                    entry["real"],
                    entry["handle"],
                    json.dumps(entry["card"]),
                    json.dumps(entry["profile"]),
                ),
            )
            chars.activate(cur, cur.fetchone()["id"])
            created += 1

        # One post so the first tick has a non-empty slate to react to.
        cur.execute("SELECT count(*) AS n FROM posts")
        if cur.fetchone()["n"] == 0:
            cur.execute("SELECT id FROM characters WHERE handle = %s", (cast[0]["handle"],))
            row = cur.fetchone()
            if row:
                cur.execute(
                    "INSERT INTO posts (world_id, character_id, body) VALUES (%s, %s, %s) "
                    "RETURNING id",
                    (CONFIG.world_id, row["id"], "first post."),
                )
                seed_id = cur.fetchone()["id"]
                cur.execute("UPDATE posts SET root_id = id WHERE id = %s", (seed_id,))

    print(f"seeded {created} characters ({len(cast)} in cast)")


if __name__ == "__main__":
    seed()
