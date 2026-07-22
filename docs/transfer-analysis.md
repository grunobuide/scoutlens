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

**Baseline B holds up.** MRR for transferred players (0.239) is close to
its full-population value (0.254) — a modest, unsurprising dip given
n=26, not a collapse. **The Baseline B − A delta is, to three decimal
places, the same for transferred players as for the general population
(+0.228 both times)** — the CI is far wider for the 26-player subset
(as expected at this sample size) but still clears 0 by a comfortable
margin ([0.089, 0.393]).

This is the direct evidence D010 called for: **Baseline B's advantage
over the trivial baseline is not an artifact of team continuity.** For
the specific players where team continuity structurally cannot help —
exactly the population a recruitment tool cares most about, since
recruitment is fundamentally about players *changing* clubs — the
event-derived signal is still there, at essentially the same strength as
in the team-stable majority of the population.

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
