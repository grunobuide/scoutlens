# ScoutLens — Decisions Log

Append-only. Each entry records a decision that adjusts or clarifies
`00_ScoutLens_Project_Brief_v1.md`, with the reasoning, so a future reader
does not have to reconstruct *why* the charter deviates from the brief.

---

## D001 — 2026-07-20 — Data stack: Polars + Parquet

**Decision:** raw JSON artifacts are converted to Parquet during acquisition
(SLS-004/005); all downstream processing (`src/scoutlens/*`) uses Polars,
not pandas.

**Why:** ~3.25M events in raw JSON can run several GB; pandas is the
familiar default but risks memory pressure across the joins needed for
minutes reconstruction and feature aggregation. Polars + Parquet handles
that scale comfortably on a single machine without introducing a database
server.

**How to apply:** `ingestion.py` writes Parquet as its output contract.
Notebooks and `src/` modules read Parquet via Polars. If a specific
operation is awkward in Polars, drop to DuckDB over the same Parquet files
rather than pandas — don't mix dataframe libraries mid-pipeline.

---

## D002 — 2026-07-20 — Execution mode: pair programming incremental

**Decision:** work proceeds task by task (roughly per SLS-xxx item or
smaller), with review/approval before moving to the next step — not as an
unattended multi-day autonomous run.

**Why:** the brief's own 10-day plan is dense (23 sequential tasks + final
report) for solo execution; incremental review lets scope get cut
correctly (see D003) instead of discovering at Day 10 that something
important was skipped silently.

**How to apply:** don't batch multiple SLS-xxx tasks into one uninterrupted
stretch of work without checking in. Surface partial results (row counts,
schema findings, license status) as they're produced, not only at
day-boundary checkpoints.

---

## D003 — 2026-07-20 — Scope cut-order if the 10-day timebox is at risk

**Decision:** if time runs short, cut in this order:
1. First to go: Day 9 "Context diagnostics / error analysis" depth (keep a
   minimal version, drop the exhaustive neighborhood analysis).
2. Second: reduce the feature catalog (Day 6) toward the smaller end of the
   20–40 range, prioritizing families with the cleanest event-tag support.
3. Never cut: Gate 1 (Days 1–5, data feasibility) and the core Baseline
   A vs. B temporal retrieval experiment (Days 7–8) — these are what the
   GO/PIVOT/KILL decision is actually made from.

**Why:** H3/H4/H5 (temporal stability, beyond-position signal, baseline
competitiveness) are the hypotheses the spike exists to test. Context
diagnostics explains *why* a result looks the way it does — valuable, but
secondary to having the result at all.

**How to apply:** if a day's work is running long, apply this order before
extending the timebox itself.

---

## D004 — 2026-07-20 — License must be verified on the Figshare artifact page directly, before SLS-002/003

**Decision:** before building the source inventory or manifest, check the
actual license terms on the Figshare collection page (v5) for each artifact
to be consumed — not just the CC BY 4.0 statement in the paper text.

**Why:** the Pappalardo et al. dataset has been mirrored across multiple
hosts over time (Figshare, and others); a paper's stated license does not
guarantee the artifact page carries identical terms today. Gate 0
(provenance) depends on this being right before any other work proceeds.

**How to apply:** this is the literal first action of SLS-002, not a
footnote. If Figshare terms diverge from the paper, stop and reassess Gate
0 before continuing.

---

## D005 — 2026-07-20 — Minutes reconstruction: 80/20 rule, don't chase every edge case in v1

**Decision:** implement a first-pass minutes derivation that handles the
common cases (clean starting XI, clean substitutions) and explicitly tags
everything else via `derivation_status` (`missing_formation`,
`substitution_conflict`, `dismissal_uncertain`, `invalid`) rather than
trying to resolve extra time, red cards, and missing-formation matches
correctly on the first attempt.

**Why:** minutes reconstruction is already flagged in the brief as the
highest technical risk (section 11.1); trying to make it perfect before
moving on risks consuming most of Week 1. The status field makes the gap
visible without blocking downstream work.

**How to apply:** only invest further in the hard edge cases if the
eligible population computed in SLS-011 is too small to clear Gate 1 with
the easy cases alone. If it clears comfortably, leave the edge cases as
documented known limitations.

---

## D006 — 2026-07-20 — 450-minute threshold flagged as a known noise risk, not just a parameter

**Decision:** keep ≥450 minutes/split as the starting threshold for the
primary experiment (per the brief), but explicitly track it as a candidate
source of noise that could be mistaken for "instability" in the Day 9
analysis — not purely a population-size lever.

**Why:** 450 minutes is roughly 5 full matches; profiles built on that
little data will be noisier, and low temporal-stability scores at that
threshold may reflect sample noise rather than genuine role change. This
needs to be visible in the sensitivity analysis (minimum minutes →
population size → temporal stability curve, already planned) and called
out explicitly in the final report's limitations section, not just implied
by the presence of the curve.

---

## D007 — 2026-07-22 — SLS-015 temporal split must key on player × competition × period

**Decision:** the chronological split (SLS-015) and every downstream
temporal-retrieval step key each profile on `(player_id, competitionId,
period)`, not `(player_id, period)`.

**Why:** flagged in code review — a player who appears in both a domestic
league and an international tournament (Euro 2016 / World Cup 2018, per
[`eligible-population.md`](eligible-population.md)) would otherwise
produce two profiles for the same `(player_id, period)` key, silently
colliding into one retrieval target. This is a real, not hypothetical,
scenario in this dataset (SLS-011's population cascade shows multiple
player×competition rows for the same player).

**How to apply:** `compute_player_features` (SLS-014) is already agnostic
to this — it takes whatever events/minutes scope it's given and returns
one row per `player_id` in that scope. The obligation is on SLS-015's
split logic to call it once per `(competitionId, period)` combination and
carry `competitionId` through as part of the retrieval unit's identity,
not to change SLS-014 itself.

---

## D008 — 2026-07-22 — Feature normalization/null-handling strategy

**Decision (resolved 2026-07-22, SLS-017):** per-feature z-score
standardization, fit on the full combined query+candidate population for
a given comparison (not per-period separately). Null ratio features are
mean-imputed *before* standardizing, which makes them land at exactly
z=0 ("average, uninformative") rather than a fabricated extreme. Full
writeup: [`baseline-b-standardization.md`](baseline-b-standardization.md).

**Why:** flagged in code review — `docs/feature-definitions.md`'s features
mix very different scales and shapes: `progressive_pass_distance_p90` runs
into the hundreds, ratio features (`pass_completion_pct`,
`duel_win_pct`, ...) are bounded in [0,1], and several ratio features can
be `null` for a player who never attempted the underlying action (e.g.
`shot_conversion_pct` for a center-back). Baseline B (SLS-017) computes
cosine similarity over these features — without an explicit
standardization step, high-variance/high-magnitude features like
progressive distance and event volume will dominate the similarity
score purely by scale, and `null`s will break the computation outright if
not handled before the similarity step.

**How to apply:** before implementing SLS-017, decide and document: (a)
the standardization method (z-score per feature, computed over which
population — within-period, within-role, or global?), (b) what happens to
`null` ratio features — impute (to what value, and is that defensible?),
drop the player from that feature's contribution, or drop the feature
entirely for players below some attempt-count floor. Do not let this
default silently to "fill nulls with 0" without writing down why that's
the right choice — a 0%-filled `shot_conversion_pct` for a player who
never shot is a different claim than "no signal," and cosine similarity
will treat it as real information either way.
