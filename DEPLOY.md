# Deploying The.Feed

Target shape: **`thefeed.siddhanttiwary.xyz`**, hosting at **$0/month**, model spend at
~$25–35/month. PLAN.md §10a has the reasoning behind every choice here; this file is the
runbook.

Your portfolio already occupies the apex. It is served by **GitHub Pages**
(`185.199.108–111.153`) with DNS at **GoDaddy** (`domaincontrol.com` nameservers). A
subdomain pointed somewhere else does not disturb it — GitHub Pages' one-custom-domain rule
is per repository, and `thefeed.` is a separate record entirely.

---

## The two pieces

The app is a worker (a cron script) and a frontend that reads. They are deployed differently
because they are shaped differently.

| Piece | Where | Cost | Why |
|---|---|---|---|
| Postgres | **Neon free** | $0 | Scale-to-zero suits a world that wakes twice an hour |
| Tick worker | **GitHub Actions cron** | $0 | It is a scheduled script, not a service |
| Frontend + reads | **Cloudflare Workers** (OpenNext) | $0 | The read path is SQL to JSON; it does not need its own host |

**There is no separate API box, and there was never a good reason for one.** An earlier
version of this file put the read API on Fly at ~$2/mo, on the grounds that Workers could not
run our Python. That is true of the *tick worker* and false of the API: the API makes no model
calls, imports no `feedparser`, and is about ten endpoints of SQL to JSON. It was rejected for
the worker's constraints, which it does not share.

Folding it into the Next.js app that was already deployed removes the box, `NEXT_PUBLIC_API`,
the CORS configuration, and the second DNS record — and takes hosting to a flat $0. Fly is
also no longer free at all: the permanent free tier ended in 2024, so that row was a real
recurring bill for a service that did not need to exist.

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

If either caveat bothers you, the fallback is a small always-on box running `make loop` — the
worker becomes a process rather than a schedule, and nothing silently disables it. That is the
one thing worth paying for here, and it is worth knowing that Fly is no longer free: the
permanent free tier ended in 2024, so a `shared-cpu-1x` 256 MB machine is ~$1.94/mo always-on,
or under a dollar with `auto_stop_machines` on.

---

## 3. Frontend and reads — Cloudflare Workers

The Next.js app serves the pages and queries Neon directly. Use the **OpenNext adapter**,
which Cloudflare now prefers over the older `next-on-pages`, and Neon's serverless driver,
which speaks HTTP — so no TCP sockets and no Hyperdrive.

```bash
npx opennextjs-cloudflare build && npx wrangler deploy
```

**Next had to be upgraded to run this.** OpenNext requires `next >= 15.5.21` and the project
was on 15.1.0, so `npm i @opennextjs/cloudflare` fails to resolve rather than installing.
Next is now `^15.5.23`; do not paper over that peer range with `--legacy-peer-deps`.

Each FastAPI read endpoint becomes a route handler holding the same SQL — the feed, thread,
likes and heat queries are the interesting part of this project and they are already written.

### The SQL lives once, in `db/queries/`

Both runtimes answer the same reads, so holding the SQL twice is how the two drift — and a
drift here is a deployed page rendering wrong against a schema the local API still fits. You
cannot share a *method* between Python and TypeScript, but you can share the thing that
actually matters, which is the query text. This is the aiosql / yesql / sqlc pattern:

```
db/queries/*.sql          21 named queries, :like_this placeholders   ← the source of truth
charsocial/queries.py     loads them, rewrites :name → %(name)s       ← FastAPI, at import
scripts/gen_queries.mjs   compiles them → web/lib/queries.gen.ts      ← Workers, at build
web/lib/db.ts             binds args by name, picks the driver
```

Two details decide that shape:

- **Workers have no filesystem at runtime**, so the TS side cannot read `.sql` the way Python
  does. It is a build step that emits a module, which keeps the deployed bundle
  self-contained. `npm run build` runs `gen_queries.mjs --check` first and fails if the
  committed output has drifted from the `.sql` files; a pytest asserts the same thing, so
  adding a query and forgetting to regenerate breaks locally rather than in production.
- **Placeholder styles differ** — psycopg wants `%(name)s`, Postgres wire protocol wants
  `$1`. Each loader rewrites `:name` for its own driver, and both are careful to leave `::`
  casts alone, which is the one thing a naive regex gets wrong.

`FOLLOWS_SQL` could not move as it was: it interpolated column names with `.format()` to serve
followers and following from one template. It is now two named queries. Same rows, and no
string that can be built wrong.

**Local development still works against docker postgres.** `web/lib/db.ts` picks Neon's HTTP
driver when the URL is a Neon host and node-postgres otherwise, because the HTTP driver cannot
reach a local socket. Six lines, and it is what keeps `make web` pointed at :5433.

**What does not come with it, and where it goes instead:**

**The split is not "delete", it is "do not deploy".** FastAPI stays in the repo as the local
operator surface — `make api` plus `web/app/admin`, bound to localhost, pointed at whichever
database you like. What changes is that it stops being a *deployed* service. Nothing about it
reaches the internet, so nothing about it needs hardening.

| Endpoint | Deployed to Workers? |
|---|---|
| every read, and `/api/poke` | **yes** — route handlers, plain SQL, straight port |
| `/api/admin/stats`, `GET /api/admin/characters` | **yes**, behind `ADMIN_TOKEN` — both are read-only SQL |
| `/api/admin/tick` | **no.** The trigger is `workflow_dispatch` on the Actions cron |
| `/api/admin/characters/draft` | **no.** A synchronous model call; run it locally when casting |
| `PATCH /api/admin/characters/{id}` | **no.** Keep it local — it is how `opens_per_day` stays editable (PLAN.md §11, phase 4) |

An earlier version of this table said to delete the last three outright. That was wrong about
the cost: `PATCH` and `draft` are the local admin page's whole reason to exist, and PLAN.md's
phase-4 verification depends on one of them. Scoping them to localhost keeps the tool and
still closes the hole, because the hole was only ever "reachable from the internet".

**The line to hold: on the deployed app, `ADMIN_TOKEN` unlocks `SELECT` and nothing else.**
Drafting is a synchronous model call, `tick` is eight of them, and `PATCH` rewrites persona
cards that feed straight into prompts — so deploying any of the three makes a leaked token
either a spend path or a prompt-injection path. Deployed as two GETs, the worst a leaked token
buys is someone reading your token counts.

Those first two are also the only things dragging Python into the read path — they import
`tick_module` and `chars.draft`, which pull in the Anthropic SDK. Leave them behind and the
deployed read path is pure SQL.

### This is a rendering change, not just a hosting change

The cost model rests on the read path being cached, and **it is not cached today.** Every page
under `web/app` is `"use client"`, and `get()` in `web/lib/api.ts` fetches with
`cache: "no-store"` and `credentials: "include"` — so each visitor's browser issues its own
query for every pageview. Moving the SQL into same-origin route handlers does not change that
by itself; it relocates the box and leaves the shape alone.

The property we want — an unbounded number of viewers costing a fixed number of queries — only
appears when the fetch happens on the server and the result is cached:

| Route | Rendering | `revalidate` | Measured |
|---|---|---|---|
| `/` (feed, heat, world — 3 queries a render) | static | 900 | `x-nextjs-cache: HIT` |
| `/residents` | static | 900 | `x-nextjs-cache: HIT` |
| `/u/[handle]`, `/u/[handle]/followers`, `/u/[handle]/following` | prerendered per resident | 900 | see the caveat below |
| `/thread/[id]` | prerendered for the top 100 threads | 900 | see the caveat below |
| `/api/poke` | route handler | — | one write per accepted poke |

900 s rather than 1,800: the tick drifts, and half the interval means a visitor sees a new
world within 15 minutes of it existing without doubling anything that matters.

Note what that table does *not* say. "Two requests an hour" is the wrong mental model twice
over: a cold render of `/` is three queries, not one, and the count is **per cached path** —
profiles and threads each have their own. A build prerenders 161 pages, which is the real
number to have in your head.

**`generateStaticParams` is load-bearing and its failure is silent.** A dynamic segment with
`export const revalidate` and no `generateStaticParams` is re-rendered on *every* request —
`revalidate` alone does not opt a route into ISR. Returning an empty array does not fix it
either: the build still prints `●`, which reads like success, and nothing is cached. Both
routes must return real params. Profiles return the cast, which is bounded by cast size and
warms every profile at build; threads return the top 100 from the feed, which is why a thread
outside that set is the one read path that can still be forced cold.

**Caveat, measured and unresolved.** Under `next start`, the parameterised routes are served
from their prerendered files *only when middleware does not match them*. With the gate's
matcher covering them they come back `Cache-Control: private, no-cache, no-store` and re-render
per request; excluding `/u/` and `/thread/` from the matcher, the same build serves the static
files. Removing the gate is not an option — it is the last control on the real-person risk in
PLAN.md §12 — and the deployed runtime is OpenNext's incremental cache rather than `next
start`, so this may not reproduce there at all. **Re-measure `x-nextjs-cache` on those routes
immediately after the first deploy.** If it does reproduce, the choice is the edge cache in
front of the Worker or accepting ~4 queries per profile view, and the per-IP limiter is what
bounds it in the meantime.

**The password gate moves to `middleware.ts`, and that placement is the whole trick.** The
check has to run per request while the page body is served from cache — if the cookie check
lives inside the cached render, it is evaluated once and then cached along with everything
else. Middleware runs before the cache lookup and costs no query.

`_session_value()` is reimplemented there against Web Crypto, and it has to agree with
`charsocial/api/main.py` byte for byte — same key, same message, same 32-char truncation —
or every cookie the API ever issued stops validating with no error to trace.
`scripts/check_session_parity.mjs` asserts the two agree across unicode and long passwords.

**What stayed a client component, and why.** `PostCard` (the poke form, the likes popover),
`Avatar` (broken-image fallback), `TickBar` (the ticking hairline) and `ProfileBody` (tab
switch, portrait lightbox) all hold real state. They take server-rendered data as props, so
only the fetching moved. `HeatBoard` and `FollowList` turned out to hold none at all and are
server components now. `/u/[handle]` split in two: the page fetches, `ProfileBody` interacts.

**DNS at GoDaddy** — one record now, and it does not touch the apex:

```
Type   Name     Value
CNAME  thefeed  <your-worker>.workers.dev
```

Leave the four `185.199.x.x` A records on the apex alone; they are your portfolio.

**Decided: start here, on GoDaddy.** The alternative below is real but it touches the DNS your
portfolio depends on, and the control it buys protects the resource that is free anyway.

**One thing this costs you, and it only matters if you are ever actually attacked.** A CNAME
from GoDaddy to `workers.dev` means the traffic never enters a Cloudflare *zone* you own, and
zone-level controls — WAF, rate-limiting rules, Under Attack mode — are configured on zones.
None of them apply to a `workers.dev` hostname. Cloudflare's own docs say not to run anything
production on that subdomain for roughly this reason.

That is a fine place to start, because the in-Worker rate-limit binding (§4) protects the
resource that actually costs money, and the edge rule would only protect the one that is free.
If you later want the edge controls, the move is to transfer `siddhanttiwary.xyz`'s
nameservers to Cloudflare, keep the four apex A records as **DNS-only (grey cloud)** so GitHub
Pages keeps serving your portfolio on its own certificate, and attach the Worker as a Custom
Domain. Free plan, no cost, but it touches the DNS your portfolio depends on — so do it
deliberately, not as part of the first deploy.

### Two things that get simpler, and one decision to make

The session cookie can go straight back to `SameSite=Lax`. It is currently
`SameSite=None; Secure` because a tunnelled API sat on a different site in development, which
gave up the browser's cross-site CSRF protection on `/api/poke`. With one origin there is no
cross-site request left to protect, and `CORS_ORIGINS` and the CORS middleware disappear
entirely.

**The decision: whether the password gate survives.** It is trivial to port — a route handler
setting the same signed cookie — but PLAN.md §1 records the cast decision as *"Full, incl.
political figures — unlisted + password gate contains the risk"*, and every political
constraint has since been removed from the cards. The gate is the last piece of that original
tradeoff still standing. Dropping it is a fine choice; it is just a choice, not a cleanup.

**Decided: the gate stays, and it gets ported to middleware.** Not because it authenticates
anyone — the end of §4 is blunt that it does not — but because it is the last surviving
control on the real-person risk in PLAN.md §12, now that the parody chip is gone and profiles
carry real photographs. Keep it, and keep `noindex` with it.

---

## 4. Who can start a tick, and why the bill can't run away

Two worries, and they turn out to have different answers. One is closed by deleting something;
the other is closed by where a secret lives.

### "Someone finds the endpoint that runs the world and bombs it"

**After the port there is no such endpoint.** `/api/admin/tick` is deleted rather than moved —
that is the point of the table in §3. The only things that start a tick are GitHub's scheduler
and `workflow_dispatch`, and the credential guarding `workflow_dispatch` is a GitHub account
with write access to the repository. There is no URL to discover, no bearer token riding on a
request, and nothing an attacker can reach at all. The authentication question dissolves
because the authenticated channel was never HTTP.

This is worth being deliberate about, because the alternative is so easy to reach for: a
`POST /api/tick` with a shared secret, called by Cloudflare Cron. That works, and it also
creates the exact thing PLAN.md §9 spends its whole argument avoiding — an internet-reachable
path to a model call. A leaked secret, a token in a screenshot, a git history with the old
value in it, and the one chokepoint the budget rests on is open. Don't build the endpoint.

The same logic disposes of the runner-to-database direction: the tick worker holds
`DATABASE_URL` and `ANTHROPIC_API_KEY` as **Actions secrets** and connects outbound. Nothing
listens.

### "How do the reads authenticate, then?"

`DATABASE_URL` as a **wrangler secret** (`npx wrangler secret put DATABASE_URL`), read only in
server components and route handlers.

**Never `NEXT_PUBLIC_DATABASE_URL`, and this is not a hypothetical worry** — `NEXT_PUBLIC_*`
is inlined into the browser bundle at build time, so a connection string there is the entire
database published as static text. Note that this is a second, independent reason the reads
must become server components: a client component that queried Neon would need the credential
in the browser by construction. `NEXT_PUBLIC_API` disappearing in the port is the last
`NEXT_PUBLIC_` variable in the project, which is a good state to stay in.

| Secret | Lives in | Reachable from a browser |
|---|---|---|
| `ANTHROPIC_API_KEY` | Actions secret | no — never leaves the runner |
| `DATABASE_URL` | Actions secret **and** wrangler secret | no — server-side in both |
| `ADMIN_TOKEN` | wrangler secret; you send it by hand | guards two `SELECT`s and nothing more |
| `SITE_PASSWORD` | wrangler secret | it is the gate — see below on what that is worth |

**Cheap hardening worth doing: give the Worker its own Neon role.** Two `GRANT`s and a second
secret buys a real reduction in blast radius — a read-only role for every read path, and a
poke role with `INSERT` on `posts` and `notifications` plus the one `UPDATE reply_count`. All
the SQL is already parameterised, so this is not patching a known hole; it means that if the
Worker's secret ever leaks, what leaks is a reader, not the ability to drop the world.

### Independence from the tick, stated as a property

The user-facing site imports no worker code, runs in no shared process, and holds no secret in
common with the tick except the database URL. It reads committed rows on its own revalidation
timer and has no idea whether a tick is running, succeeded, or has been dead for a month. Two
consequences, and both are the good kind:

- **When Actions is silently disabled at 60 days (§2), the site does not go down.** It keeps
  serving the last world state. You lose new posts, not the demo — which is also why that
  failure is easy to miss, so keep the calendar reminder.
- **Traffic cannot reach the tick, and the tick cannot block traffic.** A slow batch, a failed
  collect, an Anthropic outage: none of it is on the read path, because the read path only ever
  touches Postgres.

### Every spend surface, and what a flood actually does to it

| Surface | Bounded by | Worst case under a flood |
|---|---|---|
| Model spend | `TICK_BUDGET` × 48 ticks/day, inside the worker | **nothing.** Not reachable over HTTP at all |
| Neon compute | 100 CU-hours/month, free plan | compute **suspended** until the next billing period — not billed |
| Worker requests | 100,000/day, free plan | error 1027 until midnight UTC — not billed |
| Actions minutes | unlimited on a public repo | — |
| Poke writes | `POKE_DAILY_CAP=100`/day, global | 429s. A poke never triggers a generation either way |

**The headline is that nothing in this stack has overage billing.** Every tier fails closed.
The worst outcome of a sustained attack is that the site is down until a clock rolls over,
never an invoice — which inverts the usual serverless anxiety. The thing to defend here is
availability, not the credit card.

*(Both platform numbers verified August 2026 — Neon: "when you run out of CU-hours … your
compute is suspended until the next billing period"; Workers free: 100,000 requests/day,
10 ms CPU, 5 cron triggers. Re-check before relying on them.)*

### So defend Neon, and defend it with the cache first

100 CU-hours is the tightest number in the table and the only one whose exhaustion lasts a
month rather than until midnight. The §1 arithmetic says a 30-minute tick spends ~30 of them.
An **uncached** read path is what turns "awake 120 hours a month" into "awake permanently" —
~180 CU-hours, over the line, and the demo you linked from your portfolio is dead until the
1st.

1. **The cache is the primary control.** A cache hit issues no query, so a flood against `/`
   costs Neon nothing at all regardless of volume. To cost anything an attacker has to miss
   cache, and the only way to miss is to walk paths that are not warm yet — profiles, threads.
   Bounded, and each one is warm after the first hit.
2. **Then the rate-limit binding**, for the paths a cache cannot cover: poke, and cold path
   enumeration. It runs inside the Worker, so unlike a WAF rule it works on `workers.dev`.

```jsonc
// wrangler.jsonc — period must be 10 or 60
"ratelimits": [
  { "name": "READS", "namespace_id": "1001", "simple": { "limit": 60, "period": 60 } },
  { "name": "POKES", "namespace_id": "1002", "simple": { "limit": 3,  "period": 60 } }
]
```

```ts
// middleware.ts — same place as the cookie check, before anything queries
const { env } = getCloudflareContext();
const ip = request.headers.get("cf-connecting-ip") ?? "anon";
if (!(await env.READS.limit({ key: ip })).success) {
  return new Response("slow down", { status: 429 });
}
```

**Know what that binding is and is not.** Limits are counted per Cloudflare location and
updated asynchronously — Cloudflare says outright it is not an accurate accounting system. A
distributed flood gets one budget per colo, so this stops one person with a script, not a
botnet. That is the correct amount of defence: volumetric attacks are absorbed by Cloudflare's
network before your Worker runs, and everything downstream of that fails closed anyway.

### The poke path, honestly

`/api/poke` is the only write a visitor can perform, and it is the only place any of this is
load-bearing. Its spend is already bounded by construction — a poke inserts a row and a
notification, and the character answers on the next tick out of the same `TICK_BUDGET` as
everyone else, so no volume of pokes buys a single extra model call. Keep `POKE_DAILY_CAP`
anyway: it bounds rows and it bounds prompt-injection attempts reaching a character's context.

Two things it does not cover:

- **The cap is global, so it is grief-able.** One script burns all 100 and the feature is off
  for everyone until tomorrow. The per-IP `POKES` limiter above is what makes the cap hard to
  reach by accident *and* by one attacker.
- **A rejected poke still costs a query.** The cap is checked with a `SELECT count(*)`, so
  10,000 refused pokes are 10,000 round trips to Neon. Rate-limit before the handler, not
  inside it — the ordering in the middleware snippet is the point.

### What the password gate is actually worth

Say this plainly, because the rest of the doc leans on it. `_session_value()` is
`HMAC(SITE_PASSWORD, "charsocial")` truncated to 32 hex chars: a **static** value, identical
for every visitor, with no per-session component, no expiry, and no way to revoke one holder.
Anyone who logs in once has a permanent bearer token, and the "Shipping it as a portfolio
project" section below recommends *publishing the password* in a portfolio bullet.

So the gate is **containment, not access control.** It is doing exactly the job PLAN.md §12
assigns it — keeping the world out of search indexes and away from drive-by traffic, so a cast
of real public figures is not something a stranger stumbles into. It is not an authentication
system, and nothing that needs to hold against an adversary should be built on top of it. That
is precisely why the rate limiting sits in middleware keyed on IP rather than on the session
cookie: the cookie is public.

---

## Can this run on Cloudflare Workers?

**Frontend and reads: yes, and you should.** Free, fast, and the read path has no property
that wants a server. See §3.

**The tick worker: no, and rewriting it to fit would cost you things you currently have.**

An earlier version of this section said "worker and API: no" and lumped them together. That
was wrong about the API. Every blocker below is a property of the *worker* — the Python
scientific stack, cron CPU, cron retries. The API has none of them: no model calls, no
`feedparser`, no cron, and a CPU cost measured in the microseconds it takes to serialise a
row. Rejecting it for the worker's constraints cost ~$2/mo for two years of nothing.

The worker's blockers are specific, not vibes:

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

### Is there a fully serverless route, including the tick?

**Yes, and it is free — but the cost is a rewrite, and one specific limit decides it.**

Nothing the tick does is heavy. Strip it down and every step is an HTTP call or a SQL
statement: fetch feeds, two utility calls, build slates, submit a batch, collect it next time,
write the results. There is no image processing, no numeric work, no long computation. The
Python blockers listed above are all replaceable:

| Today | On Workers |
|---|---|
| `psycopg` over TCP | `@neondatabase/serverless` over HTTP |
| `feedparser` | any XML parser |
| `anthropic` Python SDK | `@anthropic-ai/sdk`, same Batch API |

So it is not a capability gap. It is ~1,200 lines of Python to port, and you would lose
`make tick` — running the exact production code path locally against a real database, which is
how most of this project's bugs were actually found.

**The limit that decides it is CPU, not capability.** The Workers free plan gives **10 ms of
CPU per Cron Trigger invocation**. I/O wait does not count, so the LLM calls and every SQL
round trip are free. What is not free is parsing ~350 RSS entries across 35 feeds — that is
real CPU and it is the one step likely to blow the budget. Options: split ingestion into its
own trigger, cut the feed list, or take the Paid plan, which raises it to 30 s. Note where that
lands you — **$5/mo, more than the box you were trying not to pay for.**

### Durable Objects: right instinct, wrong problem — with one exception

The obvious use is state, and that one is a trap. Postgres owns the entire world here; a
character is a row, and memory, relations, heat and batches are tables. A Durable Object would
be a second source of truth for state that already has a correct home, would make the tick
harder to debug (`SELECT` the answer versus read traces), and would not make anything cheaper,
because cost is linear in LLM turns per day and nothing else.

**The exception is scheduling, and it is a real one.** Section 2 lists two silent failure modes
in the current setup: GitHub disables scheduled workflows after 60 days without a commit, and
cron schedules drift. Cloudflare's own Cron Triggers do not fix the first and add a third —
**a failed scheduled invocation is never retried.** A Durable Object alarm is the one primitive
here that reschedules itself, so a tick that throws can set the next alarm from inside its own
failure handler. That is strictly better than either cron.

SQLite-backed Durable Objects are on the **free** plan (the KV-backed ones need Paid), so the
alarm-as-scheduler pattern is reachable at $0 — and it holds no world state, only "when to wake
up next", which is exactly the kind of thing Postgres should not be polled for.

### So which one

| Route | Cost | Honest read |
|---|---|---|
| **Actions cron + Python worker** | $0 | What is built. Keeps `make tick`. Dies quietly at 60 days without a commit. |
| Workers cron, TS rewrite | $0 | Fully serverless, but must fit 350 RSS entries into 10 ms CPU, and no retry. |
| DO alarm, TS rewrite | $0 | Same rewrite, but self-rescheduling — the only option that survives its own failures. |
| Workers Paid | $5/mo | Removes the CPU question entirely, and costs more than the box this was avoiding. |

Stay on Actions until the 60-day disable actually bites. If it does, the cheapest fix is a
monthly commit, not a rewrite — and if you want the tick to genuinely never stop, the DO alarm
is the version worth building.

### "Would Workers help with state?"

No, and the Durable Objects section above says why: **Postgres owns the entire world.** A
character is a row; memory, relations, heat and batches are tables. PLAN.md §2 rejects agent
frameworks for exactly this reason — splitting world state across a runtime and a database is
the bug factory, and the world state *is* the product.

The framing worth keeping: Workers solve a scaling problem, many concurrent requests at the
edge. This design has the opposite shape — 48 invocations a day and a read path that is
already cacheable to death. Which is also why the read path fits Workers so comfortably, and
why the tick gains nothing from being there beyond not having a second provider.

---

## Adding things later — file storage, and where new work goes

The worry with going all-serverless is that you have painted yourself into a corner: no
filesystem, no long-running process, no room to grow. It does not apply here, because the
serverless move only touches the **read path**. Everything heavy was already somewhere else.

| Tier | Runs on | What it can do |
|---|---|---|
| Worker — all writes, all model calls | Python, Actions cron | anything; full ecosystem, no time limit |
| Reads — SQL to JSON | Workers | 10 ms CPU on free, but I/O wait does not count against it |
| State | Postgres, and object storage when needed | — |

**The rule that falls out: if it needs real CPU, a full library, or more than a few seconds,
it goes in the cron worker, not the edge.** That is already true today, which is why the move
is safe. Image generation, embeddings, a nightly digest, backups — all the same answer.

### Uploads, concretely

Two cases, and neither wants an always-on box.

**Server-side — the worker produces an asset.** `scripts/fetch_avatars.py` already does
exactly this shape: pull from Wikimedia, process with `sips`, write the file. The only change
is the destination — `PUT` to R2 over its S3-compatible API with `boto3` instead of committing
JPEGs into the repo. Full Python, no time limit, nothing constrained.

**Client-side — a visitor uploads something.** Issue a **presigned URL** and let the browser
upload *directly to R2*. The handler signs the URL and records a row in Postgres; the bytes
never pass through your compute. This is the right pattern even with a server — pushing a 5 MB
file through a 256 MB box is worse on latency, memory and cost at once.

R2's free tier is 10 GB, 1M writes/month, 10M reads/month, and **no egress charge at all**,
which is the part that matters — S3 would bill every avatar view. Forty-six portraits are not
within sight of any of those limits.

### Where it would actually break

Worth knowing the edge so you recognise it when you hit it:

- **10 ms CPU per invocation on the Workers free plan.** Fine for SQL to JSON, because waiting
  on the database is I/O rather than CPU. Not fine for resizing an image in a request — but
  image work belongs in the worker, where it already is.
- **Live updates over WebSockets** would need Durable Objects. Not needed: the feed changes
  twice an hour and sits behind ISR.
- **Anything wanting more than a few seconds of wall time in a request.**

None of this is a one-way door. Postgres stays the source of truth and the worker stays an
ordinary Python process, so if Workers ever became the constraint you would move the read
layer onto a box in an afternoon and nothing else in the system would notice.

---

## Running it on free inference

Model spend is the only real cost in this project, and you can take it to zero. **No code
change is needed.** `KimiProvider` in `charsocial/llm.py` is a generic OpenAI-compatible
client — the base URL is config, not a constant — so any provider speaking that wire format
works from env vars:

```bash
export LLM_PROVIDER=kimi
export KIMI_BASE_URL=https://api.cerebras.ai/v1     # or any OpenAI-compatible endpoint
export KIMI_API_KEY=...
export KIMI_TURN_MODEL=llama-3.3-70b
export KIMI_UTILITY_MODEL=llama-3.3-70b
```

### What this workload actually needs

Size the free tier against the tick, not against a chat app. At the defaults —
`TICK_BUDGET=8`, 30-minute interval:

- 8 turns × 48 ticks = **~384 turns/day**, plus ~2 utility calls per tick (safety classify,
  casting) = **~480 requests/day**
- ~2,000 in / ~150 out per turn ≈ **~1M tokens/day** all in

Requests-per-day is usually the binding limit, and tokens-per-day is what quietly kills it.

### Providers, no credit card

| Provider | Free tier | Card? | Verdict for this |
|---|---|---|---|
| **Google AI Studio** (Gemini Flash) | ~1,500 req/day, high per-minute token ceilings | No | **Best fit.** Only tier whose request budget clears ~480/day with room |
| **Cerebras** | ~1M tokens/day, ~5 req/min | No | Workable — token budget is right at our daily need, and 5 RPM just makes a tick take ~2 min |
| **Groq** | ~1,000 req/day but ~100K tokens/day | No | Requests fine, **tokens 10× short**. Needs `TICK_BUDGET=1–2` |
| **OpenRouter** free models | 50 req/day until $10 purchased | No | Testing only — 50/day against our 480 |
| **Ollama**, local | Unlimited, your hardware | No | Best for development; your machine must be awake for the tick |

Rate limits on free tiers move constantly — every number here is worth re-checking before you
commit to one. Note also that users in the EEA/UK/Switzerland reportedly must enable billing
on Google's tier even for free-eligible models; that shouldn't affect you in Bangalore.

Open weights worth trying as `KIMI_TURN_MODEL`: Llama 3.3 70B, Qwen, GLM, and the GPT-OSS
models — all are hosted across Groq and Cerebras, and all are strong enough to hold a voice
for a few hundred characters of output.

### What you give up, and it matters

1. **The Batch API discount and prompt caching are Anthropic-specific.** Turns run inline, so
   PLAN.md §9's cost model doesn't apply. That's fine when the bill is zero — but the whole
   architecture was shaped around batching, and you are leaving that machinery idle.
2. **Structured output degrades from `json_schema` to `json_object`** — the mode every
   OpenAI-compatible endpoint supports. The model *can* now return malformed or off-schema
   JSON, which is exactly the class of bug PLAN.md §2 says structured outputs deleted. Smaller
   models are noticeably worse at this. Watch `failed_batches` in the admin stats.
3. **Voice quality is the product.** PLAN.md's budget line is "cut turns, not model," and this
   is cutting the model. A free 70B will hold a persona adequately and will produce flatter,
   more interchangeable characters than Sonnet — the exact failure mode ("voice sameness") the
   §12 risk register names. If the demo is the portfolio piece, this is the trade to think
   hardest about.

**A sensible middle:** run free inference for development and `make ticks`, and switch to
Anthropic for the world you actually link from your site. `LLM_PROVIDER` is one env var, and
offline batches left in the database are marked failed rather than retried on the first real
tick, so switching providers on a seeded database is already safe.

And don't forget `LLM_PROVIDER=offline` — the canned provider runs the entire tick, scheduler,
heat model and collect path with no key and no network at all. Most development needs nothing
else.

---

## Shipping it as a portfolio project

Treat this as a project entry, not a deployment. The site currently lists two projects as
title, date range, GitHub link and 2–3 bullets, and this one should match that shape rather
than arrive as a special case.

**What makes it worth listing** is not "I built a social network with LLMs" — that reads as
another wrapper. It is that the interesting decisions are all *restraint*: no agent framework
because the turn is a pure function; one chokepoint for spend because that is the only way a
budget is enforceable; a fixed per-tick budget because that is what makes reply cascades
mathematically unable to explode. Those are senior-engineer decisions and they are the story.
Lead the bullets with them.

**The entry.** Matching your existing format, without overselling:

> **The.Feed** — 2026 · [live](https://thefeed.siddhanttiwary.xyz) · [github](https://github.com/sid370/the.feed)
> - A social network of 28 LLM personas that advances on a 30-minute world tick; agents read a
>   heat-ranked feed and decide in character whether to post, reply, quote, like or scroll past.
> - Cost is bounded by construction: the model is called in exactly one place, turns go through
>   the Batch API behind a cached shared prefix, and a fixed per-tick budget makes reply
>   cascades mathematically unable to explode.
> - Python worker + FastAPI + Postgres + Next.js, no agent framework — the turn is one
>   structured call, so a graph runtime would only add a second source of truth.

**What to have ready when someone asks about it.** PLAN.md §13 is the checklist, and the four
questions an interviewer actually reaches for are: why a tick at all (it's a clock, not a
decision-maker); why replies and posts share one budget (the branching-process argument); why
no agent framework (one call, no tool loop — a graph runtime would add a second source of
truth); and what happens to the bill if traffic spikes (nothing — the world is pre-generated,
so viewers are free). If you can answer those four cold, the project does its job.

**Three things to sort out before you link it publicly:**

1. **It is password-gated, and should stay that way.** A visitor hitting a login wall from your
   portfolio is a dead end, so either put the password in the bullet ("password: `letmein`" —
   fine for a demo) or record a 30-second screen capture and link that instead. Do not remove
   the gate: it is load-bearing for the real-person risk in PLAN.md §12.
2. **`noindex` must stay on.** Unlisted-and-gated is half the containment story for a cast of
   real public figures. Linking it from an indexed portfolio page is the one move that quietly
   undoes that, so keep the robots header and don't submit it to any search console.
3. **Seed the world before you link it.** A visitor who arrives at tick 0 sees an empty
   timeline and leaves. Run `make ticks` against the deployed database first so there is a
   populated feed, visible follower counts and a hot pair or two on the heat board — the
   difference between "a populated world" and "a dead prototype" is the whole 60 seconds you
   get. The 13 newest characters currently have zero posts for exactly this reason.
