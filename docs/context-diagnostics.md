# ScoutLens — Context & Minutes Diagnostics (SLS-020)

Implementation: [`src/scoutlens/evaluation/diagnostics.py`](../src/scoutlens/evaluation/diagnostics.py)
(`compute_primary_team`, `neighbor_concentration`) plus
`get_top_k_neighbors` in
[`retrieval.py`](../src/scoutlens/evaluation/retrieval.py). Tests:
[`tests/evaluation/test_diagnostics.py`](../tests/evaluation/test_diagnostics.py).

Two questions from the brief: does Baseline B's signal come from real
playing-style similarity, or from confounds (same team, same league)
that would masquerade as role signal? And is the ≥450-minute threshold's
apparent stability just an artifact of sample noise at that specific
cutoff, per the risk flagged in
[D006](decisions-log.md#d006--2026-07-20--450-minute-threshold-flagged-as-a-known-noise-risk-not-just-a-parameter)?
Both checked directly against real data (global condition, five domestic
leagues, ≥450 min/period, Baseline B's top-10 neighbors for all 1,257
queries — 12,570 query-neighbor pairs).

## Team and league concentration in the top-10 neighbors

| Confound | Observed | Expected under uniform-random neighbor selection | Enrichment |
|---|---|---|---|
| Same primary team as query | 4.79% | 1.05% (98 teams, actual squad-size-weighted) | ~4.6x |
| Same league as query | 25.04% | 20.06% (actual league-size-weighted, leagues are near-equal size) | ~1.25x |

"Expected under random" is computed from the *actual* team/league size
distribution in the period-B candidate pool (sum of squared population
shares), not a naive `1/n` — teams and leagues aren't equal size, so a
naive uniform assumption would be wrong.

**Reading:** there is a real, non-trivial team effect — a query's
neighbors are about 4.6x more likely to share their team than pure
chance would predict, meaning shared tactical system/teammates does
leak into the similarity to some degree. But it's still a small minority
of neighbors overall: **95.2% of top-10 neighbors play for a different
team than the query.** The league effect is close to negligible — 25%
observed vs. 20% expected is a mild enrichment, not "the model mostly
just learned league style." Neither confound comes close to explaining
Baseline B's retrieval performance; the bulk of the signal is not
"teammate-finding" or "league-style-finding" in disguise.

## Minimum-minutes → population → stability curve (resolves D006)

Global condition, Baseline A vs. Baseline B, at six candidate thresholds:

| Threshold (min/period) | Eligible (player×competition) | MRR (A) | MRR (B) | Delta (B−A) | 95% CI |
|---|---|---|---|---|---|
| 225 | 1,534 | 0.024 | 0.221 | 0.197 | [0.182, 0.215] |
| 450 | 1,257 | 0.026 | 0.254 | 0.228 | [0.208, 0.249] |
| 675 | 955 | 0.032 | 0.297 | 0.266 | [0.241, 0.289] |
| 900 | 686 | 0.043 | 0.358 | 0.316 | [0.284, 0.346] |
| 1,125 | 415 | 0.067 | 0.424 | 0.357 | [0.316, 0.398] |
| 1,350 | 226 | 0.105 | 0.445 | 0.340 | [0.286, 0.397] |

**Reading:** D006 flagged a risk that the ≥450 threshold specifically
might be noisy enough to make a real signal look weak or unstable, or
mistake sample noise for genuine instability. That risk does not
materialize here. Both baselines' MRR — and, more importantly, the
Baseline B − A delta — climb steadily and the delta's confidence
interval stays comfortably clear of 0 across the **entire** range tested,
from the loosest threshold (225 min, 1,534 players) to the strictest
(1,350 min, 226 players). The signal is not a fragile artifact that
appears only near 450 minutes; it strengthens with more data, exactly as
expected if it reflects a real underlying stability rather than noise.

The one caveat worth carrying forward: the CI *widens* at the highest
thresholds (e.g. [0.286, 0.397] at 1,350 vs. [0.182, 0.215] at 225) —
expected, since the eligible population shrinks to 226 players, and the
apparent dip in the point estimate from 1,125 to 1,350 (0.357 → 0.340) is
well within the overlapping CIs, not a real reversal. ≥450 minutes
remains a reasonable primary-experiment choice: comfortably inside the
range where the signal is both strong and precisely estimated, not
sitting on an edge case.

## What this doesn't yet cover

This is quantitative stratification (team/league confounds, minutes
sensitivity) across the whole population. Qualitative investigation of
*specific* neighbor sets — which cases look coherent, which look wrong,
and why — is SLS-021's job, not this one.
