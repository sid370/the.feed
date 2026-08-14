"""Measure whether the feed reads as human: action mix, thread size, length, tic rate.

Usage: python -m scripts.voice_audit [--since-hours N]
"""
from __future__ import annotations

import argparse
import re
import sys

from charsocial import db
from charsocial.config import CONFIG

TIC_MIN_CHARS = 4

# One post to a character's name shows every tic at 100% — a sample-size artefact.
TIC_MIN_POSTS = 10

TARGETS = {"originals": 0.40, "max_thread": 20, "tic_rate": 0.15}


def _window(since_hours: float | None) -> tuple[str, dict]:
    """Posts written before a fix are permanent evidence against it, so scope the run."""
    args = {"world": CONFIG.world_id}
    if since_hours is None:
        return "", args
    return " AND p.created_at > now() - make_interval(mins => %(mins)s)", {
        **args, "mins": int(since_hours * 60)
    }


def _rows(cur, sql, args):
    cur.execute(sql, args)
    return [dict(r) for r in cur.fetchall()]


def mix(cur, where, args) -> dict:
    return _rows(
        cur,
        f"""
        SELECT count(*) AS total,
               count(*) FILTER (WHERE p.parent_id IS NOT NULL) AS replies,
               count(*) FILTER (WHERE p.quote_of_id IS NOT NULL) AS quotes,
               count(*) FILTER (WHERE p.parent_id IS NULL
                                  AND p.quote_of_id IS NULL) AS originals
          FROM posts p WHERE p.world_id = %(world)s{where}
        """,
        args,
    )[0]


def threads(cur, where, args) -> list[dict]:
    return _rows(
        cur,
        f"""
        SELECT coalesce(p.root_id, p.id) AS root, count(*) AS n
          FROM posts p WHERE p.world_id = %(world)s{where}
         GROUP BY 1 ORDER BY n DESC LIMIT 8
        """,
        args,
    )


def lengths(cur, where, args) -> list[dict]:
    return _rows(
        cur,
        f"""
        SELECT c.handle, count(*) AS n,
               percentile_disc(0.5) WITHIN GROUP (ORDER BY length(p.body)) AS median_chars,
               max(length(p.body)) AS max_chars
          FROM posts p JOIN characters c ON c.id = p.character_id
         WHERE p.world_id = %(world)s{where}
         GROUP BY 1 ORDER BY median_chars DESC
        """,
        args,
    )


def tics(cur, where, args) -> list[dict]:
    """Count each card's own declared tics against that character's real output."""
    rows = _rows(
        cur,
        f"""
        SELECT c.handle, c.persona_card, p.body
          FROM posts p JOIN characters c ON c.id = p.character_id
         WHERE p.world_id = %(world)s{where}
        """,
        args,
    )
    bodies: dict[str, list[str]] = {}
    cards: dict[str, dict] = {}
    for r in rows:
        bodies.setdefault(r["handle"], []).append(r["body"])
        cards[r["handle"]] = r["persona_card"] or {}

    found = []
    for handle, posts in bodies.items():
        if len(posts) < TIC_MIN_POSTS:
            continue
        for tic in cards[handle].get("tics") or []:
            # Cards also use `tics` for prose descriptions of a habit, which are not countable.
            phrase = str(tic).strip()
            if len(phrase) < TIC_MIN_CHARS or len(phrase.split()) > 6:
                continue
            pattern = re.compile(re.escape(phrase.rstrip(".!")), re.IGNORECASE)
            hits = sum(1 for b in posts if pattern.search(b))
            if hits:
                found.append({"handle": handle, "tic": phrase, "hits": hits,
                              "of": len(posts), "rate": hits / len(posts)})
    return sorted(found, key=lambda f: f["rate"], reverse=True)


def report(since_hours: float | None) -> int:
    """Non-zero exit when a target is missed, so this can gate a change."""
    where, args = _window(since_hours)
    with db.connect() as conn, conn.cursor() as cur:
        counts = mix(cur, where, args)
        thread_rows = threads(cur, where, args)
        length_rows = lengths(cur, where, args)
        tic_rows = tics(cur, where, args)

    scope = f"last {since_hours}h" if since_hours else "all time"
    total = counts["total"] or 1
    original_share = counts["originals"] / total
    biggest = thread_rows[0]["n"] if thread_rows else 0
    worst_tic = tic_rows[0] if tic_rows else None

    print(f"[{scope}] posts {counts['total']}  "
          f"originals {counts['originals']} ({original_share:.0%})  "
          f"replies {counts['replies']}  quotes {counts['quotes']}")
    print("\nlargest threads: " + ", ".join(str(t["n"]) for t in thread_rows))

    print("\nmedian length by character")
    for row in length_rows:
        print(f"  {row['handle']:<16} n={row['n']:<4} median={row['median_chars']:<5} "
              f"max={row['max_chars']}")

    print("\ntic rates (worst 12)")
    for row in tic_rows[:12]:
        print(f"  {row['handle']:<16} {row['rate']:>5.0%}  "
              f"{row['hits']}/{row['of']}  {row['tic']!r}")

    failures = []
    if original_share < TARGETS["originals"]:
        failures.append(f"originals {original_share:.0%} < {TARGETS['originals']:.0%}")
    if biggest > TARGETS["max_thread"]:
        failures.append(f"largest thread {biggest} > {TARGETS['max_thread']}")
    if worst_tic and worst_tic["rate"] > TARGETS["tic_rate"]:
        failures.append(
            f"tic {worst_tic['tic']!r} at {worst_tic['rate']:.0%} > {TARGETS['tic_rate']:.0%}"
        )

    print()
    for f in failures:
        print(f"FAIL  {f}")
    if not failures:
        print("PASS  all targets met")
    return 1 if failures else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--since-hours", type=float, default=None,
                        help="only score posts written in this window")
    sys.exit(report(parser.parse_args().since_hours))
