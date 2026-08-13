"""Postgres access. Plain SQL on purpose — the scheduler is arithmetic you want to read."""
import contextlib
from collections.abc import Iterator
from pathlib import Path
from typing import LiteralString, cast

import psycopg
from psycopg.rows import DictRow, dict_row

from charsocial.config import CONFIG

MIGRATIONS = Path(__file__).resolve().parent.parent / "db" / "migrations"

# Guards against overlapping cron invocations double-spending the budget.
TICK_LOCK = 0x0C5A_71CB

# Every connection here is dict_row. Saying so in the type is what lets a checker catch a
# renamed column at `row["handle"]` instead of leaving every row an unchecked tuple.
Cursor = psycopg.Cursor[DictRow]


def connect() -> psycopg.Connection[DictRow]:
    # Parameterised rather than the bare psycopg.connect(): that one is typed as returning
    # tuple rows whatever row_factory says, which is what made every row["col"] unchecked.
    return psycopg.Connection[DictRow].connect(
        CONFIG.database_url, row_factory=dict_row, autocommit=False
    )


@contextlib.contextmanager
def cursor() -> Iterator[Cursor]:
    with connect() as conn, conn.cursor() as cur:
        yield cur
        conn.commit()


def one(cur: Cursor) -> DictRow:
    """fetchone() for a query that cannot return zero rows — an aggregate, or RETURNING.

    Names the impossible case where it happens instead of letting it surface as a None
    subscript further down.
    """
    row = cur.fetchone()
    if row is None:
        raise RuntimeError("expected a row, got none")
    return row


@contextlib.contextmanager
def tick_lock(cur: Cursor) -> Iterator[bool]:
    """Yields True if this process owns the tick, False if another one already does."""
    cur.execute("SELECT pg_try_advisory_lock(%s) AS got", (TICK_LOCK,))
    got = one(cur)["got"]
    try:
        yield got
    finally:
        if got:
            cur.execute("SELECT pg_advisory_unlock(%s)", (TICK_LOCK,))


def migrate() -> None:
    """Applies every unapplied migration in filename order.

    Tracked per file rather than "does the first table exist" — that shortcut meant every
    migration after 001 was silently skipped on an existing database.
    """
    with cursor() as cur:
        cur.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "  name TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
        cur.execute("SELECT name FROM schema_migrations")
        done = {r["name"] for r in cur.fetchall()}

        for path in sorted(MIGRATIONS.glob("*.sql")):
            if path.name in done:
                continue
            # 001 predates this table; adopt an existing schema instead of re-running it.
            if path.name.startswith("001_"):
                cur.execute("SELECT to_regclass('public.characters') IS NOT NULL AS ready")
                if one(cur)["ready"]:
                    cur.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (path.name,))
                    continue
            # psycopg demands a literal query string to make injection hard to write by
            # accident. A migration is a file in this repo, not input.
            cur.execute(cast(LiteralString, path.read_text()))
            cur.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (path.name,))


def reset() -> None:
    with cursor() as cur:
        cur.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    migrate()
