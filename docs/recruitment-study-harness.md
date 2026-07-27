# ScoutLens — Recruitment Study Execution Harness (h00)

Beads issue `scoutlens-h00`. Builds everything the recruitment-validation
study ([`recruitment-validation-protocol.md`](recruitment-validation-protocol.md),
D016) needs **except the one thing an agent cannot honestly provide:
real expert ratings**. Logged as D023. Code: `src/scoutlens/study/`;
tests: `tests/study/`.

The study can only support or reject a *recruitment-usefulness* claim
once real scouts have rated the shortlists — same-player retrieval and
the external replication (D022) establish *stability*, not usefulness.
This harness makes the study runnable by a human the moment raters are
available: it generates the blinded materials from frozen data and
implements the full pre-registered analysis, verified on synthetic
ratings.

## What the harness produces

`uv run python -m scoutlens.study.shortlists` writes, deterministically
for a fixed seed, to `artifacts/recruitment_study/`:

- **`rating_sheet.json`** — the rater-facing materials. 40 role-stratified
  query players (10 GK / DF / MF / FW), each with a profile card and **15
  candidate cards** (name, age, role, league, minutes, key per-90 stats).
  The 15 = three arms of 5, **merged and shuffled with no arm labels**
  (blinding).
- **`arm_key.json`** — the separate answer key mapping each candidate to
  its arm. Raters never see this.
- **`manifest.json`** — protocol pointer, dataset, seed, blinding note,
  expected 600 ratings/rater.

Dataset: **Wyscout 2017/18 (CC BY 4.0)** — cleaner than StatsBomb for
materials shown to external raters (no non-commercial / logo constraints
on the cards), and the primary v0.1 dataset.

### The three arms (D016 §2)
Built **mutually exclusive** so the 15 are distinct and every rating
attributes to exactly one arm:
- **B** — Baseline B: cosine top-5 on the 32 standardized features.
- **C_role** — the honest cheap control: same role, closest period-B
  minutes to the query.
- **R** — random same-role (floor).

The query player and his own period-B "true match" are excluded — the
scenario is *replacement*, so the player himself is never a candidate.

## The analysis (implemented, tested, waiting for ratings)

`scoutlens.study.analysis.analyze_study(ratings, reliability)` applies the
pre-registered plan mechanically:

- **Primary:** paired **B − C_role** query-level mean-rating difference,
  Wilcoxon signed-rank (normal approximation — no scipy in the project)
  plus a paired bootstrap CI.
- **Reliability gate:** interval-metric **Krippendorff's α**, floor 0.40.
- **Secondary:** B − random, win-rate of B over C_role, mean rating per
  arm.
- **Decision:** the three pre-declared failure criteria (claim /
  instrument / floor) map to **GO / REDESIGN / NO-GO** with no
  post-hoc freedom.

All statistics are implemented from scratch and unit-tested (Krippendorff
α against a hand-computed case and boundary conditions; Wilcoxon against
all-positive and symmetric inputs; the decision logic against synthetic
GO / NO-GO / REDESIGN / floor-fail scenarios).

## What remains (the human-in-the-loop part)

The harness deliberately stops where honesty requires a human:

1. **Recruit 2–5 expert raters** and obtain consent for anonymized
   publication (D016 §6, §10).
2. **Collect ratings** — each rater scores all 40 queries × 15 candidates
   (1–5 rubric, D016 §5), ~600 ratings/rater. A 5-query pilot first,
   discarded.
3. **Run** `analyze_study` on the collected long-format ratings + the
   reliability matrix → the pre-registered metrics and GO/REDESIGN/NO-GO.
4. **Publish** protocol deviations (if any), ratings (anonymized), and
   the outcome — including a null result.

`scoutlens-h00` stays open until real ratings exist and the analysis is
run: the harness is complete, but the study's conclusion is not something
this repository can manufacture. Fabricating ratings would be worthless;
the value is that steps 1–4 are now a data-collection exercise, not a
build.
