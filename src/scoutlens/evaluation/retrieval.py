"""Same-player temporal retrieval experiment (SLS-018: global condition;
SLS-019 reuses this for the within-role condition).

For each eligible player (period A profile = query), rank the period B
candidate pool and find the rank of that same player's own period B
profile. MRR / median rank / Recall@K summarize how well a baseline
recovers "this is probably the same player" from event-derived signal
alone.

"Global" means the candidate pool is every eligible period-B profile
across every competition passed in, not scoped per-competition — the
harder, more general version of the test (a full within-competition
scoping would make retrieval easier and mask league-level confounds,
which is exactly what SLS-020's diagnostics look for separately).
"""

from __future__ import annotations

import dataclasses
import statistics

import polars as pl

from scoutlens.evaluation.similarity import baseline_a_rank, baseline_b_rank, baseline_c_rank, impute_and_standardize
from scoutlens.features.aggregation import FEATURE_COLUMNS


@dataclasses.dataclass(frozen=True)
class RetrievalMetrics:
    n: int
    mrr: float
    median_rank: float
    recall_at_1: float
    recall_at_5: float
    recall_at_10: float


def compute_metrics(ranks: list[int]) -> RetrievalMetrics:
    if not ranks:
        raise ValueError("compute_metrics called with an empty rank list")
    n = len(ranks)
    return RetrievalMetrics(
        n=n,
        mrr=sum(1.0 / r for r in ranks) / n,
        median_rank=statistics.median(ranks),
        recall_at_1=sum(1 for r in ranks if r <= 1) / n,
        recall_at_5=sum(1 for r in ranks if r <= 5) / n,
        recall_at_10=sum(1 for r in ranks if r <= 10) / n,
    )


def select_eligible_both_periods(
    period_profiles: pl.DataFrame, minutes_threshold: int, competition_ids: list[int]
) -> pl.DataFrame:
    """Rows from `period_profiles` (build_period_profiles output) restricted
    to `competition_ids`, with `minutes_played >= minutes_threshold` in
    *both* periods for the same (player_id, competitionId) — the actual
    population the retrieval experiment can be run against, per
    chronological-split.md (looser season-level eligibility isn't enough
    here: a player must clear the bar in each period separately)."""
    scoped = period_profiles.filter(pl.col("competitionId").is_in(competition_ids))
    eligible = scoped.filter(pl.col("minutes_played") >= minutes_threshold)
    both_periods = (
        eligible.group_by(["player_id", "competitionId"])
        .agg(pl.col("period").n_unique().alias("n_periods"))
        .filter(pl.col("n_periods") == 2)
        .select("player_id", "competitionId")
    )
    return eligible.join(both_periods, on=["player_id", "competitionId"], how="inner")


def run_baseline_a_retrieval(
    query_profiles: pl.DataFrame, candidates: pl.DataFrame, scope_column: str | None = None
) -> pl.DataFrame:
    """query_profiles/candidates need `player_id`, `competitionId`, `role`,
    `minutes_played`. Returns one row per query: `player_id`,
    `competitionId`, `rank` (of that player's own row in `candidates`),
    `pool_size` (candidates actually ranked against, after scoping).

    `scope_column` (e.g. "role" for SLS-019's within-role condition), when
    given, restricts each query's candidate pool to rows where
    `candidates[scope_column] == query[scope_column]` before ranking.

    The true match is identified by `(player_id, competitionId)` together,
    per D007 — not `player_id` alone. In the current single-season,
    domestic-leagues-only population no player appears in two
    competitions, so this doesn't change today's numbers, but a `player_id`
    -only match would silently mismatch as soon as one did (multi-season
    data, a player in both a league and a tournament, etc.)."""
    rows = []
    for query in query_profiles.iter_rows(named=True):
        pool = candidates
        if scope_column is not None:
            pool = pool.filter(pl.col(scope_column) == query[scope_column])
        ranked = baseline_a_rank(query["role"], query["minutes_played"], pool)
        match = ranked.filter(
            (pl.col("player_id") == query["player_id"]) & (pl.col("competitionId") == query["competitionId"])
        )
        if match.height == 0:
            continue
        rows.append({
            "player_id": query["player_id"], "competitionId": query["competitionId"],
            "rank": match.row(0, named=True)["rank"], "pool_size": pool.height,
        })
    return pl.DataFrame(rows)


def run_baseline_c_retrieval(query_profiles: pl.DataFrame, candidates: pl.DataFrame) -> pl.DataFrame:
    """Robustness-check baseline (see robustness-checks.md): `same role
    AND same team -> same role only -> same team only -> neither`, minutes
    proximity as the tiebreak within each tier. Isolates how much
    Baseline B's advantage over Baseline A survives once a cheap
    same-team signal is added to the trivial baseline too — if Baseline C
    closes most of the gap to Baseline B, team membership (not
    event-derived playing style) would be doing most of the work.

    `query_profiles`/`candidates` need `player_id`, `competitionId`,
    `role`, `team_id`, `minutes_played`. Same D007-correct
    `(player_id, competitionId)` matching as the other two baselines."""
    rows = []
    for query in query_profiles.iter_rows(named=True):
        ranked = baseline_c_rank(query["role"], query["team_id"], query["minutes_played"], candidates)
        match = ranked.filter(
            (pl.col("player_id") == query["player_id"]) & (pl.col("competitionId") == query["competitionId"])
        )
        if match.height == 0:
            continue
        rows.append({
            "player_id": query["player_id"], "competitionId": query["competitionId"],
            "rank": match.row(0, named=True)["rank"], "pool_size": candidates.height,
        })
    return pl.DataFrame(rows)


def run_baseline_b_retrieval(
    query_profiles: pl.DataFrame,
    candidates: pl.DataFrame,
    feature_columns: list[str] = FEATURE_COLUMNS,
    scope_column: str | None = None,
    metric: str = "cosine",
) -> pl.DataFrame:
    """query_profiles/candidates must already be standardized on the same
    fitted population (see impute_and_standardize) — this function only
    ranks, it does not fit.

    `scope_column` (e.g. "role" for SLS-019's within-role condition), when
    given, restricts each query's candidate pool to rows where
    `candidates[scope_column] == query[scope_column]` before ranking —
    `candidates` must carry that column even though it isn't part of
    `feature_columns` (it passes through `baseline_b_rank` untouched).

    `metric`: forwarded to `baseline_b_rank` — `"cosine"` (default) or
    `"euclidean"`, a robustness comparison point (see robustness-checks.md).

    The true match is identified by `(player_id, competitionId)` together,
    per D007 — see the same note on `run_baseline_a_retrieval`."""
    rows = []
    keep_cols = ["player_id", "competitionId"] + ([scope_column] if scope_column else []) + feature_columns
    candidate_features = candidates.select(keep_cols)
    for query in query_profiles.iter_rows(named=True):
        pool = candidate_features
        if scope_column is not None:
            pool = pool.filter(pl.col(scope_column) == query[scope_column])
        query_features = {c: query[c] for c in feature_columns}
        ranked = baseline_b_rank(query_features, pool, feature_columns, metric=metric)
        match = ranked.filter(
            (pl.col("player_id") == query["player_id"]) & (pl.col("competitionId") == query["competitionId"])
        )
        if match.height == 0:
            continue
        rows.append({
            "player_id": query["player_id"], "competitionId": query["competitionId"],
            "rank": match.row(0, named=True)["rank"], "pool_size": pool.height,
        })
    return pl.DataFrame(rows)


def get_top_k_neighbors(
    query_profiles: pl.DataFrame,
    candidates: pl.DataFrame,
    feature_columns: list[str] = FEATURE_COLUMNS,
    k: int = 10,
    scope_column: str | None = None,
) -> pl.DataFrame:
    """Like `run_baseline_b_retrieval`, but returns every query's top `k`
    neighbors (not just the true match's rank) — SLS-020's context
    diagnostics need the actual neighbor identities to check what they
    have in common (team, league), not just how well-ranked the true
    match was. `query_profiles`/`candidates` must already be standardized
    on the same fitted population, same contract as `baseline_b_rank`.

    Returns one row per (query, neighbor): `query_player_id`,
    `competitionId` (the query's), `neighbor_rank`, `neighbor_player_id`,
    `neighbor_competitionId`, `is_true_match` (whether this neighbor *is*
    the query's own period-B row, identified by `(player_id,
    competitionId)` together per D007 — diagnostics that measure
    confounds among the neighbors, e.g. `neighbor_concentration`, should
    exclude `is_true_match` rows first: a correctly-retrieved true match
    trivially shares the query's team, which would otherwise inflate an
    apparent team confound with retrieval successes rather than mistakes).
    """
    rows = []
    keep_cols = ["player_id", "competitionId"] + ([scope_column] if scope_column else []) + feature_columns
    candidate_features = candidates.select(keep_cols)
    for query in query_profiles.iter_rows(named=True):
        pool = candidate_features
        if scope_column is not None:
            pool = pool.filter(pl.col(scope_column) == query[scope_column])
        query_features = {c: query[c] for c in feature_columns}
        ranked = baseline_b_rank(query_features, pool, feature_columns)
        top_k = ranked.sort("rank").head(k)
        for neighbor in top_k.iter_rows(named=True):
            is_true_match = (
                neighbor["player_id"] == query["player_id"] and neighbor["competitionId"] == query["competitionId"]
            )
            rows.append({
                "query_player_id": query["player_id"], "competitionId": query["competitionId"],
                "neighbor_rank": neighbor["rank"], "neighbor_player_id": neighbor["player_id"],
                "neighbor_competitionId": neighbor["competitionId"], "is_true_match": is_true_match,
            })
    return pl.DataFrame(rows)


def bootstrap_mrr_delta(
    ranks_a: pl.DataFrame, ranks_b: pl.DataFrame, n_resamples: int = 1000, seed: int = 0
) -> dict:
    """Paired bootstrap over queries for MRR(B) - MRR(A). `ranks_a`/`ranks_b`
    must cover the same (player_id, competitionId) query set — joined here
    to guarantee alignment before resampling, rather than trusting caller
    row order. Explicitly sorted by (player_id, competitionId) after the
    join, not just joined: a join's output row order isn't guaranteed by
    polars, so without this sort, `rng.randrange` draws against index
    positions that could vary run to run even with the same seed —
    harmless for the point estimate (order-invariant) but a real source
    of the ~0.002 CI-bound jitter observed across runs before this fix
    (found in review; previously only documented as a caveat)."""
    paired = (
        ranks_a.join(ranks_b, on=["player_id", "competitionId"], suffix="_b")
        .sort(["player_id", "competitionId"])
        .select(pl.col("rank").alias("rank_a"), pl.col("rank_b"))
    )
    n = paired.height
    rank_a = paired["rank_a"].to_list()
    rank_b = paired["rank_b"].to_list()

    import random
    rng = random.Random(seed)
    deltas = []
    for _ in range(n_resamples):
        idx = [rng.randrange(n) for _ in range(n)]
        mrr_a = sum(1.0 / rank_a[i] for i in idx) / n
        mrr_b = sum(1.0 / rank_b[i] for i in idx) / n
        deltas.append(mrr_b - mrr_a)

    deltas.sort()
    lo = deltas[int(0.025 * n_resamples)]
    hi = deltas[int(0.975 * n_resamples) - 1]
    point_estimate = (sum(1.0 / r for r in rank_b) / n) - (sum(1.0 / r for r in rank_a) / n)
    return {"point_estimate": point_estimate, "ci_low": lo, "ci_high": hi, "n_resamples": n_resamples, "n_queries": n}


def bootstrap_mrr_delta_clustered(
    ranks_a: pl.DataFrame,
    ranks_b: pl.DataFrame,
    clusters: pl.DataFrame,
    n_resamples: int = 1000,
    seed: int = 0,
) -> dict:
    """Cluster bootstrap for MRR(B) - MRR(A): resamples whole *clusters*
    of queries with replacement instead of individual queries, so
    within-cluster correlation (teammates' retrieval difficulty moving
    together, league-level effects) widens the interval instead of being
    ignored — the check feasibility-report.md's Limitation #12 asked for.

    `clusters` maps every query to a cluster: columns `player_id`,
    `competitionId`, `cluster` (any hashable dtype — team_id, league id).
    Queries missing from `clusters` (null after the left join) raise:
    silently dropping them would change the estimand.

    Same determinism contract as `bootstrap_mrr_delta`: sorted before
    resampling, fixed seed reproduces bit-identical CI bounds. Each
    resample draws `n_clusters` clusters with replacement and pools
    their queries, so resample sizes vary with cluster sizes — standard
    for the cluster bootstrap; the delta is a per-resample mean, so
    unequal sizes are handled naturally."""
    paired = (
        ranks_a.join(ranks_b, on=["player_id", "competitionId"], suffix="_b")
        .join(clusters, on=["player_id", "competitionId"], how="left")
        .sort(["player_id", "competitionId"])
        .select(pl.col("rank").alias("rank_a"), pl.col("rank_b"), pl.col("cluster"))
    )
    if paired["cluster"].null_count() > 0:
        raise ValueError(
            f"{paired['cluster'].null_count()} queries have no cluster assignment — "
            "the clusters table must cover every (player_id, competitionId) query"
        )
    n = paired.height
    by_cluster: dict = {}
    for rank_a, rank_b, cluster in paired.iter_rows():
        by_cluster.setdefault(cluster, []).append((1.0 / rank_a, 1.0 / rank_b))
    cluster_ids = sorted(by_cluster)
    n_clusters = len(cluster_ids)

    import random
    rng = random.Random(seed)
    deltas = []
    for _ in range(n_resamples):
        total_a = total_b = 0.0
        count = 0
        for _ in range(n_clusters):
            drawn = by_cluster[cluster_ids[rng.randrange(n_clusters)]]
            for rr_a, rr_b in drawn:
                total_a += rr_a
                total_b += rr_b
            count += len(drawn)
        deltas.append((total_b - total_a) / count)

    deltas.sort()
    lo = deltas[int(0.025 * n_resamples)]
    hi = deltas[int(0.975 * n_resamples) - 1]
    point_estimate = (
        sum(1.0 / r for r in paired["rank_b"]) - sum(1.0 / r for r in paired["rank_a"])
    ) / n
    return {
        "point_estimate": point_estimate,
        "ci_low": lo,
        "ci_high": hi,
        "n_resamples": n_resamples,
        "n_queries": n,
        "n_clusters": n_clusters,
    }


def run_global_retrieval_experiment(
    period_profiles: pl.DataFrame,
    role_lookup: pl.DataFrame,
    minutes_threshold: int,
    competition_ids: list[int],
    feature_columns: list[str] = FEATURE_COLUMNS,
    scope_column: str | None = None,
    n_resamples: int = 1000,
    seed: int = 0,
) -> dict:
    """End-to-end retrieval run (SLS-018 global condition when
    `scope_column=None`; SLS-019's within-role condition when
    `scope_column="role"` — see `run_within_role_retrieval_experiment`,
    a thin wrapper for that case). Returns a dict with the eligible
    population, both baselines' RetrievalMetrics, their raw rank tables
    (for SLS-020/021 diagnostics, including `pool_size` when scoped —
    a scoped pool can be smaller than the global one, which affects how
    a given rank should be read), and the bootstrap CI on the MRR delta.
    """
    eligible = select_eligible_both_periods(period_profiles, minutes_threshold, competition_ids)
    eligible = eligible.join(role_lookup, on="player_id", how="left")

    query_a = eligible.filter(pl.col("period") == "A")
    candidates_b = eligible.filter(pl.col("period") == "B")

    ranks_a = run_baseline_a_retrieval(query_a, candidates_b, scope_column=scope_column)
    metrics_a = compute_metrics(ranks_a["rank"].to_list())

    combined_features = impute_and_standardize(eligible, feature_columns)
    query_a_std = combined_features.filter(pl.col("period") == "A")
    candidates_b_std = combined_features.filter(pl.col("period") == "B")
    ranks_b = run_baseline_b_retrieval(query_a_std, candidates_b_std, feature_columns, scope_column=scope_column)
    metrics_b = compute_metrics(ranks_b["rank"].to_list())

    delta = bootstrap_mrr_delta(ranks_a, ranks_b, n_resamples=n_resamples, seed=seed)

    return {
        "n_eligible_player_competition": eligible.select("player_id", "competitionId").unique().height,
        "n_candidates_period_b": candidates_b.height,
        "baseline_a": metrics_a,
        "baseline_b": metrics_b,
        "mrr_delta": delta,
        "ranks_a": ranks_a,
        "ranks_b": ranks_b,
    }


def run_within_role_retrieval_experiment(
    period_profiles: pl.DataFrame,
    role_lookup: pl.DataFrame,
    minutes_threshold: int,
    competition_ids: list[int],
    feature_columns: list[str] = FEATURE_COLUMNS,
    n_resamples: int = 1000,
    seed: int = 0,
) -> dict:
    """SLS-019: identical to the global experiment (SLS-018) except each
    query's candidate pool is restricted to players sharing its nominal
    role. Standardization is still fit on the full (all-roles) eligible
    population — only the *candidate pool at ranking time* is scoped, not
    the feature scale — so this tests "does the signal survive once role
    stops resolving the problem," per the brief's H4, rather than
    re-normalizing away cross-role variance that might itself be
    meaningful."""
    return run_global_retrieval_experiment(
        period_profiles, role_lookup, minutes_threshold, competition_ids, feature_columns,
        scope_column="role", n_resamples=n_resamples, seed=seed,
    )
