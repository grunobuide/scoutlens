"""Baseline A (SLS-016) and Baseline B (SLS-017).

Baseline A: `same nominal role -> nearest minutes played`. Baseline B:
standardized event-derived features + cosine similarity. Per the brief,
Baseline A is the trivial method the "real" method (B) has to beat — if B
can't outperform "just find someone in the same position with a similar
workload," added complexity isn't earning its place.

Both baselines share the same shape (`*_rank(query, candidates, ...) ->
ranked DataFrame with a 1-indexed `rank` column`), so SLS-018's retrieval
evaluation can run either one through identical harness code.
"""

from __future__ import annotations

import math

import polars as pl


def baseline_a_rank(query_role: str, query_minutes: float, candidates: pl.DataFrame) -> pl.DataFrame:
    """Ranks `candidates` (must have `player_id`, `role`, `minutes_played`)
    against a query player's `role` and `minutes_played`.

    Ordering: same role as the query first, ordered by ascending minutes
    distance; different-role candidates after, also ordered by ascending
    minutes distance. This is a full ranking over every candidate (not a
    same-role filter) so it plugs directly into rank-based retrieval
    metrics (MRR, Recall@K, SLS-018) where the correct answer might, in
    principle, be a different nominal role.

    `player_id` is used as a final, deterministic tiebreak — ties on
    (same_role, minutes_distance) would otherwise have unstable order.
    """
    ranked = candidates.with_columns(
        same_role=(pl.col("role") == query_role),
        minutes_distance=(pl.col("minutes_played") - query_minutes).abs(),
    ).sort(["same_role", "minutes_distance", "player_id"], descending=[True, False, False])
    return ranked.with_row_index("rank", offset=1)


def impute_and_standardize(profiles: pl.DataFrame, feature_columns: list[str]) -> pl.DataFrame:
    """Resolves D008 (decisions-log.md). Fits mean/std **on `profiles`
    itself** and returns a copy with `feature_columns` replaced by
    z-scores.

    Null handling: a null in a ratio feature (e.g. `shot_conversion_pct`
    for a player who never shot) means "this action never came up," which
    is itself role signal, not missing data to apologize for — but cosine
    similarity can't consume a null. Nulls are imputed with the
    population's non-null mean *before* standardizing. Mean-imputation
    preserves the population mean exactly, so an imputed value's z-score
    comes out to exactly 0 — "average, uninformative on this axis" rather
    than a fabricated extreme (0 would read as "attempted and always
    failed," which is a different and wrong claim for a player who simply
    never attempted the action).

    Caller must pass the full population the fit should be computed over
    — e.g. every eligible player-period row across *both* periods being
    compared for a competition. Fitting period A and period B separately
    would measure the query and the candidate pool on different scales,
    silently distorting the similarity.
    """
    exprs = []
    for col in feature_columns:
        mean_val = profiles[col].mean()
        if mean_val is None:
            # every value in this column is null across the whole
            # population — no signal to standardize; contributes nothing.
            exprs.append(pl.lit(0.0).alias(col))
            continue
        imputed = pl.col(col).fill_null(mean_val)
        std_val = profiles[col].fill_null(mean_val).std()
        if not std_val:
            exprs.append(pl.lit(0.0).alias(col))
        else:
            exprs.append(((imputed - mean_val) / std_val).alias(col))
    return profiles.with_columns(exprs)


def baseline_b_rank(
    query_features: dict[str, float], candidates: pl.DataFrame, feature_columns: list[str]
) -> pl.DataFrame:
    """Ranks `candidates` by cosine similarity to `query_features`.

    Both `query_features` and `candidates[feature_columns]` must already
    be standardized on the *same* fitted population — call
    `impute_and_standardize` once on the combined query+candidate pool,
    then split the query row back out, before calling this. This function
    only ranks; it does not fit anything, mirroring `baseline_a_rank`.

    `player_id` breaks ties deterministically, same as Baseline A.
    """
    query_norm = math.sqrt(sum(query_features[c] ** 2 for c in feature_columns))
    dot_expr = sum((query_features[c] * pl.col(c) for c in feature_columns), start=pl.lit(0.0))
    norm_expr = sum((pl.col(c) ** 2 for c in feature_columns), start=pl.lit(0.0)).sqrt()

    ranked = candidates.with_columns(
        cosine_similarity=pl.when((norm_expr > 0) & (query_norm > 0))
        .then(dot_expr / (norm_expr * query_norm))
        .otherwise(0.0)
    ).sort(["cosine_similarity", "player_id"], descending=[True, False])
    return ranked.with_row_index("rank", offset=1)
