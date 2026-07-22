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

**Resolved (2026-07-22, SLS-020):** the risk did not materialize. The
Baseline B−A MRR delta's confidence interval stays clear of 0 across
every threshold tested from 225 to 1,350 minutes, strengthening (not
weakening or reversing) as the threshold rises. ≥450 minutes sits
comfortably inside the range where the signal is both strong and
precisely estimated. Full curve:
[`context-diagnostics.md`](context-diagnostics.md).

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

---

## D009 — 2026-07-22 — Post-publication review: two correctness bugs found and fixed after Gate 2 was recorded

**Decision:** fix both immediately rather than treat the already-recorded
GO decision as final; keep Gate 2's verdict (GO) but correct the evidence
behind it.

**Why:** an external review of the merged spike found two real issues:

1. `neighbor_concentration`'s team/league confound measurement included a
   query's own correctly-retrieved true match as a "neighbor." A player's
   team essentially never changes within one season split, so a correct
   retrieval trivially "shares the query's team" — this measured
   retrieval *success*, not a confound, and inflated the apparent team
   effect from a real ~1.24x to a reported ~4.6x.
2. `run_baseline_a_retrieval`/`run_baseline_b_retrieval` identified the
   true match by `player_id` alone, not `(player_id, competitionId)` as
   D007 requires. Harmless today (no player appears in two domestic
   competitions in this single-season dataset) but would silently
   misbehave the moment that stopped being true — exactly the kind of bug
   D007 was written to prevent, that slipped past because SLS-018/019/020
   never exercised the case it guards against.

Both were confirmed against real data before fixing (not just taken on
the reviewer's word) — see
[`context-diagnostics.md`](context-diagnostics.md) for the corrected
numbers. A third, lower-severity issue (the chronological split's sort
had no explicit tiebreak, and Euro 2016 genuinely has two matches tied on
`dateutc` straddling the split boundary) was fixed the same way, with a
regression test proving the split is now independent of input row order.

**How to apply:** `neighbor_concentration` now excludes true matches by
default (`include_true_matches=True` opts back into the old, inflated
behavior, kept only for explicit before/after comparison). Retrieval
matching now requires `(player_id, competitionId)`, with a regression
test simulating a player in two competitions. `assign_periods` sorts by
`(dateutc, wyId)`. None of this changed the headline MRR/CI numbers
(verified by re-running) — it made the *diagnostic* conclusion stronger
(smaller, more defensible confounds) and closed a latent correctness gap
that hadn't yet been exercised by real data. Gate 2 remains GO.

---

## D010 — 2026-07-22 — Team continuity dominates a trivial role+team+minutes baseline; reframe, don't retract

**Decision:** report this prominently rather than treat it as a footnote,
and reorder the next-experiment priorities around it (testing transferred
players moves to #1) — without reopening Gate 2.

**Why:** the robustness battery's Baseline C (same role AND same primary
team first, then role only, then team only, minutes as tiebreak — no
event data at all) scored MRR 0.589, beating Baseline B's 0.254 by more
than 2x. Root cause: the eligible population requires ≥450 minutes in
both halves of the *same season*, and players essentially never change
clubs mid-season, so a club's specific-role sub-roster is small enough
(often 2–4 eligible players) that "closest minutes within this club's
same-role players" nearly solves same-player retrieval on its own. This
is a genuine limitation of the *experimental design* — team continuity
was always implicitly available as a shortcut the current population
never controls for — not evidence that Baseline B's own result is
fabricated or that Gate 2 was wrong: Baseline B still clearly beats
Baseline A (the charter's actual criterion), and a teammates-excluded
sensitivity check (robustness-checks.md, Check 4) confirms Baseline B's
own performance doesn't depend on team-clustering.

**How to apply:** every MRR/Recall number in `feasibility-report.md` and
`gate-2-decision.md` should now be read with the qualifier "given team
continuity across the split," not as evidence of individual stability
independent of it. The next experiment that actually isolates individual
signal from team-continuity is testing players who changed clubs between
the two periods — where Baseline C's advantage structurally cannot apply.
Until that's run, do not describe the retrieval result as proof of
"stable individual playing style" without this caveat attached.

---

## D011 — 2026-07-22 — Transferred-players follow-up run the same day; caveat confirmed, not resolved

**Decision:** treat D010's caveat as directly tested, with an honest
small-sample qualifier — not as fully resolved, and not as still fully
open either.

**Why:** [`transfer-analysis.md`](transfer-analysis.md) isolated the 26
of 1,257 eligible players (2.1%) whose primary team (per
`compute_primary_team`) differs between period A and period B, and
re-ran all three baselines with queries restricted to just them, against
the same global period-B candidate pool used everywhere else. Result:
Baseline C (role+team+minutes) collapsed from MRR 0.589 (best of the
three baselines in the general population) to MRR 0.010 — statistically
indistinguishable from Baseline A — direct confirmation the D010 root
cause was correctly diagnosed. Baseline B's MRR for this subset (0.239)
stayed close to its full-population value (0.254), and the Baseline B−A
delta point estimate was, to three decimal places, identical for
transferred players as for everyone else (+0.228 both), though the CI is
far wider at n=26 (`[0.089, 0.393]` vs. `[0.210, 0.250]`).

**How to apply:** this is real, direct, encouraging evidence that
Baseline B's signal is not primarily a team-continuity artifact — a
meaningfully stronger claim than D010 could make on its own (which only
showed Baseline B doesn't *lean on* teammates being in the pool, not that
it survives team change). But n=26 is small enough that this should be
described as "confirms the direction, doesn't yet make it precise" — the
wide CI is the honest summary. Do not round this up to "proven" in any
future report; the natural way to tighten it is a larger transferred-player
sample from another season (feasibility-report.md's next-experiment #1).

---

## D012 — 2026-07-22 — "Extend to another season" requires a new external dataset; work paused here pending feedback

**Decision:** stop follow-up work at this point (post-D011) rather than
start a new-dataset integration without confirming it's the right next
project. Documented the scoping research in
`feasibility-report.md`'s next-experiment #1 so it isn't re-derived from
scratch whenever this is picked back up.

**Why:** confirmed empirically — not assumed — that the Pappalardo/Wyscout
collection this entire spike is built on has exactly one season per
competition (`competitionId` → single `seasonId`, no exceptions). There is
no second season hiding in the same collection; getting one requires a new
external source entirely, which reopens Gate-0-style work (source
discovery, per-artifact license verification, schema audit) before any
acquisition code exists. Researched StatsBomb Open Data as the most
likely candidate: free, but (a) no single season covers all five leagues
at full depth — La Liga alone has deep multi-season coverage (18
seasons, including 2018/19), the other four leagues are sparse — and (b)
a structurally different event schema, meaning integration would mean
re-doing the equivalent of SLS-005–SLS-014's work for a new source, not
reusing the existing pipeline with new input files. Real, multi-day
scope, not a rerun. The user asked to pause here, gather feedback, and
open a separate project when ready to continue rather than commit to that
scope unilaterally mid-session.

**How to apply:** the next session picking this up should start from
`feasibility-report.md`'s next-experiment #1 (which already has the
StatsBomb findings and a recommendation — La Liga 2018/19 as the
narrowest viable single-league test, if a full license/match-count audit
confirms it holds up) rather than re-researching dataset options from
zero. Treat this as a new mini-Gate-0, with its own provenance/license
documentation, not as a continuation of the existing acquisition
pipeline.
