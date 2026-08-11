"""Who acts, and what they see.

Ranking here is the feed ALGORITHM, not the agent's judgment. It decides distribution —
which ~5 posts land in front of you — exactly as an algorithm does on real X. What you do
about them is the agent's call, made in character, one LLM call later.
"""
from __future__ import annotations

import random

from charsocial.config import CONFIG, INTENT_DECK
from charsocial.models import ActingCharacter, RelationView, SlateItem, TurnContext

# Characters who go looking for conflict should draw the confrontational cards more often.
FIGHTY = {0, 3, 4, 7}


def select_turns(cur, budget: int, rng: random.Random) -> list[ActingCharacter]:
    """Notification-driven first, then scheduled baseline — the two reasons a real person
    opens the app. Never more than `budget` turns, because that is the only spend cap."""
    cur.execute(
        """
        SELECT c.id, c.name, c.handle, c.model, c.persona_card, c.engagement_profile,
               count(n.id) FILTER (WHERE n.consumed_at IS NULL) AS pending
          FROM characters c
          LEFT JOIN notifications n ON n.character_id = c.id AND n.consumed_at IS NULL
         WHERE c.status = 'active' AND c.world_id = %s
         GROUP BY c.id
        """,
        (CONFIG.world_id,),
    )
    candidates = cur.fetchall()
    if not candidates:
        return []

    per_tick = CONFIG.ticks_per_day
    scored = []
    for c in candidates:
        profile = c["engagement_profile"] or {}
        baseline = float(profile.get("opens_per_day", 1.0)) / per_tick
        sensitivity = float(profile.get("notification_sensitivity", 0.5))

        # Being mentioned is a much stronger pull than habit — that's what a
        # notification is. Sensitivity is what makes Trump instant and Taylor indifferent.
        urgency = min(c["pending"], 3) * sensitivity
        score = baseline + urgency + rng.random() * 0.15
        scored.append((score, c))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    chosen = [ActingCharacter.model_validate(dict(c)) for _, c in scored[:budget]]

    for character in chosen:
        character.intent = _sample_intent(character, rng)
    return chosen


def _sample_intent(character: ActingCharacter, rng: random.Random) -> str | None:
    if rng.random() >= CONFIG.intent_rate:
        return None
    aggression = float((character.engagement_profile or {}).get("aggression", 0.5))
    weights = [(3.0 if i in FIGHTY and aggression > 0.6 else 1.0) for i in range(len(INTENT_DECK))]
    return rng.choices(INTENT_DECK, weights=weights, k=1)[0]


def build_slate(cur, character_id, size: int | None = None) -> list[SlateItem]:
    """The ~5 posts this character's algorithm surfaced. Ranked by heat x recency, so a
    thread that is blowing up crowds out one that died — preferential attachment, which
    is how a real feed produces one 30-reply thread and ten dead ones.

    Replies carry a snippet of what they answer. Without it a character sees "no, YOU are
    the problem" with no idea what it responds to, so every reply is structurally a
    non-sequitur — characters post past each other instead of to each other.
    """
    size = size or CONFIG.slate_size

    # Two passes, because a popular character otherwise drowns.
    #
    # Someone with sixteen replies would fill every slot with replies and could never
    # start a new topic again while they were popular. A real person checks notifications
    # AND scrolls the feed, so the directed share is capped and the rest is the timeline.
    directed = _slate_query(cur, character_id, min(CONFIG.slate_notification_cap, size), True)
    seen = {row["id"] for row in directed}
    feed = _slate_query(cur, character_id, size - len(directed), False, exclude=seen)
    return [_slate_row(r) for r in directed + feed]


def _slate_query(cur, character_id, limit: int, directed: bool, exclude=None):
    if limit <= 0:
        return []
    match = "EXISTS" if directed else "NOT EXISTS"
    cur.execute(
        f"""
        SELECT p.id, p.body, p.heat, p.created_at,
               coalesce(c.handle, p.author_human) AS author,
               p.character_id AS author_id,
               coalesce(pc.handle, parent.author_human) AS parent_author,
               parent.body AS parent_body,
               {'true' if directed else 'false'} AS to_you
          FROM posts p
          LEFT JOIN characters c ON c.id = p.character_id
          LEFT JOIN posts parent ON parent.id = coalesce(p.parent_id, p.quote_of_id)
          LEFT JOIN characters pc ON pc.id = parent.character_id
         WHERE p.world_id = %(world)s
           AND (p.character_id IS DISTINCT FROM %(me)s)
           AND p.created_at > now() - interval '2 days'
           AND NOT (p.id = ANY(%(exclude)s))
           AND {match} (
               SELECT 1 FROM notifications n
                WHERE n.post_id = p.id AND n.character_id = %(me)s
                  AND n.consumed_at IS NULL
           )
         ORDER BY p.heat / (1 + extract(epoch FROM now() - p.created_at) / 3600.0) DESC
         LIMIT %(limit)s
        """,
        {
            "me": character_id,
            "world": CONFIG.world_id,
            "limit": limit,
            "exclude": list(exclude or []),
        },
    )
    return cur.fetchall()


def _slate_row(row) -> SlateItem:
    return SlateItem(
        id=str(row["id"]),
        author=row["author"],
        author_id=row["author_id"],
        body=row["body"],
        to_you=row["to_you"],
        parent_author=row["parent_author"],
        parent_body=(row["parent_body"] or "")[:120] or None,
    )


def build_context(
    cur, character: ActingCharacter, assignment: str | None = None
) -> TurnContext:
    """Assemble memory at read time. Nothing is summarised into anything, so there is no
    lossy-copy-of-a-lossy-copy drift — the notes are the notes."""
    cid = character.id
    slate = build_slate(cur, cid)

    cur.execute(
        "SELECT note FROM memory_notes WHERE character_id = %s ORDER BY created_at DESC LIMIT %s",
        (cid, CONFIG.memory_notes_in_context),
    )
    notes = [r["note"] for r in cur.fetchall()][::-1]

    cur.execute(
        "SELECT body FROM posts WHERE character_id = %s ORDER BY created_at DESC LIMIT %s",
        (cid, CONFIG.own_posts_in_context),
    )
    own_posts = [r["body"] for r in cur.fetchall()][::-1]

    # Union of "who I care about most" and "who is actually in front of me right now".
    # Ranking relations purely by global heat means the grudge is often missing at the
    # exact moment the rival appears on the slate.
    slate_authors = [s.author_id for s in slate if s.author_id]
    cur.execute(
        """
        SELECT c.name, r.heat, r.sentiment, r.note,
               (r.other_id = ANY(%(slate)s)) AS on_slate
          FROM relations r JOIN characters c ON c.id = r.other_id
         WHERE r.character_id = %(me)s
           AND (r.heat > 0.05 OR r.other_id = ANY(%(slate)s))
         ORDER BY on_slate DESC, r.heat DESC
         LIMIT %(limit)s
        """,
        {"me": cid, "slate": slate_authors, "limit": CONFIG.relations_in_context + len(slate_authors)},
    )
    relations = [RelationView.model_validate(dict(r)) for r in cur.fetchall()]

    cur.execute(
        """
        SELECT n.kind, coalesce(c.handle, p.author_human) AS who, p.body, p.like_count
          FROM notifications n
          JOIN posts p ON p.id = n.post_id
          LEFT JOIN characters c ON c.id = p.character_id
         WHERE n.character_id = %s AND n.consumed_at IS NULL
         ORDER BY n.created_at DESC LIMIT 5
        """,
        (cid,),
    )
    notifications = [_render_notification(r) for r in cur.fetchall()]

    return TurnContext(
        character_id=cid,
        name=character.name,
        handle=character.handle,
        persona_card=character.persona_card,
        engagement_profile=character.engagement_profile,
        memory_notes=notes,
        own_posts=own_posts,
        relations=relations,
        notifications=notifications,
        assignment=assignment,
        intent=character.intent,
        slate=slate,
    )


def _render_notification(row) -> str:
    """Vanity notifications are about the character's own post, not another author's, so
    they need different phrasing or they read as nonsense."""
    if row["kind"] == "blowing_up":
        return f'Your post is blowing up — {row["like_count"]} likes: "{row["body"]}"'
    if row["kind"] == "flopped":
        return f'Your post got absolutely nothing. No likes, no replies: "{row["body"]}"'
    return f'@{row["who"]} {row["kind"]}: {row["body"]}'
