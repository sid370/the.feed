"""The world tick — the only clock in the system.

It is a CLOCK, not a decision-maker. It decides who gets a turn and what lands in front of
them; the agent decides what to do about it. That distinction is why cascades cannot
explode: a reply written this tick is not seen until the next one, so a beef unfolds over
hours instead of recursing in four seconds. Pacing and cascade-safety fall out of the same
mechanism, with no depth caps anywhere.
"""
from __future__ import annotations

import random
import time

from charsocial import db
from charsocial.config import CONFIG
from charsocial.models import ActingCharacter, Assignment
from charsocial.worker import collect, engagement, heat, news, scheduler, submit


def run(seed: int | None = None) -> dict:
    rng = random.Random(seed if seed is not None else time.time_ns())
    stats: dict = {"skipped": False}

    # Network first, transaction second. Fetching feeds can take tens of seconds and a
    # Postgres transaction held open across that gets dropped mid-tick.
    feed_entries = news.fetch_feeds() if CONFIG.news_enabled else []

    with db.connect() as conn, conn.cursor() as cur:
        with db.tick_lock(cur) as owned:
            if not owned:
                return {"skipped": True, "reason": "another tick holds the lock"}

            # Committed on its own before the body runs. If this shared the body's
            # transaction, a rollback would take the row with it and the error handler
            # below would update zero rows — silently, every time.
            cur.execute(
                "INSERT INTO ticks (world_id, budget) VALUES (%s, %s) RETURNING id",
                (CONFIG.world_id, CONFIG.tick_budget),
            )
            tick_id = cur.fetchone()["id"]
            conn.commit()

            try:
                # 1-2. collect the previous batch and apply its consequences
                stats["posts_written"] = collect.collect_open_batches(cur)

                # 3. decay, so old feuds cool and old threads sink
                heat.decay(cur)

                # 4-5. headlines in, unsafe ones gated out
                stats["headlines_ingested"] = news.store(cur, feed_entries)
                stats["headlines_classified"] = news.classify(cur) if CONFIG.news_enabled else 0

                # 6-7. cast, and let newsworthiness set the mix
                budget = CONFIG.tick_budget
                assignments, news_share = news.cast(cur, max_picks=budget)
                news_slots = min(len(assignments), int(round(budget * news_share)))
                assignments = assignments[:news_slots]
                # Only burn the headlines actually used — cast proposes more than fit.
                news.mark_used(cur, assignments)
                stats["news_share"] = news_share
                stats["assignments"] = len(assignments)

                # 8. who acts — notifications first, then scheduled baseline
                acting = scheduler.select_turns(cur, budget, rng)
                acting = _prioritise_assigned(acting, assignments, cur, budget)

                # 9-10. build slates and submit ONE batch. The only spend in the system.
                batch_id, turns = submit.submit_turns(cur, acting, assignments, tick_id)
                stats["batch_id"] = batch_id
                stats["turns_sent"] = turns

                # 11. free engagement — arithmetic, no model calls
                likes, follows = engagement.scatter(cur, rng)
                stats["likes"] = likes
                stats["follows"] = follows

                # 12. let characters notice their own numbers
                stats["vanity"] = engagement.vanity_notifications(cur)

                cur.execute(
                    "UPDATE ticks SET finished_at = now(), news_share = %s, turns_sent = %s, "
                    "posts_written = %s WHERE id = %s",
                    (news_share, turns, stats["posts_written"], tick_id),
                )
                conn.commit()
            except Exception as exc:  # a failed tick must not poison the next one
                conn.rollback()
                with conn.cursor() as err_cur:
                    err_cur.execute(
                        "UPDATE ticks SET finished_at = now(), error = %s WHERE id = %s",
                        (str(exc)[:500], tick_id),
                    )
                conn.commit()
                stats["error"] = str(exc)
                raise

    stats["tick_id"] = tick_id
    return stats


def _prioritise_assigned(
    acting: list[ActingCharacter], assignments: list[Assignment], cur, budget: int
) -> list[ActingCharacter]:
    """A character the showrunner cast for a headline should get a turn even if the
    scheduler didn't pick them — otherwise the casting call was wasted spend."""
    if not assignments:
        return acting

    have = {c.handle for c in acting}
    wanted = [a.handle for a in assignments if a.handle not in have]
    if not wanted:
        return acting

    cur.execute(
        """
        SELECT id, name, handle, model, persona_card, engagement_profile
          FROM characters
         WHERE handle = ANY(%s) AND status = 'active' AND world_id = %s
        """,
        (wanted, CONFIG.world_id),
    )
    extra = [ActingCharacter.model_validate(dict(r)) for r in cur.fetchall()]
    # Budget is a hard ceiling: cast members displace scheduled turns, never add to them.
    return (extra + acting)[:budget]
