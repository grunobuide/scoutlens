# Public understanding check

The frozen comprehension checklist for `scoutlens-9a3.7`. It asks whether the
public site, on its own, communicates what ScoutLens actually showed — and,
just as importantly, what it did not.

This is **portfolio communication QA, not scientific validation**. It does not
test whether the science is right. It tests whether a reader who has never seen
this repository arrives at the same understanding the artifacts support.

**Current policy (2026-09-15, D056):** one eligible human review is available.
The owner directed work to continue without waiting for a second reviewer.
Run 1 remains **BLOCK**. Implementation may proceed; release requires the
recorded defects to be remediated, the automated gates to pass, and the case
study to disclose the limited comprehension evidence. This is not a claim of
validated public comprehension. Section 6 preserves the original protocol's
assessment and is not retroactively re-scored.

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

One eligible first-time human reviewer is sufficient to collect formative
feedback under D056. They must have **never used this repository**. A second
independent reviewer remains desirable but is not a dependency for v1 work or
release.

**The project owner is not eligible.** Neither is any agent that has worked a
ScoutLens bead, and neither is an agent given this file. Knowing the canonical
answer makes you unable to measure whether the site conveys it — you will read
your own knowledge into ambiguous copy, which is exactly the failure mode this
gate exists to catch.

The **90-second** first-understanding goal remains a UX target. Record elapsed
time and distinguish reading/answering from facilitator recording time when
measurable. Do not subtract an invented typing allowance from run 1's 2:53 or
claim that the target was met. Reviewer count or timing alone no longer freezes
implementation. One reader cannot establish general comprehensibility.

An optional follow-up with R1 may assess whether corrections address their
confusion. Label it **non-blind follow-up, same participant**; do not count it
as a second reader or independent evidence. Automated or agent review is also
not a substitute human participant.

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

**Canonical (clarified by D056):** no live generative model produces the public
pages. The v2 rankings do use a learned diagonal metric, fitted offline and
evaluated as ML; Python computes and exports the stored evidence. The browser
does not recompute it. The planned local explanation toolkit may narrate that
evidence under a fail-closed contract, with a configurable model, but cannot
invent values, soften caveats or make recommendations. Saying that the project
uses no ML at all would also be wrong.

**Passes if** the reviewer distinguishes the frozen numerical/ML pipeline from
generative explanation, or correctly identifies that no live LLM produces the
current pages and any generative explanation is constrained to stored evidence.

**Blocks if** they attribute the numerical results or rankings to live LLM
invention, or infer that an AI proves playing style or recommends players.
Correctly identifying the offline learned diagonal metric is not a failure.

**Evidence:** `/science/` "Engineering and AI boundary" section, both the
Engineering and Governed AI articles.

---

## 4. Verdict rules

**D056 supersedes the reviewer-count, mandatory fresh-retest and hard timing
requirements of the 2026-08-11 release policy.** It does not turn wrong answers
into correct ones. A narrowly scoped defect bead is still required on any of:

1. A fixed-answer miss on any of the six.
2. An answer that requires repository knowledge to produce.
3. Any inference that the data is current or the site makes a recruitment
   recommendation.
4. Failure to identify the strongest limitation (Q3 blocking condition).

These findings block communication-gate closure until their remedies are
integrated and verified. They do not block the independent AI evidence-contract
work. A remedy can be accepted technically using deterministic assertions,
artifact agreement and review of the rendered surface; that does not prove
the reader now understands it.

A defect bead names the question, the answer given, the element the reviewer
was reading, and the copy surface that owns the fix. **It does not propose the
new wording** — that is the narrative bead's judgement, and an auditor who
drafts the fix has stopped auditing.

A new blind run requires a new eligible reader. A repeat with R1 is allowed as
the explicitly labelled follow-up in section 2.2 and is optional. Waiting for a
fresh reader is not a v1 dependency under D056.

`scoutlens-9a3.7` can close as **remediation complete; comprehension evidence
limited (n=1)** after all four recorded findings have a documented technical
disposition, automated criteria AC3–AC6 pass, and the case-study handoff states
the residual risk. It cannot close as "comprehension PASS" based on this
exception. Run 1, its 2:53 timing and its BLOCK verdict remain unchanged.

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

**Historical record:** the count/retest statements below describe the policy
under which run 1 was conducted. D056 replaces those requirements prospectively;
it does not change any recorded answer, grade, timing or verdict below.

| Run | Date | Build | Reviewer | Timed | Verdict |
|---|---|---|---|---|---|
| 1 | 2026-09-15 | `b943b44` | R1 | yes, 2:53 | **BLOCK** |

AC1 and AC2 remain open: the gate needs two eligible reviewers, and run 1
blocked.

### Run 1 — 2026-09-15

```
Reviewer:        R1
Eligible:        1st subject
Timed:           yes
Build:           b943b44
Total elapsed:   2:53
```

| Q | Answer (verbatim) | Elapsed | Delivery | Recorded | Re-graded |
|---|---|---|---|---|---|
| 1 | data from european season of 17/18 and then data from a different year | 0:50 | volunteered | pass | pass |
| 2 | it is an experiment showing how a player can be identified by their actions in the game | 1:18 | volunteered | partial | partial |
| 3 | it could be biased, too much data to check individual records | 1:56 | volunteered | partial | **block** |
| 4 | i would like to see more recent data, or be able to use ai on it | 2:20 | volunteered | partial | **block** |
| 5 | identifying players | 2:39 | volunteered | partial | **pass** |
| 6 | describing player types | 2:53 | volunteered | block | block |

Ambiguities raised unprompted: none. Element-read column not captured — see
"what run 1 exposed about the instrument" below.

**Verdict: BLOCK.** Unchanged by the re-grade; §4 rule 1 fires on Q6 alone, and
the run is 2:53 against a 90-second target.

#### Why three grades moved

The live grading used a "partial" on Q4 and Q5, and §3 defines a partial only
for **Q2** and **Q3**. The other four are scored pass or block. The facilitator
tool offered a Partial button on all six, so this is an instrument defect that
produced a softer record than the protocol allows, not a grader error — it has
been corrected.

- **Q3 → block.** "It could be biased, too much data to check individual
  records" is not one of the weaker limitations §3's partial contemplates (the
  26-player transfer sample, the lower-magnitude replication). It is a generic
  doubt. §3 blocks when a reviewer "cannot identify any limitation, or names one
  the site does not make", and *too much data to check individual records* is
  not a limitation this site makes.
- **Q4 → block.** The answer is a wish ("more recent data, or be able to use ai
  on it"), not a claim the site disclaims. §3: blocks if they cannot name one.
- **Q5 → pass.** "Identifying players" is terse but it is finding the right
  player, and it is not read as a quality score. §3 asks for exactly that and
  offers no partial. Marking it down was harsher than the protocol.

#### What run 1 says about the site

Four findings, each filed rather than fixed — §3 of the ownership boundary keeps
this bead out of copy.

1. **Q6 is the serious one.** "Describing player types" inverts two claims at
   once: that no AI produces what is rendered, and that the fingerprint is not
   proof of playing style. The second is the site's most-repeated caveat.
2. **Q4 produced nothing at all.** The landing page carries a hero boundary
   line *and* a dedicated "Not supported / Where the evidence stops" matrix, and
   the reviewer could not recall a single item from either. Three disclaimers,
   zero recall.
3. **Q3 never reached the team confound** — the critical-severity caveat that
   sits in the landing hero next to the supported claim.
4. **Q2 lost the temporal structure.** "Identified by their actions" drops
   *across two chronological halves*, which is what makes the result a result
   rather than a description.

#### What run 1 exposed about the instrument

- The **element-read** column is empty for all six. It is the field that tells a
  defect bead *which* surface failed, and under live time pressure it was the
  first thing to go. Capture it for run 2 even if the answer is "did not look at
  anything".
- The partial-button defect above.
- 2:53 against a 90-second target, with a reviewer who answered promptly and
  never stalled. The target may be measuring the facilitator's typing speed as
  much as the reader's comprehension. Worth watching in run 2 before treating
  rule 5 as a property of the site.

## 7. What this document does not cover

AC3 (cross-route value agreement) and AC4 (link and no-JavaScript integrity)
are **automated** and live in `web/e2e/claims-consistency.spec.ts`, not here.
They check that the site is internally consistent and cites what it displays.
This document checks something no assertion can: whether a person reading it
arrives at the right understanding.

**AC5** lives in `web/scripts/check-static-output.mjs`, beside the
recommendation-wording check that was already there. It bans assertive
phrasings of the unsupported claims, bans wording that would imply the data is
live, and requires every route to carry "not current scouting information" —
the machine-checkable half of Q1's blocking condition. The claim boundaries the
site states in order to disclaim them are excepted, and that exception is read
from the shipped artifact rather than hardcoded. See
[`frontend-release-gates.md`](frontend-release-gates.md) §3.4.

Keeping them separate matters. If the automated audit and the human checklist
disagree, that is a finding — the site is self-consistent but not
comprehensible, or comprehensible but citing something it should not.
