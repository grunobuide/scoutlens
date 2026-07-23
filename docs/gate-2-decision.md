# ScoutLens — Gate 2 Decision (SLS-022)

**Decision: GO.**

Recorded 2026-07-22, jointly by the user and this session, after
reviewing the evidence below. This is the second and final formal gate of
the charter ([`project-charter.md`](project-charter.md)) — analytical
signal is sufficient to conclude the primary experiment supports
continuing the ScoutLens research program, subject to the stated scope
and limitations.

## Evidence against the brief's Gate 2 criteria

| Criterion | GO requirement | Actual | Source |
|---|---|---|---|
| Baseline B beats Baseline A materially | yes | MRR 0.0256 → 0.2539 (global, ~10x); 0.0256 → 0.2787 (within-role) | [`temporal-retrieval-global.md`](temporal-retrieval-global.md), [`temporal-retrieval-within-role.md`](temporal-retrieval-within-role.md) |
| Gain has a consistent confidence interval | yes | CI excludes 0 at every minutes threshold tested, 225–1,350 min | [`context-diagnostics.md`](context-diagnostics.md) |
| Signal holds up within-role | yes | Within-role delta (+0.253, CI [0.232, 0.274]) is at least as large as the global delta (+0.228, CI [0.208, 0.248]) — structurally can't be explained by Baseline A's free role-matching, since Baseline A's own numbers didn't move | [`temporal-retrieval-within-role.md`](temporal-retrieval-within-role.md) |
| No collapse in the main strata | yes, with a noted exception | Team confound ~1.14x enriched, league ~1.08x — both small (see corrections below). Goalkeeper is the weakest role stratum (MRR 0.129) but still clearly positive, plausibly because the feature catalog (SLS-013) is built almost entirely around outfield actions | [`context-diagnostics.md`](context-diagnostics.md) |
| Errors are investigable and explicable | yes | Worst cases have identifiable, heterogeneous causes (genuine profile change at 3 of 4 top misses; sample-size noise at 1 of 4) rather than being unexplained; close misses are football-coherent (attacking-fullback and defensive-midfielder sub-clusters), not arbitrary | [`error-analysis.md`](error-analysis.md) |

Every criterion clears, several with considerable margin. This is a
notably cleaner Gate 2 outcome than the charter's own framing anticipated
as the default case — the brief treated "Baseline B beats Baseline A" as
a real open question, not a foregone conclusion.

**Correction (2026-07-22, post-publication review):** the team/league
confound numbers above were recomputed after finding the original
analysis counted a query's own correctly-retrieved true match as a
"neighbor" — which trivially shares the query's team, inflating the
apparent team effect roughly 4x. Fixed (`diagnostics.py` now excludes
true matches from concentration calculations by default) and re-run; the
corrected numbers were smaller than originally reported, which
*strengthens* this row's conclusion rather than weakening it. Full
before/after: [`context-diagnostics.md`](context-diagnostics.md).
A second, independent bug was found and fixed in the same review: the
retrieval matching logic identified the true match by `player_id` alone
rather than `(player_id, competitionId)` per D007 — currently harmless
for the headline retrieval numbers (no eligible player appears in two
domestic competitions), but would silently misbehave with multi-season
or multi-competition data. Fixed with regression tests; headline MRR/CI
numbers are unchanged by this fix (verified by re-running).

**Second correction (2026-07-22, second review round, D013):** the
team-confound figure above was *itself* still wrong — 1.30%, not the
1.20% now shown — because the diagnostic's `player_id`-keyed join was
vulnerable to the same class of bug as the D007 fix, just in a different
function: `compute_primary_team` runs over every competition a player
appears in, so 28.7% of the eligible population (361 of 1,257 — mostly
via Euro/World Cup appearances, plus a smaller number of genuine
mid-season transfers *between* two of the five domestic leagues) had
duplicate `player_id` rows feeding `neighbor_concentration`'s join.
`neighbor_concentration` now raises `ValueError` on a duplicated
`player_id` in its input rather than silently over- or under-counting —
this caught the bug immediately on re-run, rather than requiring another
manual audit. Corrected: team ~1.14x (not 1.24x), league unaffected at
~1.08x. Still small; still strengthens rather than weakens this row.

## What Gate 2 does — and does not — license

Per [`project-charter.md`](project-charter.md), the **maximum permitted
claim** from this spike is:

> Event-derived profiles show sufficient evidence of **stable**
> player-role signal to justify **continuing** the ScoutLens research
> program.

Not, and never: *"ScoutLens finds the best players to sign."* Same-player
temporal retrieval is a test of representation stability, not a
validation of recruitment quality — a stable role fingerprint is a
prerequisite for a recruitment-oriented similarity search to be
meaningful, not proof that such a search produces good recruitment
outcomes. This distinction must appear in the final report's limitations
section (SLS-023), not just here.

A second, narrower wording caution: "stable player-*role* representation"
is this decision's own phrasing, inherited from the charter — what the
within-role experiment (H4) actually establishes is that the signal isn't
explained by the 4 nominal role categories, not that the extra signal is
specifically role information as opposed to individual quality, set-piece
duties, or team system. "Stable player statistical fingerprint" is the
more precise claim the evidence supports; treat "role representation" as
a plausible interpretation carried forward from the charter's original
framing, not an independently verified finding.

## Standing limitations carried into the final report

- **Population scope:** quantitative results are reported on the five
  domestic leagues only. Euro 2016 and World Cup 2018 remain in the
  dataset and in qualitative discussion (Gate 1 decision), but their
  eligible population is near-zero once split into two periods
  ([`chronological-split.md`](chronological-split.md)) — not part of the
  headline numbers.
- **Survivorship bias:** requiring ≥450 minutes in *both* periods selects
  for players who stayed established and available all season — it
  structurally excludes breakout players, injury returns, players losing
  their starting spot, and mid-season transfers, which are exactly the
  cases a recruitment-oriented tool would most need to handle. The
  result here is about established players specifically, not players in
  general — see [`feasibility-report.md`](feasibility-report.md).
- **Carrying features are proxies**, not ground truth (no native carry
  event in this dataset — [`feature-definitions.md`](feature-definitions.md)).
- **Sequence involvement** was cut from the feature catalog v0 entirely
  (D003 scope-priority order).
- **Two unresolved sentinel-encoding ambiguities** in `players.foot` and
  `weight`/`height` were flagged, not silently resolved — currently
  inconsequential since no anthropometric feature is in the catalog
  ([`data-quality-report.md`](data-quality-report.md)).
- **players count discrepancy** (3,603 vs. the paper's stated 4,299) is
  still unexplained ([`data-provenance.md`](data-provenance.md)).
- **Code license** for this repository (independent of the CC BY 4.0 data
  license) remains an open decision, deferred by the user.
- **Team continuity is a stronger predictor than event-derived features
  in this experimental design** (found 2026-07-22 in a post-spike
  robustness battery — [`robustness-checks.md`](robustness-checks.md)): a
  trivial role+team+minutes baseline beats Baseline B by >2x, because
  eligible players essentially never change clubs within one season. Does
  not change this gate's verdict (Baseline B vs. A, the charter's actual
  criterion, is unaffected and confirmed not to depend on team-clustering
  itself). **Directly tested the same day**
  ([`transfer-analysis.md`](transfer-analysis.md)): among the 26 eligible
  players who *did* change clubs between periods, the team-based baseline
  collapses to chance level, unambiguously. Baseline B's advantage over
  Baseline A also survives, but a closer look than MRR alone (median rank,
  Recall@5/10) shows real, moderate degradation for this subset — a
  smaller, more mixed win than "unchanged," not a clean null result
  either. n=26 is small and a larger sample (another season) is still the
  natural follow-up, now the top item in
  [`feasibility-report.md`](feasibility-report.md)'s next-experiment list.

## Next step

SLS-023: write the final ScoutLens Data & Modeling Feasibility Report,
synthesizing every SLS-00X document into the charter's required
structure, with the GO/PIVOT/KILL decision and recommended next
experiment recorded explicitly.
