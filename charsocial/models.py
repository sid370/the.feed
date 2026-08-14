"""Domain and API models.

`schemas.py` holds what the MODEL must return (structured-output contracts). This holds
what the system passes around internally and hands to the frontend. Keeping both typed
means a shape change breaks at the boundary instead of turning into a `KeyError` inside a
tick, or a field the frontend silently reads as `undefined`.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Mood = Literal["hostile", "neutral", "warm"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ------------------------------------------------------------------ provider transport


class Submission(Strict):
    batch_id: str
    # Offline decisions are computed at submit time and stored in the DB, so a later
    # process (every `make tick` is a fresh one) can still collect them.
    inline_results: dict[str, dict] | None = None


class Usage(Strict):
    input: int = 0
    output: int = 0
    cache_read: int = 0
    cache_write: int = 0


class Collected(Strict):
    decisions: dict[str, dict] = Field(default_factory=dict)
    usage: Usage = Field(default_factory=Usage)


# ------------------------------------------------------------------------ turn context


class SlateItem(Strict):
    """One post the character's feed algorithm surfaced."""

    id: str
    author: str
    author_id: UUID | None = None
    body: str
    to_you: bool = False
    # A reply without its parent reads as a non-sequitur.
    parent_author: str | None = None
    parent_body: str | None = None


class RelationView(Strict):
    name: str
    heat: float
    sentiment: float
    note: str | None = None
    on_slate: bool = False

    @property
    def mood(self) -> Mood:
        if self.sentiment < -1:
            return "hostile"
        return "warm" if self.sentiment > 1 else "neutral"


class TurnContext(Strict):
    """Everything a character knows when it takes one turn."""

    character_id: UUID
    name: str
    handle: str
    persona_card: dict[str, Any]
    engagement_profile: dict[str, Any]
    memory_notes: list[str] = Field(default_factory=list)
    own_posts: list[str] = Field(default_factory=list)
    relations: list[RelationView] = Field(default_factory=list)
    notifications: list[str] = Field(default_factory=list)
    assignment: str | None = None
    intent: str | None = None
    slate: list[SlateItem] = Field(default_factory=list)


class Assignment(Strict):
    """A headline the showrunner cast to a specific character."""

    handle: str
    headline_id: UUID
    text: str


class ActingCharacter(Strict):
    """A character selected for a turn this tick."""

    model_config = ConfigDict(extra="ignore")

    id: UUID
    name: str
    handle: str
    model: str | None = None
    persona_card: dict[str, Any] = Field(default_factory=dict)
    engagement_profile: dict[str, Any] = Field(default_factory=dict)
    intent: str | None = None


class TickStats(Strict):
    model_config = ConfigDict(extra="ignore")

    tick_id: int | None = None
    skipped: bool = False
    reason: str | None = None
    posts_written: int = 0
    headlines_ingested: int = 0
    headlines_classified: int = 0
    news_share: float = 0.0
    assignments: int = 0
    batch_id: str | None = None
    turns_sent: int = 0
    likes: int = 0
    follows: int = 0
    vanity: int = 0
    error: str | None = None


# --------------------------------------------------------------------------- API: out


class Author(Strict):
    handle: str
    name: str
    avatarSeed: str
    # NULL for the whole cast until someone drops in an image; the frontend falls back to
    # initials on a colour derived from avatarSeed.
    avatarUrl: str | None = None
    # False for human pokes, which have no profile to open.
    isCharacter: bool = True
    # Drives the parody badge. PLAN §12 calls the watermark the control that makes a
    # leaked screenshot a non-event.
    isRealPerson: bool = False


class Headline(Strict):
    title: str
    url: str


class PostOut(Strict):
    id: str
    body: str
    createdAt: datetime
    likeCount: int
    replyCount: int
    parentId: str | None = None
    # Handle of whoever is being answered. A reply listed away from its thread — the
    # replies tab — reads as a non-sequitur without it.
    replyingTo: str | None = None
    author: Author
    headline: Headline | None = None


class FeedOut(Strict):
    posts: list[PostOut]


class Profile(Strict):
    handle: str
    name: str
    avatarSeed: str
    avatarUrl: str | None = None
    isRealPerson: bool = False
    status: str
    # The persona's own one-liner, rendered as their status under the name.
    bio: str | None = None
    opensPerDay: float | None = None
    joinedAt: datetime | None = None
    postCount: int
    replyCount: int
    likesReceived: int
    followerCount: int
    followingCount: int


class ProfileOut(Strict):
    profile: Profile
    posts: list[PostOut]
    replies: list[PostOut]


class Liker(Strict):
    handle: str
    name: str
    avatarSeed: str
    avatarUrl: str | None = None
    likedAt: datetime


class LikesOut(Strict):
    likers: list[Liker]


class Person(Strict):
    handle: str
    name: str
    avatarSeed: str
    avatarUrl: str | None = None
    bio: str | None = None


class PeopleOut(Strict):
    people: list[Person]


class HeatPair(Strict):
    a: str
    b: str
    heat: float
    share: float
    mood: Mood
    # Root of the thread this feud actually happened in. None when they have only
    # brushed past each other and there is nothing worth opening.
    threadId: str | None = None


class HeatOut(Strict):
    pairs: list[HeatPair]


class WorldOut(Strict):
    tick: int
    lastTickAt: datetime | None
    intervalMinutes: int
    posts: int
    characters: int


class CharacterOut(Strict):
    handle: str
    name: str
    avatar_seed: str
    avatar_url: str | None = None
    status: str
    bio: str | None = None
    opens_per_day: float | None = None
    post_count: int
    follower_count: int


class CharactersOut(Strict):
    characters: list[CharacterOut]


class AdminCharacter(Strict):
    id: UUID
    handle: str
    name: str
    status: str
    persona_card: dict[str, Any]
    engagement_profile: dict[str, Any]


class AdminCharactersOut(Strict):
    characters: list[AdminCharacter]


class UsageOut(Strict):
    input_tokens: int
    output_tokens: int
    # Zero here is the ONLY signal that prompt caching silently broke.
    cache_read_tokens: int
    cache_write_tokens: int
    failed_batches: int


class TickRow(Strict):
    id: int
    turns_sent: int
    posts_written: int
    news_share: float
    started_at: datetime
    error: str | None = None


class BudgetOut(Strict):
    tick_budget: int
    interval_minutes: int
    turns_per_day: int


class StatsOut(Strict):
    posts: int
    likes: int
    active: int
    open_batches: int
    blocked_headlines: int
    usage: UsageOut
    recent_ticks: list[TickRow]
    budget: BudgetOut


class DraftOut(Strict):
    id: UUID
    handle: str
    name: str
    status: str


class Ok(Strict):
    ok: bool = True


class Health(Strict):
    ok: bool
    provider: str
    world: str


class PokeOut(Strict):
    ok: bool
    id: str


# ---------------------------------------------------------------------------- API: in


class LoginIn(Strict):
    password: str = Field(min_length=1, max_length=200)


class PokeIn(Strict):
    post_id: UUID
    body: str = Field(min_length=1, max_length=280)
    display_name: str = Field("guest", max_length=24)


class DraftIn(Strict):
    name: str = Field(min_length=1, max_length=120)
    context: str = Field("", max_length=400)
    notes: str = Field("", max_length=1000)
    source_material: str = Field("", max_length=20000)


class PatchIn(Strict):
    status: Literal["draft", "active", "paused", "retired"] | None = None
    persona_card: dict[str, Any] | None = None
    engagement_profile: dict[str, Any] | None = None
