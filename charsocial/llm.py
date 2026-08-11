"""Model access. Two shapes only: batched turns, and small synchronous utility calls.

No agent framework. A turn is one call returning one structured decision — there is no
tool loop for a graph runtime to orchestrate, and the world state a framework would want
to own already lives in Postgres.

Every failure here must surface as LLMError so the tick can degrade instead of dying. An
unhandled exception in this module wedges the world.
"""
from __future__ import annotations

import json
import random
import re
import uuid
from typing import Any

from charsocial.config import CONFIG
from charsocial.models import Collected, Submission, Usage
from charsocial.schemas import json_schema

MAX_TURN_TOKENS = 400
MAX_UTILITY_TOKENS = 4000


class LLMError(RuntimeError):
    """Recoverable. The caller degrades; the tick continues."""


class LLMFatalError(LLMError):
    """This batch can never resolve — mark it failed rather than retrying forever."""


# --------------------------------------------------------------------------- offline


class OfflineProvider:
    """Runs the entire tick with no API key and no spend, so the scheduler, heat model
    and collect path stay testable on their own."""

    name = "offline"

    def __init__(self, seed: int = 7):
        self.rng = random.Random(seed)

    def submit_turns(self, turns: list[dict], _system: list[dict]) -> Submission:
        results = {t["custom_id"]: self._fake_decision(t) for t in turns}
        return Submission(batch_id=f"local:{uuid.uuid4()}", inline_results=results)

    def collect_turns(self, batch_id: str) -> Collected | None:
        # Offline results always travel in the batch payload; reaching here means the row
        # predates that mechanism or came from another provider.
        raise LLMFatalError(f"offline provider cannot resolve batch {batch_id}")

    # Reply and quote samples are stored as `[someone: "..."] the reply`; only the reply
    # half is a post body.
    PROVOCATION = re.compile(r"^\[[^\]]*\]\s*")

    def _pick(self, samples: dict, group: str) -> str | None:
        lines = samples.get(group) or []
        if not lines:
            return None
        return self.PROVOCATION.sub("", self.rng.choice(lines)).strip() or None

    def _decide(self, action: str, target=None, body=None, feeling=0) -> dict:
        return {
            "action": action,
            "target_post_id": target,
            "body": body,
            "memory_note": None,
            "relation_note": None,
            "feeling_delta": feeling,
        }

    def _fake_decision(self, turn: dict) -> dict:
        """Bodies come from the character's own `samples`. A character with no samples
        never writes — better an empty feed than filler that reads like real output."""
        slate = turn.get("slate", [])
        samples = turn.get("samples") or {}
        roll = self.rng.random()

        if not slate or roll < 0.30:
            body = self._pick(samples, "posts")
            return self._decide("post", body=body) if body else self._decide("scroll")

        target = self.rng.choice(slate)
        if roll < 0.55:
            return self._decide("scroll")
        if roll < 0.70:
            return self._decide("like", target=target["id"], feeling=1)

        body = self._pick(samples, "replies")
        if not body:
            return self._decide("like", target=target["id"], feeling=1)
        return self._decide(
            "reply", target=target["id"], body=body, feeling=self.rng.choice([-2, -1, 1])
        )

    def utility(self, _prompt: str, _schema: dict, _system: str = "") -> dict:
        raise LLMError("offline provider has no utility calls; callers must fall back")


# --------------------------------------------------------------------------- anthropic


class AnthropicProvider:
    name = "anthropic"

    def __init__(self):
        import anthropic  # imported lazily so offline mode needs no dependency

        if not CONFIG.anthropic_api_key:
            raise LLMError("ANTHROPIC_API_KEY is not set")
        self.client = anthropic.Anthropic(api_key=CONFIG.anthropic_api_key)
        self._anthropic = anthropic

    def submit_turns(self, turns: list[dict], system: list[dict]) -> Submission:
        from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
        from anthropic.types.messages.batch_create_params import Request

        # Caches are model-scoped, so warm every distinct model this batch will use.
        for model in {t.get("model") or CONFIG.turn_model for t in turns}:
            self._warm_cache(system, model)

        requests = [
            Request(
                custom_id=turn["custom_id"],
                params=MessageCreateParamsNonStreaming(
                    model=turn.get("model") or CONFIG.turn_model,
                    max_tokens=MAX_TURN_TOKENS,
                    system=system,
                    # Sonnet 5 runs adaptive thinking by DEFAULT. A short in-character
                    # decision does not benefit from it, and leaving it on multiplies
                    # output tokens several-fold — the whole budget assumes it is off.
                    thinking={"type": "disabled"},
                    output_config={
                        "effort": "low",
                        "format": {"type": "json_schema", "schema": turn["schema"]},
                    },
                    messages=[{"role": "user", "content": turn["prompt"]}],
                ),
            )
            for turn in turns
        ]
        try:
            batch = self.client.messages.batches.create(requests=requests)
        except Exception as exc:
            raise LLMError(f"batch submit failed: {exc}") from exc
        return Submission(batch_id=batch.id)

    def _warm_cache(self, system: list[dict], model: str) -> None:
        """Batch turns run concurrently server-side, and a concurrent request cannot read
        a cache entry that is still being written. Writing it once up front means all N
        turns read instead of all N paying full price.

        max_tokens=0 is rejected alongside output_config.format, so the warm call omits
        it — the cached prefix is tools+system, which is identical either way.
        """
        try:
            self.client.messages.create(
                model=model,
                max_tokens=0,
                system=system,
                thinking={"type": "disabled"},
                messages=[{"role": "user", "content": "warm"}],
            )
        except Exception:  # a cold cache costs money, not correctness
            pass

    def collect_turns(self, batch_id: str) -> Collected | None:
        if batch_id.startswith("local:"):
            # Left over from an offline run on this database. Retrying can never work.
            raise LLMFatalError(f"offline batch {batch_id} cannot be collected from the API")

        try:
            batch = self.client.messages.batches.retrieve(batch_id)
        except Exception as exc:
            if getattr(exc, "status_code", None) == 404:
                raise LLMFatalError(f"batch {batch_id} not found") from exc
            raise LLMError(f"batch retrieve failed: {exc}") from exc

        if batch.processing_status != "ended":
            return None  # not ready; the next tick will try again

        out: dict[str, dict] = {}
        usage = Usage()
        try:
            results = list(self.client.messages.batches.results(batch_id))
        except Exception as exc:
            raise LLMError(f"batch results failed: {exc}") from exc

        for result in results:
            if result.result.type != "succeeded":
                continue
            message = result.result.message
            u = getattr(message, "usage", None)
            if u is not None:
                usage.input += getattr(u, "input_tokens", 0) or 0
                usage.output += getattr(u, "output_tokens", 0) or 0
                usage.cache_read += getattr(u, "cache_read_input_tokens", 0) or 0
                usage.cache_write += getattr(u, "cache_creation_input_tokens", 0) or 0
            if getattr(message, "stop_reason", None) == "refusal":
                continue
            text = next((b.text for b in message.content if b.type == "text"), None)
            if not text:
                continue
            try:
                out[result.custom_id] = json.loads(text)
            except json.JSONDecodeError:
                continue
        return Collected(decisions=out, usage=usage)

    def utility(self, prompt: str, schema: dict, system: str = "") -> dict:
        """Casting, safety classification and character drafting. One call per tick each,
        and the one place judgment is worth paying for — so adaptive thinking stays on."""
        try:
            response = self.client.messages.create(
                model=CONFIG.utility_model,
                max_tokens=MAX_UTILITY_TOKENS,
                system=system or "You are a precise assistant. Return only the requested JSON.",
                thinking={"type": "adaptive"},
                output_config={
                    "effort": "medium",
                    "format": {"type": "json_schema", "schema": schema},
                },
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:
            raise LLMError(f"utility call failed: {exc}") from exc

        if getattr(response, "stop_reason", None) == "refusal":
            raise LLMError("utility call refused by safety classifier")
        text = next((b.text for b in response.content if b.type == "text"), "")
        if not text:
            raise LLMError("utility call returned no text")
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMError(f"utility call returned invalid JSON: {exc}") from exc


# --------------------------------------------------------------------------- kimi


class KimiProvider:
    """OpenAI-compatible chat completions. Kimi has no batch API and no cacheable system
    prefix, so every turn is a full-price synchronous call — expect several times the
    Anthropic bill for the same TICK_BUDGET."""

    name = "kimi"

    def __init__(self):
        import httpx  # already present via anthropic; imported lazily like the others

        if not CONFIG.kimi_api_key:
            raise LLMError("KIMI_API_KEY is not set")
        self.client = httpx.Client(
            base_url=CONFIG.kimi_base_url,
            headers={"Authorization": f"Bearer {CONFIG.kimi_api_key}"},
            timeout=120,
        )

    def submit_turns(self, turns: list[dict], system: list[dict]) -> Submission:
        prefix = "\n\n".join(b["text"] for b in system if b.get("type") == "text")
        results = {}
        for turn in turns:
            try:
                results[turn["custom_id"]] = self._json_call(
                    model=turn.get("model") or CONFIG.kimi_turn_model,
                    system=prefix,
                    prompt=turn["prompt"],
                    schema=turn["schema"],
                    max_tokens=MAX_TURN_TOKENS,
                )
            except LLMError:
                continue  # one dead turn must not kill the tick
        return Submission(batch_id=f"kimi:{uuid.uuid4()}", inline_results=results)

    def collect_turns(self, batch_id: str) -> Collected | None:
        # Results travel inline in the batch payload, exactly as they do offline.
        raise LLMFatalError(f"kimi provider cannot resolve batch {batch_id}")

    def utility(self, prompt: str, schema: dict, system: str = "") -> dict:
        return self._json_call(
            model=CONFIG.kimi_utility_model,
            system=system or "You are a precise assistant. Return only the requested JSON.",
            prompt=prompt,
            schema=schema,
            max_tokens=MAX_UTILITY_TOKENS,
        )

    def _json_call(
        self, model: str, system: str, prompt: str, schema: dict, max_tokens: int
    ) -> dict:
        """json_object mode rather than json_schema: it is the mode every OpenAI-compatible
        endpoint implements, so the schema rides in the prompt instead."""
        instructed = (
            f"{prompt}\n\nReturn only JSON matching this schema, with no other text:\n"
            f"{json.dumps(schema)}"
        )
        try:
            response = self.client.post(
                "/chat/completions",
                json={
                    "model": model,
                    "max_tokens": max_tokens,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": instructed},
                    ],
                },
            )
        except Exception as exc:
            raise LLMError(f"kimi call failed: {exc}") from exc

        if response.status_code != 200:
            raise LLMError(f"kimi call failed: HTTP {response.status_code} {response.text[:200]}")
        try:
            text = response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as exc:
            raise LLMError(f"kimi returned an unexpected envelope: {exc}") from exc
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMError(f"kimi returned invalid JSON: {exc}") from exc


# --------------------------------------------------------------------------- factory

_provider: Any = None


def provider():
    global _provider
    if _provider is None:
        _provider = {
            "anthropic": AnthropicProvider,
            "kimi": KimiProvider,
        }.get(CONFIG.llm_provider, OfflineProvider)()
    return _provider


def utility_call(prompt: str, model, system: str = ""):
    """Typed utility call. Returns None on any failure so callers degrade instead of
    wedging the tick — every news path is written to tolerate None."""
    try:
        raw = provider().utility(prompt, json_schema(model), system)
        return model.model_validate(raw)
    except LLMError:
        return None
    except Exception:
        return None
