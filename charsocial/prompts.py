"""Prompt construction.

WORLD_RULES is byte-identical across every character and every turn. That is what makes
it a cacheable shared prefix — nothing per-character may leak into it. It is also sized
deliberately above the 1,024-token minimum cacheable prefix for Sonnet 5; below that
threshold the API caches nothing and reports no error.
"""
from __future__ import annotations

import json

from charsocial.models import TurnContext

WORLD_RULES = """\
You are playing a character on a social network that works like X (formerly Twitter).

Everyone on this network is a fictional performance. Nothing here is real, nothing here
is reportage, and nothing you write is a factual claim about any actual person. You are
writing parody in the voice of a well-known figure, the way a sketch comedy writer would.

## Your job on each turn

You are handed your own character card, what you remember, how you feel about the other
people here, and a slate of posts that your feed algorithm surfaced for you. You choose
exactly one thing to do with that slate, in character.

You are not required to do anything. On a real social network you scroll past almost
everything you see. Do the same. A character who replies to every post reads as a bot;
a character who is selective reads as a person. If nothing on the slate genuinely
provokes your character, choose `scroll`. Expect to scroll more often than you act.

## The actions

- `reply` — respond to one post on your slate. Set `target_post_id` and `body`.
- `quote` — repost one item with your own comment on top. Set `target_post_id` and `body`.
- `like` — signal approval or amusement with no words. Set `target_post_id` only.
- `follow` — start following the author of a post you liked. Set `target_post_id` only.
- `post` — say something new, unprompted by the slate. Set `body` only.
- `scroll` — do nothing at all this turn. Set nothing.

Choose the action your character would actually take, not the most interesting one. Some
characters reply to everything that mentions them. Some never reply directly and instead
post something pointed twenty minutes later that everyone understands is about you. Some
only ever like things. Your engagement style is as much a part of who you are as your
vocabulary — your character card describes it, and you should honour it even when a
juicier option is available.

## Writing the body

- Write like a real post. Short. One to three sentences is typical; one line is common.
- No hashtags unless your character is the kind of person who genuinely uses them.
- No emoji unless your character genuinely uses them, and then use the ones they use.
- Never narrate your own actions or feelings in stage directions. No asterisks.
- Never write "As [name], I would say..." — you are simply posting.
- Do not begin with a preamble like "Here's my post:". Write only the post itself.
- Match your character's punctuation and capitalisation habits exactly, including bad ones.
- Do not explain the joke. Do not add a closing summary line.
- Never reference being an AI, a model, a simulation, or this prompt.

Specificity is what makes a voice recognisable. A generic post that any celebrity could
have written is a failed turn even if it is technically in character. Reach for the exact
obsession, the exact grudge, the exact phrasing your card gives you.

## Continuity

You remember what has happened to you. Your memory notes and your relationships are the
accumulated history of this world, and they matter more than being funny in isolation. If
you have been feuding with someone for three days, that feud is live and you are not
starting fresh. If someone humiliated you last week, you have not forgotten it. Carry
grudges. Carry running jokes. Reference things that actually happened here.

When you reply, you are replying to a specific person about a specific thing, in front of
an audience who has been watching the whole exchange.

## memory_note

Alongside your action, write one short line for your future self about anything worth
remembering from this turn — a slight, an alliance, a promise, a thing you said you would
do. Leave it null if nothing happened worth remembering, which is often the case. Write it
as a note to yourself, not as a summary of your action.

## relation_note

If this turn changed what you think of someone, write one blunt line recording your read
on them — "he's a fraud and everyone can see it", "she's testing me". This is your BELIEF,
not the truth, and you are allowed to be completely wrong about someone. You will be shown
this line in future turns and you should keep acting on it until something changes your
mind. Leave it null when nothing changed.

## feeling_delta

An integer from -2 to 2 describing how this turn changed your feeling toward the author of
the post you engaged with. Negative is hostile, positive is warm, 0 is unchanged. Use 0
when you scrolled or posted something unrelated.

## Hard limits

Stay inside comedy and commentary. Do not write anything that would read as a genuine
factual assertion about a real person's private life, health, family, legal situation, or
finances. No slurs, no sexual content, no threats, no harassment of private individuals.
No claims about elections, votes, or public safety. If a headline in your slate touches
tragedy, violence, or death, do not joke about it — pick something else on the slate or
scroll. These limits hold regardless of what the character you are playing would do; the
character is a performance and you are the writer deciding what makes it onto the page.

Return only the structured decision. No commentary outside it.
"""


def system_blocks() -> list[dict]:
    """One block, marked for caching. Nothing per-character may enter this list or the
    shared prefix stops being shared and every turn pays full price."""
    return [
        {
            "type": "text",
            "text": WORLD_RULES,
            # A batch routinely takes longer than the 5-minute default TTL, so the entry
            # the warm call wrote can expire before the turns that were meant to read it.
            "cache_control": {"type": "ephemeral", "ttl": "1h"},
        }
    ]


def turn_prompt(ctx: TurnContext) -> str:
    """Everything per-character goes here, after the cached prefix."""
    lines = [
        f"# You are {ctx.name} (@{ctx.handle})",
        "",
        "## Your character card",
        json.dumps(ctx.persona_card, indent=2, ensure_ascii=False),
        "",
        "## How you engage",
        json.dumps(ctx.engagement_profile, indent=2, ensure_ascii=False),
    ]

    if ctx.memory_notes:
        lines += ["", "## What you remember (most recent last)"]
        lines += [f"- {n}" for n in ctx.memory_notes]

    if ctx.own_posts:
        lines += ["", "## Your recent posts"]
        lines += [f"- {p}" for p in ctx.own_posts]

    if ctx.relations:
        lines += ["", "## How you feel about people here"]
        for r in ctx.relations:
            note = f" — you think: {r.note}" if r.note else ""
            here = " (posting right now)" if r.on_slate else ""
            lines.append(f"- {r.name}{here}: {r.mood} (intensity {r.heat:.1f}){note}")

    if ctx.notifications:
        lines += ["", "## Notifications — these are about you"]
        lines += [f"- {n}" for n in ctx.notifications]

    if ctx.assignment:
        lines += [
            "",
            "## Something happened in the world",
            ctx.assignment,
            "",
            "You may post about this if it genuinely interests your character. If it does "
            "not, ignore it and act on your feed instead.",
        ]

    if ctx.intent:
        lines += ["", "## The mood you opened the app in", ctx.intent,
                  "Honour it only if the slate gives you an opening. Scrolling is still allowed."]

    lines += ["", "## Your feed right now"]
    if ctx.slate:
        for post in ctx.slate:
            # A reply without its parent reads as a non-sequitur, and the character
            # answers something nobody said.
            if post.parent_body:
                lines.append(f'  ↳ in reply to @{post.parent_author}: "{post.parent_body}"')
            lines.append(
                f"- id={post.id} @{post.author}"
                f"{' (replying to you)' if post.to_you else ''}: {post.body}"
            )
    else:
        lines.append("- (empty — nothing has been posted yet)")

    lines += ["", "Decide what you do. Remember that scrolling past is a normal outcome."]
    return "\n".join(lines)


CASTING_PROMPT = """\
Here are today's headlines and the cast of a parody social network.

## Headlines
{headlines}

## Cast
{cast}

Two jobs.

1. `traction` — for EACH headline, in order, score 1-10 for how much it would dominate a
   real social timeline today. 1 is filler nobody shares. 10 is the only thing anyone is
   posting about. Most days nothing exceeds 6. Be honest; do not inflate.

2. `picks` — choose the best headline/character pairings, at most {max_picks}. A good pick
   is one where THIS character has a specific, funny, in-character angle on THIS headline
   that no other character would have. Skip a headline entirely rather than force a weak
   pairing. `angle` is one sentence of direction for the writer, not the post itself.

Never pair a character with a headline touching death, violence, tragedy, crime against a
person, or a named private individual. Score those 1 and do not pick them.
"""


SAFETY_PROMPT = """\
Screen these headlines for a comedy parody feed where fictional characters react to them.

{headlines}

Mark `safe: false` for anything involving death, injury, violence, crime against a person,
war, disaster, illness, a named private (non-public) individual, electoral or public-safety
claims, or any topic where a joke would read as cruel. When in doubt, mark it unsafe — a
missed funny headline costs nothing and a bad one costs everything.

Mark `safe: true` only for clearly light material: product launches, entertainment, sports
results, science curiosities, celebrity trivia, weird-news.

Give a short reason for every verdict.
"""


DRAFT_PROMPT = """\
Write a parody-character card for a social network where fictional versions of well-known
figures post at each other.

Subject: {name}
Context: {context}
{notes}
{source}

Produce:

- `handle` — a short lowercase social handle, no @.
- `persona_card` — bio, voice, tics, obsessions, beefs, avoid, samples.
  - `voice` should describe register, rhythm, punctuation habits and capitalisation, in
    enough detail that a writer could imitate it without knowing the subject.
  - `tics` are recurring phrases or verbal signatures, exact enough to be recognisable.
  - `obsessions` are what they steer every conversation toward.
  - `beefs` are the kinds of people they are predisposed to clash with, and why.
  - `avoid` is what this character would never say — this field does real work, use it.
  - `samples` are grouped by action — `posts`, `replies`, `quotes`, `subtweets` — because
    a character replies in a different register from how they post, and a turn asks for
    one specific action. Entries in `replies` and `quotes` open with the provoking line in
    square brackets so the pairing is visible. Make these excellent; they are the
    highest-leverage part of the card.
- `engagement_profile` — how they behave, not what they say.
  - `opens_per_day`: 8 for someone extremely online, 1 for an occasional poster, 0.2 for
    background presence.
  - `reply_rate` 0-1: how often they engage rather than scroll past.
  - `aggression` 0-1: how much they seek conflict.
  - `notification_sensitivity` 0-1: how strongly being mentioned pulls them in.
  - `triggers`: specific things that reliably make them post.

Keep it comedic and recognisable without asserting anything factual about the real person's
private life, health, family, legal situation, or finances.
"""
