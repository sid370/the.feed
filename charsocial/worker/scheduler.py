"""Who acts, and what they see.

Ranking here is the feed ALGORITHM, not the agent's judgment. It decides distribution —
which ~5 posts land in front of you — exactly as an algorithm does on real X. What you do
about them is the agent's call, made in character, one LLM call later.
"""
from __future__ import annotations

import random
import re

from charsocial import db
from charsocial.config import CONFIG, INTENT_DECK
from charsocial.models import ActingCharacter, RelationView, SlateItem, TurnContext

# Characters who go looking for conflict should draw the confrontational cards more often.
FIGHTY = {0, 3, 4, 7}

CANDIDATE_POOL = 5

# Filled on first use from the whole cast; see common_terms.
_COMMON: frozenset[str] | None = None


def select_turns(cur: db.Cursor, budget: int, rng: random.Random) -> list[ActingCharacter]:
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


def build_slate(cur: db.Cursor, character_id, size: int | None = None,
                interests: tuple[str, ...] = ()) -> list[SlateItem]:
    """The ~5 posts this character's algorithm surfaced.

    Candidates are filtered in SQL and then scored and selected in Python, which is the
    split X's own For You pipeline uses and the only way the selection rules below can see
    what has already been picked.

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
    cap = min(CONFIG.slate_notification_cap, size)
    # Affinity is deliberately absent from the directed pass: somebody talking to you is
    # relevant whether or not they happened to mention one of your obsessions.
    directed = _select(_candidates(cur, character_id, cap, True), cap)
    seen = {row["id"] for row in directed}
    feed = _select(
        _candidates(cur, character_id, size - len(directed), False, exclude=seen),
        size - len(directed),
        interests,
    )
    return [_slate_row(r) for r in directed + feed]


def _raw_terms(card: dict, profile: dict) -> set[str]:
    """`obsessions` and `triggers` only, at seven characters or more.

    `beefs` is written as "people who do X" clauses, so it contributed mostly verbs and
    function words; dropping it roughly halved the term count and left the nouns. The length
    floor is doing the same job crudely — "engineering" and "cardinality" survive it,
    "across" and "answer" do not.
    """
    raw = list(card.get("obsessions") or []) + list(profile.get("triggers") or [])
    words: set[str] = set()
    for phrase in raw:
        words.update(re.findall(r"[a-z]{7,}", str(phrase).lower()))
    return words


def common_terms(cur: db.Cursor) -> frozenset[str]:
    """Terms appearing across many cards, which therefore distinguish nobody.

    Cards write `obsessions` and `beefs` as prose, so naive word extraction pulls in
    "account", "across", "answers" alongside "rockets" and "cardinality". A blocklist of
    English function words never ends; asking which terms are shared by much of the cast
    does the same job and tunes itself as characters are added. Cached per process — the
    cast changes on a re-seed, not on a tick.
    """
    global _COMMON
    if _COMMON is None:
        cur.execute(
            "SELECT persona_card, engagement_profile FROM characters WHERE world_id = %s",
            (CONFIG.world_id,),
        )
        rows = cur.fetchall()
        counts: dict[str, int] = {}
        for row in rows:
            for term in _raw_terms(row["persona_card"] or {}, row["engagement_profile"] or {}):
                counts[term] = counts.get(term, 0) + 1
        ceiling = max(2, len(rows) // 6)
        _COMMON = frozenset(t for t, n in counts.items() if n > ceiling)
    return _COMMON


def interest_terms(cur: db.Cursor, card: dict, profile: dict) -> tuple[str, ...]:
    """What a character steers toward, from their own card, minus what everyone shares.

    Phoenix does this with embeddings; at 39 characters and a few thousand posts a term
    match is most of the benefit for none of the infrastructure. Without it every character
    sees the same hottest posts and engages with whatever is in front of them, which is
    what reads as having no taste.
    """
    return tuple(sorted(_raw_terms(card, profile) - common_terms(cur)))


def _affinity(body: str, interests: tuple[str, ...]) -> float:
    if not interests:
        return 1.0
    hits = sum(1 for term in interests if term in body.lower())
    return 1.0 + CONFIG.interest_boost * min(hits, 3)


def _diversity_multiplier(k: int) -> float:
    """home-mixer's `diversity_multiplier`: (1 - floor) * decay^k + floor."""
    return (1 - CONFIG.author_floor) * CONFIG.author_decay**k + CONFIG.author_floor


def _select(rows: list, limit: int, interests: tuple[str, ...] = ()) -> list:
    """Apply interest affinity and author diversity, then take the best posts one
    conversation at a time.

    `k` is an author's rank among their OWN candidates, so every multiplier is known
    before selection starts — this is how `compute_slate_contexts` does it in home-mixer.
    """
    weighted = [(r["rank_score"] * _affinity(r.get("body") or "", interests), r) for r in rows]
    weighted.sort(key=lambda pair: pair[0], reverse=True)
    per_author: dict = {}
    scored = []
    for base, row in weighted:
        k = per_author.get(row["author_id"], 0)
        per_author[row["author_id"]] = k + 1
        scored.append((base * _diversity_multiplier(k), row))

    chosen: list = []
    roots: set = set()
    for _, row in sorted(scored, key=lambda pair: pair[0], reverse=True):
        if len(chosen) >= limit:
            break
        # One branch of a conversation per slate. Three replies from the same argument is
        # how a character ends up answering the same point three times.
        if row["root"] in roots:
            continue
        roots.add(row["root"])
        chosen.append(row)

    return chosen


def _candidates(cur: db.Cursor, character_id, limit: int, directed: bool, exclude=None):
    """A dead thread is dead for everyone; being talked to only buys extra turns in a live one."""
    if limit <= 0:
        return []
    match = "EXISTS" if directed else "NOT EXISTS"
    # The reply cap is lifted when someone is talking to you, so you can always answer back.
    reply_cap = (
        ""
        if directed
        else """
           AND (
               SELECT count(*) FROM posts mine
                WHERE mine.character_id = %(me)s
                  AND coalesce(mine.root_id, mine.id) = coalesce(p.root_id, p.id)
           ) < %(reply_cap)s
        """
    )
    saturation = reply_cap + """
           AND (
               SELECT count(*) FROM posts sibling
                WHERE sibling.world_id = %(world)s
                  AND coalesce(sibling.root_id, sibling.id) = coalesce(p.root_id, p.id)
           ) < %(size_cap)s
    """
    cur.execute(
        f"""
        SELECT p.id, p.body, p.heat, p.created_at,
               coalesce(p.root_id, p.id) AS root,
               coalesce(c.handle, p.author_human) AS author,
               p.character_id AS author_id,
               coalesce(pc.handle, parent.author_human) AS parent_author,
               parent.body AS parent_body,
               {'true' if directed else 'false'} AS to_you,
               p.heat / (1 + extract(epoch FROM now() - p.created_at) / 3600.0)
                 * CASE WHEN f.follower_id IS NULL THEN %(oon_discount)s ELSE 1 END
                 * CASE WHEN coalesce(ac.n, 0) < %(quiet_posts)s
                        THEN %(quiet_boost)s ELSE 1 END AS rank_score
          FROM posts p
          LEFT JOIN characters c ON c.id = p.character_id
          LEFT JOIN posts parent ON parent.id = coalesce(p.parent_id, p.quote_of_id)
          LEFT JOIN characters pc ON pc.id = parent.character_id
          LEFT JOIN follows f
                 ON f.follower_id = %(me)s AND f.followee_id = p.character_id
          LEFT JOIN (
              SELECT character_id, count(*) AS n FROM posts
               WHERE world_id = %(world)s GROUP BY character_id
          ) ac ON ac.character_id = p.character_id
         WHERE p.world_id = %(world)s
           AND (p.character_id IS DISTINCT FROM %(me)s)
           AND p.created_at > now() - interval '2 days'
           AND NOT (p.id = ANY(%(exclude)s))
           AND NOT EXISTS (
               SELECT 1 FROM impressions i
                WHERE i.post_id = p.id AND i.character_id = %(me)s
           )
           {saturation}
           AND {match} (
               SELECT 1 FROM notifications n
                WHERE n.post_id = p.id AND n.character_id = %(me)s
                  AND n.consumed_at IS NULL
           )
         ORDER BY rank_score DESC
         LIMIT %(limit)s
        """,
        {
            "me": character_id,
            "world": CONFIG.world_id,
            # Selection needs room to reject on author and conversation, so the pool is
            # deliberately wider than the slate.
            "limit": limit * CANDIDATE_POOL,
            "exclude": list(exclude or []),
            "reply_cap": CONFIG.thread_reply_cap,
            "size_cap": CONFIG.thread_size_cap,
            "oon_discount": CONFIG.oon_discount,
            "quiet_boost": CONFIG.quiet_author_boost,
            "quiet_posts": CONFIG.quiet_author_posts,
        },
    )
    return cur.fetchall()


def record_impressions(cur: db.Cursor, character_id, post_ids) -> None:
    """Called once a slate has actually been submitted, never when one is merely built."""
    for post_id in post_ids:
        cur.execute(
            "INSERT INTO impressions (character_id, post_id) VALUES (%s, %s) "
            "ON CONFLICT DO NOTHING",
            (character_id, post_id),
        )


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
    interests = interest_terms(cur, character.persona_card or {},
                               character.engagement_profile or {})
    slate = build_slate(cur, cid, interests=interests)

    # Recency plus importance, both normalised to 0-1 and summed with equal weight, after
    # Park et al. Recency decays exponentially at 0.995 per hour, so yesterday's slight
    # still outranks this morning's small talk but a year-old one eventually lets go.
    cur.execute(
        """
        SELECT note FROM (
            SELECT note,
                   power(%(decay)s, extract(epoch FROM now() - created_at) / 3600.0)
                     + importance / 10.0 AS score,
                   created_at
              FROM memory_notes
             WHERE character_id = %(me)s
             ORDER BY score DESC
             LIMIT %(limit)s
        ) top ORDER BY created_at
        """,
        {
            "me": cid,
            "limit": CONFIG.memory_notes_in_context,
            "decay": CONFIG.memory_recency_decay,
        },
    )
    notes = [r["note"] for r in cur.fetchall()]

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
