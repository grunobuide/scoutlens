# ScoutLens — Baseline B: Standardization & Cosine Similarity (SLS-017)

Implementation: [`src/scoutlens/evaluation/similarity.py`](../src/scoutlens/evaluation/similarity.py)
(`impute_and_standardize`, `baseline_b_rank`). Resolves
[D008](decisions-log.md#d008--2026-07-22--feature-normalizationnull-handling-strategy-open-must-be-resolved-before-sls-017),
left open at SLS-014.

## The decision (D008 resolved)

**Standardization:** per-feature z-score
(`(x - mean) / std`), fit on the population passed to
`impute_and_standardize` — the caller must pass the full combined
population the query and candidate pool are drawn from (e.g. every
eligible player-period row across *both* periods for a competition), so
the query and candidates are measured on the same scale. Fitting the two
periods separately would silently distort the similarity.

**Null handling:** a null in a ratio feature (`shot_conversion_pct`,
`duel_win_pct`, ...) means "this action never came up for this player" —
itself a real signal (e.g. a center-back who never shoots), not missing
data to apologize for. Nulls are imputed with the population's non-null
mean *before* standardizing. Mean-imputation preserves the population
mean exactly, so an imputed value's z-score comes out to **exactly 0** —
"average, uninformative on this axis" — rather than a fabricated extreme.
Filling with 0 pre-standardization was explicitly rejected: for
`shot_conversion_pct`, a raw 0 reads as "attempted and always failed,"
which is a different and wrong claim for a player who simply never shot.

**Degenerate columns:** a feature with zero variance (or entirely null)
across the fitted population contributes exactly 0 to every row — it
carries no discriminating signal, so it's excluded from the similarity
computation in effect, without needing a separate feature-selection step.

## Baseline B ranking

`baseline_b_rank(query_features, candidates, feature_columns)` computes
cosine similarity between the (already-standardized) query vector and
each candidate row, ranks descending, and breaks ties on `player_id`
deterministically — same contract shape as `baseline_a_rank` (SLS-016),
so SLS-018's retrieval harness can run either baseline through identical
code.

## Early plausibility check (not the SLS-018 experiment)

Quick, informal check against real data — English top flight, ≥450
min/period, standardization fit on the 626-row combined period A+B
eligible pool:

- The same query player used in SLS-016's baseline A smoke test (who
  ranked **22nd of 315** under Baseline A) ranks **1st of 315** under
  Baseline B, with cosine similarity 0.90.
- Across a 30-player sample: Baseline B produced a better (lower) rank
  than Baseline A in 25 cases, a worse rank in 4, and tied in 1.

This is a strong early plausibility signal, not a result — SLS-018 runs
the actual global temporal retrieval experiment (MRR, Recall@K, bootstrap
CIs) that Gate 2 will be evaluated against. Recorded here only to confirm
the standardization/similarity implementation behaves sensibly before
building the full evaluation on top of it.
