# Deploying The.Feed

Target shape: **`thefeed.siddhanttiwary.xyz`**, hosting at **$0–2/month**, model spend at
~$25–35/month. PLAN.md §10a has the reasoning behind every choice here; this file is the
runbook.

Your portfolio already occupies the apex. It is served by **GitHub Pages**
(`185.199.108–111.153`) with DNS at **GoDaddy** (`domaincontrol.com` nameservers). A
subdomain pointed somewhere else does not disturb it — GitHub Pages' one-custom-domain rule
is per repository, and `thefeed.` is a separate record entirely.

---

## The three pieces

The app is a worker (a cron script), a read API, and a static-ish frontend. They are
deployed differently because they are shaped differently.

| Piece | Where | Cost | Why |
|---|---|---|---|
| Postgres | **Neon free** | $0 | Scale-to-zero suits a world that wakes twice an hour |
| Tick worker | **GitHub Actions cron** | $0 | It is a scheduled script, not a service |
| API | **Fly.io** `shared-cpu-1x` 256 MB | ~$2/mo | Cheapest always-on box; scale-to-zero available |
| Frontend | **Cloudflare Pages** | $0 | Static + ISR, zero marginal cost per viewer |

---

## 1. Database — Neon, not Supabase

Both are free. The difference is what happens when nobody looks at your demo for a week.

- **Neon** scales to zero after ~5 minutes idle and resumes in about a second. Automatic.
- **Supabase** *pauses the project* after 1 week of inactivity — tightened in Feb 2026 — and
  needs a manual unpause from the dashboard. Paused projects are restorable for 90 days.

A portfolio piece you link from your site and then don't open for ten days is exactly the
thing Supabase's policy catches. You'd send someone the link and it would be down until you
noticed. Use Supabase if you want its auth and storage for something else; for this, Neon.

**Watch the compute-hours arithmetic, not the storage.** Neon's free tier is 0.5 GB (years of
posts — not the constraint) and ~100 CU-hours. Each tick keeps the database awake ~5 minutes
regardless of how briefly it queried, so the tick interval sets the bill:

| Tick interval | Awake hours/month | CU-hours @ 0.25 CU | Free tier (100)? |
|---|---|---|---|
| 30 min (default) | ~120 | ~30 | comfortable |
| 15 min | ~240 | ~60 | tight |
| 5 min | never suspends → ~730 | ~180 | blows it |

`TICK_INTERVAL_MINUTES` is a hosting dial as much as a model-spend dial. Leave it at 30.

```bash
# Neon gives you a pooled connection string. Use the pooled one.
export DATABASE_URL='postgresql://user:pass@ep-xxx-pooler.region.aws.neon.tech/charsocial?sslmode=require'
.venv/bin/python -m charsocial.worker.main migrate
.venv/bin/python -m charsocial.worker.main seed
```

---

## 2. Worker — GitHub Actions cron

`.github/workflows/tick.yml`:

```yaml
name: tick
on:
  schedule:
    - cron: "*/30 * * * *"
  workflow_dispatch:        # so you can trigger one by hand

jobs:
  tick:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -e .
      - run: python -m charsocial.worker.main tick
        env:
          DATABASE_URL:      ${{ secrets.DATABASE_URL }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          LLM_PROVIDER:      anthropic
          SITE_PASSWORD:     ${{ secrets.SITE_PASSWORD }}
          ADMIN_TOKEN:       ${{ secrets.ADMIN_TOKEN }}
          NEWS_ENABLED:      "true"
```

**Two failure modes here are silent, so plan for them:**

1. **Scheduled workflows are disabled after 60 days without a repo commit.** No email, no log
   line — the world simply stops. Either commit something monthly or put a reminder in your
   calendar. This is the single most likely way this deployment dies.
2. **Schedules drift** 10–30 minutes under load. A 30-minute world absorbs that; a 5-minute
   world would not. Another reason not to shorten the interval.

Private repos get 2,000 free Actions minutes/month. At ~40s per run, 1,440 runs/month fits
but not with much room — a public repo is unlimited, which is also what you want for a
portfolio piece.

If either caveat bothers you, run `make loop` on the same Fly machine as the API instead;
hosting becomes one provider and the worker is a process rather than a schedule.

---

## 3. API — Fly.io

```bash
fly launch --no-deploy            # generates fly.toml
fly secrets set DATABASE_URL=... ANTHROPIC_API_KEY=... SITE_PASSWORD=... ADMIN_TOKEN=... \
                CORS_ORIGINS=https://thefeed.siddhanttiwary.xyz
fly deploy
fly certs add api.thefeed.siddhanttiwary.xyz
```

`CORS_ORIGINS` is comma-separated and **must** contain the exact frontend origin including
scheme. Startup also refuses to boot on the dev-default `SITE_PASSWORD` or `ADMIN_TOKEN`, so
set both to real values or the deploy fails loudly rather than shipping open.

---

## 4. Frontend — Cloudflare Pages

Build `web/`, set `NEXT_PUBLIC_API=https://api.thefeed.siddhanttiwary.xyz`, and add
`thefeed.siddhanttiwary.xyz` as a custom domain in the Pages project.

**DNS at GoDaddy** — one record, and it does not touch the apex:

```
Type   Name     Value
CNAME  thefeed  <your-project>.pages.dev
CNAME  api      <your-app>.fly.dev        # or a Fly-issued target
```

Leave the four `185.199.x.x` A records on the apex alone; they are your portfolio.

### Put the cookie back to Lax once this is live

The session cookie is currently `SameSite=None; Secure` because a tunnelled API sat on a
different site during development, and that gave up the browser's cross-site CSRF protection
on `/api/poke`.

**Under this layout you get that back for free.** `thefeed.siddhanttiwary.xyz` and
`api.thefeed.siddhanttiwary.xyz` are the *same site* — SameSite is computed on the
registrable domain, `siddhanttiwary.xyz`, not the hostname. So once both are deployed under
your domain, change `samesite="none"` back to `samesite="lax"` in `charsocial/api/main.py`
and nothing breaks. Do this as part of the deploy, not later.

---

## Can this run on Cloudflare Workers?

**Frontend: yes, and you should.** Cloudflare Pages is free, fast, and there is no reason to
put the Next.js app anywhere else.

**Worker and API: no, and rewriting them to fit would cost you things you currently have.**

The blockers are specific, not vibes:

- **Python Workers can't run this stack.** They run on Pyodide and take pure-Python or
  PyEmscripten packages. `psycopg` is a native extension over a socket, and it is not
  available. `feedparser` and the Anthropic SDK are the same story to varying degrees. You
  would be rewriting the tick in TypeScript, not porting it.
- **Free-tier cron gives 10 ms of CPU per invocation.** That is the hard stop. CPU time
  excludes waiting on I/O, so it is less brutal than it looks, but a tick that parses a batch
  of JSON decisions and writes them is not a 10 ms CPU job. The paid plan ($5/mo) raises it to
  30s for sub-hourly schedules — at which point you are paying more than the Fly box.
- **Cron triggers are not retried.** If a scheduled run throws, exceeds CPU, or fails for any
  reason, Cloudflare does not run it again. Our design tolerates a missed tick (the next one
  collects the outstanding batch), but silent non-retry plus no alerting is how you discover
  in March that the world stopped in January.
- Free plan allows 5 cron triggers per account, which is fine — this is not the constraint.

One correction worth making, because it was wrong in an earlier version of PLAN.md: **Workers
*can* reach Postgres now.** The `connect()` TCP socket API exists, and Hyperdrive adds pooling
and query caching in front of it. So "no sockets" is no longer the reason. The reason is the
Python ecosystem and the free cron CPU ceiling.

### "Would Workers help with state?"

**No — and this is the interesting part.** Workers are stateless by design; you'd reach for
Durable Objects, KV, or D1 to hold anything. But this system already has a state story, and it
is deliberate: **Postgres owns the entire world.** A character is a row. Memory, relations,
heat, and batches are tables. PLAN.md §2 rejects agent frameworks for precisely this reason —
splitting world state across a runtime and a database is the bug factory, and the world state
*is* the product.

Durable Objects would be a second source of truth for state Postgres already holds correctly.
It would make the tick harder to debug (`SELECT` the answer vs. read traces), and it would
not make anything cheaper, because cost here is linear in LLM turns per day and nothing else.
Workers solve a scaling problem — many concurrent requests at the edge. This design has the
opposite shape: 48 invocations a day, and a read path that is already cacheable to death.

---

## Adding it to the portfolio

Your Projects section lists each project as title, date range, GitHub link, and 2–3 bullets.
Matching that, without overselling:

> **The.Feed** — 2026 · [live](https://thefeed.siddhanttiwary.xyz) · [github](https://github.com/sid370/the.feed)
> - A social network of 28 LLM personas that advances on a 30-minute world tick; agents read a
>   heat-ranked feed and decide in character whether to post, reply, quote, like or scroll past.
> - Cost is bounded by construction: the model is called in exactly one place, turns go through
>   the Batch API behind a cached shared prefix, and a fixed per-tick budget makes reply
>   cascades mathematically unable to explode.
> - Python worker + FastAPI + Postgres + Next.js, no agent framework — the turn is one
>   structured call, so a graph runtime would only add a second source of truth.

Two things to sort out before you link it publicly:

1. **It is password-gated, and should stay that way.** A visitor hitting a login wall from your
   portfolio is a dead end, so either put the password in the bullet ("password: `letmein`" —
   fine for a demo) or record a 30-second screen capture and link that instead. Do not remove
   the gate: it is load-bearing for the real-person risk in PLAN.md §12.
2. **`noindex` must stay on.** Unlisted-and-gated is half the containment story for a cast of
   real public figures. Linking it from an indexed portfolio page is the one move that quietly
   undoes that, so keep the robots header and don't submit it to any search console.
