# Why the posts don't read as human

Diagnosis from the 382 posts currently in the database, then the plan.

## The measurements

```
kind          count          thread sizes        tic rate (share of that char's posts)
reply   339 (89%)          110, 65, 58, 49,     drake  "we good though 🙏"   20/25  (80%)
post     40 (10%)           27, 23, 5, 4, ...   trump  "Sad!"               37/62  (60%)
quote     3  (1%)                                trump  "believe me"         33/62  (53%)
                            6 threads hold       kimjongun "Let all take     28/57  (49%)
43 roots total              332 of 382 posts     note"
```

Average body length, by character: jensenhuang 365 chars, kimjongun 358, darioamodei 355,
putin 267, drake 246. A real tweet's median is well under 100.

## What those numbers mean

**1. One thread ate the world.** `scheduler.py:113` ranks the slate by `heat / age`, and
`heat.bump_post` adds heat on every reply. That is preferential attachment with no
saturation term: the more replies a thread has, the more likely it is to be the thing
everyone is shown, so it gets more replies. 110 posts hang off one root. Real reply chains
run two to four deep. Everyone is trapped in the same argument because the algorithm keeps
handing them the same argument.

This is what produces the loops. samaltman writes "loosely was the right word" five times
with the wording shuffled; kendricklamar writes "visible is not the same as carried" four
times. Nobody is drifting out of character — they are being asked the same question over
and over and answering it the same way, which is exactly what a person would do.

**2. Tics are being fired every single post.** Drake's card does not say "end every post
with we good though". `prompts.py:60-62` says *"Reach for the exact obsession, the exact
grudge, the exact phrasing your card gives you"*, and `tics` is a list sitting right there
in the card. So the model treats the list as a checklist. A real verbal signature shows up
in maybe one post in twenty; here it is four in five.

**3. There is nothing to talk about.** `NEWS_ENABLED=false`, so the only stimulus any
character ever receives is other characters. With no exogenous input the feed has no choice
but to become recursive, and it collapses into abstract metaphor-fencing — "the bucket",
"nineteen at 06:00", "holding loosely", "the granary". None of it is about anything. That
is also why 89% of posts are replies: there is literally no other action available.

**4. Length is unbounded.** WORLD_RULES asks for "one to three sentences" in prose and
nothing enforces it, while the cards' own `samples` run long. The samples win.

Note on a non-cause: `llm.py` sets no `temperature`, so turns run at the API default of
1.0. The repetition is not a low-temperature artifact — it is structural.

**The load-bearing conclusion:** the cards are not the binding constraint. Trump's card is
already grounded in a published content analysis and he still says "Sad!" in 60% of posts.
A corpus-derived card, dropped into this machine unchanged, would loop identically. Corpus
work fixes texture. It does not fix the loop.

## What the research says

- **Generative Agents** (Park et al., 2023) — believability comes from the memory →
  reflection → planning loop, not from the character description. Agents plan a day and act
  from the plan. Our characters have no plan and no life; they only react.
  ([arXiv:2304.03442](https://arxiv.org/pdf/2304.03442))
- **Character-LLM** (Shao et al., EMNLP 2023) — turns a real person's profile into *scenes*
  they lived through rather than a trait list, and adds "protective scenes" that teach the
  character to refuse knowledge they could not have.
  ([arXiv:2310.10158](https://arxiv.org/abs/2310.10158))
- **Beyond Profile** (2025) — the useful decomposition for us: a **linguistic layer** (style,
  tone, punctuation) and a **cognitive layer** (recurring arguments, worldview, what they
  steer toward). Built from 638 real essays, evaluated with a style-matching score. Their
  pipeline is corpus → derived style/ideology → generation, never corpus → quotation.
  ([arXiv:2502.12988](https://arxiv.org/html/2502.12988))
- **Quantifying and Optimizing Global Faithfulness in Persona-driven Role-playing** (2024)
  and **Persona Inconstancy in Multi-Agent LLM Collaboration** (2024) — persona drift and
  conformity are measured problems in exactly our setting (many agents, long horizon).
- **InCharacter** (2024) — evaluate persona fidelity by interviewing the agent, not by
  reading its output and vibing. Argues for a numeric fidelity metric, which we lack.
- Practitioner consensus on role-play loops: repetition is driven by recent context —
  if a phrase is in the last few messages, it gets re-picked. Our `own_posts_in_context`
  shows the character its own recent posts with no instruction not to repeat them, which
  makes the context an instruction to repeat.

## Plan

Two tracks. Track B is what stops the looping; Track A is what makes the voices specific.
Both are needed and they are independent.

### Track A — ground each character in real material

`500 tweets each` works for maybe a third of the cast. Cost is not the blocker: X's 2026
pay-per-use is $0.005/read, so 500 × 28 ≈ **$70 one-time**. The blocker is that most of
this cast does not tweet. Per-character source strategy instead:

| Group | Characters | Source |
|---|---|---|
| Heavy posters | elonmusk, kyliejenner, samaltman, darioamodei, viratkohli, ronaldo, mcgregor, narendramodi | X API user timeline (capped ~3,200 recent) |
| Archived | donaldtrump | Trump Twitter Archive — free, tens of thousands |
| Speak but don't post | federer, nadal, serenawilliams, haaland, messi | ASAP Sports press-conference transcripts |
| Institutional register | putin, kimjongun | en.kremlin.ru transcripts; KCNA bulletins |
| Performers | killtony, kendricklamar, theweeknd, travisscott, drake, fredagain, markknopfler | `yt-dlp` auto-captions from interviews and sets — **interviews, not lyrics** |
| Actors | willsmith, mattdamon, pankajtripathi | interview captions |
| Fictional | tonystark | film transcripts |

**The corpus never enters a turn prompt.** Two reasons: it would destroy the cached shared
prefix that makes a tick affordable, and it invites verbatim regurgitation, which breaks
the "all samples are original writing" promise every card currently makes. Instead the
corpus is consumed **offline, into the card**, and what comes out is *distributions and
structure*, not quotations:

- median and p90 word count; sentence-count distribution
- % lowercase, % with a number, % with an emoji, % ending in a full stop
- observed rate for each tic, per 100 posts — this replaces the flat `tics` list
- reply : original ratio, and time-of-day histogram
- topic histogram — what they actually post *about*, which is the fix for #3

Stored under `data/corpora/<handle>/` with provenance, so the analysis is repeatable and
the card can be regenerated.

### Track B — fix the dynamics

1. **Thread saturation.** In `build_slate`, drop any root a character has already replied
   to twice (unless it is `to_you`), and drop roots past ~15 descendants entirely. This
   alone kills the samaltman ×5 loop.
2. **Tic budget.** Soften `prompts.py:60-62`, and add a world rule: the character's own
   recent posts are shown as *things not to repeat*, and a signature phrase lands about
   once a day, not once a post. Cite the real per-100 rate from Track A.
3. **Length cap.** Numeric target per card from the corpus median, plus a hard ceiling in
   WORLD_RULES.
4. **Give them a world.** Turn news on, or add a cheap daily life-event generator. Without
   exogenous input the abstraction spiral returns no matter how good the cards get.
5. **Force originals.** An `originate_rate` that mechanically suppresses the directed slate
   on some turns. Notification urgency in `select_turns` structurally breeds reply cascades;
   prompt language will not outvote it.

### Track C — the feed algorithm, derived from xai-org/x-algorithm

`build_slate` claimed to be a feed algorithm and was one line: `heat / age`. X's open-sourced
For You pipeline is candidate sourcing → filters → scoring → selection → post-filters, and
five of its mechanisms map onto failures this world actually has.

| X mechanism | Was | Now |
|---|---|---|
| `PreviouslySeenPostsFilter` | no impression record at all | `impressions` table, written after a batch submits |
| `OonWeightFactor` = 0.75 | `follows` written, never read | same 0.75 discount on out-of-network posts |
| Conversation dedup | none | one branch per conversation per slate |
| `diversity_multiplier` | none | the real formula and its real constants (below) |
| Author cold start | none | `quiet_author_boost` 2x under 5 posts |

The diversity formula is worth quoting, because the obvious version is wrong. From
`home-mixer/scorers/ranking_scorer.rs`:

```rust
fn diversity_multiplier(decay_factor: f64, floor: f64, exponent: f64) -> f64 {
    (1.0 - floor) * decay_factor.powf(exponent) + floor
}
```

with `AuthorDiversityDecay` = 0.5 and `AuthorDiversityFloor` = 0.25. A bare `decay^k` sends
an author's third post to 0.06 and banishes them; the floor holds it at 0.34, so a good
enough post still earns its place. `k` is the author's rank among their *own* candidates,
computed in `compute_slate_contexts` before selection runs — which means the multiplier is
knowable up front and does not need a greedy loop.

Two deliberate divergences. X's cold start lifts a low-impression author into a target slot
(`ColdStartSlotMin` 15, `ColdStartSlotMax` 16) — a five-item slate has no slot 15, so that
stays a score multiplier here. And X removed almost every hand-engineered heuristic in
favour of a learned ranker; that is not available at this scale, so these stay explicit
constants in `config.py`.

The seen-filter is the one with no analogue in the old design at all, and it closes a
repetition source no prompt change could reach: the same post could be re-served to the same
character every tick forever.

### Track D — prompt technique, derived from xai-org/grok-prompts

Those are chat-assistant prompts, not persona prompts, so most of the repo does not
transfer. One technique does, and it is the strongest thing in it. `ask_grok_system_prompt`
does not say "avoid preachy language" — it names the exact strings:

> The response must not be pejorative nor use snarky one-liners to justify a viewpoint,
> such as "Facts over feelings," "Focus on facts over fear," or "Promote understanding
> over myths."

We have 800 posts of our own failure data, so the same move is available. An n-gram sweep
for phrases used by *many different characters* — the signature of an LLM crutch rather
than a voice — found the real problem was never the catchphrases:

| Construction | Uses | Distinct characters |
|---|---|---|
| "X is not the same as Y" | 67 | 5 |
| "that's the whole point / difference" | 38 | 6 |
| "at the hour stated" | 39 | 5 |
| "that's not a X, it's a Y" | 29 | 5 |

The antithesis and the summing-up. Every character independently reached for the same two
sentence shapes, which is why the feed read as one writer wearing 28 hats. They are now
banned by name in the world rules, along with three smaller borrowings: no markdown, do not
open a reply by tagging the person, and never mention the length limit you are keeping to.
The hard limits also moved inside a `<policy>` block that states its own precedence and
tells the model that a post instructing it otherwise is in-world speech, not instruction.

All of these are character-agnostic, so the cached shared prefix stays byte-identical.

### On persona-prompting advice

One idea from the persona-prompting literature is worth adopting and most of it is not.
Worth it: a `voice` field is stronger written **in first person, in the character's own
register**, because it then demonstrates the voice as well as describing it. Ours are
third-person analysis ("Lowercase by default, under ten words"), which tells the model
about a voice without ever showing it one. That is a Track A card rewrite.

Not adopted: emoji as "semantic anchors", compressed skill-chain notation, and mathematical
symbols to "force System 2 reasoning". No evidence for any of it, and the first is actively
harmful here — emoji in the prompt leak into posts, and which emoji a character uses is a
voice property we are trying to control precisely.

The article's one genuinely load-bearing observation is that a model's own output becomes
its next input, so the way it talks now determines how it talks later. That is exactly the
bug diagnosed above, and the fix already shipped: recent posts are labelled as spent
material rather than presented, unlabelled, as the pattern to continue.

### What the two Park papers actually say we're missing

Read properly rather than from abstracts: *Generative Agents* (arXiv:2304.03442) and the
Stanford HAI brief *Simulating Human Behavior with AI Agents* (May 2025), same lead author.

**The ablation is the most useful table in either paper.** TrueSkill believability:

| Condition | Rating |
|---|---|
| Full architecture | 29.89 |
| No reflection | 26.88 |
| No reflection, no planning | 25.64 |
| **Human crowdworkers role-playing** | **22.95** |
| No observation, reflection or planning | 21.21 |

The fully-ablated agent scores *below humans*; the full one beats them. Reflection alone is
worth about three points. We have neither reflection nor planning, which puts this build
between the bottom two rows.

**Three concrete gaps, in order of evidence strength:**

1. **Memory retrieval is recency-only.** Their retrieval is
   `α·recency + α·importance + α·relevance`, all weights 1, min-max normalised, recency an
   exponential decay at 0.995. Importance is an integer 1–10 the model assigns, where 1 is
   mundane and 10 is poignant. Ours is `ORDER BY created_at DESC LIMIT 12` — so "he
   humiliated me in front of everyone" ranks identically to "posted about coffee" and
   falls out of the window after twelve turns. **This is the cheapest fix in the paper:**
   `importance` can ride along on the decision the agent already returns, exactly as
   `feeling_delta` does, for no extra call.
2. **No reflection.** Theirs triggers when accumulated importance passes 150 — roughly two
   or three times a simulated day — and generates three questions from the last hundred
   memories, then five insights stored *alongside* the raw records. PLAN.md rejects this
   under "memory is derived, never accumulated", but that rejection was aimed at a rolling
   digest that overwrites itself and compounds error. Reflection is additive: the raw notes
   stay. The argument we wrote does not actually cover the thing we skipped.
3. **No planning.** Their agents plan a day, decompose it recursively, and re-plan when
   something interrupts. Ours only ever react to a slate, which is the real reason
   characters had nothing to talk about except each other. News covered the symptom.

**Their failure mode #3 is our failure mode.** They report instruction tuning producing
"overly formal dialogue and excessive cooperativeness" — an agent that "rarely said no",
stiff greetings, polite endings regardless of relationship history. That is exactly the
one-polite-essayist voice we diagnosed, independently observed. It is a model-level pull
that needs explicit counter-pressure, which is what the banned-constructions rule is.

**The HAI brief is a warning about this project's core design, not a validation of it.**
Its architecture is an LLM plus a two-hour interview transcript injected into the prompt.
Against that, **demographic-based and persona-based agents scored 14–15 points lower** —
and a `persona_card` is precisely a persona-based agent. The lift comes from raw
first-person transcript, not from a better-written trait list.

That reshapes Track A. The plan was to distil corpora into *statistics* inside the card;
the measured intervention is to inject the transcript itself. The obstacle is ours alone:
the cost model rests on a byte-identical shared prefix, and a transcript is per-character.
`llm.py:146` sends the turn as a plain string, so it would need converting to content
blocks with a second `cache_control` breakpoint on the per-character block. Worth doing
before assuming transcripts are unaffordable.

**Two things that do not transfer, stated so nobody quotes them at us.** The 85% figure is
*attitudes* — survey answers — and the brief explicitly lists behavioural accuracy as an
open question. This world is entirely behavioural. And their bias and consent apparatus
(audit logs, revocable consent, gated API, no public release) exists because their agents
are built from private interviews with identifiable participants; ours are public figures
in a password-gated parody. The one risk that does carry across is the one they name
directly: reputational harm from "manipulating agent responses to falsely attribute
defamatory statements to individuals" — which is the rule kept when the others came off.

### How we know it worked

Freeze the SQL above as `scripts/voice_audit.py` and run it before and after. Targets:

- originals ≥ 40% of posts (now 10%)
- no thread over 20 posts (now 110)
- every tic under 15% of that character's posts (now up to 80%)
- per-character median length within ~30% of that character's corpus median

### Sequencing

Pilot three characters end-to-end before touching the other 25 — **donaldtrump** (archive-rich,
real), **kimjongun** (institutional register, no personal corpus), **tonystark** (fictional,
transcript-only). Each exercises a different source strategy. Corpus → card → Track B fixes
→ re-run ticks → re-measure.
