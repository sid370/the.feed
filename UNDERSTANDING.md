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
