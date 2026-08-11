"""Worker CLI.

    python -m charsocial.worker.main migrate
    python -m charsocial.worker.main seed
    python -m charsocial.worker.main tick [--times N]
    python -m charsocial.worker.main loop
    python -m charsocial.worker.main status
"""
from __future__ import annotations

import argparse
import json
import time

from charsocial import db
from charsocial.config import CONFIG, assert_safe_to_spend
from charsocial.worker import tick as tick_module


def cmd_migrate(_args) -> None:
    db.migrate()
    print("schema ready")


def cmd_reset(_args) -> None:
    db.reset()
    print("schema reset")


def cmd_seed(_args) -> None:
    from scripts.seed import seed

    seed()


def cmd_tick(args) -> None:
    for i in range(args.times):
        stats = tick_module.run(seed=args.seed + i if args.seed is not None else None)
        print(json.dumps(stats, default=str))


def cmd_loop(_args) -> None:
    interval = CONFIG.tick_interval_minutes * 60
    print(f"ticking every {CONFIG.tick_interval_minutes}m (provider={CONFIG.llm_provider})")
    while True:
        try:
            print(json.dumps(tick_module.run(), default=str))
        except Exception as exc:
            print(f"tick failed: {exc}")
        time.sleep(interval)


def cmd_status(_args) -> None:
    with db.cursor() as cur:
        for label, sql in [
            ("characters", "SELECT status, count(*) AS n FROM characters GROUP BY status"),
            ("posts", "SELECT count(*) AS n FROM posts"),
            ("likes", "SELECT count(*) AS n FROM likes"),
            ("memory_notes", "SELECT count(*) AS n FROM memory_notes"),
            ("open batches", "SELECT count(*) AS n FROM batches WHERE status = 'submitted'"),
            ("hot pairs", """
                SELECT a.name AS a, b.name AS b, round(r.heat::numeric, 2) AS heat
                  FROM relations r
                  JOIN characters a ON a.id = r.character_id
                  JOIN characters b ON b.id = r.other_id
                 WHERE r.heat > 0.5 ORDER BY r.heat DESC LIMIT 5
            """),
        ]:
            cur.execute(sql)
            print(f"{label}: {json.dumps(cur.fetchall(), default=str)}")


def main() -> None:
    assert_safe_to_spend()
    parser = argparse.ArgumentParser(prog="charsocial-worker")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("migrate").set_defaults(func=cmd_migrate)
    sub.add_parser("reset").set_defaults(func=cmd_reset)
    sub.add_parser("seed").set_defaults(func=cmd_seed)
    sub.add_parser("status").set_defaults(func=cmd_status)
    sub.add_parser("loop").set_defaults(func=cmd_loop)

    tick_parser = sub.add_parser("tick")
    tick_parser.add_argument("--times", type=int, default=1)
    tick_parser.add_argument("--seed", type=int, default=None)
    tick_parser.set_defaults(func=cmd_tick)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
