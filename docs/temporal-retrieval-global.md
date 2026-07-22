# ScoutLens — Temporal Role Stability Experiment: Global Retrieval (SLS-018)

Implementation: [`src/scoutlens/evaluation/retrieval.py`](../src/scoutlens/evaluation/retrieval.py).
Tests: [`tests/evaluation/test_retrieval.py`](../tests/evaluation/test_retrieval.py).
This is the primary quantitative result the spike's GO/PIVOT/KILL decision
rests on (Gate 2, SLS-022) — the first hard test of H3 (temporal
stability) and H5 (baseline competitiveness).

## Method

For each eligible player, period A's feature profile is the query; every
eligible period B profile across all five domestic leagues combined is
the candidate pool ("global" — not scoped per-competition, the harder
test). A baseline "succeeds" for a query when it ranks that player's own
period B profile highly among all 1,257 candidates.

**Population:** the five domestic leagues (England, France, Germany,
Italy, Spain) — World Cup 2018 and Euro 2016 excluded from this
quantitative result per the limitation already established in
[`gate-1-decision.md`](gate-1-decision.md) and confirmed empirically in
[`chronological-split.md`](chronological-split.md) (near-zero
period-eligible population). **Threshold:** ≥450 minutes in *each* period
(the brief's suggested starting point). **Result:** 1,257 eligible
player×competition combinations, forming both the query set (period A)
and the candidate pool (period B) — every query's correct answer is
guaranteed to be present in the pool.

**Metrics:** MRR, median rank, Recall@1/5/10, standard for this kind of
retrieval evaluation. **Baseline B standardization:** fit once on the
combined 2,514-row (query + candidate) population per
[D008](decisions-log.md#d008--2026-07-22--feature-normalizationnull-handling-strategy),
so query and candidates are on the same scale. **Uncertainty:** paired
bootstrap (1,000 resamples, seed 0) over the MRR delta (B − A), pairing
each query's Baseline A and Baseline B rank before resampling so the
comparison is query-for-query, not just two independent distributions.

## Results

| Metric | Baseline A (role + minutes) | Baseline B (standardized features + cosine) |
|---|---|---|
| MRR | 0.0256 | **0.2539** |
| Median rank (of 1,257) | 128 | **16** |
| Recall@1 | 0.32% | **16.2%** |
| Recall@5 | 2.70% | **34.5%** |
| Recall@10 | 4.85% | **43.3%** |

**MRR delta (B − A): +0.228, 95% bootstrap CI [0.208, 0.248].** The
interval excludes 0 by a wide margin — Baseline B's advantage over the
trivial baseline is not attributable to sampling noise at this population
size.

Runtime: 7.7s end to end (standardization, both baselines' full
1,257-query × 1,257-candidate ranking, 1,000-resample bootstrap) — no
performance concern at this scale.

## Reading against H3 / H5

- **H5 (baseline competitiveness):** clearly cleared. Baseline B beats
  Baseline A by roughly 10x on MRR, with a confidently non-zero CI. The
  brief's condition for adding complexity later — "improvement over
  baselines + confidence interval + robustness across strata" — has its
  first leg satisfied; robustness across strata (role, league, minutes)
  is SLS-019/020, not yet checked.
- **H3 (temporal stability):** Baseline B recovering the correct player
  in the top 10 of 1,257 candidates 43% of the time, from event-derived
  statistics alone and with no player identity features whatsoever, is
  meaningful evidence that a player's period-A statistical profile
  carries real signal about their period-B profile. Recall@1 of 16.2% is
  the more demanding read: roughly 1 in 6 players' exact statistical
  "fingerprint" is unique enough, even among 1,257 peers, to be the
  single best match.
- **Not yet established:** whether this signal is mostly explained by
  role (a Baseline B profile might just be finding "another player with
  a similar role," which Baseline A already does crudely) — that is
  exactly what H4 and SLS-019 (within-role retrieval) test. This global
  result is necessary but not sufficient evidence for the spike's
  headline claim.

## Known limitation carried forward

Per [`chronological-split.md`](chronological-split.md), this excludes
Euro 2016 and World Cup 2018 from the quantitative population. They
remain in the dataset for qualitative/exploratory discussion per the
Gate 1 decision, but including their near-zero eligible population in
this statistic would misrepresent both.
