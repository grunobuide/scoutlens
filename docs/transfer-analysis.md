# ScoutLens — Transferred Players Follow-Up

Direct test of the [D010](decisions-log.md#d010--2026-07-22--team-continuity-dominates-a-trivial-roleteamminutes-baseline-reframe-dont-retract)
finding: does Baseline B's event-derived signal hold up once Baseline C's
team-continuity shortcut structurally cannot apply? Implementation:
[`identify_transferred_players`](../src/scoutlens/evaluation/diagnostics.py)
+ [`run_transfer_analysis.py`](../src/scoutlens/evaluation/run_transfer_analysis.py).
Reproduce with:

```
uv run python -m scoutlens.evaluation.run_transfer_analysis
```

## Population

Of the 1,257 eligible player×competition combinations (five domestic
leagues, ≥450 min/period), **26 (2.1%) have a different primary team in
period B than in period A** — identified from `compute_primary_team`
(SLS-020), not self-reported transfer data (this dataset has none). A
small sample; results below are directional, not conclusive on their own,
and the confidence interval is reported honestly rather than treated as
tight.

Queries use the **same global period-B candidate pool as the main
experiment** (all 1,257 candidates, transferred or not) — only which
players we ask the *query* to be about changes; the pool a transferred
player's true match has to be found within is exactly as hard as for
everyone else.

## Results

| | Full population (n=1,257) | Transferred only (n=26) |
|---|---|---|
| Baseline A (role + minutes) | MRR 0.0256, median rank 128 | MRR 0.0105, median rank 149, Recall@1/5/10 all 0% |
| **Baseline B** (32 features + cosine) | **MRR 0.2539**, median rank 16 | **MRR 0.2387**, median rank 38.5, Recall@10 34.6% |
| Baseline C (role + team + minutes) | MRR 0.5893, median rank 2 | **MRR 0.0101**, median rank 150.5, Recall@1/5/10 all 0% |
| Baseline B − A delta | +0.228, 95% CI [0.210, 0.250] | +0.228, 95% CI [0.089, 0.393] |

## Reading

**Baseline C's team-based advantage completely collapses** for
transferred players — MRR drops from 0.589 (best of the three baselines
in the general population) to 0.010 (statistically indistinguishable
from Baseline A's already-weak performance). This confirms directly, not
just by inference, that Baseline C's strength was entirely about team
continuity: remove that continuity and the baseline has nothing left.

**Baseline B's MRR holds up — but MRR alone overstates how uniform that
is.** Flagged in a second review round: the full metric picture for
transferred players is more mixed than "MRR nearly unchanged" alone
suggests.

| Metric | Full population | Transferred only |
|---|---|---|
| MRR | 0.2539 | 0.2387 |
| Median rank | 16 | **38.5** |
| Recall@1 | 16.2% | **19.2%** (slightly better) |
| Recall@5 | 34.5% | **26.9%** (worse) |
| Recall@10 | 43.3% | **34.6%** (worse) |

Median rank roughly doubles and Recall@5/10 both drop meaningfully — at
n=26, MRR's near-parity is consistent with a small number of perfect
(rank-1) retrievals propping up the average (Recall@1 of 19.2% is ~5 of
26 queries) while the *rest* of the transferred population ranks
noticeably worse than the general population's typical case. MRR is not
wrong, but reading it alone as "performance is basically unchanged" would
overstate the uniformity of the result.

**The honest summary:** Baseline C's team-based advantage still
completely and unambiguously collapses (0.589 → 0.010, the clean, large,
unambiguous part of this finding) — that conclusion doesn't depend on
which metric is used. Baseline B's advantage over Baseline A also
survives (the B−A delta stays positive and the CI clears 0), but the
*degree* to which Baseline B's absolute retrieval quality holds up for
transferred players specifically is less clean than the MRR number alone
implies — some real degradation is visible in rank distribution and
Recall@5/10, plausibly reflecting that a new club changes real aspects of
a transferred player's role/usage (new system, new teammates, different
minutes pattern) on top of whatever the underlying individual signal is.
This is exactly the kind of nuance a larger sample (another season) would
resolve — n=26 cannot currently distinguish "mostly noise around a stable
signal" from "a real, moderate degradation specific to transferred
players."

## Honest caveats

- **n=26 is small.** The point-estimate match with the full population
  (+0.228 both) is a striking, encouraging coincidence in the third
  decimal place — read the *direction and rough magnitude* as the
  finding, not the exact match. The wide CI [0.089, 0.393] is the more
  honest summary of precision here.
- **This dataset has no confirmed transfer records** — "transferred" is
  inferred from a change in derived primary team between the two halves
  of one season, which could in rare cases reflect a data artifact (e.g.
  a loan, or the primary-team tie-break in
  `compute_primary_team` landing differently) rather than an actual
  permanent transfer. Not expected to be common enough to change the
  reading, but not independently verified either.
- **Still single-season.** A genuinely larger transferred-player sample
  requires another season's data (already priority #2 in
  [`feasibility-report.md`](feasibility-report.md)'s next-experiment
  list) — this result should be treated as encouraging preliminary
  confirmation, not the final word on the question it was designed to
  answer.
