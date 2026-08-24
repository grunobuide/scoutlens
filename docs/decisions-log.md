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

## D034 — 2026-08-06 — Public narrative and information architecture frozen for the flagship

**Decision:** adopt [`public-experience-narrative.md`](public-experience-narrative.md)
(specification 1.0.0) as the single authority for beginner-facing product copy
and information architecture of the Player Fingerprint Lab, before any page or
visual redesign. The entry audience is the curious non-specialist; deeper-audit
audiences are technical hiring managers, engineers, and data scientists. The
flagship keeps three routes — `/`, `/lab/`, and the retained `/science` URL —
with frozen navigation labels **Overview**, **Fingerprint Lab**, and **How it
works** (the `/science` route keeps its URL; only the label changes on
implementation). The spec freezes one plain-language thesis with a mandatory
boundary sentence, a 30-second explanation, and six timed comprehension
questions whose canonical answers cite artifact identifiers; a vocabulary
progression and a route/claims/copy matrix bound every later writer and
delegated frontend agent. The spec adds no result values: headline numbers
remain owned by `scoutlens.showcase` artifact fields and are referenced by
`metric_id`, never duplicated.

**Why:** the current public experience contains strong evidence but assumes
technical context too early, and a visual redesign without a frozen explanatory
sequence would create a second, inconsistent scientific narrative. A separate
`/about` page would duplicate `/science` and split provenance links; an
expert-only `/science` with a simplified landing would leave metric
definitions, sources, and limitations without a durable public home; and letting
an implementing frontend agent invent copy in place would mix product,
scientific, and visual authority into one unreviewable change. Freezing the
content contract first keeps scientific authority with the artifacts and gives
delegated implementation beads a bounded, reviewable spec.

**Alternatives rejected:**

1. Add a separate `/about` page — rejected: would duplicate the science route,
   split provenance links across two pages, and create two competing
   explanations.
2. Keep `/science` expert-only and simplify only the landing — rejected: metric
   definitions, sources, and limitations still need a durable public home, and
   beginner readers would not be able to follow the audit trail.
3. Let the implementing frontend agent invent copy in place — rejected: mixes
   product, scientific, and visual authority and is not reviewable as one
   decision.

**Review boundary:** this specification is normative until a later decision-log
entry supersedes it. Any change to the thesis, glossary progression, route
ownership, CTA order, or navigation labels requires a new decision entry. If a
plain-language formulation changes a frozen claim, omits the team-context
confound, implies current scouting, or cannot cite an existing evidence ID,
stop and request scientific review; do not resolve the conflict with softer or
more promotional wording (the spec's stop condition).

**How to apply:** implementation beads consume the spec: `scoutlens-9a3.5`
(identity-challenge contract) reads §2, §4, and §7; frontend copy work applies
the frozen navigation label, secondary CTA, and glossary surface rules without
new CSS or copied results; `scoutlens-jtt.6` AI narration is bounded by §8 and
the `scoutlens-jtt.6.1` evidence-bundle contract; `docs/case-study.md`
(`scoutlens-jtt.7.3`) consumes the same thesis and adds narrative, not data.
Tracks Beads `scoutlens-9a3.1`.

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

---

## D038 — 2026-08-06 — Initial /lab JavaScript budget measures module-browser transfer

**Decision:** the initial-JavaScript portion of the static budget gate
(`web/scripts/check-budgets.mjs`) now counts only `<script>` assets that
module-capable browsers actually fetch — scripts without the `noModule`
attribute. The legacy `noModule` polyfill emitted by the pinned Next.js
runtime (a core-js 3.38.1 + whatwg-fetch bundle; 39,520 gzip bytes in the
2026-08-06 `/lab` production export) is excluded from the measured total but
still asserted present and reported on a separate line, so it can never be
dropped silently. The frozen 204,800-byte cap and every other threshold in
`web/quality-budgets.json` and `web/lighthouserc.json` are unchanged. Measured
result for the frozen showcase export: `/lab` initial JavaScript drops from
the nominal 197,105 to 157,585 gzip bytes (47,215 below the 204,800 cap),
restoring the ≥ 20,480-byte headroom required by `scoutlens-jtt.14`. Initial
`/lab` transfer excluding fonts moves from 302,667 to 263,147 gzip bytes.

**Why:** after full chunk attribution of the 197,105 gzip baseline, the only
project-owned initial chunk is the `/lab` page chunk at 9,145 gzip bytes; the
remaining 187,960 gzip bytes are pinned Next.js/React/Turbopack runtime plus
the legacy-only polyfill. The nominal 184,320 target is therefore unattainable
by project code alone without changing the cap or hacking the pinned runtime —
both prohibited by the issue. The polyfill is not initial JavaScript for any
measured surface: Chromium (Playwright, axe, Lighthouse), every listed target
device, and all module-capable browsers skip `noModule` scripts entirely and
never download the file, so counting it overstated real initial transfer by
about 20% and hid true headroom. Excluding it aligns the gate with the browser
semantics the Lighthouse budget already assumes, without relaxing any
threshold.

**Alternatives rejected:**

1. Keep counting `noModule` scripts and accept ~7.7 KB headroom — rejected:
   the nominal acceptance criterion (≤ 184,320 gzip) could not be met without
   changing a frozen threshold or patching the pinned Next runtime, both
   explicitly out of scope.
2. Patch the Next.js export to drop the legacy polyfill — rejected: mutates
   pinned runtime output, diverges from upstream `next build` evidence, and
   breaks byte-for-byte reproducibility expectations.
3. Raise or relax any number in `web/quality-budgets.json` or
   `web/lighthouserc.json` — rejected explicitly by acceptance criterion 6 of
   `scoutlens-jtt.14`.

**Review boundary:** this definition governs only which scripts the budget
script counts as initial JavaScript; reductions in framework or application
initial transfer remain measured and budgeted. A `noModule` payload is
excluded only when module-capable browsers cannot fetch it, and the gate still
fails if the module script set is empty. Revisit the nominal budget when the
pinned Next runtime stops emitting the legacy polyfill; until then the legacy
line keeps that payload visible and versioned.

**Evidence:** closure of `scoutlens-jtt.14` records the before/after chunk
gzip table (197,105 → 157,585 module-browser total plus 39,520 legacy) and the
full quality run.

---

## D039 — 2026-08-09 — Identity-challenge contract frozen for implementation

**Decision:** adopt [`identity-challenge-contract.md`](identity-challenge-contract.md)
(specification 1.0.0) as the single authority for the deterministic
identity-challenge interaction on `/lab/`. The challenge is a guided reveal of
the temporal retrieval experiment — not a player quiz, recommendation game, or
client-side model — that transitions the user from a plain-language question
through a hidden-identity fingerprint to a rank reveal and contribution
evidence, then into the full Lab explorer.

**Placement:** a dedicated challenge panel on `/lab/`, rendered above the full
Lab explorer, sharing the same route and client bundle. URL states:
`?player=<key>&challenge=query|reveal|evidence`. No separate route. A no-JS
degraded state renders a static result sentence server-side.

**Why:** the Lab exposes the right evidence but begins as a dense dashboard. A
guided reveal makes the scientific question concrete before presenting all
controls. The contract freezes the state machine, copy, artifact bindings,
focus order, error states, and performance budget so the implementation bead
(`scoutlens-9a3.6`) contains no product-design decisions. Every value comes
from the versioned `PlayerProfileArtifact`; no retrieval is recomputed in the
browser. The featured profile is `manifest.featured_profile` with its editorial
selection reason visibly disclosed.

**Alternatives rejected:**

1. Separate `/challenge` route — rejected: fragments the Lab's single-route
   model and duplicates the profile-loading path.
2. Modal overlay on landing — rejected: traps focus and hides the evidence
   surface behind a dialog.
3. Landing-only inline section — rejected: overloads the first-interpretation
   point and delays the CTA to the Lab.
4. Football-name trivia quiz — rejected: recognition skill is unrelated to the
   research question and encourages gamified quality interpretation.
5. Compute candidates live in the browser — rejected: Python artifacts are the
   sole scientific authority.
6. AI chat as primary interaction — rejected: AI would overshadow deterministic
   evidence and create a runtime dependency.

**Review boundary:** this contract is normative until a later decision-log
entry supersedes it. Any change to the state machine, copy, placement, URL
semantics, or allowed artifact fields requires a new decision entry. The
uncertainty behavior is conditional on `scoutlens-jtt.5.4`: until that closes,
the challenge renders the `uncertainty_pending` caveat; after it closes, the
challenge renders the interval from the artifact field.

**How to apply:** implement `scoutlens-9a3.6` against this contract. The
challenge must not increase the `/lab` initial JavaScript gzip total beyond
the frozen 204,800-byte cap (D038). Tracks Beads `scoutlens-9a3.5`; depends
on `scoutlens-9a3.1` (narrative spec, D034), `scoutlens-9a3.2` (explanation
catalog), `scoutlens-9a3.3` (provenance component), `scoutlens-uze.4`
(responsive baseline), and `scoutlens-jtt.5.4` (uncertainty in Lab).

---

## D040 — 2026-08-10 — Modeling-track agent ownership contract frozen

**Decision:** freeze
[`modeling-agent-contract.md`](modeling-agent-contract.md) as the binding
file-ownership contract for every bead labelled `modeling`
(`scoutlens-iex.3`). It mirrors the frontend contract (`D033`): the same three
ownership levels, the same Denied-by-default rule for any unlisted path, and
the same precedence — subordinate to a current user instruction and to
`AGENTS.md` / `CLAUDE.md`, and if the contract and a bead disagree, the bead
loses and the executor stops. It is additionally subordinate to the
`CONTAINMENT` block in `bd_orchestrator.py`. This replaces the placeholder in
`CLAUDE.md` under "Fronteiras de propriedade", which said the modeling
contract was unwritten and `src/scoutlens/**` was therefore non-delegable.

**Why:** the modeling track was already dispatchable — `bd_orchestrator.py`
routes the `modeling` label to `personas/data-scientist.md` behind a
`pytest -q` gate — while having no written boundary. `scoutlens-jtt.12` proved
the gap was not theoretical: it required normalizing identity strings in
`src/scoutlens/**` and then regenerating `public/showcase/**`, a path the
frontend contract classifies as Denied and owns under `scoutlens-jtt`. Without
a rule, an agent either refuses correct work or performs an unreviewable
rewrite of published data. Both are failures.

**Impact:** three points where the classification proposed in the bead was
changed after checking the repository rather than accepted as given.
(1) `schemas/**` does not exist and `configs/**` holds only a `README.md`;
both are listed as reserved-and-Denied so that creating them cannot land in an
unlisted path by accident, and so the near-miss with the live `config/`
directory is explicit. (2) `artifacts/` is split: the regenerable
subdirectories are Conditional regeneration-only, while the recorded
`*_results.json` files are Denied outright — a new run writes a new file and
never overwrites a recorded result. (3) `web/**` stays Denied, but with one
narrow exception (scenario D) permitting deletion of a downstream
compensation that exists solely because of the producer defect the bead fixes,
reviewer `scoutlens-uze`, and only when the rendered text is provably
unchanged. Without that exception `scoutlens-jtt.12` could not have been
executed end to end, which the bead required; with a broader one the contract
would have granted the modeling track presentation reach, which the bead
forbade. The exception is bounded by six conditions and excludes layout,
styling, copy, ordering and any displayed value.

The regeneration rule is the substance: an artifact is only ever the recorded
output of one of eight named module commands, must reproduce byte-identically
on a second run, must produce a diff explainable as the stated change and
nothing else, and ships a six-part evidence packet — including a count of
affected records derived independently of the code that produced the change,
per the D037 standard. Publishing a release asset is outward-facing, so an
agent that cannot perform it stops after rebuilding the pack and hands off
rather than repinning against an asset that does not exist (D030).

**How to apply:** every `modeling` bead fills the §6 handoff template before
starting, and closes against the §7 Definition of Done. `scoutlens-iex.2`
fills the empty "Convenções do projeto" section of
`personas/data-scientist.md` by pointing at this contract rather than
restating it. Changing this contract requires its own bead and a new decision
record; it is Denied to every ordinary modeling bead.

---

## D041 — 2026-08-10 — Player-disjoint representation benchmark preregistered

**Decision:** freeze the confirmatory benchmark for `scoutlens-qop` before
any learned model is fitted, as
[`representation-benchmark-protocol.md`](representation-benchmark-protocol.md)
with the executable copy in `src/scoutlens/benchmark/protocol.py`
(`scoutlens-qop.1`). Protocol hash
`886ba315b587a91d0fa9ab5c7387f172f8957cf2cfde8a39a65216cb4ff31f1d`; split
assignment digest
`715bdb90af59860c2510d6a69f43970c9734bef4e4e061740658d2496c30d96a`;
split seed 2718. Recording that hash here is what opens the test split —
`assert_test_set_unlocked()` reads this ledger and raises otherwise, and any
edit to `PROTOCOL` changes the hash and re-locks it.

KEEP requires all of: Wyscout test delta MRR at least +0.020 over
`baseline_b_cosine`; paired 95% CI lower bound above 0; no role subgroup with
at least 100 queries dropping more than 0.020; StatsBomb external delta
positive with CI lower bound above -0.010; operational budgets pass.
Otherwise DROP. The neural contrastive arm runs only if the interpretable
diagonal model clears validation delta at least +0.010 with CI lower bound
above -0.005.

**Why:** the published temporal-retrieval result is descriptive — it fits the
scaler on the same population it scores, which is right for a feasibility
claim and wrong for a generalization claim. A confirmatory answer needs
held-out humans, statistics fitted on training data only, and a threshold
written down while the answer is still unknown. Two design choices follow
from that and are worth naming because they change what the numbers mean.
The split unit is the **human**, not `(player_id, competitionId)`, so no
model can be fitted on one half of a person and scored on the other. And
candidate pools are **within-split**, so a test query can never retrieve a
training player.

**Impact:** 1,257 eligible players split 753 / 251 / 253, role-stratified,
deterministic by `sha256(f"{seed}:{player_id}")` rather than a shuffled RNG,
so the assignment is order-independent and adding a player perturbs only its
own position. The frozen canonical feature sets — 28 primary, 30 plus-carry
— existed only in prose since D021 and are now executable and self-checking.
Within-split pools mechanically raise MRR: Baseline B scores 0.320 within
-role on train and 0.429 on validation against 0.279 published on the full
population. Nothing improved; the pool shrank from 1,257 to 753/251. **Only
the within-split paired delta is comparable**, and the protocol says so in
three places because it is the easiest thing here to misread.

Fitted scaler statistics are quantized to 12 significant digits. Polars
reduces sums in parallel, so a mean or std over identical input differed by
1-2 ULPs between runs — never enough to move an integer rank (the metrics
were already bit-identical across runs) but enough to make the serialized
scaler irreproducible, and an artifact that cannot be regenerated
byte-for-byte is not publishable under the modeling contract (D040 §4.1).
Quantizing costs ~1e-12 relative on each z-score.

One preregistration finding is recorded rather than quietly fixed: the frozen
subgroup rule gates only on role subgroups with at least 100 queries, but the
largest test subgroup is Defender at 95 (then Midfielder 90, Forward 48,
Goalkeeper 20), so as specified the criterion gates on **zero** roles and is
inert. Counting split sizes by role is design information, not outcome
information, so establishing this did not open the test set. Changing a
preregistered threshold is a charter decision rather than an executor's call,
so the number stands as frozen and the choice is routed to `scoutlens-qop.5`.

`artifacts/benchmark/split-manifest.json` and
`artifacts/benchmark/frozen-baselines.json` are versioned by the same rule as
the six existing result summaries: small, always regenerated by their script,
and the numbers a clone needs to check a claimed improvement without local
Wyscout data. Recorded explicitly because it required a `.gitignore`
negation, and D040 lists `.gitignore` as Denied to a modeling bead — the
crossing was raised rather than taken silently, and authorized by the user
before the edit.

**How to apply:** `scoutlens-qop.2` and `qop.3` measure their delta against
`artifacts/benchmark/frozen-baselines.json` and must not refit the scaler.
The test split is evaluated once per candidate model; a second look is a new
protocol version with a new hash and a new decision record. A null result is
published, not redesigned around.

---

## D042 — 2026-08-10 — Diagonal metric clears the continuation gate: CONTINUE_NEURAL

**Decision:** record the `scoutlens-qop.2` result and apply the D041
continuation gate without exception: **`CONTINUE_NEURAL`**. Validation delta
+0.2174 against the required +0.010, 95% CI [+0.1686, +0.2642] against the
required lower bound above -0.005. `scoutlens-qop.3` may run the neural
contrastive arm. Spec hash
`47488d603e9246f45fdd3e3d0aa95835bb569e5793444b87950c34e2531aa3bd`, frozen
separately from the D041 protocol hash so a qop.2 hyperparameter can never
disturb the lock holding the test split shut. Full write-up in
[`diagonal-metric-benchmark.md`](diagonal-metric-benchmark.md).

This decides nothing about adoption. The showcase still ships Baseline B;
`scoutlens-qop.4` takes the KEEP or DROP decision and is blocked on
`scoutlens-qop.5`.

**Why the model is shaped this way:** the diagonal metric scores as cosine in
the space scaled by `sqrt(w)`, so `w = 1` *is* the frozen Baseline B. The
learned model strictly generalizes the incumbent rather than competing with
it, regularization shrinks toward `w = 1` rather than toward an arbitrary
zero, and ranking reuses the audited `run_baseline_b_retrieval` path untouched
by pre-scaling features. Cosine is a point in the hypothesis space, which is
what makes the comparison clean.

**Impact:** selected lambda = 0 on validation (the top three arms are within
0.0004, so selection is effectively flat for lambda <= 0.01). One-time test
evaluation of the selected model gives cosine 0.4264 versus diagonal 0.6532,
delta +0.2268, CI [+0.1835, +0.2737]. Validation and test agree closely, which
is the evidence that selecting on validation did not overfit it. Every role
improves and none degrades, but no role reaches the 100-query minimum, so no
subgroup gates anything — the D041 inert-gate finding, now confirmed against
real numbers rather than inferred from counts.

A delta this large deserves disbelief first, so three controls were run.
Lambda at 1e5 converges to validation MRR 0.428984, matching the cosine
reference to six decimals. Five random reweightings give 0.4070-0.4597,
straddling cosine's 0.4290 with no systematic gain. Training on shuffled
positives gives 0.3452, materially worse than cosine. The last is decisive:
destroying the same-player correspondence while holding everything else fixed
destroys the gain, so the signal is within-player stability rather than an
artefact of fitting.

The six features whose weights collapse to approximately zero are all sparse
outcome ratios - conversion, on-target share, block share, take-on success,
assists, defensive-duel win rate. Over half a season these rest on few events
and swing between periods. This is a statement about **measurement stability
at this sample size**, not about what matters in football: a striker's
conversion rate is not unimportant, it is unstable across half-seasons. Three
of 28 features are flagged unstable across the regularization grid and must
not be quoted as findings.

A latent defect was found by the test suite and fixed before any result was
recorded: applying the L2 penalty as an explicit gradient step diverges once
`2*lr*lambda/n_features` exceeds 1, which turned a heavy penalty into an
oscillation that collapsed weights instead of shrinking them toward the
incumbent. Under the old form lambda = 1e5 gave validation MRR 0.1186 and
`max|w-1|` of 3.0; the penalty is now applied proximally, which is stable for
every lambda and has the correct limit. The preregistered grid tops out at
lambda = 10 and was in the stable region, so no reported number changed - the
selected lambda = 0 arm is mathematically untouched by the fix - but the grid
was safe by luck rather than by design.

**How to apply:** `scoutlens-qop.3` measures its delta against the same
validation reference and reuses this gate shape. Whoever takes the qop.4
decision should note that at this effect size the +0.020 practical floor is
not doing any work; what remains is the interpretability and maintenance trade
- a 28-number weight vector that must be versioned and refit whenever the
feature set, population or split changes, against a transparent cosine with no
fitted parameters. That is a product judgement, not a measurement one.

---

## D043 — 2026-08-10 — Neural contrastive arm is out: a published null

**Decision:** record the `scoutlens-qop.3` result. The compact neural
contrastive projection **does not earn its place**: it beats plain cosine
comfortably but loses to the interpretable diagonal metric from D042, on test
by -0.0419 with a 95% interval of [-0.0773, -0.0057] that lies entirely below
zero. The neural arm is out of contention for `scoutlens-qop.4`; the live
question is diagonal versus cosine. Spec hash
`39d4e4098e3c6b55f540702de5cee0b3146c94d22b89e1ff5ebc7cd669e62f84`. Full
write-up in [`neural-contrastive-benchmark.md`](neural-contrastive-benchmark.md).

Nothing public changes. The showcase still ships Baseline B.

**Why it was run at all:** D042 recorded `CONTINUE_NEURAL`, and the
preregistered rule said that opens this arm. The gate is read from qop.2's
machine-readable artifact rather than restated, and the run refuses to
proceed if that artifact was produced under a different protocol hash.

**Impact:** validation MRR cosine 0.4290, diagonal 0.6464, neural 0.6112;
test cosine 0.4264, diagonal 0.6532, neural 0.6113. Neural minus cosine is
+0.1822 on validation; neural minus diagonal is -0.0352 on validation
(interval touching zero) and -0.0419 on test (interval clear of zero). Adding
a hidden layer and 3,936 parameters made re-identification worse than 28
interpretable weights. All three methods were scored on identical query sets
and identical candidate pools, asserted at runtime rather than assumed, and
the diagonal arm was read from qop.2's artifact rather than retrained.

Two findings beyond the headline. First, **the neural similarity score is not
calibrated**: binned into quintiles on test, top-1 accuracy is flat at
0.451 / 0.420 / 0.451 / 0.580 / 0.451, so a score of 0.94 is no more likely
to be correct than one of 0.74. It is a ranking signal, not a confidence
signal, and nothing downstream may read it as one. Second, **the selected
configuration is the largest in the declared grid** and validation MRR rises
monotonically with capacity, so a larger network might close the gap. That
does not license running one: extending the grid after seeing the result is
architecture search, an explicit non-goal, and is what preregistration exists
to prevent. The honest claim is therefore narrow - within the declared family
and budget, the neural projection loses - not that no neural model could win.

The model was written in numpy with analytic gradients rather than adding a
deep learning framework. The bead names no dependency and D040 makes
`pyproject.toml` Conditional on the bead justifying one; a multi-gigabyte
dependency for a two-layer network over 753 training rows is not justifiable,
and hand-written gradients keep the run deterministic. The gradient is
verified against a numerical one in the test suite.

Two defects were found by the test suite and fixed before the result was
recorded, both in the gate-reading path rather than the model: binding the
qop.2 artifact path as a **default argument** froze it at import and made the
STOP branch unreachable and untestable, and `relative_to(REPO_ROOT)` raised
for any artifact outside the repository. Neither affected the reported
numbers, but the first meant the no-training path had never actually been
exercised.

Training is deterministic: learning curves and per-arm checkpoint digests are
bit-identical across runs. One reported calibration statistic was not, drifting
in its last ULPs because numpy reduces sums in parallel; reported calibration
values now pass through the same 12-significant-digit precision pin introduced
in D041, so the artifact regenerates identically apart from timings, peak RSS,
artifact size and the generated-at stamp.

**How to apply:** `scoutlens-qop.4` should treat the neural arm as closed and
decide between the diagonal metric and cosine on the interpretability and
maintenance trade, not on the metric. A future attempt at more capacity needs
its own preregistration, its own hash and its own decision record; this null
stands on the record either way and is not a reason to retry differently.

---

## D044 — 2026-08-11 — Role-subgroup minimum amended to 50; supersedes only D041's subgroup clause

**Decision:** amend the role-subgroup gate of the player-disjoint benchmark
from "at least 100 queries" to **"at least 50 queries"** (`scoutlens-qop.5`).
This supersedes **only** the `subgroups.reportable_minimum_queries` clause of
`D041`. Every other element of that protocol — population, split membership,
seed 2718, preprocessing, canonical feature sets, baselines, metrics, paired
intervals, KEEP thresholds, the neural continuation gate, budgets and the
external-test design — stands unchanged.

- Protocol hash before amendment:
  `886ba315b587a91d0fa9ab5c7387f172f8957cf2cfde8a39a65216cb4ff31f1d`
- Protocol hash after amendment:
  `041cd1f7f514133a7e3c45724fef5c7fc1369d0115b8718f6b67f3177e60b4ce`

**Which roles gate, exactly.** At a minimum of 50, on the frozen test split:
**Defender (95 queries) and Midfielder (90 queries) gate** the KEEP decision.
**Forward (48) and Goalkeeper (20) are reported but do not gate.** Forward at
48 does *not* meet a threshold of 50; an earlier sentence in
`representation-benchmark-protocol.md` claimed a minimum of 50 would include
Forward, and that statement was wrong and is corrected by this record.

**Why:** as frozen, D041's minimum of 100 gated **no role at all** — the
largest test subgroup is Defender at 95. The clause was inert, which removed
the protection it existed to provide: catching a model that improves overall
while degrading one role. Three options were written into `scoutlens-qop.5`
(lower to 50; pool validation and test; accept the inert gate) at the time the
inertness was discovered from split counts alone.

**Pre-result provenance.** The option set and the recommendation were recorded
in `scoutlens-qop.5` on 2026-08-10, **before `scoutlens-qop.2` had been run
and before `scoutlens-qop.3` existed as a result**. The counts that motivated
the amendment are split sizes by role, which are design information rather
than outcome information. The human decision of 2026-08-11 selected option 1
and explicitly rejected pooling validation with test, lowering to 45 to
capture Forward, and accepting an inert aggregate-only gate. This is protocol
governance, not result-driven tuning.

**Recorded results are immutable.** `artifacts/benchmark/diagonal-results.json`
and `artifacts/benchmark/neural-results.json` were produced under the D041
hash and are **not** regenerated, overwritten or normalized by this
amendment. No metric, interval, learned weight, model spec, checkpoint digest
or split assignment changes. The diagonal and neural arms are **not** retrained.

**How `scoutlens-qop.4` must apply this.** Take the per-role tables already
recorded in those two artifacts and apply the >= 50 rule to them as recorded.
Defender and Midfielder are the gating subgroups; Forward and Goalkeeper are
reported with their small-sample uncertainty and cannot fail the gate. Do not
re-run either arm to obtain per-role numbers that already exist.

**One intended consequence, stated so it is not mistaken for a fault.** The
gate-evidence guard in `run_neural.py` refuses to proceed when the qop.2
artifact's recorded protocol hash differs from the running protocol's. After
this amendment those hashes differ by construction, so re-running the neural
arm now fails closed until qop.2 is regenerated under the amended protocol.
That is correct: an arm may not be run against a preregistration it was not
measured under. Since re-running the arms is explicitly out of scope here, and
qop.4 consumes the recorded evidence rather than re-running it, nothing in the
remaining pipeline is blocked by this.

**How to apply:** the amended hash above is what `assert_test_set_unlocked()`
now looks for; recording it here is what re-opens test access. Any further
change to `PROTOCOL` re-locks the split again and needs its own record.

---

## D045 — 2026-08-11 — KEEP the interpretable diagonal representation

**Decision:** **KEEP** the diagonal representation. Every preregistered clause
of `D041`, with the subgroup minimum as amended by `D044`, passes; the rule is
conjunctive with no discretionary override, so KEEP follows mechanically
(`scoutlens-qop.4`). Frozen cosine is **retained as the transparent audit and
reference baseline**. The neural arm remains a final DROP under `D043` and was
not a candidate. Full table in
[`keep-drop-decision.md`](keep-drop-decision.md).

| Clause | Threshold | Observed |
|---|---|---|
| Wyscout test delta MRR | >= +0.020 | +0.2268 |
| Wyscout paired CI lower | > 0 | +0.1835 |
| Worst gating role subgroup | >= -0.020 | +0.2017 |
| StatsBomb external delta | > 0 | +0.1362 |
| StatsBomb paired CI lower | > -0.010 | +0.1165 |
| Operational budgets | see below | within budget |

**Why the cross-provider result carries the most weight:** the 28 weights were
frozen on the Wyscout training split and applied to StatsBomb 2015/16 with
**nothing refit** - 1,061 queries, cosine 0.2265 to diagonal 0.3627. All four
roles clear the >= 50 minimum on that population and all four improve
(Defender +0.1498, Midfielder +0.1520, Forward +0.1128, Goalkeeper +0.0655).
Weights learned on one provider and season transfer to a different provider
and season, across every role, without refitting. Standardization is computed
provider-natively, because a z-score is how a provider's raw counts are made
comparable at all, and it is applied identically to both arms so it cannot
move the delta the clause tests. The two canonical-28 lists are asserted
identical in set *and order* at runtime, because the frozen weights are
applied positionally.

**Lineage is proved, not asserted:** substituting D041's subgroup block back
into the amended protocol reproduces the D041 hash
`886ba315b587a91d0fa9ab5c7387f172f8957cf2cfde8a39a65216cb4ff31f1d` exactly, so
every other clause is byte-identical to what qop.2 and qop.3 were measured
under and their recorded results remain valid evidence. The check is capable
of failing; a test tampers with an unrelated clause and confirms it reports
failure. Nothing was retrained, regenerated or overwritten to reach this
decision.

**One correction, recorded because it changed the outcome.** The budget clause
was first implemented as "peak RSS of this decision run", which measured 4.35
GiB - dominated by reading StatsBomb's 166 MB event table - and failed,
producing a DROP. That figure is incurred identically by cosine and diagonal,
because the run scores both arms over the same data. A clause whose value does
not depend on which representation is chosen cannot inform a choice between
them: implemented that way it forces DROP unconditionally regardless of any
measurement. The clause now tests the cost of *adopting* the representation -
28 weights to version, 37.2 s for the full regularization grid, 1.7 s
inference, a 25.9 KiB artifact, and peak RSS bounded above by the 1.39 GiB
qop.3 recorded running a strictly heavier model over the same pipeline. It
remains capable of failing, and tests drive it to failure on both time and
memory. The harness figure stays in the artifact as an observation, not as a
decision input. The argument for the correction holds independently of which
outcome it produces, which is what makes it a correction rather than moving
the goalposts.

**The trade being accepted.** Cosine has no fitted parameters and never needs
refitting. The diagonal metric adds a weight vector that must be versioned,
regenerated and kept in step with the canonical feature set, the eligible
population and the split, and refit whenever any of those change. That is a
standing maintenance obligation. It is accepted because the gain is large,
cross-provider replicated, and carried by 28 auditable numbers - one per named
feature, each readable as how much that feature pulls relative to plain cosine.
At this effect size the +0.020 practical floor is cleared by an order of
magnitude, so the measurement was never the hard part; this trade is.

**How to apply:** nothing public changes yet. The showcase still ships
Baseline B cosine. Promoting the representation into the published product
touches the showcase artifacts, the payload pin, the uncertainty artifacts
computed under cosine, and the web layer, and is filed as its own bead rather
than bundled into a decision record. `w = 1` reproduces cosine exactly, so the
audit baseline remains a point inside the adopted model's own hypothesis
space. No causal, recruitment or transfer-success claim follows: better
same-player retrieval means the fingerprint is a more reliable description of
observed play, and nothing more.

---

## D046 — 2026-08-12 — Resampled rank statistics are rounded at display, not at the producer

**Decision:** format resampled rank statistics to **one decimal place in the
web layer**, leaving the published artifact unchanged (`scoutlens-jtt.16`).
`median_rank` and both `rank_ci_95` bounds now render through a single shared
formatter; a trailing `.0` is trimmed so a whole rank still reads as a whole
number. The artifact remains the authority and no stored value is rounded.

**Why this defect existed:** rank bounds come from percentile interpolation
between order statistics, so they are legitimately fractional - the published
data carries `median_rank` 166.5 and intervals such as 1-130.2, and 484 of 600
sampled published intervals have a non-integer bound. Three surfaces
interpolated those numbers straight into a template, so a value like 111.1 that
is not exactly representable as a double printed its full binary expansion. The
live Lab read `rank interval 1-111.09999999999991`. The neighbouring code was
already correct: `raw_ci_95` has always used `toFixed(2)`. Only the rank path
was missed.

**Why it survived every gate:** every fixture used whole-number ranks (median
9, interval 6-16), so unit and E2E assertions rendered a clean string and
passed. `scoutlens-jtt.5.4` regenerated the win32 visual baselines *with the
defect already present*, which blessed it as the expected rendering, and the
linux baselines were never regenerated at all, so no visual test flagged it
either. It surfaced only when `scoutlens-uze.10` regenerated the stale linux
baselines and the resulting image was read rather than assumed.

**Why display rather than the producer:** rounding at the producer would change
artifact bytes and therefore require a new content-addressed dataset version, a
rebuilt payload pack and a new immutable release asset under `D030` - an
outward-facing publication step - to fix what is a formatting defect. It would
also discard genuine precision from every non-web consumer. Display-side
rounding fixes what is wrong without touching a single published number.
Producer-side rounding remains available as a separate decision if a future
consumer wants integer ranks in the artifact itself; this record does not
foreclose it.

**Impact:** the three affected surfaces are `lab-explorer.tsx` (retrieval
stability and neighbour card) and `neighbor-comparison-drawer.tsx`. Every
already-integer rendering is byte-identical to before, so only genuinely
fractional values change on screen. The E2E fixture now carries deliberately
fractional statistics, including the exact double `111.09999999999991`, and the
tests assert both the formatted output and the absence of the raw expansion -
closing the coverage gap that let this ship. Visual baselines were regenerated
on **both** platforms, which also brings the linux set forward across the three
rendering changes it had missed (`scoutlens-uze.10`).

**How to apply:** any new surface rendering a resampled rank must use
`formatRank` / `formatRankBound` from `web/src/components/rank-format.ts`
rather than interpolating the number. A fixture whose statistics are all whole
numbers does not exercise this path and is not sufficient coverage.

---

## D047 — 2026-08-12 — Showcase 2.0.0 diagonal representation contract frozen

**Decision:** freeze `scoutlens.showcase/2.0.0` as the producer/consumer
contract for diagonal rankings, **before any v2 artifact is generated**
(`scoutlens-qop.6.2`). Normative text in
[`showcase-artifact-contract-v2.md`](showcase-artifact-contract-v2.md); the
schema is authoritative. `1.0.0` remains supported, immutable and byte-identical,
and stays the frozen cosine audit baseline.

This record also **ratifies the adoption-budget interpretation of D045** using
the direct measurements from `scoutlens-qop.6.1`. D045 quoted a 1.39 GiB upper
bound borrowed from the neural run; three fresh-process measurements of the
isolated diagonal adoption path give a maximum of 30.3 s wall, 1.46 GiB peak
RSS and 7,462 serialized bytes, against limits of 1,800 s, 4 GiB and 5 MiB. The
measured peak slightly exceeds the bound D045 quoted, so that bound is
superseded by measurement while its conclusion stands with wide margin. The
operational precondition for promotion is met.

**Why a new major rather than added fields:** v1 publishes unweighted-cosine
rankings; v2 publishes rankings from the diagonal representation kept in D045.
The same field name carrying a differently-computed number is the most
dangerous kind of silent break, so the score is renamed `cosine_similarity` to
`similarity_score`, every ranking-bearing block must name the representation
that produced it, and the dataset version marker moves from `-v1-` to `-v2-`.
A weighted metric must not be published under a name that claims plain cosine.

**Frozen v2 decisions:** `public/showcase/v2` with a required
`representation.json` that the manifest must hash - an unhashed representation
could be swapped without detection. Representation identity is id, weight
digest, ordered canonical-28 ids and their digest, training provider,
population and split digest, the D044 protocol hash, the D042 spec hash and the
D045 reference. Ranking method is `weighted_cosine_diagonal_v1`. Weighted
contribution reconstruction is normative: a subject's feature contributions
must sum to its `similarity_score` within 1e-6, because evidence that does not
reconstruct the number it explains is not evidence. Order is part of identity -
the same weights in a different feature order describe a different metric, so
both digests are recomputed rather than trusted. `match_bootstrap_diagonal_v1`
is the only publishable v2 uncertainty design: v1 intervals describe the
sampling stability of cosine-based ranks, and attaching them to diagonal
rankings would show an interval that does not describe the number beside it.

**Compatibility:** known majors 1 and 2 both validate; an unknown major fails
closed rather than falling back to the newest schema, because silently
validating a future payload against today's rules reports success for something
the consumer does not understand. v1 schema, generated types and validation
behaviour are unchanged; v2 consumer types are emitted alongside as
`showcase-v2.ts` / `showcase-v2.schema.json` so neither type set shifts under a
consumer. `pnpm contracts:generate` remains the only writer of
`web/src/contracts/generated/**` and is deterministic.

**Impact:** no `public/showcase/v2` file, payload pack, uncertainty artifact,
ranking value or UI copy was created or changed. Cosine audit evidence stays
exposed through frozen v1, this ledger and `audit_baseline` metadata, not a
browser recomputation or a primary-flow toggle.

**How to apply:** `scoutlens-qop.6.3` computes diagonal uncertainty under
`match_bootstrap_diagonal_v1`; later leaves generate artifacts. Each is gated on
this contract rather than the reverse. Any change to v2 semantics is a new
decision record, and a change that alters meaning is a new major.

## D048 — 2026-08-13 — Showcase 2.0.0 schema_version consts corrected

**Decision:** correct `schema_version` from `1.0.0` to `2.0.0` on the four v2
artifact types that were pinned to the wrong major, regenerate the v2 consumer
types, and make the producer stamp whichever major the bundle is published
under (`scoutlens-qop.6.4.5`). This amends `D047`; it does not reopen it.

**The defect.** `D047` froze the v2 contract as a schema plus a validator.
`showcase-2.0.0.schema.json` pinned `schema_version` to `"1.0.0"` on
`feature_catalog_artifact`, `player_index_artifact`, `player_profile_artifact`
and `research_summary_artifact`, while `validate_v2_bundle` required `"2.0.0"`
on any artifact declaring one. Both rules are reachable on every v2 bundle and
`schema_version` is `required`, so **no v2 catalog, index, profile or research
summary could be published at all**. The contract was unsatisfiable for four of
its six artifact types from the moment it was frozen.

It is an isolated omission rather than a design choice. v2 otherwise drops
`cosine_similarity`, adds `similarity_score`, requires `representation_id` on
all six ranking-bearing blocks and excludes `match_bootstrap_v1`. The shared
`dataset_version` `$def` received the `-v2-` marker and the inlined `manifest`
const received `2.0.0`; the four other **inlined** consts were missed. A
constant written once in a shared definition was updated; the same constant
written by hand in five places was updated in one of them.

**Why not conform to the schema instead.** Stamping v2 artifacts `1.0.0` would
make `artifact_major()` route a diagonal profile to the cosine schema, which
rejects its `-v2-` dataset version and its `similarity_score`. A v2 artifact
that self-describes as the v1 contract is the precise silent break `D047` was
written to prevent, so the schema is what was wrong, not the producer.

**How it survived the freeze.** Every v2 test written by `scoutlens-qop.6.2`
used stub artifacts, which cannot reach full schema validation. The defect was
found by `scoutlens-qop.6.4.2`, whose bounded end-to-end export was the first
thing to route a schema-complete artifact through `major=2`. A validator
exercised only against stubs has not been exercised against its own contract.

**Corrections.** Four consts in the v2 schema; `pnpm contracts:generate`
regenerating `showcase-v2.ts` and `showcase-v2.schema.json` (four lines each,
v1 generated types byte-identical); the v2 major declared once as
`catalog.SCHEMA_VERSION_V2` beside the v1 constant, so no producer module can
drift from another; `build_showcase_bundle` and `build_research_summary`
stamping the major the bundle is published under rather than the module
constant.

**Guard.** The new test is an invariant over `$defs` rather than four
assertions: every artifact type in a major must declare that major's version.
It covers artifact types added later, in either major. Alongside it, three real
published v1 artifacts are restamped as v2 and validated, after the test first
proves those three types differ between majors by nothing but the two version
strings — so the restamp is provably the whole delta rather than a hopeful
minimum. Eight of the fourteen fail against the pre-fix schema.

**Impact:** no `public/**` file, payload pack, uncertainty artifact, ranking
value or UI copy changed. v1 schema, v1 generated types and v1 behaviour are
unchanged. No v2 artifact existed to invalidate: this correction lands before
the first v2 dataset is published, which is the only reason it is an amendment
rather than a breaking change to a published contract.

**How to apply:** `scoutlens-qop.6.4.2` completes the v2 publication path -
`validate_published_directory` is still v1-hardcoded and rejects a v2 bundle
that `validate_v2_bundle` has already accepted - and then `scoutlens-qop.6.4.3`
regenerates and audits the production artifacts.

## D049 — 2026-08-13 — Showcase 2.0.0 retrieval method renamed to diagonal

**Decision:** `identity_retrieval.method` in `scoutlens.showcase/2.0.0` becomes
`combined_scaler_diagonal_v1` (`scoutlens-qop.6.4.6`). This amends `D047`; v1
keeps `combined_scaler_cosine_v1` byte-identical.

**The defect.** The v2 schema pinned `method` to the v1 value and
`builder.py` emitted it unconditionally, so a v2 profile stated that its
rankings were produced by plain cosine while `representation.ranking_method` in
the same dataset stated `weighted_cosine_diagonal_v1`. Two fields, one payload,
contradicting each other - and the first of them is the rule `D047` wrote for
itself: a weighted metric must not be published under a name claiming plain
cosine.

**It is reader-facing, not internal.** `web/src/components/lab-explorer.tsx`
renders `profile.retrieval.method` verbatim as `<code>`. A published v2 dataset
would have shown "combined_scaler_cosine_v1" beside diagonal scores.

**Why this value.** Parallel construction to v1. The combined scaler is
unchanged, so the prefix stays true; only the scorer name moves. It stays
distinct from `representation.ranking_method`, which names the scorer exactly,
so the two fields describe the procedure and the metric without either claiming
to be the other.

**The class, and the guard.** This is the second instance of the defect `D048`
records: a v1 value carried into v2 that no longer describes the payload. Both
were found by inspection rather than by a test, so the guard is now a standing
sweep over every `const`, `enum` and `pattern` in the v2 schema, failing on any
value naming plain cosine or a `_v1` scorer outside two documented
audit-baseline references. The exception list is deliberately short: a long one
is how this class hides. Sweeping every fixed value catches the next instance;
a per-field assertion only catches the fields someone remembered.

**Impact:** no `public/**` file, payload pack, uncertainty artifact, ranking
value or UI component changed. No v2 artifact existed to invalidate -
`scoutlens-qop.6.4.3` found this while preparing the first production
regeneration and stopped before running it, which is why this is an amendment
and not a republication.

**How to apply:** `scoutlens-qop.6.4.3` resumes, regenerates the 1,257-profile
v2 dataset twice, audits it independently and promotes the audited bytes.

## D050 — 2026-08-17 — Payload pin contract 2.0.0, and the version it is not

**Decision:** freeze `scoutlens.showcase-payload-pack/2.0.0` as the pin document
for hydrating a showcase-2.0.0 dataset, and make zero-argument hydration derive
its target from the validated pin (`scoutlens-qop.6.6.1`). The repository pin is
**not** changed here; `scoutlens-qop.6.6` repins after publication.

**The distinction this freezes.** The code blurred two version numbers that mean
different things:

- `schema_version` versions **the pin document itself**;
- `showcase_schema_version` names **the artifact contract being hydrated**.

A v2 pin is schema `2.0.0` describing a showcase `2.0.0` dataset, but the two
move independently, and conflating them is how a pin ends up promising a dataset
it does not describe. They are now separate required fields, and a v2 pin that
claims to hydrate showcase `1.0.0` is refused.

**Exact key sets, per schema.** `1.0.0` accepts only the frozen legacy shape;
`2.0.0` additionally requires `showcase_schema_version`, `manifest_sha256` and
`representation` (`id` and `sha256`). Neither accepts the other's fields, so a
document that straddles both shapes is rejected outright rather than validating
on the union. The dataset-version prefix must match the schema's major.

**Why the manifest and representation digests are pinned.** The archive carries
players only; the manifest and the representation are tracked in Git and could
be at any revision. Without pinning them, a v2 player set could hydrate against
a manifest that never produced it and every per-file check would still pass -
each extracted profile would match a manifest that is simply the wrong one.

**Hydration derives its own target.** With no explicit paths, hydration resolves
`public/showcase/v{major}/manifest.json` and `players/` from the validated pin,
and only after validation: a pin that fails its own checks never gets to say
where it would have written. There is no fallback to v1. Explicit paths remain
available for tests and recovery and must still agree with every pinned
identity.

**Building a pin verifies rather than trusts.** The `pin` command recomputes
every field from the artefacts themselves and then requires the `qop.6.4.4`
sidecar to agree. The sidecar is an operator convenience, never the authority: a
pin built from a sidecar alone would attest to whatever the sidecar happened to
say. The writer round-trips the document through the loader before publishing,
because a pin this module cannot read is not a pin, and replacing an existing
pin requires an explicit flag - it retargets every clean clone's hydration.

**v1 rollback.** The frozen `1.0.0` shape stays accepted for exactly the v1
dataset, so restoring the previous pin file is the whole rollback procedure. The
repository pin and its v1 behaviour are unchanged by this record and are pinned
by a test.

**Impact:** no `config/`, `public/`, `web/`, `artifacts/`, producer, scientific
or generated-contract file changed. No archive was uploaded and no pin was
repointed.

**How to apply:** `scoutlens-qop.6.6` publishes the `qop.6.4.4` candidates,
builds the pin with this command, replaces `config/showcase-payload-pack.json`
under explicit authority, and flips `DEPLOYED_SHOWCASE_MAJOR` in
`web/src/contracts/showcase-repository.ts` so the site serves what the pin
hydrates.

## D051 — 2026-08-18 — Identity-challenge contract 2.0.0: artifact bindings follow the public major

**Decision:** advance the identity-challenge contract to specification `2.0.0`
(`scoutlens-9a3.8`). It supersedes **only** `D039`'s bindings to
`scoutlens.showcase/1.0.0`. Every placement, state, transition, accessibility
and performance decision `D039` froze stands unchanged.

**Why the concept survives a major version.** The challenge never computed
anything - it reveals stored outputs. When the stored outputs changed name and
meaning under `D047`, the bindings had to follow and the interaction did not.
A contract that still named `cosine_similarity` was naming a field that no
longer exists, which is a broken specification rather than a design question.

**What changed, in one line each.** The primary value becomes
`retrieval.global.similarity_score`, labelled *Learned weighted similarity*
because a weighted metric must not be presented under a name claiming plain
cosine. `representation_id` becomes visible provenance at reveal and evidence.
Contribution lists are consumed from `evidence_refs` in published order rather
than sorted in the browser. `weighted_contribution` explains the shown score;
the unweighted `contribution` is retained as the cosine audit view and confined
to the advanced disclosure. Uncertainty is driven by `uncertainty.status`
instead of the hard-coded pending case. The full enumeration is §14 of the
contract; ten deltas, no eleventh.

**Two corrections the field audit forced**, and they are the reason the audit
happened before the freeze rather than after. The 1.0.0 mandatory-caveat list
required `uncertainty_pending`, a code the published v2 profiles do not carry -
requiring it would have failed closed on a valid dataset. And 1.0.0 instructed
the implementation to state that sampling-stability intervals "are not
available in this dataset version", which is now false: the published dataset
reports `available` under `match_bootstrap_diagonal_v1`. A contract that
asserts a data state instead of reading it goes stale the moment the data
moves.

**The fitted-weight boundary is stated precisely.** The fingerprint displays 32
measurements per period; the representation fits weights for 28 of them. Some
fitted weights are exactly zero - three in the published dataset - so a feature
can be inside the fitted set and contribute nothing. The copy therefore says
that 28 features *carry a fitted weight*, not that 28 features influence the
score, and `feature_weight` on each evidence item is the authority rather than
a feature's position in a list.

**Boundaries unchanged.** No client-side computation, no gamification, no live
LLM, deterministic and working without JavaScript. No recruitment, quality,
tactical-fit, causal or future-performance claim; the forbidden-language lists
are untouched, with one wording fix where a list explained contributions as
explaining "the cosine similarity".

**Impact:** documentation only. No web, source, schema, generated-contract,
artifact or config file changed, and no scientific value, order or precision
moved. Verified against the published profile `wy-8287-c-795`: every field this
contract binds already exists, so no schema or artifact change is required.

**How to apply:** `scoutlens-9a3.6` implements this contract. It contains no
product-design decisions and may not reintroduce browser-side sorting,
recomputation or a cosine-primary label.

## D052 — 2026-08-20 — The challenge's client code is statically imported, not lazy-loaded

**Decision:** the identity challenge's interactive states are implemented as a
new client component **statically imported** by the Lab page, sharing the
existing page chunk. It is not lazy-loaded, and it is not folded into
`lab-explorer.tsx`. The `204,800`-byte initial-JavaScript cap remains the
binding invariant and is measured on every change.

**Why this needed a decision.** §10 of the identity-challenge contract
contradicts itself once a new client component is required. Its *Lazy chunks*
row states "the challenge does not introduce lazy-loaded components", while the
budget invariant beneath the table states "if the challenge implementation
requires a new client component, it must be lazy-loaded outside the initial
route transfer". Read together, one clause forbids what the other mandates.

**The premise that failed.** Both clauses rest on the table's assumption that
the challenge "reuses the existing Lab page chunk and `lab-explorer.tsx` client
bundle". That holds for the fingerprint plot, and `scoutlens-9a3.6.2` confirmed
it holds for orientation and degraded, which are server-rendered and add no
JavaScript at all. It does not hold for the state machine. `LabExplorer` has no
challenge states, does not read the `challenge` URL parameter, and implements
none of §6.2's focus movement or §6.3's announcements. The contract assumed no
new client component would be needed; `scoutlens-9a3.6.3` establishes that one
is.

**Why static import rather than the alternatives.** A small statically-imported
client component is merged into the existing page chunk by the bundler rather
than emitted separately, so "adds zero new chunks" and "no new lazy chunks" both
hold literally. Lazy-loading would satisfy the invariant's second sentence but
violate the *Lazy chunks* row, and would put a network round trip on the primary
CTA of the flagship interaction on an otherwise fully static site. Hosting the
states inside `lab-explorer.tsx` would satisfy both clauses literally, at the
cost of adding a second responsibility to a 1,012-line component and coupling
the challenge to the explorer while its orientation and degraded states remain a
separate server component.

**What stays binding.** The cap. §10's purpose is that `/lab` initial JavaScript
does not exceed `204,800` gzip bytes (`D038`), and that number is unchanged.
Measured headroom before this work was `45,877` bytes. If the challenge's client
code ever consumes a disproportionate share of it, lazy-loading becomes the
remedy the invariant intends — the decision here is which mechanism is default,
not that the budget is negotiable.

**Impact:** `scoutlens-9a3.6.3` and `scoutlens-9a3.6.4`. No artifact, schema,
config or scientific change. §10's wording remains as frozen; this entry records
how the contradiction is resolved in implementation rather than editing a frozen
contract mid-build.

**How to apply:** every pull request touching the challenge's client code
records `pnpm budget:check` before and after. A change that reduces headroom
materially is a signal to split the component, not to raise the cap — `D038` and
§5.5 of the frontend agent contract both forbid raising it.

## D053 — 2026-08-24 — Focus order is for controls; informational rows live in reading order

**Decision:** the identity challenge's 32 fingerprint rows and its contribution
rows are informational graphics with complete accessible names, reached in
reading order. They are **not** Tab stops. The state's CTA remains the first
focusable element. `docs/identity-challenge-contract.md` advances to
specification **2.1.0**; §6.1 is rewritten to separate focus order from reading
order. No product code changes — this corrects the document to match what
already ships.

**The contradiction.** §6.1 required, in the same paragraph, that the CTA be
"the first focusable element" and that "Tab moves between feature rows". The
rows precede the CTA in the DOM, which §6.6 fixes as the reading order. If the
rows are focusable the CTA cannot be first; if the CTA is first the rows cannot
be Tab stops. `scoutlens-9a3.6.4` surfaced this and declined to resolve it in
code, because choosing between two frozen requirements is a product decision.

**Why the rows stay out of focus order.** A Tab stop is a promise that
something can be activated. Thirty-two stops that do nothing put the primary
action of the query state behind thirty-two dead ends, and a keyboard user
without a screen reader gets the cost with none of the benefit. Screen-reader
users lose nothing: browse and virtual-cursor navigation reach every row in DOM
order, which is the artifact's published order, and each row carries a complete
accessible name. The shipped implementation exposes them as non-interactive
`role="img"`, and `scoutlens-9a3.6.4` proved it axe-clean in all four states at
320, 360, 768 and 1280.

**One correction the amendment forced.** The original §6.1 said each query row
"announces its feature label and period-A percentile" — correct, and it
survives. But an accessibility rule phrased as "every row announces both period
values" would be wrong here: §3.2 hides the period-B fingerprint in the query
state, so a row announcing period B would hand the answer to precisely the
readers who depend on announcements while hiding it from everyone else. The
contract now states the per-state rule explicitly in a table: query carries
period A, reveal and evidence carry both.

**The same defect appeared twice more**, and both are fixed in the same pass.
§6.1 also used *Tab* for the reveal's rank and baseline block and for the
evidence contribution list; neither is focusable either. Rewriting the section
around the focus/reading distinction fixes all three consistently rather than
patching the one that was noticed.

**Impact:** documentation only. No web, source, schema, artifact, snapshot or
config file changes; no metric, score, row order or accessible-name content
moves. The 2.0.0 artifact bindings from `D051` are untouched, which is why this
is a minor version rather than a major.

**How to apply:** treat any future "Tab moves to …" phrasing about
non-interactive content as a defect in the sentence, not a requirement on the
implementation. This is the third self-conflict found in this contract during
`scoutlens-9a3.6` — after §10's lazy-chunk contradiction (`D052`) and §8's
uncertainty-design reading — all three from the document specifying behaviour it
had not yet watched anything perform.
