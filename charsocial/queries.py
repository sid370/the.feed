"""Named SQL loaded from db/queries/*.sql, shared with the TypeScript read path.

Both the FastAPI service and the deployed Workers app answer the same reads. Holding the
SQL twice is how the two drift, so it lives once in .sql files and each side loads it with
a ~20-line adapter — psycopg's %(name)s here, positional $1 there.

Placeholders are written :like_this. A `::float` cast is not a placeholder and the pattern
below is written to leave it alone.
"""
from __future__ import annotations

import re
from pathlib import Path

QUERY_DIR = Path(__file__).resolve().parent.parent / "db" / "queries"

_NAME = re.compile(r"^--\s*name:\s*(\w+)\s*$", re.M)
_PARAM = re.compile(r"(?<!:):([a-z_][a-z0-9_]*)")


def strip_body(body: str) -> str:
    """A comment introducing the next query lands at the end of the previous one's body."""
    lines = body.strip().splitlines()
    while lines and lines[-1].lstrip().startswith("--"):
        lines.pop()
    return "\n".join(lines).strip()


def _load() -> dict[str, str]:
    loaded: dict[str, str] = {}
    for path in sorted(QUERY_DIR.glob("*.sql")):
        chunks = _NAME.split(path.read_text())
        for name, body in zip(chunks[1::2], chunks[2::2]):
            if name in loaded:
                raise ValueError(f"duplicate query name {name!r} in {path.name}")
            loaded[name] = _PARAM.sub(r"%(\1)s", strip_body(body))
    if not loaded:
        raise RuntimeError(f"no queries found in {QUERY_DIR}")
    return loaded


SQL = _load()
