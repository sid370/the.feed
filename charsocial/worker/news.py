"""Headlines: ingest, gate, cast.

Source restriction is the primary safety control and the classifier is defence in depth —
not the other way round. General news is dominated by tragedy, which is also the most
viral category, so an unrestricted feed reliably hands a comedian persona a death to joke
about. Two layers, and the cheap one does most of the work.
"""
from __future__ import annotations

from charsocial.config import CONFIG, RSS_FEEDS
from charsocial.llm import utility_call
from charsocial.models import Assignment
from charsocial.prompts import CASTING_PROMPT, SAFETY_PROMPT
from charsocial.schemas import CastingPlan, SafetyReport


def fetch_feeds() -> list[tuple[str, str, str]]:
    """Network only — no database handle.

    This deliberately runs BEFORE the tick opens its transaction. Fetching five RSS
    feeds can take tens of seconds, and holding a Postgres transaction open across
    that gets the connection dropped mid-tick.
    """
    try:
        import feedparser
    except ImportError:
        return []

    import socket

    previous = socket.getdefaulttimeout()
    socket.setdefaulttimeout(6)
    entries: list[tuple[str, str, str]] = []
    try:
        for source, url in RSS_FEEDS:
            try:
                feed = feedparser.parse(url)
            except Exception:
                continue
            for entry in feed.entries[:10]:
                title = (getattr(entry, "title", "") or "").strip()
                link = (getattr(entry, "link", "") or "").strip()
                if title and link:
                    entries.append((source, title[:300], link))
    finally:
        socket.setdefaulttimeout(previous)
    return entries


def store(cur, entries: list[tuple[str, str, str]]) -> int:
    added = 0
    for source, title, link in entries:
        cur.execute(
            "INSERT INTO headlines (url, title, source) VALUES (%s, %s, %s) "
            "ON CONFLICT (url) DO NOTHING",
            (link, title, source),
        )
        added += cur.rowcount
    return added


def classify(cur) -> int:
    """Gate anything not yet screened. Unscreened headlines can never be used."""
    cur.execute(
        "SELECT id, title FROM headlines WHERE safe IS NULL ORDER BY ingested_at DESC LIMIT %s",
        (CONFIG.headlines_per_tick * 2,),
    )
    rows = cur.fetchall()
    if not rows:
        return 0

    listing = "\n".join(f"{i}. {r['title']}" for i, r in enumerate(rows))
    report = utility_call(SAFETY_PROMPT.format(headlines=listing), SafetyReport)

    if report is None:
        # No classifier available (offline). Fail closed — unscreened stays unusable.
        return 0

    verdicts = {v.index: v for v in report.verdicts}
    for i, row in enumerate(rows):
        verdict = verdicts.get(i)
        if verdict is None:
            continue
        cur.execute(
            "UPDATE headlines SET safe = %s, reject_reason = %s WHERE id = %s",
            (verdict.safe, None if verdict.safe else verdict.reason[:200], row["id"]),
        )
    return len(rows)


def cast(cur, max_picks: int) -> tuple[list[Assignment], float]:
    """One LLM call that scores newsworthiness and pairs headlines with characters.

    Matching a headline to the character who'd be funniest on it is exactly the judgment
    a scoring function is bad at and a model is good at — which is why the showrunner
    earns its cost here and nowhere else.
    """
    if not CONFIG.news_enabled or max_picks <= 0:
        return [], 0.0

    cur.execute(
        """
        SELECT id, title FROM headlines
         WHERE safe IS TRUE AND used_at IS NULL
         ORDER BY ingested_at DESC LIMIT %s
        """,
        (CONFIG.headlines_per_tick,),
    )
    headlines = cur.fetchall()
    if not headlines:
        return [], 0.0

    cur.execute(
        """
        SELECT handle, name, persona_card->>'bio' AS bio
          FROM characters WHERE status = 'active' AND world_id = %s
        """,
        (CONFIG.world_id,),
    )
    cast_rows = cur.fetchall()
    if not cast_rows:
        return [], 0.0

    plan = utility_call(
        CASTING_PROMPT.format(
            headlines="\n".join(f"{i}. {h['title']}" for i, h in enumerate(headlines)),
            cast="\n".join(f"- @{c['handle']} ({c['name']}): {c['bio']}" for c in cast_rows),
            max_picks=max_picks,
        ),
        CastingPlan,
    )
    if plan is None:
        return [], 0.0

    top = max(plan.traction) if plan.traction else 0
    news_share = _share(top)

    by_handle = {c["handle"]: c for c in cast_rows}
    assignments = []
    for pick in plan.picks[:max_picks]:
        if pick.headline_index >= len(headlines) or pick.character_handle not in by_handle:
            continue
        headline = headlines[pick.headline_index]
        traction = (
            plan.traction[pick.headline_index]
            if pick.headline_index < len(plan.traction)
            else 0
        )
        cur.execute("UPDATE headlines SET traction = %s WHERE id = %s", (traction, headline["id"]))
        assignments.append(
            Assignment(
                handle=pick.character_handle,
                headline_id=headline["id"],
                text=f'Headline: "{headline["title"]}"\nYour angle: {pick.angle}',
            )
        )

    return assignments, news_share


def mark_used(cur, assignments: list[Assignment]) -> None:
    """Called after the tick truncates to its news budget.

    `cast` proposes up to the full budget but only `news_share` of them get a turn.
    Stamping used_at inside cast burned the rest permanently without anyone posting them.
    """
    ids = [a.headline_id for a in assignments]
    if ids:
        cur.execute("UPDATE headlines SET used_at = now() WHERE id = ANY(%s)", (ids,))


def _share(top_traction: int) -> float:
    """Newsworthiness drives the mix, so the feed breathes with the news cycle: a big
    story pulls most of the tick, a quiet day leaves the world to its own drama."""
    if top_traction <= 0:
        return 0.0
    scaled = (top_traction - 1) / 9.0
    span = CONFIG.news_share_ceiling - CONFIG.news_share_floor
    return round(CONFIG.news_share_floor + span * scaled, 3)
