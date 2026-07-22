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


Scaler = dict[str, tuple[float, float] | None]
"""feature_column -> (mean, std) used to fit it, or None if the column was
degenerate (all-null or zero-variance) — see `fit_scaler`."""


def fit_scaler(profiles: pl.DataFrame, feature_columns: list[str]) -> Scaler:
    """Computes the (mean, std) each feature will be standardized against.
    `mean` is the *non-null* mean (nulls are mean-imputed before std is
    computed, so imputed rows land at exactly z=0 — see `apply_scaler`).
    A column that's entirely null, or has zero variance after imputation,
    gets `None` (degenerate — contributes exactly 0 under `apply_scaler`,
    same as before, just now with an inspectable reason)."""
    scaler: Scaler = {}
    for col in feature_columns:
        mean_val = profiles[col].mean()
        if mean_val is None:
            scaler[col] = None
            continue
        std_val = profiles[col].fill_null(mean_val).std()
        scaler[col] = None if not std_val else (mean_val, std_val)
    return scaler


def apply_scaler(profiles: pl.DataFrame, feature_columns: list[str], scaler: Scaler) -> pl.DataFrame:
    """Applies a `Scaler` fit elsewhere (see `fit_scaler`) to `profiles`,
    replacing `feature_columns` with z-scores. Split from `fit_scaler` so
    a scaler fit on one population (e.g. period A alone) can be applied to
    a different population (e.g. period B) — needed to compare "fit on
    A+B combined" (D008's original choice, via `impute_and_standardize`)
    against "fit on A alone" as a robustness check."""
    exprs = []
    for col in feature_columns:
        fit = scaler.get(col)
        if fit is None:
            exprs.append(pl.lit(0.0).alias(col))
            continue
        mean_val, std_val = fit
        exprs.append(((pl.col(col).fill_null(mean_val) - mean_val) / std_val).alias(col))
    return profiles.with_columns(exprs)


def impute_and_standardize(profiles: pl.DataFrame, feature_columns: list[str]) -> pl.DataFrame:
    """Resolves D008 (decisions-log.md). Fits mean/std **on `profiles`
    itself** (via `fit_scaler`) and returns a copy with `feature_columns`
    replaced by z-scores (via `apply_scaler`) — the common case where the
    population being fit and the population being transformed are the
    same. For fit-on-one/apply-to-another (e.g. the A-only-fit robustness
    check), call `fit_scaler`/`apply_scaler` directly instead.

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
    return apply_scaler(profiles, feature_columns, fit_scaler(profiles, feature_columns))


def baseline_b_rank(
    query_features: dict[str, float],
    candidates: pl.DataFrame,
    feature_columns: list[str],
    metric: str = "cosine",
) -> pl.DataFrame:
    """Ranks `candidates` by similarity to `query_features`.

    Both `query_features` and `candidates[feature_columns]` must already
    be standardized on the *same* fitted population — call
    `impute_and_standardize` (or `fit_scaler`/`apply_scaler`) once on the
    relevant population, then split the query row back out, before
    calling this. This function only ranks; it does not fit anything,
    mirroring `baseline_a_rank`.

    `metric`: `"cosine"` (default — direction of the standardized feature
    vector, scale-invariant) or `"euclidean"` (straight-line distance in
    standardized feature space, scale-sensitive — a robustness comparison
    point, not the primary method; see D008 and the robustness-checks
    writeup for why cosine was chosen as the default).

    `player_id` breaks ties deterministically, same as Baseline A.
    """
    if metric not in ("cosine", "euclidean"):
        raise ValueError(f"unknown metric: {metric!r}")

    if metric == "cosine":
        query_norm = math.sqrt(sum(query_features[c] ** 2 for c in feature_columns))
        dot_expr = sum((query_features[c] * pl.col(c) for c in feature_columns), start=pl.lit(0.0))
        norm_expr = sum((pl.col(c) ** 2 for c in feature_columns), start=pl.lit(0.0)).sqrt()
        score_expr = pl.when((norm_expr > 0) & (query_norm > 0)).then(dot_expr / (norm_expr * query_norm)).otherwise(0.0)
        ranked = candidates.with_columns(cosine_similarity=score_expr)
        return ranked.sort(["cosine_similarity", "player_id"], descending=[True, False]).with_row_index("rank", offset=1)

    # euclidean: smaller distance = more similar, so sort ascending
    sq_dist_expr = sum(((pl.col(c) - query_features[c]) ** 2 for c in feature_columns), start=pl.lit(0.0))
    ranked = candidates.with_columns(euclidean_distance=sq_dist_expr.sqrt())
    return ranked.sort(["euclidean_distance", "player_id"], descending=[False, False]).with_row_index("rank", offset=1)


def baseline_c_rank(
    query_role: str, query_team_id: int, query_minutes: float, candidates: pl.DataFrame
) -> pl.DataFrame:
    """Robustness-check baseline: `same role AND same team -> same role
    only -> same team only -> neither`, ties within each tier broken by
    ascending minutes distance. `candidates` need `player_id`, `role`,
    `team_id`, `minutes_played`.

    Purpose: isolate how much of Baseline A's weak performance was "role
    alone isn't enough" versus "role *and* team together still wouldn't
    be enough" — i.e. how much headroom is left for Baseline B's
    event-derived features specifically, once both cheap categorical
    signals are already accounted for."""
    same_role = pl.col("role") == query_role
    same_team = pl.col("team_id") == query_team_id
    ranked = candidates.with_columns(
        same_role=same_role, same_team=same_team,
        minutes_distance=(pl.col("minutes_played") - query_minutes).abs(),
    ).sort(["same_role", "same_team", "minutes_distance", "player_id"], descending=[True, True, False, False])
    return ranked.with_row_index("rank", offset=1)
