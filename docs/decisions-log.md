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

---

## D013 — 2026-07-22 — Second review round: a second instance of the D009 bug class, plus a wrong dataset recommendation

**Decision:** fix the diagnostics bug and make the function fail loudly
on the underlying precondition (not just recompute the one number
by hand), correct the StatsBomb recommendation from D012, and tighten
report language where a second reviewer found it still overclaiming.

**Why:** a second, independent review of the merged spike + follow-up
work found:

1. **The team-concentration number from D009's own fix was still
   wrong.** `run_report.py` built `query_team`/`neighbor_team` by
   selecting `player_id` + `team_id` from `compute_primary_team`'s full
   output — but that function runs over *every* competition a player
   appears in, so a player with minutes recorded under more than one
   `competitionId` (Euro/World Cup appearances, or a genuine mid-season
   transfer between two of the five domestic leagues) produces duplicate
   `player_id` rows with different `team_id` values. 361 of 1,257
   eligible players (28.7%) are affected. This silently inflated
   `neighbor_concentration`'s join. Published: 1.30% / ~1.24x. Corrected:
   1.20% / ~1.14x — exactly matching the reviewer's independently
   recomputed figure.
2. **The `feasibility-report.md` recommendation to use "StatsBomb La
   Liga 2018/19" was wrong.** Verified directly: that release is a
   Messi/Barcelona-focused subset (a few dozen matches), not a full
   380-match season — confirmed by fetching the actual file. StatsBomb's
   2015/16 season covers four of the five domestic leagues at full depth
   (Premier League, La Liga, Serie A, Ligue 1 — Bundesliga's 2015/16
   release is itself a small subset, ~34 matches, confirmed the same
   way) and is the corrected recommendation.
3. Report language still said "stable player-role signal" in the
   Executive Summary/charter-quote sections despite the body text
   elsewhere already having moved to the more precise "statistical
   fingerprint" framing — a genuine inconsistency, not just a style
   preference.
4. The transferred-players write-up (D011) reported MRR holding up but
   didn't call out that median rank (16→38.5) and Recall@10 (43.3%→
   34.6%) moved unfavorably for that subset — MRR alone can be dominated
   by a handful of rank-1 hits at n=26, and the fuller picture is more
   mixed than "holds up" alone conveys.

**How to apply:** `neighbor_concentration` now raises `ValueError` on any
duplicate `player_id` in its inputs instead of trusting the caller to
have scoped correctly — this is the structural fix, not just a one-time
recomputation, and it caught itself immediately on re-run (see
`context-diagnostics.md`). Numbers corrected throughout
`context-diagnostics.md`, `feasibility-report.md`, `gate-2-decision.md`.
The StatsBomb recommendation, report-language consistency, and the
transfer-analysis metric picture are corrected in the same pass — see
each document's own change for specifics rather than duplicating them
here.

---

## D014 — 2026-07-23 — StatsBomb mini Gate 0: GO for the replication epic, with license constraints

**Decision:** clear `scoutlens-8mc.1` (license + match-count audit) with a
**GO** for non-commercial research replication on StatsBomb Open Data
2015/16, scoped to Premier League (2), Ligue 1 (7), La Liga (11), and
Serie A (12), season_id 27, pinned to repository commit
`b0bc9f22dd77c206ddedc1d742893b3bbe64baec`. Full audit:
[`statsbomb-provenance.md`](statsbomb-provenance.md).

**Why:** D012/D013 left the StatsBomb verification explicitly
non-exhaustive (file-size scaling, surface-level license check). This
audit closed both gaps against the actual files:

1. **Counts, exact:** PL/La Liga/Serie A 380 each; Ligue 1 **377** (the
   release omits Bastia–Gazélec Ajaccio wk 14, Saint-Étienne–PSG wk 23,
   Troyes–Bordeaux wk 36 — six clubs at 37 matches, negligible for
   aggregates but the Ligue 1 validation must expect it); Bundesliga 34
   (Leverkusen-only — exclusion confirmed); La Liga 2018/19 re-confirmed
   as the Messi release (Barcelona in all 34 files, not even
   Barcelona-complete). Events + lineups files exist for all 1,517
   candidate matches (verified via full git-tree listings, not
   sampling).
2. **License, per-clause:** the "StatsBomb Public Data User Agreement"
   (LICENSE.pdf, 2023-09-08) is *not* an open license. Redistribution of
   the data is prohibited (1.2.1, 7); commercial exploitation of the
   data **and of derived analyses** is prohibited (1.2.2); publishing
   analysis is allowed but requires StatsBomb logo attribution (1.4 +
   README); user registration is requested (2.2). All materially
   stricter than the Wyscout CC BY 4.0.

**How to apply:** acquisition code (`scoutlens-8mc.2`) pins the source
to the audited commit SHA and downloads only competitions {2,7,11,12} ×
season 27. Raw *and* per-player derived StatsBomb tables stay out of
Git (license obligation now, not just hygiene). Any published
StatsBomb-derived result must carry logo attribution and stays
non-commercial; the Wyscout-vs-StatsBomb asymmetry in licensing must be
stated wherever the two sets of results are compared. Remaining user
actions before acquisition: register at statsbomb.com/resource-centre
(recommended), decide how the logo obligation will be met at
publication time.

---

## D015 — 2026-07-23 — Versioned experiment config, run manifests with data checksums, and a fresh-run drift test

**Decision:** close the reproducibility gap D013 left open (beads issue
`scoutlens-a72`, part of the v0.1 release epic) with three pieces:
`config/experiment.json` as the single versioned source of experiment
parameters; a `_manifest` embedded in every artifact
(`run_manifest.build_run_manifest`: resolved config + config-file
sha256, git commit, Python/Polars/platform versions, sha256 + size per
input Parquet); and an opt-in fresh-run drift test
(`SCOUTLENS_DRIFT=1 uv run pytest
tests/evaluation/test_artifact_drift.py`) that regenerates all three
result sets and compares them to the checked-in artifacts
number-by-number, completing the chain: docs ↔ checked-in artifact
(`test_artifacts.py`) ↔ fresh run (`test_artifact_drift.py`).

**Why:** D013's `_run_metadata()` recorded only commit + timestamp — it
could not tie published numbers to the exact data bytes (the processed
Parquets are local and gitignored) or catch a silent divergence between
the code and the checked-in artifacts. The parameters were also
re-declared as constants in each of the three runners, so a change in
one place could silently desynchronize the others.

The drift test earned its keep on its very first execution: it caught
`transferred_pairs` in the transfer artifact shuffling row order between
two identical runs (Polars join output order isn't guaranteed).
`identify_transferred_players` now sorts by `(player_id, competitionId)`
— all published *numbers* were unaffected (the 26 pairs were identical
as a set), but the artifact bytes were nondeterministic, which is
exactly the class of problem this task existed to eliminate.

**How to apply:** any change to `config/experiment.json`, the evaluation
code, or the local data must regenerate the three artifacts and pass
both test layers before merging; `test_run_manifest.py` additionally
pins the config values the published v0.1 numbers were produced with, so
a parameter change fails loudly until the pin, artifacts, and doc prose
are updated together. Bootstrap `n_resamples`/`seed` now thread from the
config through `run_global_retrieval_experiment` /
`run_within_role_retrieval_experiment` instead of relying on defaults.

---

## D016 — 2026-07-23 — Recruitment-validation protocol designed (blinded expert shortlist study)

**Decision:** the recruitment claim will be tested as a **blinded,
pre-registered expert study of shortlist plausibility** — Baseline B's
top-5 vs a role+minutes heuristic vs random same-role, merged and
shuffled per query, rated 1–5 by 2–5 experts on 40 role-stratified
queries; primary metric is the paired B−(role+minutes) rating
difference, with failure criteria declared before any data collection.
Full protocol: [`recruitment-validation-protocol.md`](recruitment-validation-protocol.md).
Design only (beads `scoutlens-j23`); execution is `scoutlens-h00`,
gated on the external-replication outcome.

**Why:** feasibility-report.md's Known Limitation #2 is the spike's
central boundary — same-player retrieval proves stability, not
usefulness, and no automated metric on this dataset can close that gap.
The two candidate methodologies the report floated were expert review
and downstream-task validation; the protocol picks expert review as the
only primary and explicitly rejects transfer-retrodiction as a
secondary (confounded enough to quietly substitute a different question
for the one being asked). The comparison arm is role+minutes rather
than Baseline C because team continuity is meaningless for recruitment
— the honest cheap alternative is a spreadsheet heuristic, and the
claim only matters if B beats it in expert eyes.

**How to apply:** the protocol document is the pre-registration —
execution must follow it or publish deviations; the primary metric and
the three failure criteria (claim / instrument / floor) cannot be
swapped after ratings exist. A null or failed result is publishable and
closes the question honestly.

---

## D017 — 2026-07-23 — The 3,603-vs-4,299 players "discrepancy" is an arithmetic error in the source paper

**Decision:** close Known Limitation #6 / Recommended Next Experiment #5
(beads `scoutlens-6w8`) as **fully reconciled, with the residual bounded
to the source paper itself**, and pin the reconciliation with
`tests/data/test_player_counts.py`.

**Why:** every counting definition was reproduced from primary sources
(the paper's PDF, Table 1) against the local data:

- Counting **distinct rostered players (lineup+bench) per competition**
  reproduces the paper's Table 1 `#players` column *exactly*, all seven
  values: 619 (Spain), 603 (England), 686 (Italy), 537 (Germany),
  629 (France), 736 (World Cup), 552 (Euro).
- Those values sum to **4,362**. The paper's totals row prints
  **4,299** — which matches neither its own column sum nor the distinct
  union nor any other constructible definition. The "4,299 total
  players" is an arithmetic/typographic error in the paper.
- The true distinct union is **3,618** = 3,603 players.json profiles
  + 15 rostered-but-unprofiled players, all of whom are unused bench
  players (0 minutes, 0 events — verified) and therefore irrelevant to
  every published ScoutLens number.

**How to apply:** the dataset is complete for every purpose this project
uses it for; no correction to any published number is needed. The three
data-gated tests keep the reconciliation true (per-competition counts,
the 4,362/3,618 arithmetic, and the harmlessness of the 15 unprofiled
players). Anyone citing the dataset's size should cite 3,603 profiled
players (or 3,618 rostered), never 4,299.

---

## D018 — 2026-07-23 — Cluster-aware bootstrap: the headline CI survives team- and league-level resampling

**Decision:** close Known Limitation #12 (beads `scoutlens-n44`) as
**checked, conclusion unchanged**: `bootstrap_mrr_delta_clustered`
(retrieval.py) resamples whole clusters instead of independent queries,
and robustness-checks.md Check 6 reports it beside the published
interval. The i.i.d. interval stays the published headline, explicitly
labeled approximate; the clustered intervals are the calibration check,
not a replacement.

**Why:** queries share teams and leagues, so the i.i.d. bootstrap's
independence assumption was a documented but untested caveat. Results
(same seed/resamples as the published numbers, from
config/experiment.json): i.i.d. CI [0.2083, 0.2479]; team-clustered
(98 clusters, the meaningful unit) [0.2044, 0.2525] — ~23% wider;
league-clustered (5 clusters — far too few for a calibrated bootstrap,
reported as a stress test only) [0.1952, 0.2510]. The MRR delta of
0.2283 stays far from zero under every resampling scheme, so
Limitation #12's "likely survives a more conservative interval" is now
verified rather than assumed.

**How to apply:** any future headline CI on paired retrieval deltas
should report the team-clustered interval alongside the i.i.d. one
(Check 6's pattern); the function raises on queries missing a cluster
assignment rather than silently dropping them. Unit tests cover
determinism, input-order independence, the single-cluster degenerate
case, unmapped-query rejection, and point-estimate agreement with the
i.i.d. bootstrap.

---

## D019 — 2026-07-23 — Code license: MIT

**Decision:** the repository's code is licensed under the MIT License
(beads `scoutlens-3y8`, a user decision — chosen by the user 2026-07-23
from MIT / Apache-2.0 / AGPL-3.0 / all-rights-reserved).

**Why:** ScoutLens is publicly positioned as a research/portfolio
project; MIT maximizes readability and reuse with zero friction, and a
permissive license on the code does not constrain the author's own
future commercialization of it. The choice deliberately does not touch
the data side: Wyscout-derived data remains CC BY 4.0 (attribution per
DATA_LICENSES.md), and any StatsBomb-derived work keeps that source's
non-commercial + attribution constraints (D014) regardless of the code
license.

**How to apply:** LICENSE at the repo root; `license = "MIT"` in
pyproject.toml; README's license section updated. Known Limitation #9
in feasibility-report.md is closed. Any published analysis still
carries the applicable *data* attribution obligations — MIT covers the
code only.

---

## D020 — 2026-07-24 — StatsBomb feature-compatibility map: GO with a bounded redesign

**Decision:** clear `scoutlens-8mc.4` (the design gate before the
StatsBomb pipeline) with **GO, conditional on a frozen redesign**. Full
inventory and rules: [`statsbomb-feature-compatibility.md`](statsbomb-feature-compatibility.md).

**Why:** verified each of the 32 v0.1 feature concepts against a real
StatsBomb 2015/16 events + lineup file (match 3754217), not the spec
alone. Of the 32: 22 map directly, 6 by defensible approximation, 1 is
unavailable (`smart_passes_p90` — Wyscout-proprietary), 1 is
structurally non-comparable (`events_p90` — StatsBomb's event taxonomy is
far denser: native Ball Receipt / Carry / Pressure inflate any
total-event count), and 2 shift construct (the carry family: StatsBomb
has a **native Carry event**, so what Wyscout measured by an Acceleration
proxy is measured natively here). No NO-GO condition surfaced.

Six structural differences documented and given frozen handling rules:
event taxonomy (denser), coordinates (120×80 → normalize to Wyscout
0–100 and reuse thresholds), possession (StatsBomb native → secondary set
only), lineup/minutes (interval-based, cleaner than the Wyscout
reconstruction), identifiers (disjoint namespaces → the replication is
within-StatsBomb compared at the aggregate-metric level, not a
cross-provider player merge), and missingness (StatsBomb encodes
outcome-by-presence, inverting Wyscout's accurate/not-accurate tag pair;
shots are cleaner — no GK-conceded contamination).

**How to apply:** two disjoint sets are frozen. The **canonical shared
set** (28 features = 22 Direct + 6 Approx, excluding the Unavailable and
Non-comparable ones) drives the like-for-like replication, with
normalization/eligibility/standardization/retrieval rules pinned
identical to v0.1 so the comparison is clean; the carry construct-shift
is kept but must be flagged in every comparison. The **provider-native
secondary set** (native xG, Pressure-based pressing, possession-sequence
involvement, freeze-frame features) is analyzed separately and must never
silently widen the canonical set. `8mc.2` may now build the pipeline
against open-data commit b0bc9f22dd, competitions {2,7,11,12} × season 27.

---

## D021 — 2026-07-24 — StatsBomb pipeline: provider-scoped ingestion, interval-union minutes, validation

**Decision:** implement the StatsBomb ingestion / minutes / validation
pipeline (beads `scoutlens-8mc.2`) as a **separate package**
(`src/scoutlens/statsbomb/`) that shares no code with `scoutlens.data.*`,
so both providers stay independently reproducible and all Wyscout
behaviour is untouched. Schema and reproduction:
[`statsbomb-pipeline.md`](statsbomb-pipeline.md).

**Why:** the frozen comparison design (D020) requires StatsBomb-native
parsing — a denser event taxonomy, 120×80 coordinates, outcome-by-
presence, and interval-based lineups. Two findings shaped the code:

1. **The StatsBomb match clock overlaps across periods** (period 1 ran to
   48:38, period 2 restarts at 45:00 in the reference match), so a naive
   final-whistle-minus-kickoff over-counts. Minutes are summed per period
   with each stint clipped to its `[Half Start, Half End]` bounds.
2. **Lineup files occasionally record overlapping stints for one player**
   (Coquelin in match 3754217: an injury off-and-on plus a tactical-shift
   position that outlives his own substitution). Summing stints would
   credit >100% of a match; the pipeline **unions** per-period intervals
   instead and flags the row `overlap_merged` rather than smoothing it.
   Validation warns if the flag rate is high.

**How to apply:** `uv run python -m scoutlens.statsbomb.ingestion`
materializes the four-league 2015/16 processed set (~5 GB, pinned to
open-data commit b0bc9f22dd); raw and processed StatsBomb data stay
gitignored per the licence (D014). Event frames use an explicit schema
(inference overflows at scale). 25 StatsBomb tests (unit + malformed-
input + real-sample integration) pass; the full-scale download is the
entry step of 8mc.3, deferred until that experiment runs.

---

## D022 — 2026-07-24 — External replication executed: the v0.1 signal replicates on StatsBomb 2015/16

**Decision:** close the external-replication experiment (beads
`scoutlens-8mc.3`) with **the v0.1 signal replicates, at somewhat lower
magnitude**. Full results and side-by-side:
[`statsbomb-replication.md`](statsbomb-replication.md);
`artifacts/statsbomb_replication_results.json`.

**Why:** ran the full v0.1 temporal-stability battery on the StatsBomb
four-league 2015/16 processed set (1,061 eligible player×competition,
5.3M events) using the frozen canonical 28-feature set (D020), reusing
the provider-agnostic evaluation layer with `feature_columns=CANONICAL`.
Results:

- **Global:** Baseline B (28 features + cosine) MRR 0.203, median rank 19,
  vs Baseline A (role+minutes) MRR 0.038 — delta 0.165, 95% CI
  [0.146, 0.185], confidently non-zero (~5.3× vs Wyscout's ~10×; absolute
  MRR 0.20 vs 0.25). **Holds within role** (B MRR 0.227), the v0.1
  pattern.
- **Team-continuity confound reproduces:** Baseline C (role+team+minutes)
  MRR 0.602, median rank 2 — beats B ~3×, same as Wyscout (D010).
- **Transferred players (n=19):** C collapses to chance (MRR 0.028); B
  retains a *positive* edge over A (delta 0.054) but the CI includes zero
  [−0.004, 0.124] — inconclusive at small n, and weaker in point estimate
  than Wyscout's n=26. The larger-sample need is unchanged.
- **Sensitivity:** the +2 native-carry variant (30 features) lifts global
  B to 0.227 — a measurement improvement (StatsBomb sees carrying
  natively), reported separately and kept out of the primary 28 exactly
  so it can't be mistaken for a method effect. Also corrected the D020
  "28 vs 30" wording (the construct-shift carries are held *out* of the
  primary set).

**How to apply:** nothing overturns Gate 2; this strengthens its
external-validity side while preserving the same honest boundary on the
transferred-player / recruitment-usefulness question (still the top
follow-up, now via `h00` and a larger transferred sample). Provider
comparison is at the aggregate-metric level only (disjoint id namespaces,
D020 §5). Artifact versioned + snapshot-tested (`test_artifacts.py`).

---

## D023 — 2026-07-27 — Recruitment-study execution harness built (ratings collection is the human-in-the-loop remainder)

**Decision:** build the full execution harness for the recruitment
study (beads `scoutlens-h00`) — blinded shortlist generation + the
pre-registered analysis pipeline — and stop where honesty requires a
human: real expert ratings. Harness: `src/scoutlens/study/`; doc:
[`recruitment-study-harness.md`](recruitment-study-harness.md). `h00`
stays open pending real ratings.

**Why:** h00 is the first issue allowed to support/reject a *recruitment
usefulness* claim, which same-player retrieval (v0.1) and the external
replication (D022) cannot. That requires human judgement in the loop; an
agent cannot recruit scouts or fabricate ratings without invalidating the
study. So the honest, high-value move is to make the study *runnable* —
generate the materials and implement the analysis — leaving only data
collection.

- **Shortlists** (`shortlists.py`): 40 role-stratified queries (10 per
  role) from the frozen Wyscout data (CC BY 4.0 — cleaner than StatsBomb
  for rater-facing cards); three mutually-exclusive arms of 5 —
  B (cosine top-5), C_role (role+closest-minutes), R (random same-role);
  query player + his own true-match excluded; 15 candidates merged and
  shuffled with **no arm labels**, arm key stored separately. Verified on
  real data: blinded, 200/200/200 arm balance, 15 distinct per query.
- **Analysis** (`analysis.py`): the pre-registered plan implemented
  without scipy — paired B−C_role Wilcoxon signed-rank + bootstrap CI
  (primary), interval Krippendorff α (reliability gate 0.40), secondary
  metrics, and the three failure criteria → GO/REDESIGN/NO-GO. Unit-tested
  incl. a hand-computed Krippendorff α (0.85) and synthetic
  GO/NO-GO/REDESIGN/floor scenarios.

**How to apply:** `uv run python -m scoutlens.study.shortlists`
regenerates the materials; a human recruits 2–5 raters, collects ~600
ratings/rater (5-query discarded pilot first), then `analyze_study`
produces the outcome. Study materials stay under `artifacts/` (gitignored,
regenerable). Only after real ratings can h00 close with a
GO/REDESIGN/NO-GO on recruitment usefulness.

---

## D024 — 2026-07-27 — Ratio-shrinkage experiment (v0.2): pathology real per feature, immaterial to retrieval

**Decision:** run the ratio-shrinkage experiment (beads `scoutlens-dul`,
Known Limitation #11) as an **additive comparison** that leaves the v0.1
catalog frozen, and — on the null result — **not** adopt shrinkage into
the default features. Full result:
[`shrinkage-experiment.md`](shrinkage-experiment.md);
artifact `shrinkage_experiment_results.json` (versioned + snapshot-tested).

**Why:** the 7 `*_pct` ratio features are over-trusted at low attempt
counts (1-of-1 = 1.0). Empirical-Bayes Beta-Binomial shrinkage
(`features/shrinkage.py`) fits a Beta prior per ratio and reports
`(k+α)/(n+α+β)`. It does exactly what Limitation #11 asks per feature
(low-sample ratios pulled toward the mean by up to 0.75), but Baseline B
retrieval barely moves — global MRR 0.2539 → 0.2512, median rank 16 → 15;
within-role 0.2787 → 0.2770, median 12 → 11. The raw arm reproduces the
v0.1 headline **exactly** (0.2539), confirming the plumbing. The null is
consistent with the distributed-signal finding (robustness Check 5): no
single ratio carries the result, so standardization+cosine over 32
features already dilutes any one over-trusted ratio.

**How to apply:** shrinkage stays out of the default catalog (complexity
must earn its place); the implementation is retained for any future use
that reads individual ratios directly (per-player interpretation,
scout-facing cards, a feature-weighting model). Aggregation gained a
purely-additive `with_counts=True` (default byte-identical to v0.1) to
expose the numerator/denominator counts. Limitation #11 is resolved:
characterized, fixed, and its (non-)effect measured.

---

## D025 — 2026-07-28 — Reproducibility contract extended to all published experiments

**Decision:** make `config/experiment.json` version 2 the single parameter
source for all five published result artifacts and require every artifact to
carry the D015 `_manifest` contract. The StatsBomb replication now reads its
Wyscout reference from the versioned Gate-2 artifact instead of duplicating
headline constants. The opt-in fresh-run drift suite covers the original
three Wyscout artifacts, StatsBomb replication, and ratio shrinkage.

**Why:** D022 and D024 added valuable experiments but bypassed part of the
reproducibility machinery they were documented as inheriting: their settings
were hardcoded, their artifacts had no full manifest, and the drift suite did
not regenerate them. Separately, three StatsBomb integration tests referenced
one developer's temporary absolute path, so they silently skipped elsewhere.
Those are presentation and auditability failures even though the numerical
results themselves reproduce exactly.

**How to apply:** changing any published parameter requires editing
`config/experiment.json`, regenerating the affected artifact, and running
`SCOUTLENS_DRIFT=1 uv run pytest tests/evaluation/test_artifact_drift.py`.
StatsBomb provider integration uses schema-faithful synthetic fixtures in CI;
licensed raw data stays local. The quality workflow installs from `uv.lock`
with `--frozen`, tests Python 3.11 and 3.14, and runs Ruff, Mypy, and a package
build.

---

## D026 — 2026-07-28 — Flagship thesis: an evidence-first Player Fingerprint Lab

**Decision:** reposition ScoutLens from a completed feasibility spike into an
evidence-first Player Fingerprint Lab. The public claim is temporal stability
of individual statistical fingerprints — not recruitment usefulness, transfer
success, player quality, or proof of playing style. The Wyscout-derived public
showcase will make the fingerprint, feature evidence, confounders, replication,
and uncertainty explorable. StatsBomb remains aggregate replication evidence
because of its non-commercial and redistribution constraints.

**Why:** Gate 2, the robustness battery, and external replication are already a
strong portfolio-grade scientific foundation. Requiring 2–5 unknown scouts to
complete the optional recruitment study would optimize for a stronger claim the
flagship does not need while delaying the missing deliverable: a clear public
experience. The completed harness still demonstrates honest human-in-the-loop
design and is preserved, but `scoutlens-h00` is deferred and no longer blocks
modeling work.

**How to apply:** the flagship roadmap is Beads epic `scoutlens-jtt`. Its order
is reproducibility → public narrative → typed showcase/vertical-slice spec →
interactive application → uncertainty and evidence-grounded AI → learned-metric
benchmark → release. The first web implementation is static-first; any backend
or advanced model must earn its operational or measured value.

---

## D027 — 2026-07-28 — Manifests identify dirty source trees exactly

**Decision:** extend every experiment `_manifest` with `git_dirty` and a
deterministic `source_sha256` over the relative paths and bytes of every Python
module under `src/scoutlens/`. Keep `git_commit` as the human-navigable anchor,
but do not treat it as a complete source identity when the working tree is
dirty.

**Why:** an artifact can legitimately be regenerated before its implementation
is committed. Recording only `HEAD` then points to a revision that does not
contain the code that produced the numbers. Input and config checksums cannot
close that gap. The source-tree digest makes the exact scientific code state
comparable without making artifacts self-referential; `git_dirty` makes the
reason for a commit/hash mismatch explicit.

**How to apply:** compare `source_sha256`, `config_sha256`, and every input hash
when auditing two runs. Use `git_commit` to navigate history and `git_dirty` to
decide whether that commit alone is sufficient. Regenerating any of the five
published artifacts must refresh all four provenance dimensions together.

---

## D028 — 2026-07-28 — Full-catalog, static-first flagship contract

**Decision:** make the first Player Fingerprint Lab a three-route static
experience over the complete 1,257-unit Wyscout Gate-2 population. Python owns
features, scalers, retrieval, neighbors, additive cosine evidence, caveats, and
later uncertainty; the TypeScript application consumes immutable JSON through
the versioned `scoutlens.showcase/1.0.0` contract. The Lab separates same-player
identity retrieval from a five-item, self-excluded statistical-neighbor view.

**Why:** a small curated demo would be easier but would introduce selection
ambiguity exactly where the research claims population-level evidence. A full
static catalog is still operationally small and makes the portfolio stronger.
Separating retrieval from neighbors prevents “the model recognizes the same
player” from being misread as “the model recommends similar signings”. Keeping
scientific computation in Python creates one audited source of truth and a
clean future seam for an API without requiring backend operations now.

**How to apply:** implement Beads `scoutlens-jtt.4` against
[`flagship-vertical-slice.md`](flagship-vertical-slice.md) and
[`showcase-artifact-contract.md`](showcase-artifact-contract.md). The first
slice must represent uncertainty as explicitly pending; `scoutlens-jtt.5`
fills the predeclared match-bootstrap fields without redesigning the UI
contract. AI remains optional and consumes evidence IDs only after both layers
exist.

---

## D029 — 2026-07-28 — Exact cardinality for v1 confidence intervals

**Decision:** require exactly two numeric bounds in all five confidence-interval
arrays declared by `scoutlens.showcase/1.0.0`, while continuing to allow `null`
for unavailable uncertainty. Keep the contract version unchanged because this
pre-release correction rejects only malformed arrays that the exporter has
never produced. Regenerate the web schema, TypeScript types, and public manifest
so their provenance records the corrected schema.

**Why:** `prefixItems` with `items: false` limited an interval to at most two
items but still admitted empty and one-bound arrays. That contradicted the
documented tuple shape, the Python builders, and strict Ajv tuple validation.
Adding `minItems: 2` and `maxItems: 2` makes the scientific boundary explicit
without changing any valid artifact shape, dataset value, or numerical result.

**How to apply:** every confidence interval in the v1 contract is either `null`
or a two-number array. Future contract edits must keep Python validation, strict
Ajv compilation, generated TypeScript types, and the published manifest in
lockstep. A change to interval meaning or estimation remains a separately
versioned scientific decision.

---

## D030 — 2026-07-28 — Content-addressed showcase payload distribution

**Decision:** distribute the 1,257 manifest-declared player profiles as one
deterministic `tar+gzip` GitHub Release asset instead of committing 147 MB of
repetitive JSON or requiring provider data during a web build. Pin the dataset
version, archive byte count, SHA-256, path count, filename, and HTTPS location
in `config/showcase-payload-pack.json`. The release tag and content-addressed
filename are immutable publication identifiers by policy; the digest remains
the consumer's authority.

**Why:** the complete profile population is required for an honest flagship,
but its source JSON is inappropriate for code review and Git history. A compact
derived-data pack preserves clean-clone builds and the full population while a
fail-closed hydrator prevents a mutable or malformed download from silently
becoming application data. The pack contains only public derived aggregates;
raw Wyscout/Pappalardo rows remain excluded.

**How to apply:** build archives only from validated exporter output, with
sorted paths and normalized archive metadata. Hydration must verify the pinned
archive size and digest, reject unsafe or non-manifest paths, verify every
profile's manifest size and SHA-256 in staging, and atomically replace
`public/showcase/v1/players` only after all checks pass. A changed payload or
dataset requires a new content-addressed filename and release pin.

---

## D031 — 2026-07-29 — Match-bootstrap v1 is frozen before execution

**Decision:** preregister `match_bootstrap_v1` before inspecting production
uncertainty results. Resample whole matches with replacement inside frozen
competition-period strata; keep the observed 1,257-profile cohort fixed; use
500 draws from seed 1729; rebuild minutes, all 32 features, the combined-period
scaler, percentiles, similarities, ranks, and observed-neighbor stability; and
publish type-7 95% percentile intervals only with at least 450 valid replicate
observations. The normative method is
[`uncertainty-method.md`](uncertainty-method.md), with machine pins in
[`config/uncertainty.json`](../config/uncertainty.json).

**Why:** sampling already-aggregated players would ignore match dependence,
while silently dropping players absent from a replicate would make stability
look better than it is. The fixed universe therefore keeps missing candidates
in the denominator and ranks them after present candidates; an absent query
invalidates only that subject-replicate. Duplicate matches weight both events
and minutes by their multiplicity. These decisions, the missingness rules,
ordering, quantile algorithm, and tolerances are fixed before real results so
the method cannot be tuned toward a cleaner portfolio story. Counter-addressed
SHA-256 rejection sampling makes every draw independent of Python version,
execution order, and partial failures while avoiding modulo bias.

**How to apply:** implement Bead `scoutlens-jtt.5.2` against the versioned
config and the synthetic truth fixture under `tests/uncertainty/fixtures`.
Generate the complete deterministic draw plan before computing subjects,
record its hash and invalid-reason counts, and fail closed on contract drift.
`scoutlens-jtt.5.3` may fill the existing showcase fields but may not change
their estimands. Any analytical change requires a new design version and
decision before production re-execution.

---

## D032 — 2026-07-29 — Bootstrap memory is bounded by projected streaming aggregation

**Decision:** preserve `match_bootstrap_v1` unchanged and bound its memory by
projecting only consumed Parquet columns, aggregating the 3.25 million event
rows through a lazy/streaming Polars plan, and reading checkpoint columns in
narrow feature/retrieval/neighbor projections during summarization. Keep both
worker counts supported. The production reference uses two workers and records
500/500 completed resamples in 50.83 seconds, 1,134,657,536 bytes peak RSS,
288,373,735 checkpoint bytes, and 1,664,262 final Parquet bytes on Windows.

**Rationale:** the first correct eager implementation met the 15-minute target
but breached the 4 GiB limit with both two workers (52.06 seconds,
4,991,041,536 bytes) and one worker (63.52 seconds, 4,991,221,760 bytes).
Phase isolation showed that preparation alone could peak at 4,994,580,480
bytes, so reducing concurrency or merely separating execution from summary
could not solve the underlying materialization. Column projection lowered
eager preparation to 4,193,447,936 bytes; lazy/streaming sufficient-statistic
aggregation lowered it further to 1,129,742,336 bytes. The optimized full run
retains 74% headroom under the frozen memory ceiling and finishes in under one
minute.

**Alternatives considered:** one worker was rejected because it was slower and
had the same peak. Process-isolated replicate/summary stages were rejected
because the eager preparation already exceeded the limit and would add
orchestration without addressing the cause. Reducing the 500 draws, changing
the cohort, weakening validity, or relaxing the 4 GiB threshold was ruled out
because it would change or evade the preregistered contract. A more complex
external compute backend was unnecessary after local streaming met both
targets.

**How to apply:** build per-match sufficient statistics through the canonical
feature expressions; never introduce a second feature implementation. A memory
optimization is acceptable only when worker-1, worker-2, reversed-input, and
resume tests agree and the three summary Parquets remain byte-identical. The
reference SHA-256 values are
`77838def0b4eb0fca2628f18a0b1e0ee12cc1a4d55fc7a742bc6029246485b9c`
(features),
`7cafb989f9bf9c1ad58f76b22175f8bb9afb57ea3e1a62502a50eebd5f6f247d`
(retrieval), and
`8d88ca823c494ec665470331a8322a2d101455551887d0c6724f0570f37dbcb9`
(neighbors) across eager worker-1, eager worker-2, and streaming runs. The CLI
must record both target booleans; a future breach fails the gate and requires a
new decision rather than silent degradation. Checkpoint reuse remains
fail-closed on the exact manifest, so a source change requires fresh production
checkpoints.

---

## D033 — 2026-08-04 — Frontend delegation contract and CSS ownership layers

**Decision:** freeze `frontend-agent-contract.md` as the authority for any agent
executing a `scoutlens-uze` child, and select an eight-file, selector-driven split
of the 2,654-line `web/src/app/globals.css` in a fixed cascade order: tokens,
base, primitives, shell, research-story, landing, science, lab.
`globals.css` becomes an import manifest only.
Ownership is expressed as an allow / conditional / deny table covering every
current frontend directory, with a named reviewer for every conditional entry.
Generated contracts, published showcase artifacts, research outputs, frozen
configs and the Python pipeline are denied outright, and a bead that needs one
of them stops rather than bundling the change.

**Rationale:** the stylesheet has no section markers and ownership interleaves
throughout — lab rules occupy lines 1091–2441 while landing, science and shared
research-story rules are scattered from 165 to 2518 — so parallel delegation
without a file map would have two beads editing the same lines. The split is
component-driven rather than route-driven for one case that matters:
`research-story.tsx` renders on both landing and `/science`, so a route-named
file would give `scoutlens-uze.4` and a future landing bead a competing claim on
the same 79 rules. Keeping the lab as one file keeps `scoutlens-uze.5`
disjoint from `scoutlens-uze.4`, which is what makes them parallelisable.

The reorder was checked before being frozen. A per-owner split cannot preserve
global source order, and reordering changes rendering when two rules can match
the same element, declare the same property and have equal specificity. Static
analysis over all 473 selectors under the chosen order found zero such pairs and
zero unassigned selectors. It also found 22 fully dead rule blocks — 2,839 bytes, 5.6%
of the stylesheet — whose classes no component renders, plus two partially dead
shared selector lists.

**Alternatives considered:** inferring ownership per task was rejected because
the user requires low-interpretation handoff. CSS-only permission was rejected
because responsive hierarchy and accessibility sometimes require semantic markup
changes. Permitting all of `web/**` was rejected because generated contracts,
artifact copies and the evidence-loading boundary are scientifically sensitive.
A design-system rewrite first was rejected as scope. Within the split, `@layer`
and `:where()` were rejected: both change cascade semantics, so a mechanical move
could no longer be proved visually neutral. A route-named `landing.css` /
`science.css` pair owning the research-story rules was rejected for the
concurrency reason above. Splitting the 206-rule lab layer into selector,
profile and neighbor files was rejected after measurement: 11 selector lists span
two or three of the proposed files, so the split would duplicate and reorder
declarations during the one pass that must not change rendering, and it buys no
concurrency because a single bead owns the whole Lab.

**How to apply:** implement `scoutlens-uze.3` as a pure move — intra-layer source
order preserved verbatim, media queries distributed into their owning layer with
the `64rem` block before the `48rem` block, no declaration edited or reformatted.
Delete the 22 fully dead blocks rather than carrying them, and split the two
partially dead shared selectors: `.step-list span, .research-step__marker` (line 419) keeps its
live marker half, and the `48rem` group at line 2488 keeps its `.experiment-grid`
halves. `.experiment-card--*`, `.caveat--*`, `.research-stage--*` and
`.lab-state--*` are composed at runtime through template literals and are live
despite looking unreferenced to a grep. Acceptance is a byte-identical
`getComputedStyle()` diff over every element on every route and audited state,
before and after — the static result is conservative, not a proof, and a
screenshot comparison cannot see a sub-pixel cascade change.
---

## D035 — 2026-08-07 — Chance-level control pins MRRs to the design floor

**Decision:** add a chance-level control (SLS-024) as the sixth versioned
result artifact (`chance_control_results.json`). Every published MRR is now
reported against the design's uniform-random-target floor H_N/N (harmonic
mean of reciprocal ranks), with a seeded empirical permutation null (10,000
draws) and an empirical p-value. Implementation: `evaluation/chance_level.py`
+ `evaluation/run_chance_control.py`; writeup: `docs/chance-level-control.md`.

**Why:** the existing artifacts answer method-vs-method (Baseline A/B/C)
and delta-CI questions, but never "how far above *pure design luck* is this
MRR?". A 41x and a 1.6x lift mean very different things, and the chance
level makes them comparable on one absolute axis. Key result: Baseline C,
which shows a 96x lift in the general population, collapses to 1.6x
(p = 0.116, not distinguishable from chance) for transferred players, while
Baseline B holds a 38.9x lift (p < 0.0001) against the same floor. The
team-continuity reframing (D010) is now measured on the chance-level axis.

**How to apply:** any future MRR number must be published next to its
chance level and lift; regenerating the five prior artifacts plus this one,
with the drift suite covering all six, is the completeness test. The null
p-values at n=26 transfer queries are coarse — augment with a larger
sample, per the existing next-experiment priority.

---

## D036 — 2026-08-07 — `.beads/` stays untracked; D-record `scoutlens-dij` is superseded

**Decision:** `.beads/` remains fully untracked, as `3ef206c` left it. The
earlier policy recorded in the agent instruction files — "`.beads/issues.jsonl`
is tracked in git deliberately, so backlog changes ride along with PRs as
reviewable diffs" (`scoutlens-dij`, 2026-07-23) — is superseded and must not be
reinstalled when the agent instruction files are restored from
`../ai-workflow-template` (`scoutlens-iex.1`).

The Dolt database remains the source of truth. Backlog durability is carried by
`bd dolt push` to `refs/dolt/data` on the git remote, not by a tracked export.

**Why:** the two records cannot both hold, and the newer one is both broader and
already executed. `3ef206c` untracked roughly ten scaffolding paths on one
principle — the repository contains the project and what a clean clone needs to
run it, not the tooling used to build it. Reverting a single file out of that
set would leave the boundary incoherent while keeping none of its benefit.

The durability argument that motivated `scoutlens-dij` is satisfied by a
different mechanism that is verified working here: `refs/dolt/data` exists on
`origin`, and `core.longpaths` is set globally, so the documented Windows
failure mode for `bd dolt push` (embedded Dolt cache paths exceeding 260 chars,
surfacing as a misleading `Filename too long` wrapped in credential hints) does
not apply on this machine.

The reviewable-diff argument is weaker than it first appears. `issues.jsonl` is
a passive export, currently 324 KB, and the same policy that tracked it also
forbids hand-merging it on conflict — take the newest export or regenerate from
the DB. A diff that may not be merged is a poor review artifact, and a large
generated file in every PR crowds out the changes a reviewer is there to read.

**Cost accepted:** tracking gave an incidental off-machine backup for free.
`bd dolt push` is manual, so untracking transfers that cost to a habit. Left
implicit, this recreates precisely the failure the workflow template exists to
prevent — its own README records the orchestrator having lived three weeks only
on one machine, unversioned. The decision is "untracked **and** pushed
explicitly", not "untracked".

**How to apply:** when installing the agent instruction files from the template,
replace the JSONL policy paragraph with this decision rather than copying it
forward, and do not re-add `.beads/` to `.gitignore` exceptions. Run
`bd dolt push` at the end of any session that changed the backlog; treat an
unpushed backlog the same way as uncommitted code. The contradiction also
exists upstream in `../ai-workflow-template/project-files/CLAUDE.md`, where it
would propagate to every future project installed from the template —
`scoutlens-iex.7` owns correcting it there.

---

## D037 — 2026-08-08 — Identity strings are unescaped once at the showcase producer boundary

**Decision:** normalize literal `\uXXXX` escape text in player, team, and
competition identity fields exactly once, before showcase artifact
construction, rather than decoding per-view in the web application
(`scoutlens-jtt.12`). Decode only well-formed four-hex-digit escapes;
ordinary backslashes and malformed escape text are preserved verbatim. The
showcase validator rejects any remaining literal escape in identity fields
fail-closed, and the web-only decode workaround (`decodeIdentityText` /
`decodeEscapedUnicode`) is removed.

**Why:** the Wyscout provider data itself contains literal escape text
(2,081 player fields and 8 team names, e.g. `\u00c1. Correa` and
`Atl\u00e9tico Madrid`), which the canonical UTF-8 writer emitted verbatim.
The web layer worked around it per-component, which duplicated decode logic,
let index sorting collate on escape text instead of display text, and left
artifact consumers outside the web app (API, future AI layer) with the raw
escapes. Normalizing once at the producer boundary keeps artifacts
self-describing and every consumer on the same value.

**Impact:** the regenerated dataset publishes real UTF-8 names with the new
content-addressed version `wyscout-2017-18-v1-31d2ccc6af37`; 205 team names
and 266 of 1,257 display names changed on screen-equivalent bytes. The
payload pack was rebuilt, repinned (`config/showcase-payload-pack.json`),
and published as a new immutable release asset per D030. Index sorting now
collates on display text (e.g. `A. Aquilani` sorts before `Á. Correa`
instead of after the escaped form). All values, metrics, ranks, and evidence
are numerically identical to the prior export — only identity text bytes
changed.

**How to apply:** any future identity-bearing source or pipeline change must
normalize through `scoutlens.showcase.builder.normalize_identity_text` and
satisfy the fail-closed validator; do not reintroduce per-view decoders in
the web layer. A changed dataset still requires a new content-addressed
payload pin and release asset before the pin test can be updated.
