"""Tests for the parts that must be right and don't need a database."""
import json
import random
from uuid import uuid4

import pytest

from charsocial.config import CONFIG
from charsocial.llm import OfflineProvider
from charsocial.prompts import WORLD_RULES, system_blocks, turn_prompt
from charsocial.models import (
    ActingCharacter,
    OwnThread,
    RelationView,
    SlateItem,
    TurnContext,
)
from charsocial.schemas import Decision, json_schema
from charsocial.worker import collect, scheduler
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


def _candidate(post_id, author, root, score):
    return {"id": post_id, "author_id": author, "root": root, "rank_score": score}


def test_slate_takes_one_branch_per_conversation():
    """Three replies from one argument is how a character answers the same point three
    times. X's own pipeline dedupes conversations for the same reason."""
    rows = [
        _candidate("a", "kim", "thread1", 9.0),
        _candidate("b", "trump", "thread1", 8.0),
        _candidate("c", "drake", "thread2", 1.0),
    ]
    picked = scheduler._select(rows, 3)
    assert [r["id"] for r in picked] == ["a", "c"]


def test_slate_decays_repeat_authors():
    """The loudest character had 139 posts in two days and could otherwise own the slate."""
    rows = [
        _candidate("a", "kim", "t1", 10.0),
        _candidate("b", "kim", "t2", 9.0),
        _candidate("c", "drake", "t3", 6.0),
    ]
    picked = scheduler._select(rows, 2)
    # 9.0 x 0.625 falls under drake's 6.0, so the second slot changes hands.
    assert [r["author_id"] for r in picked] == ["kim", "drake"]


def test_author_diversity_never_falls_below_the_floor():
    """Bare decay^k banishes a repeat author outright; home-mixer keeps a floor so a good
    enough post from an author already on the slate can still earn a place."""
    assert scheduler._diversity_multiplier(0) == pytest.approx(1.0)
    assert scheduler._diversity_multiplier(1) == pytest.approx(0.625)
    assert scheduler._diversity_multiplier(50) > CONFIG.author_floor - 1e-9


def test_generic_constructions_are_banned_by_name():
    """Naming the exact failing string beats describing it — the technique xAI's own @grok
    prompt uses. These three shapes appeared across 5-6 different characters, which is what
    made the whole feed sound like one writer."""
    assert "is not the same as" in WORLD_RULES
    assert "that's the whole point" in WORLD_RULES
    assert "<policy>" in WORLD_RULES and "</policy>" in WORLD_RULES


def test_tics_are_rationed_rather_than_listed():
    """Told to reach for the exact phrasing on the card, characters fired a catchphrase in
    up to 94% of posts. The card lists them; only the world rules can set the rate."""
    assert "checklist" in WORLD_RULES
    assert "once in twenty" in WORLD_RULES


def test_own_posts_are_labelled_as_spent_material():
    """Unlabelled, the model reads its own last five posts as the pattern to continue."""
    prompt = turn_prompt(
        TurnContext(
            character_id=uuid4(),
            name="Walter White",
            handle="walterwhite_ai",
            persona_card={},
            engagement_profile={},
            own_posts=["I am the one who posts"],
        )
    )
    assert "do not say any of it again" in prompt


def test_own_threads_are_offered_as_reply_targets():
    """build_slate excludes your own posts, so without an id here a character that has more
    to say about a subject it already covered can only open a second post about it."""
    prompt = turn_prompt(
        TurnContext(
            character_id=uuid4(),
            name="Donald Trump",
            handle="donaldtrump",
            persona_card={},
            engagement_profile={},
            own_threads=[OwnThread(id="m1", body="Had the Steak tonight", replies=2)],
        )
    )
    assert "id=m1" in prompt
    assert "reply to it by its id" in prompt


def test_world_rules_forbid_reusing_a_shape_not_just_a_line():
    """@netflix repeated its own docuseries skeleton with the earlier post visible under
    'do not say any of it again' — forbidding restated lines never covered reused form."""
    assert "same setup, same rhythm" in WORLD_RULES
    assert "not lines to deliver" in WORLD_RULES


def test_rotate_samples_trims_each_group_without_touching_the_card():
    """@killtony posted a card sample back almost verbatim. The card is rendered whole on
    every turn, so a vivid sample is a permanent rail unless the set moves."""
    card = {
        "bio": "comic",
        "samples": {
            "posts": [f"post {i}" for i in range(10)],
            "replies": ["only one"],
        },
    }
    rotated = scheduler.rotate_samples(card, "killtony", rotation=7)

    assert len(rotated["samples"]["posts"]) == CONFIG.samples_per_group
    assert rotated["samples"]["replies"] == ["only one"]  # too few to trim
    assert rotated["bio"] == "comic"
    # The caller's card is the row loaded for this character and is read again downstream.
    assert len(card["samples"]["posts"]) == 10

    same = scheduler.rotate_samples(card, "killtony", rotation=7)
    assert rotated["samples"]["posts"] == same["samples"]["posts"], "a replayed tick must rebuild the same prompt"

    # Across ticks, not between one pair: two seeds picking the same 3 of 10 is rare but
    # not impossible, and a test that fails once a year is worse than no test.
    seen = {
        tuple(scheduler.rotate_samples(card, "killtony", rotation=t)["samples"]["posts"])
        for t in range(10)
    }
    assert len(seen) > 1, "the rail must move between ticks"


class _StubCursor:
    """Enough cursor for the scroll path, which touches no rows."""

    def __init__(self):
        self.args = []

    def execute(self, sql, args=None):
        self.args.append(args)

    def fetchone(self):
        return None


def test_apply_coerces_character_id_before_any_self_check():
    """The batch payload is JSON, so character_id comes back a string while every id read
    out of the database is a UUID, and `"37b4…" == UUID("37b4…")` is False. That made each
    is-this-me guard fail open the moment a character could target its own thread: the
    self-relation trips a check constraint and the savepoint throws the whole turn away."""
    cur = _StubCursor()
    actor = uuid4()

    collect._apply(cur, {"character_id": str(actor)}, {"action": "scroll"}, None)

    passed = [value for args in cur.args if args for value in args]
    assert actor in passed, "downstream must receive a UUID"
    assert str(actor) not in passed, "a string here silently defeats every self-guard"


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


def test_spend_guard_rejects_unset_secrets():
    """An Actions secret that was never created arrives as "", not as the default. Checking
    only against the default let a scheduled tick spend against a blank password."""
    import charsocial.config as cfg

    blank = cfg.CONFIG.model_copy(
        update={"llm_provider": "anthropic", "admin_token": "real-token", "site_password": ""}
    )
    with pytest.raises(RuntimeError, match="SITE_PASSWORD"):
        blank.assert_safe_to_spend()

    ok = cfg.CONFIG.model_copy(
        update={
            "llm_provider": "anthropic",
            "admin_token": "real-token",
            "site_password": "a-real-password",
        }
    )
    ok.assert_safe_to_spend()


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


def test_every_shared_query_is_compiled_for_the_typescript_side():
    """db/queries/*.sql feeds both runtimes. Adding one and forgetting to regenerate
    web/lib/queries.gen.ts is a deploy-time 500, not a local failure — so fail here."""
    from pathlib import Path

    from charsocial.queries import SQL

    generated = (Path(__file__).resolve().parent.parent / "web/lib/queries.gen.ts").read_text()
    missing = [name for name in SQL if f'\n  {name}: {{ text: ' not in generated]
    assert not missing, f"stale queries.gen.ts, run scripts/gen_queries.mjs: {missing}"


def test_placeholders_survive_the_rewrite_without_eating_casts():
    from charsocial.queries import SQL

    assert "::float" in SQL["profile"]
    assert "%(world)s" in SQL["feed"] and ":world" not in SQL["feed"]
