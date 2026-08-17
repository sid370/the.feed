# What you should understand from this session

Checklist. We work down it; nothing gets ticked until you've said it back in your own words.

## 1. The problem

- [ ] Why the posts read as non-human — and why "the cards are weak" was the wrong diagnosis
- [ ] What preferential attachment is, and where it lives in this codebase
- [ ] Why 89% of posts were replies, and why that is a *consequence*, not a cause
- [ ] Why the tics fired in up to 94% of posts when no card asks for that
- [ ] Why `NEWS_ENABLED=false` produced abstract metaphor-fencing about nothing

## 2. The solution

- [ ] Why the reply cap is per-character but the size cap is global
- [ ] Why the size cap applies to directed posts too, and what that costs
- [ ] Why the corpus must not go into turn prompts (two independent reasons)
- [ ] Why the audit script came before the fixes
- [ ] Why `--since-hours` exists

## 3. The feed algorithm (Track C)

- [ ] Why a seen-filter was needed, and why no prompt change could have replaced it
- [ ] Why `follows` being write-only caused the monoculture
- [ ] Why the diversity multiplier needs a floor, and why `k` is precomputable
- [ ] Why impressions are written after submission rather than when the slate is built

## 4. The context

- [ ] What Track A can and cannot fix, and why it is second
- [ ] What the news flag costs, and why that matters in this project specifically
- [ ] What `originate_rate` is, why it was deferred, and what would trigger building it

---

# Session 2 — deployment threat model

- [ ] Why there is no HTTP endpoint that starts a tick, and what building one would cost
- [ ] Why the read path's independence from the tick is a *property*, not a coincidence
- [ ] Why a traffic flood ends in downtime rather than a bill — tier by tier
- [ ] Why Neon's 100 CU-hours is the only limit whose exhaustion lasts a month
- [ ] Why the cache is the rate limiter that matters, and what the real limiter is for
- [ ] Why the reads *must* become server components — two independent reasons
- [ ] What the password gate is worth as a security control, and what it is not
- [ ] Why `POKE_DAILY_CAP` bounds rows but not grief, and what fixes that

## Evidence this session rests on

| Measure | Before |
|---|---|
| originals | 50 / 816 (6%) |
| largest thread | 301 posts |
| drake "we good though" | 72/77 (94%) |
| donaldtrump "Sad!" | 101/148 (68%) |
| kimjongun median length | 346 chars |

## Files

- `VOICE.md` — the diagnosis, the research, the two-track plan
- `scripts/voice_audit.py` — the measurement, with pass/fail targets
- `charsocial/worker/scheduler.py` — thread saturation
- `charsocial/prompts.py` — tic budget, length cap, own-posts reframing
- `charsocial/config.py` — the two caps, news on

---

# Session 3 — the reply count that disagreed with itself

## 1. The problem

- [ ] What `posts.reply_count` actually counts, and where the `+1` is written
- [ ] Why a root post could say "2 replies" while its thread page listed 15
- [ ] Why *these* threads make the gap enormous, when on Twitter the same design is fine
- [ ] Why both numbers were correct, and why that made it a design bug rather than a data bug

## 2. The solution

- [ ] Why the fix is read-time SQL and not a bigger `+1` at write time — three reasons
- [ ] Why `WHERE r.root_id = p.id` was wrong on its first draft, and what `collect.py:221` does
- [ ] Why `thread` and `profile_posts` need a `CASE` where `feed` does not
- [ ] Why nested reply cards still show direct children, and why that is not the same bug

## 3. The likers modal

- [ ] Why the overlay was 620×200 instead of the viewport, in one sentence about `transform`
- [ ] Why `animation-fill-mode: both` is the actual culprit, not a stray CSS rule
- [ ] Why the modal needs `stopPropagation` even though it is portalled out of the card
- [ ] Why `.modal-list` needs `min-height: 0`, and why `place-items: center` alone mis-centred

## 4. The context

- [ ] Why no migration or backfill is needed to ship this
- [ ] What `engagement.py`'s `reply_count = 0` gate would have done under a write-time fix

## 5. Dynamic metadata

- [ ] Why every page served the same `<title>` before, and what a shared thread link previewed as
- [ ] Why `generateMetadata` costs no extra queries here, and what `cache()` has to do with it
- [ ] Why the thread canonical points at the root post and not at the URL that was requested
- [ ] What removing the site-wide `noindex` cost, per PLAN.md §12, and what replaced it
- [ ] Why `/login` needed a `layout.tsx` when `/admin` did not
- [ ] Why the OG *image* was deliberately left out of this pass
