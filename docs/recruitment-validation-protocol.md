# ScoutLens — Recruitment-Claim Validation Protocol (design)

Beads issue `scoutlens-j23` (protocol design only; execution is tracked
separately as `scoutlens-h00` and depends on the external-replication
outcome). Written 2026-07-23, logged as D016.

## Why this exists

The spike's central boundary (feasibility-report.md, Known Limitation
#2): same-player retrieval proves representation *stability*, not
recruitment *usefulness*. Every experiment run so far asks "can the
system find the same player again?" — no amount of that answers "are
the *other* players it surfaces actually useful to a scout?" Answering
that requires human judgment (or a real-world outcome) entering the
loop for the first time. This document specifies how, in advance, so
execution can't quietly bend toward a favorable reading — the analysis
plan and failure criteria below are the pre-registration.

## 1. The recruitment decision being evaluated

**"Shortlist generation for a stylistic replacement."** The concrete
scenario: a club is losing (or considering losing) player X and wants a
shortlist of stylistically similar players worth deeper scouting
(video, live viewing). The system's job is the *first funnel stage* —
surfacing candidates a scout finds plausible enough to spend time on —
not the final signing decision, which involves price, age, contract,
character, and context far outside event data.

This is deliberately the weakest useful claim: if experts don't find
the shortlists better than trivial alternatives at even this stage, no
stronger recruitment claim survives.

## 2. Systems under comparison

Each query player gets K=5 candidates per system (self excluded, true
period-B match excluded — the scenario is "replace X," so X isn't a
valid answer):

| Arm | System | What it tests |
|---|---|---|
| B | Baseline B (32 std. features, cosine) | the actual claim |
| C-role | Same nominal role, minutes-proximity ranked | "a cheap heuristic does as well" |
| R | Random same-role eligible players | floor |

Baseline C's team component is meaningless for recruitment (the
replacement can't come from the same roster slot), so the control is
role+minutes (Baseline A's logic) — the strongest *cheap* alternative a
club could implement with a spreadsheet.

## 3. Query sampling

- Population: the eligible set (≥450 min in both periods, five domestic
  leagues) — the population every published number describes.
- **40 queries: 10 per nominal role** (GK, DF, MF, FW), sampled at
  random within role with two constraints: no two queries from the same
  club, and league spread enforced (≥1 query per league per role where
  the role's population allows). Sampling done once, with a fixed seed,
  before any ratings are collected.
- Candidates are drawn from period-B profiles of the *other* leagues'
  players included — cross-league suggestions are the realistic
  recruitment case and league confound was measured small (~1.08x).

## 4. Blinding and presentation

- Raters see, per query: the query player's profile card and 15
  candidates (3 arms × 5) in a **single merged, randomized list** — not
  three labeled lists. Arm assignment is recorded but never shown.
- Profile cards show identical fields for query and candidates: name,
  age, role, league, minutes, and the same set of per-90 stats for
  everyone. Names are **shown** (these are public figures and expert
  judgment legitimately uses knowledge of the player — hiding names
  would test something artificial), but raters are instructed to rate
  *stylistic fit for further scouting*, not fame or absolute quality,
  and the rubric anchors reflect that.
- Randomization: candidate order shuffled per query per rater; query
  order shuffled per rater.
- Raters never see which system produced a candidate, the study's
  hypothesis, or each other's ratings.

## 5. Rubric

Per candidate (anchored 1–5): **"As a stylistic replacement candidate
for the query player, this player is…"**

1. Not a plausible candidate — wrong profile entirely
2. Weak — superficial overlap only (e.g. position alone)
3. Plausible — worth a glance, wouldn't prioritize
4. Good — would put on the video-review list
5. Strong — clearly the same style of player, would prioritize

Per query (after rating all 15): "How many of these 15 would you
genuinely take to video review?" (0–15, sanity check on scale use).

## 6. Raters

- **Minimum 2, target 3–5**, with real scouting or football-analysis
  experience (club scouts, analysts, or established public analysts).
  Recruited from the analytics community for a portfolio-stage project;
  unpaid participation acknowledged in any writeup with consent.
- Every rater rates every query (full crossing) at n=40 queries × 15
  candidates = 600 ratings per rater; pilot with 5 queries first to
  time it and debug the rubric (pilot data discarded).

## 7. Metrics

- **Primary:** mean rating difference **B − C-role**, paired within
  query (each query contributes its mean-of-5 per arm, averaged over
  raters). One number, declared here, no substitutions.
- **Secondary:** B − R difference (floor check); win rate (fraction of
  queries where B's list mean beats C-role's); fraction of B candidates
  rated ≥4 ("video-review rate"); per-role breakdown (GK expected
  weakest — feature catalog is outfield-heavy).
- **Reliability:** inter-rater agreement on the 1–5 ratings,
  Krippendorff's α (ordinal). Ratings are averaged across raters for
  the primary analysis; α is reported alongside, not used to filter.

## 8. Analysis plan (pre-registered)

- Primary test: Wilcoxon signed-rank on the 40 paired (B, C-role)
  query-level means, two-sided, α=0.05, with a bootstrap CI on the mean
  difference. Mixed-model check (rating ~ arm + (1|query) + (1|rater))
  reported as robustness, not as a substitute primary.
- Power context (not a promise): with 40 paired queries, a paired
  effect of ~0.45 SD is detectable at ~80% power. Smaller true effects
  may read as null — acceptable: an effect too small to detect at n=40
  is also too small to justify the system over a spreadsheet heuristic.
- No interim peeking at arm-labeled results before all ratings are in.
- All ratings published (anonymized rater IDs) with the analysis code.

## 9. Failure criteria (declared in advance)

1. **Claim fails** if the primary contrast (B − C-role) is not positive
   with the pre-registered test — regardless of any favorable
   secondary. Report as "recruitment usefulness not demonstrated."
2. **Instrument fails** if Krippendorff's α < 0.40 — experts don't
   agree enough for the rubric to mean anything; results are reported
   as unreliable (not as success or failure) and the rubric is revised
   before any re-run (new raters or new queries, no silent reuse).
3. **Floor fails** if B does not beat random (B − R ≤ 0): stronger than
   (1) — treat as evidence of a broken pipeline, investigate before
   interpreting anything.

## 10. Data and privacy constraints

- Player data: public event-derived aggregates. Wyscout-derived cards
  carry CC BY 4.0 attribution; if executed on StatsBomb data instead,
  the StatsBomb constraints apply (non-commercial, no raw-data
  redistribution, logo on publication — see statsbomb-provenance.md),
  and per-player *aggregate* cards shown to a handful of raters are
  analysis outputs, not data redistribution.
- Rater data: names never published; role/affiliation described only
  generically ("club analyst") with each rater's consent; raw ratings
  published under anonymized IDs.
- No minors in the eligible population (professional players, ≥450
  minutes in top-5 leagues).

## 11. Execution checklist (for scoutlens-h00)

- [ ] Confirm dataset arm (Wyscout 2017/18 vs StatsBomb 2015/16) — decision
      depends on external-replication outcome
- [ ] Freeze code + config; record run manifest for the shortlist
      generation (same `_manifest` machinery as D015)
- [ ] Sample 40 queries with fixed seed; generate 3×5 candidates per query;
      archive the arm-assignment key separately from rater materials
- [ ] Build profile cards; verify identical presentation across arms
- [ ] Recruit 2–5 raters; collect consent for anonymized publication
- [ ] Pilot on 5 queries; fix rubric/timing issues; discard pilot data
- [ ] Collect ratings (each rater: all 40 queries, shuffled)
- [ ] Compute α, primary and secondary metrics per this document
- [ ] Publish protocol deviations (if any), ratings, code, and outcome —
      including a null result

## Explicitly out of scope for the first execution

- **Downstream-task retrodiction** ("did the system rank the actual
  signed replacement highly for real transfers?") — attractive because
  it's automated, but heavily confounded (clubs don't sign for style
  fit alone, transfer data adds a new source, survivorship again) and
  it would quietly substitute a different question for the expert one.
  Worth designing separately if the expert study succeeds; not a
  secondary metric here.
- Any claim about *transfer success* of recommended players. This
  protocol validates shortlist plausibility, stage one of the funnel,
  nothing further.
