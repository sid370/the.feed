"""Tests for the parts that must be right and don't need a database."""
import json
import random
from uuid import uuid4

import pytest

from charsocial.config import CONFIG
from charsocial.llm import OfflineProvider
from charsocial.prompts import WORLD_RULES, system_blocks, turn_prompt
from charsocial.models import ActingCharacter, RelationView, SlateItem, TurnContext
from charsocial.schemas import Decision, json_schema
from charsocial.worker.news import _share


def test_shared_prefix_is_cacheable():
    """Below the minimum cacheable prefix the API caches nothing and reports no error,
    so this is the kind of regression that shows up only on the bill."""
    approx_tokens = len(WORLD_RULES) / 4
    assert approx_tokens > 1024, f"world rules too short to cache: ~{approx_tokens:.0f} tokens"


def test_system_prefix_is_byte_identical_across_calls():
    """The prefix is shared across every turn in the batch. Any per-character leak makes
    it unshared and every turn pays full price — silently, with no error."""
    a, b = system_blocks(), system_blocks()
    assert a == b
    assert len(a) == 1
    # A batch routinely outlives the 5-minute default TTL.
    assert a[0]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}


def test_decision_schema_is_strict():
    schema = json_schema(Decision)
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    assert "scroll" in schema["properties"]["action"]["enum"]


def test_scroll_is_available_as_an_action():
    """Most turns ending in nothing is what makes the feed read as real."""
    assert Decision(action="scroll").action == "scroll"


def test_news_share_scales_with_traction():
    assert _share(0) == 0.0
    quiet, big = _share(3), _share(10)
    assert CONFIG.news_share_floor <= quiet < big <= CONFIG.news_share_ceiling


def test_turn_prompt_includes_memory_and_slate():
    prompt = turn_prompt(
        TurnContext(
            character_id=uuid4(),
            name="Walter White",
            handle="walterwhite_ai",
            persona_card={"bio": "chemistry"},
            engagement_profile={"opens_per_day": 6},
            memory_notes=["saul mocked me"],
            own_posts=["I am the one who posts"],
            relations=[RelationView(name="Saul", heat=4.2, sentiment=-3)],
            notifications=["@saul replied: nice apron"],
            slate=[SlateItem(id="p1", author="saul", body="nice apron", to_you=True)],
        )
    )
    assert "saul mocked me" in prompt
    assert "hostile" in prompt
    assert "id=p1" in prompt
    assert "scrolling past is a normal outcome" in prompt


def test_offline_provider_round_trips_a_batch():
    provider = OfflineProvider(seed=3)
    turns = [
        {
            "custom_id": f"turn-{i}",
            "name": "Tester",
            "slate": [{"id": "p1", "author": "someone", "body": "hi"}],
        }
        for i in range(20)
    ]
    results = provider.submit_turns(turns, []).inline_results

    assert results is not None, "offline results must travel inline in the batch"
    assert len(results) == 20
    for decision in results.values():
        Decision.model_validate(decision)  # every canned decision must be schema-valid

    actions = [d["action"] for d in results.values()]
    assert "scroll" in actions, "offline provider should sometimes do nothing"


def test_budget_is_the_only_spend_dial():
    """Turns per day is a pure function of the two config dials — if this drifts, the
    cost model in PLAN.md is wrong."""
    per_day = 1440 / CONFIG.tick_interval_minutes * CONFIG.tick_budget
    assert per_day == pytest.approx(384, rel=0.01)


# --------------------------------------------------------------- resilience additions


def test_decision_carries_memory_and_relation_notes_free():
    """Both ride along on the decision the agent already makes — no second call."""
    d = Decision(action="reply", target_post_id="x", body="hi",
                 memory_note="he started it", relation_note="he's a fraud")
    assert d.relation_note == "he's a fraud"
    assert "relation_note" in json_schema(Decision)["properties"]


def test_offline_provider_cannot_silently_swallow_a_foreign_batch():
    """Returning {} here marked batches 'collected' having written nothing — the
    documented no-key path silently produced an empty world."""
    from charsocial.llm import LLMFatalError

    with pytest.raises(LLMFatalError):
        OfflineProvider().collect_turns("local:not-from-this-process")


def test_offline_results_survive_a_process_restart():
    """Decisions are computed at submit time and stored, because every `make tick` is a
    fresh process and in-memory state would not survive."""
    submission = OfflineProvider(seed=3).submit_turns(
        [{"custom_id": "t1", "name": "Tester", "slate": []}], []
    )
    assert submission.inline_results is not None
    Decision.model_validate(submission.inline_results["t1"])


def test_spend_guard_rejects_published_secrets():
    """A published admin token is an unbounded spend path outside the tick."""
    import charsocial.config as cfg

    live = cfg.CONFIG.model_copy(update={"llm_provider": "anthropic"})
    with pytest.raises(RuntimeError, match="ADMIN_TOKEN"):
        live.assert_safe_to_spend()


def test_turn_prompt_shows_what_a_reply_is_answering():
    """Without the parent snippet a character answers something nobody said."""
    prompt = turn_prompt(
        TurnContext(
            character_id=uuid4(),
            name="Saul",
            handle="saul",
            persona_card={},
            engagement_profile={},
            intent="You opened the app looking for a fight.",
            slate=[
                SlateItem(
                    id="p1", author="walter", body="no, YOU are the problem",
                    parent_author="don", parent_body="someone here is a fraud",
                )
            ],
        )
    )
    assert "in reply to @don" in prompt
    assert "someone here is a fraud" in prompt
    assert "looking for a fight" in prompt


def test_intent_only_fires_at_the_configured_rate():
    from charsocial.worker.scheduler import _sample_intent

    rng = random.Random(1)
    character = ActingCharacter(
        id=uuid4(), name="T", handle="t", engagement_profile={"aggression": 0.5}
    )
    hits = sum(_sample_intent(character, rng) is not None for _ in range(400))
    assert 0.25 < hits / 400 < 0.55  # configured 0.4
