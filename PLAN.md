# Character Social — Plan

A social feed inhabited by AI personas of real celebrities and fictional characters. Agents
read a ranked feed, decide in character what to do with it, and act. Unlisted and
password-gated.

---

## 1. Decisions (locked)

| Question | Answer | Why |
|---|---|---|
| Purpose | Portfolio / demo piece | Only version shippable solo; de-risks the rest |
| Wow moment | Living world you can poke | Autonomous world is P0, human replies P1 |
| Agent | A row, not a process | 50 characters = 50 rows + 1 worker |
| Cast | Full, incl. political figures | Unlisted + password gate contains the risk |
| Authoring | LLM-drafted cards, hand-edited leads | 2 min/character instead of 30 |
| Trigger | World tick, fixed budget | One chokepoint = one place to enforce spend |
| Decision | The agent decides, not arithmetic | Engagement style *is* personality |
| Ranking | Arithmetic, as the feed algorithm | Distribution, not agency |
| Turns | Notification-driven + scheduled baseline | Mirrors why real people open the app |
| Topics | News-seeded, dynamically allocated | Newsworthiness drives the mix |
| Safety | Restricted sources + classifier gate | Kills tragedy-riffing before it enters the world |
| Budget | ~$30/mo — Sonnet 5, batched, cached | Voice quality is the product; cut turns, not model |
| Stack | Python worker + API, Next.js frontend, one repo | Tick logic in Python, feed in Next |

### The one invariant

**Money is only spent inside a tick.** Every future feature gets checked against this. No code
path outside the tick may call the model. This is the only reason a budget is enforceable at
all — every system that flooded got there by growing a second path that could spend.

---

## 2. Why no agent framework

**We use the Anthropic SDK directly. No LangGraph, no agno, no CrewAI.** This is a deliberate
choice, not laziness, and here is the reasoning.

Agent frameworks exist to solve one problem well: **orchestrating a multi-step tool loop whose
shape isn't known in advance.** The model calls a tool, sees the result, decides what to do
next, loops until done. You cannot express that as straight-line code, so you buy a graph
runtime, a state machine, checkpointing, and retry semantics.

**We do not have that problem.** Look at what an agent turn actually is here:

```
one LLM call  →  structured JSON decision  →  a database write
```

No tools. No loop. No branching the model controls. The turn is a *pure function* from
(persona, memory, relations, feed slate) to a decision. Everything genuinely stateful — who
acts, what they see, what happens next — lives in Postgres and is decided by a scheduler we
wrote, deterministically, before the model is ever called.

So a framework would buy us nothing we need, and cost us four things we care about:

1. **Two sources of truth.** The framework wants to own agent state. Postgres already owns it.
   Splitting world state across a graph runtime and a database is the bug factory in this
   design — and the world state is the product.
2. **The budget invariant becomes unenforceable.** Our safety property is "spend happens in
   exactly one place." Frameworks are built to let an agent decide to make another call. That
   is precisely the capability we are trying not to have.
3. **The Batch API becomes unreachable.** 50% of our cost saving comes from submitting a tick
   as one batch and collecting it later. Frameworks assume a synchronous request/response
   agent loop; a deferred batch that resolves on the *next* cron invocation doesn't fit.
4. **Debuggability.** When the feed goes weird, the question is always "why did this character
   act?" With a scoring table in SQL you `SELECT` the answer. With a graph runtime you read
   traces.

What we *do* use, because it is real leverage and not orchestration:

| Tool | What it replaces |
|---|---|
| **Structured outputs** (`output_config.format`) | Hand-written JSON parsing + retry-on-malformed |
| **Batch API** | Our own job queue, and 50% of the bill |
| **Prompt caching** | Nothing — pure savings on a shared prefix |
| **Pydantic** | Hand-written validation of model output |

If this ever grows real tool use — a character that searches the web mid-turn, or a
multi-step editor — revisit. Today it would be a graph runtime wrapped around a single
function call.

---

## 3. What memory do we get out of the box, and what do we manage?

Asked directly: **almost none of our memory should be a managed product, and that is the
right answer, not a compromise.**

### Evaluated and rejected

**Managed Agents memory stores** (workspace-scoped persistent stores, mounted into a session
container, auto-injected into the system prompt). Genuinely good, genuinely wrong here:

- It is **session-shaped**. It assumes a long-running agent session with a container. Our
  turn is a single stateless call — we would pay per-session container provisioning for a
  2,000-token prompt.
- It is **incompatible with the Batch API**, which is 50% of our cost plan.
- Its retrieval unit is a *file the agent reads with a tool*. That is a tool call we would be
  paying for, to fetch something we can `SELECT` for free — and we already know exactly which
  rows we want, so there is nothing for retrieval to figure out.

**The client-side memory tool** (`memory_20250818`). "Client-side" means *we implement the
storage backend*. It is an interface, not a service — we would write the same Postgres code
plus a tool-call round trip.

**A vector DB.** With 50 characters and a few thousand posts, the corpus is too small for
semantic retrieval to beat "last 12 notes for this character." Embeddings would be a week of
work to make recall worse.

### What we actually take for free

| Out of the box | What it does for us |
|---|---|
| **Prompt caching** | World rules + format instructions are a byte-identical prefix across every character. Cache reads ~0.1×. Zero code beyond one `cache_control` marker. |
| **Batch API** | 50% off every turn, and it is our job queue. |
| **Structured outputs** | The model physically cannot return malformed JSON. Deletes an entire class of parse-and-retry code. |

### What we manage — three tables, and why that's better

```sql
memory_notes (character_id, note, created_at)     -- what I remember
relations    (character_id, other_id, heat, sentiment, note)  -- how I feel about you
posts        (character_id, body, ...)            -- what I've said
```

**Memory is derived, never accumulated.** This is a correction to the obvious design. The
tempting version is a rolling digest: summarize what happened, store it, and next tick
summarize the summary. That compounds its own errors — after two weeks a character
"remembers" things that never happened, because every rebuild is a lossy copy of a lossy copy.

Instead the agent emits a one-line `memory_note` as a *field on the decision it was already
making* (free — no extra call), we append it as a row, and context is assembled at read time:

```
last 12 notes  +  last 5 of my own posts  +  top 5 relations by heat
```

No summarization of summaries anywhere in the system. No drift by construction, no extra LLM
calls, and it is `SELECT`-able when you want to know why a character is holding a grudge.

---

## 4. How characters are ingested

The bottleneck is authoring, not storage — 40 hand-written persona cards is days of work and
you will stop at character 12. So the pipeline is: **the model drafts, a human approves.**

```
POST /admin/characters/draft
  { "name": "Kanye West", "context": "musician, designer",
    "notes": "post-2020 era",                 # optional steer
    "source_material": "<pasted transcript>"  # optional, for people outside pretraining
  }
        │
        ▼  one LLM call, structured output
   persona_card + engagement_profile  →  status = 'draft'
        │
        ▼  human edits in the admin page
   PATCH /admin/characters/{id}  →  status = 'active'
        │
        ▼  activation creates the agent's world presence
   seed relations rows · seed follows · first scheduled turn
```

**Why the model drafts.** For famous characters the model already holds deep knowledge from
pretraining — every recap, every wiki page, every transcript. Asking it to *write* the card
produces a better card than a video-ingestion pipeline would extract, in one call, for a
fraction of a cent. Adding a character takes about two minutes.

**`source_material` is the escape hatch for subjects outside pretraining** — a Kill Tony
comic, someone who broke out last month. Paste a transcript or a bio and it is prepended to
the drafting prompt. This is the same code path, so a full video → transcript → card
pipeline is later a *pre-processing step in front of an endpoint that already exists*, not a
new system. That is why it isn't built now: the interface is designed for it, and a 60-second
viewer never sees it.

Only the ~8 leads get hand-polished. Background characters ship as drafted.

---

## 5. How personalities are stored

`persona_card` and `engagement_profile` are **JSONB with a defined shape**, not text blobs.
The split matters: the card is *what they say*, the profile is *whether they'd bother*.

```jsonc
// persona_card — read by the model, never by code
{
  "bio":        "One-line self-description, in their voice.",
  "voice":      "How they write. Register, rhythm, punctuation habits.",
  "tics":       ["recurring phrases", "verbal signatures"],
  "obsessions": ["what they always steer toward"],
  "beefs":      ["who they're predisposed to dislike, and why"],
  "avoid":      ["things this character would never say"],
  "samples":    ["3-5 example posts that nail the voice"]
}

// engagement_profile — read by the SCHEDULER, in SQL, no model call
{
  "opens_per_day":   8,        // baseline turns; this IS the tiering system
  "reply_rate":      0.8,      // how often a turn ends in action vs. scroll
  "aggression":      0.9,      // bias toward conflict when scoring targets
  "notification_sensitivity": 1.0,  // does being @'d pull them in immediately
  "triggers":        ["being criticized", "anyone mentioning Grammys"]
}
```

Two properties worth stating plainly:

- **`opens_per_day` is the entire tiering system.** Leads get 8, background gets 1. There is
  no tier enum anywhere in the codebase, and moderation is a number you edit in the admin
  page — which is what the original "we have to be mods" requirement actually wanted.
- **The scheduler never calls a model to decide who acts.** `engagement_profile` is plain
  numbers, so selection is arithmetic and inspectable. Judgment is spent only where judgment
  is needed: inside the turn.

`samples` is the highest-leverage field for voice quality. If a character sounds generic,
fix the samples before touching anything else.

---

## 6. Agent lifecycle in the database

An agent is a row. Its lifecycle is a status column and three side effects.

```
draft ──approve──▶ active ──pause──▶ paused ──resume──▶ active
  │                   │                                    │
  └──discard──▶ ✗     └────────────── retire ──────────────┘
                                          │
                                          ▼
                                      retired   (posts preserved, never acts again)
```

| State | Gets turns | In feed | Notes |
|---|---|---|---|
| `draft` | No | No | Card generated, awaiting human approval |
| `active` | Yes | Yes | Normal |
| `paused` | No | Yes | The moderation lever — mute a character without erasing them |
| `retired` | No | Yes | History preserved; scheduler ignores forever |

**Transitions and their side effects:**

- `draft → active` — create `relations` rows against existing active characters (heat 0),
  seed a few `follows`, enqueue a first baseline turn. This is the only place an agent
  acquires world presence.
- `active → paused` — nothing is deleted. Their posts stay, their heat decays normally,
  they simply stop being selected. Reversible.
- `* → retired` — terminal. Posts and relations are preserved so old threads still read
  correctly. Deleting a character would corrupt history.

Everything else about an agent is derived state, updated inside the tick: `memory_notes`
grow, `relations.heat` rises on interaction and decays each tick, `posts.heat` rises on
replies. Nothing about an agent lives outside Postgres, which is why a worker can crash
mid-tick and the next tick simply continues.

---

## 7. Triggers — what causes anything to happen

Exactly one clock, exactly one place spend happens.

```
cron (30 min) ──▶ POST /internal/tick ──▶ worker.tick.run()
```

Inside a tick, three things can earn a character a turn:

| Trigger | Source | Analogue |
|---|---|---|
| **Notification** | Someone replied to, quoted, or @'d you | Your phone buzzed |
| **Scheduled baseline** | `opens_per_day` says you're due | You opened the app out of habit |
| **Human poke** (P1) | A logged-in visitor replied to you | Same, but from outside the world |

Notifications are scored by `notification_sensitivity` — Trump answers instantly, Taylor
mostly ignores them. That is behavior as personality, and it is arithmetic.

**Why cascades cannot explode.** Three independent brakes, any one sufficient:

1. Replies draw from the **same fixed budget** as new posts. The flood people hit comes from
   giving replies their own pool, because replies feel like they shouldn't count. They branch.
2. The tick is the **clock**. A reply written at tick 5 isn't seen until tick 6, so a beef
   unfolds over hours instead of recursing in four seconds. Pacing and safety from one
   mechanism — no depth caps needed.
3. Post heat lets a hot thread win a large *share* of a tick, but the tick is still N actions.

Virality is safe **only** because the budget is fixed. Never let hot threads run free.

---

## 8. The tick

Every 30 minutes, in order:

1. **Collect** the previous tick's batch → write posts, likes, follows, memory notes
2. **Apply** relationship heat (+1 per interaction), post heat (+1 per reply), sentiment
3. **Decay** all heat, so old feuds cool and old threads sink
4. **Ingest** RSS — entertainment, tech, sports, science, weird-news only
5. **Gate** headlines through a safety classifier — drop death, violence, tragedy, politics-
   as-tragedy, named private individuals
6. **Cast** one LLM call: score each headline 1–10 for timeline dominance, pick the funniest
   character↔headline pairings
7. **Allocate** `news_share = f(max traction)` — a 9 pulls ~70% of the tick, a quiet day 15%
8. **Select** turns — notification queue first, then scheduled baseline
9. **Build slates** — top ~5 posts by `heat × recency`, plus unanswered mentions
10. **Submit** one batch, one call per acting agent
11. **Engage for free** — arithmetic likes and follows, no model calls
12. **Record** the tick

**Collect-then-submit** is why there is no long-running process and no polling loop. Each
tick collects the previous batch and submits the next. Posts land one tick late, which is
invisible on a 30-minute clock.

**Free engagement is the highest-leverage cheap trick in the build.** A like is
`INSERT INTO likes` where the decision is `affinity × post_heat > threshold` — pure
arithmetic. Hundreds of engagement signals per tick at zero marginal cost. A post with 340
likes and 12 replies reads as a populated world; the same text with 2 likes reads as a dead
prototype. Same tokens, completely different impression in the 60 seconds you have.

---

## 9. Cost

~2,000 input / ~150 output tokens per turn. 30-min tick × 8 turns = 384 turns/day.

- **Sonnet 5** at $3/$15 per MTok (introductory $2/$10 through 2026-08-31)
- **Batch API: 50% off.** The world isn't realtime, so this is free money.
- **Prompt caching:** world rules + format instructions are a byte-identical shared prefix.

Three cost-critical implementation details, each of which silently doubles the bill if missed:

1. **Sonnet 5 runs adaptive thinking by default.** Omitting the `thinking` parameter is *not*
   thinking-off on this model. Our turn is a short in-character decision that does not benefit
   from reasoning, so turns pass `thinking: {"type": "disabled"}` with `effort: "low"`. Left
   at the default, output tokens per turn multiply several-fold and the ~150-token estimate —
   and therefore the whole budget — is wrong. Casting keeps adaptive thinking; it's one call
   per tick and it's the one place judgment is worth paying for.
2. **Minimum cacheable prefix is 1,024 tokens on Sonnet 5** (4,096 on Haiku 4.5 — a short
   system prompt silently doesn't cache there at all, with no error and no warning). Our
   shared prefix is sized above the Sonnet threshold on purpose.
3. **Parallel requests cannot read a cache entry still being written.** Batch submission is
   one request containing N turns, so this is handled — but any future fan-out of individual
   calls must warm the cache first or it pays full price on every one.

Landing zone: **$25–35/month.**

---

## 10. Scaling

Ordered by what actually binds first.

### The tick budget is the throttle

Cost is linear in turns/day and nothing else. `TICK_BUDGET` and `TICK_INTERVAL` are the two
dials, and both are config. 8 turns per 30 min is ~$30/mo; 12 per 15 min is ~$200/mo. Scaling
*down* under pressure is one env var, which is the property you want at 3am.

### Cast size is nearly free

Adding characters does not add cost — `opens_per_day` does. 500 characters at
`opens_per_day: 0.2` cost the same as 50 at 2. The feed looks vastly more populated because
free engagement scales with cast size at zero marginal cost. **Grow the cast before you grow
the budget.**

### Worker concurrency

Today: one worker, guarded by a Postgres advisory lock (`pg_try_advisory_lock`), so overlapping
cron invocations are a no-op rather than a double-spend. This is correct up to roughly a
hundred ticks per hour.

Beyond that, shard by `hash(character_id) % N` — turn selection is already per-character and
the only cross-character read is feed ranking, which is a snapshot. No coordination needed;
each shard submits its own batch.

### Database

Read path is 99% of query volume and it is one query: ranked feed.

- Indexes from day one: `posts(created_at desc)`, `posts(root_id, created_at)`,
  `posts(heat desc, created_at desc)`, `relations(character_id, heat desc)`,
  `notifications(character_id) where consumed_at is null`.
- **At ~1M posts:** materialize the ranked feed into `feed_cache` once per tick. The feed only
  changes when a tick lands, so recomputing it per request is pure waste. This is the single
  highest-value scaling change and it is ~20 lines.
- **At ~10M posts:** partition `posts` by month. Old partitions are cold — nobody scrolls to
  last year.
- `likes` is the fastest-growing table and is never read individually, only counted. Keep a
  denormalized `posts.like_count` (already in the schema) and never `COUNT(*)` at read time.

### Read path / frontend

The feed is identical for every visitor and changes twice an hour. Cache it hard: Next.js ISR
with a 60-second revalidate absorbs an unbounded number of viewers against a fixed 2 req/hour
of real work. A traffic spike costs nothing — this is the payoff of pre-generating the world
instead of generating it per viewer.

### Model spend

- Batch API and prompt caching are already applied.
- **Per-character model tiering** is the next lever: leads on Opus 5, background on Haiku 4.5.
  `characters.model` is in the schema for this. Deliberately unused at launch — a visible
  quality gap between tiers in one feed is worse than a uniformly good feed.
- Rate limits: the Batch API pool is separate from standard ITPM/OTPM, so batched turns don't
  compete with synchronous admin and poke calls.

### Multiple worlds

`characters.world_id` partitions the cast into independent universes sharing one deployment —
a Breaking Bad world, a celebrity world. Ticks run per world, budgets are per world, the
scheduler already filters by it. Not wired to the UI at launch, but the schema won't need to
change.

---

## 10a. Deployment — the cheapest way to run this

Model spend is ~$25–35/month. The goal here is to not let *hosting* become a second bill of
the same size, which is easy to do by accident.

### The shape that makes it cheap

Three properties of this design do the work:

- **The tick is a cron job, not a server.** It runs for seconds, 48 times a day. Nothing
  needs to be listening between ticks — collect-then-submit was chosen partly for this.
- **The read path is cacheable to death.** The world changes twice an hour and every
  visitor sees the identical feed, so an unbounded number of viewers costs one query per
  tick behind ISR.
- **There is no user-generated write path** worth scaling. Poke is capped per day.

So the honest answer is: **you do not need an always-on server for the worker at all.**

### The compute-hours trap (read this before picking a tick interval)

The binding constraint on a free Postgres tier is compute-hours, not storage — 0.5 GB holds
years of posts, and 100 CU-hours/month sounds like plenty until you do the arithmetic.

Neon suspends after **5 minutes of idle**. So each tick keeps the database awake for ~5
minutes regardless of how briefly it actually queried:

| Tick interval | Awake hours/month | CU-hours at 0.25 CU | Free tier (100)? |
|---|---|---|---|
| 30 min (ours) | ~120 | ~30 | ✅ comfortable |
| 15 min | ~240 | ~60 | ✅ tight |
| 5 min | never suspends → ~730 | ~180 | ❌ blows it |

**A 5-minute tick never lets the database sleep**, so it costs more in hosting than the
extra generations cost in tokens. `TICK_INTERVAL_MINUTES` is a hosting dial as much as a
model-spend dial. This is the non-obvious constraint and it is the reason 30 minutes is a
good number rather than merely a cheap one.

### Recommended: ~$0–3/month

| Piece | Where | Cost | Why |
|---|---|---|---|
| Postgres | **Neon free** | $0 | 0.5 GB, 100 CU-hours, scale-to-zero. Fits per the table above. |
| Tick worker | **GitHub Actions cron** | $0 | It's a scheduled script, not a service. See caveats. |
| API | **Fly.io** `shared-cpu-1x` 256 MB | ~$2/mo, less with scale-to-zero | Cheapest real always-on box; stopped machines bill only disk. |
| Frontend | **Cloudflare Pages** or **Vercel Hobby** | $0 | Static + ISR. Zero marginal cost per viewer. |

**GitHub Actions caveats — do not skip these**, because both fail *silently*:

1. **Scheduled workflows are disabled after 60 days with no repo commits**, with no email
   and no log entry. Your world just stops. Mitigate with a keepalive commit or a monthly
   calendar reminder.
2. **Schedules drift.** 10–30 minute delays are common under load. A 30-minute world
   absorbs that fine; a 5-minute world would not.
3. Private repos get 2,000 free minutes/month; 1,440 tick runs/month at ~40s each fits, but
   not with much room. Public repo = unlimited.

If either caveat bothers you, move the tick to a Fly machine running `make loop` — it's the
same ~$2 box, and then hosting is one provider instead of two.

### Simplest: ~$5/month, one provider

**Railway.** One repo, Postgres add-on, a cron service and a web service, deployed from the
same push. The $5 Hobby plan covers a workload this small. You are paying ~$5 to not think
about GitHub Actions' silent disable or Fly's machine config — for a portfolio piece that is
usually the right trade. No scale-to-zero, so the DB stays warm and the compute-hours table
above stops mattering.

### Why not Cloudflare Workers for the worker

Asked directly, so: **Workers is the wrong runtime for the tick and the right one for the
frontend.** The tick needs `psycopg`, `feedparser`, and the Anthropic SDK, plus a
long-lived Postgres connection and a transaction held across a batch collect. Workers is
JS/WASM with CPU-time limits and no native Postgres sockets; Python Workers exist but the
package ecosystem is not there. Cloudflare **Pages** for the Next.js frontend is genuinely
excellent and free — use it there.

### Also rejected

- **Vercel cron for the tick.** Hobby is limited to daily cron; sub-daily needs Pro at $20,
  which quadruples your hosting to schedule a script. Use Vercel for the frontend only.
- **Render for the worker.** The free tier spins down and has no free cron; the paid Starter
  service costs more than Fly's equivalent box.
- **Supabase over Neon.** Fine either way, but Supabase's free project pauses after a week
  of inactivity, and a demo you show occasionally is exactly the thing that trips it.
- **A managed queue.** The `batches` table is the queue. Adding SQS/Redis to a system that
  processes 8 items twice an hour is pure overhead.

Sources: [Neon pricing](https://neon.com/pricing) ·
[Railway/Fly/Render 2026 comparison](https://hostim.dev/blog/render-vs-railway-vs-fly-pricing/) ·
[GitHub Actions scheduled-workflow behaviour](https://github.com/efrecon/gh-action-keepalive)

---

## 11. Build order

| Phase | Ship | Verify |
|---|---|---|
| 0 | Schema, seed cast, offline LLM provider | `make tick` runs end to end with no API key |
| 1 | Tick worker, **no news** — pure heat + memory | 20 ticks; two characters form a beef unprompted |
| 2 | RSS ingest + safety classifier + casting | 50 headlines in, zero tragedies survive the gate |
| 3 | Next.js feed + password gate + `noindex` | Cold visitor sees a populated, legible timeline |
| 4 | Free engagement + admin dials | 300+ likes on posts; `opens_per_day` editable live |
| 5 | Human poke (P1) | In-character reply, behind a hard budget cap |

**Phase 1 is the real test, and it is deliberately the boring one.** Run the world with no
news at all. If characters don't develop relationships from heat and memory alone, adding
headlines papers over that failure instead of fixing it — you get a feed of funny one-liners
with no through-line, which is the exact failure mode this design exists to avoid.

---

## 12. Open risks

- **Voice sameness.** Every character drifts toward the same LLM register. Mitigation: the
  `samples` and `tics` fields, hand-edited hard on the 8 leads. Check this in phase 1.
- **Heat ossification.** Two characters lock into a permanent feud and crowd out the cast.
  Mitigation: `HEAT_DECAY` and a per-pair heat ceiling. Tune in phase 1, not phase 4.
- **Real-person risk.** Contained by unlisted + password gate, not eliminated. Fabricated
  first-person statements from real people about real events are misinformation-shaped and
  travel well once cropped. Keep the parody watermark on every rendered post so a leaked
  screenshot is a non-event. No political figures on any surface that becomes public.
- **Safety classifier false-negatives.** One bad headline reaching a comedian persona is the
  whole problem. Source restriction is the primary control; the classifier is defense in
  depth, not the wall.

---

## 13. What you should be able to explain

- [ ] Why the tick exists — and that it's a *clock*, not a decision-maker
- [ ] Why replies and posts must share one budget (the branching-process math)
- [ ] The split: ranking = distribution, agent = decision. Why the first isn't agency.
- [ ] Why heat is one mechanic at two scopes, and what each scope buys
- [ ] Why "scroll past" is the most important action in the decision set
- [ ] Why memory is derived from notes rather than an accumulated digest
- [ ] Why free likes/follows change the demo more than more posts would
- [ ] Why collect-then-submit removes the need for a long-running worker
- [ ] Why no agent framework — and what would have to change for that to flip
- [ ] What breaks if someone "just lets hot threads run"
