# Public understanding check

The frozen comprehension checklist for `scoutlens-9a3.7`. It asks whether the
public site, on its own, communicates what ScoutLens actually showed — and,
just as importantly, what it did not.

This is **portfolio communication QA, not scientific validation**. It does not
test whether the science is right. It tests whether a reader who has never seen
this repository arrives at the same understanding the artifacts support.

## 1. Why the answers live here and not in the reviewer's head

Every canonical answer in §3 is derived from a versioned artifact field or a
rendered route, and cites where. That is deliberate. A checklist whose answer
key lives in the grader's judgement measures the grader. A reviewer's answer is
scored against the artifact, so a disagreement is resolvable by opening the
file — and if the artifact and the site ever disagree, §3 is what makes that
visible instead of absorbing it.

**The answer key is not shown to reviewers.** It exists so that two different
graders reach the same verdict on the same answer.

## 2. Protocol

### 2.1 What the reviewer gets

The built public site and nothing else:

```bash
cd web && pnpm build && pnpm serve:static
```

Then `http://127.0.0.1:4173/`. The reviewer may navigate anywhere the site
links to, including `/science/` and `/lab/`, and may open any disclosure.

They must **not** get: this document, the repository, the beads backlog, the
decisions log, any `docs/*.md`, or any framing from the project owner beyond
§2.3's script. Links the site itself exposes to external sources (the
Pappalardo dataset, the CC BY 4.0 licence) are fair game — they are part of the
published experience.

### 2.2 Who is eligible

Two reviewers. Both must be people who have **never used this repository**.

**The project owner is not eligible.** Neither is any agent that has worked a
ScoutLens bead, and neither is an agent given this file. Knowing the canonical
answer makes you unable to measure whether the site conveys it — you will read
your own knowledge into ambiguous copy, which is exactly the failure mode this
gate exists to catch.

At least one reviewer must complete all six questions **within 90 seconds**.
The second reviewer is untimed; their value is depth, not speed. Record the
elapsed time for both regardless.

If only one eligible reviewer can be found, the gate does not pass. Record the
attempt and leave `scoutlens-9a3.7` open. One reviewer cannot distinguish "the
site communicates this" from "this particular person inferred it".

### 2.3 The script, read verbatim

> You are looking at a public research site. Answer six questions from what
> the site tells you. There is no penalty for saying you cannot tell — that is
> a real answer and I want it when it is true. Please think out loud.

Nothing else. Do not name the questions in advance, do not define MRR, do not
say "look at the science page", and do not react to a wrong answer until all
six are recorded. Prompting toward an answer voids that question.

### 2.4 Recording

Per question: the verbatim answer, elapsed time at that point, whether the
reviewer volunteered it or hedged, and which page or element they were looking
at. "Which element" matters more than it looks — an answer read off the hero
and the same answer dug out of a collapsed disclosure are different results
about the site.

## 3. The six questions and their canonical answers

Frozen. Changing a question's wording invalidates prior runs and requires a new
row in §6.

---

### Q1 — Vintage

> **What data is this built on, and from when?**

**Canonical:** the Wyscout / Pappalardo public event dataset, season
**2017/18**, five domestic competitions, 1,257 eligible player×competition
units.

**Passes if** the reviewer identifies the season as 2017/18, or says clearly
that the data is historical and roughly a decade old.

**Blocks if** the reviewer believes the data is current, ongoing, or
continuously updated. Currentness inference is a named stop condition.

**Evidence:** `manifest.source.season` (`"2017/18"`),
`manifest.dataset_version` (`wyscout-2017-18-v2-dc398ff5661c`),
`manifest.population.profile_count` (1257). Rendered by `DataVintageBadge` on
`/` and `/science/`.

---

### Q2 — The supported claim

> **In one sentence, what does this site say it has shown?**

**Canonical:** that event-derived profiles contain a reproducible individual
fingerprint which supports retrieving the same player across two chronological
halves of a season.

**Passes if** the answer contains both halves: *the same player can be
re-identified from their statistical profile*, and *across time / across two
periods*. "It identifies players from their stats" alone is a partial pass —
record it as such; it omits the temporal structure that makes the result a
result.

**Blocks if** the reviewer states the site shows playing style, player quality,
similar players for recruitment, or future performance. Those are §3 Q4's
territory and are explicitly unsupported.

**Evidence:** `research_summary.supported_claim`, rendered verbatim in the
landing hero's "Supported claim" panel.

---

### Q3 — The strongest limitation

> **What is the strongest reason to doubt that result?**

**Canonical:** same-season team continuity. A control using only role, team and
minutes reaches **0.5893 MRR** with a median rank of **2** — it *outperforms*
the 32-feature fingerprint's 0.2539 MRR and median rank of 16. Knowing who a
player's teammates were identifies them better than their own event profile
does.

**Passes if** the reviewer names team/club continuity, or says that knowing the
team gives away the answer. They do not need the number.

**Partial pass** if they name a real but weaker limitation — the 26-player
transfer sample, or the lower-magnitude StatsBomb replication — without
reaching the team confound. Record which they reached and in what order.

**Blocks if** they cannot identify any limitation, or name one the site does
not make. Missing the strongest confound is a named stop condition.

**Evidence:** caveat `same_season_team_confound` (severity `critical`);
experiment `wyscout_role_team_minutes`, metrics `baseline_c_mrr` = 0.5893 and
`median_rank` = 2, against `wyscout_global_gate2`'s 0.2539 / 16. Rendered in
the landing hero caveat, the claims matrix, and `/science/` stage 3.

---

### Q4 — An unsupported claim

> **Name one thing this site says it does *not* show.**

**Canonical, any one of:** statistical similarity does not prove playing style;
a statistical neighbour is not a recruitment recommendation or a replacement;
the experiment does not predict future performance, tactical fit, value or
transfer success.

**Passes if** the reviewer produces any one of the three unprompted.

**Blocks if** they cannot name one, or if they name one the site does not
actually disclaim.

**Evidence:** `research_summary.unsupported_claims` (three entries), rendered
by `ClaimsMatrix` on `/` and in the landing hero's boundary line ("Evidence of
individual signal. Not proof of playing style. Not a recruitment
recommendation.").

---

### Q5 — The metric

> **The headline number is an MRR of 0.2539, and higher is better. Better at
> what?**

**Canonical:** at ranking the correct same-player profile near the top of a
retrieval list. It is a retrieval-quality measure, not a player rating.

**Passes if** the reviewer says it measures finding/ranking the right player,
and does **not** treat it as a score of how good the player is.

**Blocks if** they read it as player quality, performance, or a rating. That is
the specific misreading the landing section intro was written to prevent, so a
miss here is a copy defect, not a reviewer error.

**Evidence:** `/` proof-band intro — "Mean reciprocal rank measures how high
the true same-player profile appears in the retrieval list. Higher is better
for this identity task—not a player rating."

---

### Q6 — The AI role

> **What role does AI play in what you are looking at?**

**Canonical:** none, in what is rendered. Every number is computed in Python
from frozen event data and exported as static JSON; there is no backend and no
client-side recomputation. AI *may* narrate deterministic evidence in future
under a fail-closed contract, but no live LLM is required for any current page,
and AI never recomputes a value, invents a metric, softens a caveat, or makes a
recommendation.

**Passes if** the reviewer says AI is not producing the numbers, or that it is
constrained to describing evidence it is given.

**Blocks if** they believe an AI model generated the results, the rankings, or
the similarity scores. That inverts the project's central claim about where the
numbers come from.

**Evidence:** `/science/` "Engineering and AI boundary" section, both the
Engineering and Governed AI articles.

---

## 4. Verdict rules

**There is no comprehension override.** Approved as human release policy on
2026-08-11 and recorded in `scoutlens-9a3.7`.

The gate **blocks**, and a narrowly scoped defect bead is filed against the
owning narrative or frontend bead, on any of:

1. A fixed-answer miss on any of the six.
2. An answer that requires repository knowledge to produce.
3. Any inference that the data is current or the site makes a recruitment
   recommendation.
4. Failure to identify the strongest limitation (Q3 blocking condition).
5. Neither reviewer finishing within 90 seconds.
6. Fewer than two eligible reviewers.

A defect bead names the question, the answer given, the element the reviewer
was reading, and the copy surface that owns the fix. **It does not propose the
new wording** — that is the narrative bead's judgement, and an auditor who
drafts the fix has stopped auditing.

Re-running the checklist after a copy fix requires **new reviewers**. A reviewer
who has seen the site once is no longer public-only. This is the expensive part
of the gate and it is not negotiable; budget for it before changing copy late.

## 5. Result template

Copy per run into §6.

```
## Run <n> — <YYYY-MM-DD>

Reviewer:        <identifier, not a name>
Eligible:        <never used the repository — how confirmed>
Timed:           <yes / no>
Build:           <git sha of the build served>
Total elapsed:   <mm:ss>

| Q | Answer (verbatim) | Elapsed | Volunteered / hedged | Element read | Verdict |
|---|---|---|---|---|---|
| 1 |  |  |  |  | pass / partial / block |
| 2 |  |  |  |  |  |
| 3 |  |  |  |  |  |
| 4 |  |  |  |  |  |
| 5 |  |  |  |  |  |
| 6 |  |  |  |  |  |

Ambiguities raised unprompted:
Defect beads filed:
Verdict: PASS / BLOCK
```

## 6. Runs

*No runs recorded. AC1 and AC2 of `scoutlens-9a3.7` are open pending two
eligible reviewers — see §2.2.*

| Run | Date | Build | Reviewer | Timed | Verdict |
|---|---|---|---|---|---|
| — | — | — | — | — | — |

## 7. What this document does not cover

AC3 (cross-route value agreement) and AC4 (link and no-JavaScript integrity)
are **automated** and live in `web/e2e/claims-consistency.spec.ts`, not here.
They check that the site is internally consistent and cites what it displays.
This document checks something no assertion can: whether a person reading it
arrives at the right understanding.

**AC5 is not yet implemented.** The forbidden-copy and currentness assertions
belong beside the existing forbidden recommendation-wording check in
`web/scripts/check-static-output.mjs`, and `web/scripts/**` is Conditional with
`scoutlens-uze.6` as its named reviewer — a bead that has closed. Tracked as
`scoutlens-uze.15`. Building a parallel audit under `web/e2e/` to route around
that would duplicate a mechanism that already exists, which is the mistake
`scoutlens-uze.6.1` made and `uze.6.2` corrected.

Keeping them separate matters. If the automated audit and the human checklist
disagree, that is a finding — the site is self-consistent but not
comprehensible, or comprehensible but citing something it should not.
