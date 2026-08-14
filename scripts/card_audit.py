"""Score the character cards themselves: sample length, banned constructions, tic budget.

`voice_audit.py` measures the feed; this measures the source. A card is what teaches the
voice, so a card demonstrating a 1,108-character post or a construction the world rules
forbid is the cause of a failure the feed audit only reports.
"""
from __future__ import annotations

import json
import pathlib
import re
import statistics
import sys

CHARACTERS = pathlib.Path(__file__).resolve().parent.parent / "characters"
FENCE = re.compile(r"```json\s*\n(.*?)\n```", re.DOTALL)
PROVOCATION = re.compile(r"^\[.*?\]\s*")

# Literal shapes. Reworded variants exist and a grep cannot catch them — this is a floor.
BANNED = (
    "is not the same as", "isn't the same as", "are not the same", "two different things",
    "that's the whole", "that is the whole", "that's the post", "the entire reason",
    "the whole lesson", "that's the entire", "that is the entire",
)

# Median is the number that shapes behaviour; max is only the world's hard ceiling, so one
# long sample from a genuinely digressive character is allowed and a long median is not.
TARGETS = {"median": 100, "max": 280, "tic_share": 0.10}
BIO_MAX = 100


def _samples(card: dict) -> list[str]:
    return [PROVOCATION.sub("", t) for group in card["samples"].values() for t in group]


def audit() -> int:
    rows, failures = [], []
    for path in sorted(CHARACTERS.glob("*.md")):
        entry = json.loads(FENCE.search(path.read_text(encoding="utf-8")).group(1))
        card = entry["card"]
        texts = _samples(card)
        lengths = [len(t) for t in texts]
        median, longest = int(statistics.median(lengths)), max(lengths)

        banned = [t for t in texts if any(b in t.lower() for b in BANNED)]
        # A tic that is itself a banned construction is worse than a sample using one:
        # `tics` is framed to the model as identity, not as an example.
        banned_tics = [t for t in (card.get("tics") or []) if any(b in str(t).lower() for b in BANNED)]

        worst_tic, worst_share = None, 0.0
        voice = str(card.get("voice", "")).lower()
        for tic in card.get("tics") or []:
            phrase = str(tic).strip().rstrip(".!")
            if len(phrase) < 4 or len(phrase.split()) > 6:
                continue
            # A phrase the voice field names is structure, not a catchphrase — Kim Jong Un's
            # "The Respected Poster" stands in for "I", so budgeting it is like budgeting a
            # pronoun. Anything not named in the voice is a signature and gets rationed.
            if phrase.lower() in voice:
                continue
            share = sum(1 for t in texts if phrase.lower() in t.lower()) / len(texts)
            if share > worst_share:
                worst_tic, worst_share = phrase, share

        # The bio is re-read on every single turn, so a fault there is amplified far harder
        # than the same fault in a sample. One bio used to say "This takes more characters
        # than the format allows" and the character wrote 500-character posts for weeks.
        bio = str(card.get("bio", ""))
        if len(bio) > BIO_MAX:
            failures.append(f"{path.stem}: bio {len(bio)} chars > {BIO_MAX}")
        if any(b in bio.lower() for b in BANNED):
            failures.append(f"{path.stem}: banned construction in bio")
        if any(bio.lower().strip(".") == t.lower().strip(".") for t in texts):
            failures.append(f"{path.stem}: bio duplicates a sample")

        rows.append((path.stem, len(texts), median, longest, len(banned), worst_share))
        if median > TARGETS["median"]:
            failures.append(f"{path.stem}: median sample {median} > {TARGETS['median']}")
        if longest > TARGETS["max"]:
            failures.append(f"{path.stem}: longest sample {longest} > {TARGETS['max']}")
        if banned:
            failures.append(f"{path.stem}: {len(banned)} sample(s) use a banned construction")
        if banned_tics:
            failures.append(f"{path.stem}: banned construction in tics — {banned_tics}")
        if worst_share > TARGETS["tic_share"]:
            failures.append(f"{path.stem}: tic {worst_tic!r} in {worst_share:.0%} of samples")

    print(f"{'card':<17}{'n':>4}{'median':>8}{'max':>6}{'banned':>8}{'top tic':>9}")
    for handle, n, median, longest, banned, share in sorted(rows, key=lambda r: -r[2]):
        print(f"{handle:<17}{n:>4}{median:>8}{longest:>6}{banned:>8}{share:>8.0%}")

    print()
    for f in failures:
        print(f"FAIL  {f}")
    if not failures:
        print(f"PASS  {len(rows)} cards within targets")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(audit())
