"""Structured-output schemas. The model physically cannot return malformed JSON,
which deletes the whole parse-and-retry path we would otherwise own."""
from typing import Literal

from pydantic import BaseModel, Field

ACTIONS = ["reply", "quote", "like", "follow", "post", "scroll"]


class Decision(BaseModel):
    """One agent turn. `scroll` is the most important option in the set — most turns
    should end in nothing, which is what makes the feed read as real and keeps the
    turn from always costing a generation."""

    action: Literal["reply", "quote", "like", "follow", "post", "scroll"]
    target_post_id: str | None = None
    body: str | None = None
    memory_note: str | None = None  # rides along free; no second call for memory
    # The character's own read on the other person — their belief, allowed to be wrong.
    # A written-down wrong belief is what lets a misunderstanding survive across ticks.
    relation_note: str | None = None
    feeling_delta: int = 0  # -2..2 toward the target's author


class CastPick(BaseModel):
    headline_index: int
    character_handle: str
    angle: str


class CastingPlan(BaseModel):
    traction: list[int]  # 1-10 per headline, index-aligned with the input
    picks: list[CastPick]


class HeadlineVerdict(BaseModel):
    index: int
    safe: bool
    reason: str


class SafetyReport(BaseModel):
    verdicts: list[HeadlineVerdict]


class Samples(BaseModel):
    """Grouped by action, because a character writes a reply differently from a post and
    the turn prompt asks for one specific action."""

    posts: list[str] = Field(default_factory=list)
    replies: list[str] = Field(default_factory=list)
    quotes: list[str] = Field(default_factory=list)
    subtweets: list[str] = Field(default_factory=list)


class PersonaCard(BaseModel):
    bio: str
    voice: str
    tics: list[str] = Field(default_factory=list)
    obsessions: list[str] = Field(default_factory=list)
    beefs: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)
    samples: Samples = Field(default_factory=Samples)


class EngagementProfile(BaseModel):
    opens_per_day: float = 1.0  # this is the entire tiering system
    reply_rate: float = 0.5
    aggression: float = 0.5
    notification_sensitivity: float = 0.5
    triggers: list[str] = Field(default_factory=list)


class CharacterDraft(BaseModel):
    handle: str
    persona_card: PersonaCard
    engagement_profile: EngagementProfile


def json_schema(model: type[BaseModel]) -> dict:
    """Pydantic -> a schema the API accepts: every field required, no extra properties."""
    schema = model.model_json_schema()
    _tighten(schema)
    for definition in schema.get("$defs", {}).values():
        _tighten(definition)
    return schema


def _tighten(node: dict) -> None:
    if node.get("type") == "object" and "properties" in node:
        node["additionalProperties"] = False
        node["required"] = list(node["properties"].keys())
    node.pop("default", None)
