"""Word-overlap scoring, shared so the write-time guard and the audit cannot disagree."""
from __future__ import annotations

import re

# Words this short are grammar, not subject matter, and every post shares them.
WORD_MIN_CHARS = 4


def words(text: str) -> frozenset[str]:
    return frozenset(re.findall(r"[a-z']{%d,}" % WORD_MIN_CHARS, (text or "").lower()))


def containment(a: frozenset[str], b: frozenset[str]) -> float:
    """How much of the shorter text reappears in the longer one; Jaccard misses rewrites."""
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))
