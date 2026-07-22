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

from scoutlens.evaluation.similarity import baseline_a_rank, baseline_b_rank, impute_and_standardize
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


def run_baseline_a_retrieval(query_profiles: pl.DataFrame, candidates: pl.DataFrame) -> pl.DataFrame:
    """query_profiles/candidates need `player_id`, `competitionId`, `role`,
    `minutes_played`. Returns one row per query: `player_id`,
    `competitionId`, `rank` (of that player's own row in `candidates`)."""
    rows = []
    for query in query_profiles.iter_rows(named=True):
        ranked = baseline_a_rank(query["role"], query["minutes_played"], candidates)
        match = ranked.filter(pl.col("player_id") == query["player_id"])
        if match.height == 0:
            continue
        rows.append({
            "player_id": query["player_id"], "competitionId": query["competitionId"],
            "rank": match.row(0, named=True)["rank"],
        })
    return pl.DataFrame(rows)


def run_baseline_b_retrieval(
    query_profiles: pl.DataFrame, candidates: pl.DataFrame, feature_columns: list[str] = FEATURE_COLUMNS
) -> pl.DataFrame:
    """query_profiles/candidates must already be standardized on the same
    fitted population (see impute_and_standardize) — this function only
    ranks, it does not fit."""
    rows = []
    candidate_features = candidates.select(["player_id"] + feature_columns)
    for query in query_profiles.iter_rows(named=True):
        query_features = {c: query[c] for c in feature_columns}
        ranked = baseline_b_rank(query_features, candidate_features, feature_columns)
        match = ranked.filter(pl.col("player_id") == query["player_id"])
        if match.height == 0:
            continue
        rows.append({
            "player_id": query["player_id"], "competitionId": query["competitionId"],
            "rank": match.row(0, named=True)["rank"],
        })
    return pl.DataFrame(rows)


def bootstrap_mrr_delta(
    ranks_a: pl.DataFrame, ranks_b: pl.DataFrame, n_resamples: int = 1000, seed: int = 0
) -> dict:
    """Paired bootstrap over queries for MRR(B) - MRR(A). `ranks_a`/`ranks_b`
    must cover the same (player_id, competitionId) query set — joined here
    to guarantee alignment before resampling, rather than trusting caller
    row order."""
    paired = ranks_a.join(ranks_b, on=["player_id", "competitionId"], suffix="_b").select(
        pl.col("rank").alias("rank_a"), pl.col("rank_b")
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


def run_global_retrieval_experiment(
    period_profiles: pl.DataFrame,
    role_lookup: pl.DataFrame,
    minutes_threshold: int,
    competition_ids: list[int],
    feature_columns: list[str] = FEATURE_COLUMNS,
) -> dict:
    """End-to-end SLS-018 global retrieval run. Returns a dict with the
    eligible population, both baselines' RetrievalMetrics, their raw rank
    tables (for SLS-020/021 diagnostics), and the bootstrap CI on the MRR
    delta."""
    eligible = select_eligible_both_periods(period_profiles, minutes_threshold, competition_ids)
    eligible = eligible.join(role_lookup, on="player_id", how="left")

    query_a = eligible.filter(pl.col("period") == "A")
    candidates_b = eligible.filter(pl.col("period") == "B")

    ranks_a = run_baseline_a_retrieval(query_a, candidates_b)
    metrics_a = compute_metrics(ranks_a["rank"].to_list())

    combined_features = impute_and_standardize(eligible, feature_columns)
    query_a_std = combined_features.filter(pl.col("period") == "A")
    candidates_b_std = combined_features.filter(pl.col("period") == "B")
    ranks_b = run_baseline_b_retrieval(query_a_std, candidates_b_std, feature_columns)
    metrics_b = compute_metrics(ranks_b["rank"].to_list())

    delta = bootstrap_mrr_delta(ranks_a, ranks_b)

    return {
        "n_eligible_player_competition": eligible.select("player_id", "competitionId").unique().height,
        "n_candidates_period_b": candidates_b.height,
        "baseline_a": metrics_a,
        "baseline_b": metrics_b,
        "mrr_delta": delta,
        "ranks_a": ranks_a,
        "ranks_b": ranks_b,
    }
