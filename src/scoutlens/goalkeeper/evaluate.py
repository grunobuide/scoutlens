"""Gate 2 of `scoutlens-e87`: the frozen comparison, implemented once.

Everything decided here is decided in `protocol.PROTOCOL` (sha256 recorded in
`D064`); this module only carries it out, and refuses to compute an outcome
unless that exact protocol is on the ledger.

Both arms reuse the published experiment's own machinery rather than a
re-implementation of it: `run_baseline_b_retrieval` with `scope_column="role"`
is the within-role ranking that produced the published numbers, and
`bootstrap_mrr_delta` is the paired bootstrap the project already reports
deltas with. The baseline arm is therefore not "a baseline like the published
one" - its goalkeeper ranks are the published within-role ranks, and a test
holds that.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import polars as pl

from scoutlens.evaluation.retrieval import (
    RetrievalMetrics,
    bootstrap_mrr_delta,
    compute_metrics,
    run_baseline_b_retrieval,
    select_eligible_both_periods,
)
from scoutlens.evaluation.similarity import impute_and_standardize
from scoutlens.features.aggregation import FEATURE_COLUMNS
from scoutlens.goalkeeper import observability as obs
from scoutlens.goalkeeper.protocol import DECISIONS_LOG, assert_gate2_unlocked

GOALKEEPER = "Goalkeeper"
FAMILY_COLUMNS: list[str] = [feature.feature_id for feature in obs.FEATURES]
KEYS = ["player_id", "competitionId", "period"]

#: From the protocol's decision rule.
KEEP_MIN_MRR_DELTA = 0.020
N_RESAMPLES = 1000
SEED = 0

KEEP = "KEEP"
DROP = "DROP"


def build_arms(
    period_profiles: pl.DataFrame,
    role_lookup: pl.DataFrame,
    events: pl.DataFrame,
    minutes: pl.DataFrame,
    period_assignment: pl.DataFrame,
    minutes_threshold: int,
    competition_ids: list[int],
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """The goalkeeper unit-periods as each arm sees them.

    Baseline: the 32 catalog features standardised on the full all-roles
    eligible population over both periods - exactly what the published
    within-role run fits (`run_within_role_retrieval_experiment`).

    Candidate: those same 32 columns, plus the family standardised on the
    population it is defined for, eligible goalkeeper unit-periods over both
    periods. Nulls under the frozen minimum-support rule are mean-imputed to
    z = 0 by `impute_and_standardize`, the catalog's D008 rule.
    """
    eligible = select_eligible_both_periods(period_profiles, minutes_threshold, competition_ids).join(
        role_lookup, on="player_id", how="left"
    )
    standardized = impute_and_standardize(eligible, FEATURE_COLUMNS)
    baseline = standardized.filter(pl.col("role") == GOALKEEPER).select(KEYS + ["role"] + FEATURE_COLUMNS)

    units = baseline.select("player_id", "competitionId").unique()
    counts = obs.unit_period_counts(events, minutes, period_assignment, units)
    family = impute_and_standardize(obs.feature_values(counts), FAMILY_COLUMNS)

    candidate = baseline.join(family, on=KEYS, how="left")
    missing = candidate.filter(pl.any_horizontal(pl.col(FAMILY_COLUMNS).is_null())).height
    if missing:
        raise ValueError(f"{missing} goalkeeper unit-periods have no family row; the arms would not be paired")
    return baseline.sort(KEYS), candidate.sort(KEYS)


def rank_arm(arm: pl.DataFrame, feature_columns: list[str]) -> pl.DataFrame:
    """Each goalkeeper's period-A profile ranked against the goalkeeper
    period-B pool: the published within-role ranking, unchanged."""
    return run_baseline_b_retrieval(
        arm.filter(pl.col("period") == "A"),
        arm.filter(pl.col("period") == "B"),
        feature_columns,
        scope_column="role",
    ).sort("player_id", "competitionId")


def decide(baseline: RetrievalMetrics, candidate: RetrievalMetrics, mrr_delta: dict) -> str:
    """The protocol's rule, verbatim: KEEP only on all three conditions."""
    keep = (
        mrr_delta["point_estimate"] >= KEEP_MIN_MRR_DELTA
        and mrr_delta["ci_low"] > 0
        and candidate.recall_at_10 >= baseline.recall_at_10
    )
    return KEEP if keep else DROP


def _bucket(rank: int) -> str:
    if rank == 1:
        return "1"
    if rank <= 5:
        return "2-5"
    if rank <= 10:
        return "6-10"
    if rank <= 20:
        return "11-20"
    return ">20"


def compare(baseline: pl.DataFrame, candidate: pl.DataFrame, *, decisions_log: Path = DECISIONS_LOG) -> dict:
    """Run the frozen comparison. Fails closed before any ranking if the
    protocol is not on the ledger."""
    assert_gate2_unlocked(decisions_log)
    ranks_base = rank_arm(baseline, FEATURE_COLUMNS)
    ranks_cand = rank_arm(candidate, FEATURE_COLUMNS + FAMILY_COLUMNS)
    metrics_base = compute_metrics(ranks_base["rank"].to_list())
    metrics_cand = compute_metrics(ranks_cand["rank"].to_list())
    delta = bootstrap_mrr_delta(ranks_base, ranks_cand, n_resamples=N_RESAMPLES, seed=SEED)

    paired = ranks_base.join(ranks_cand, on=["player_id", "competitionId"], suffix="_candidate").select(
        "player_id",
        "competitionId",
        pl.col("rank").alias("rank_baseline"),
        pl.col("rank_candidate"),
        pl.col("pool_size"),
    )
    change = paired.with_columns((pl.col("rank_candidate") - pl.col("rank_baseline")).alias("rank_change"))
    buckets = ["1", "2-5", "6-10", "11-20", ">20"]
    return {
        "queries": paired.height,
        "pool_size": sorted(set(paired["pool_size"].to_list())),
        "baseline": asdict(metrics_base),
        "candidate": asdict(metrics_cand),
        "mrr_delta": delta,
        "recall_at_10_delta": metrics_cand.recall_at_10 - metrics_base.recall_at_10,
        "rank_distribution": {
            arm: {b: sum(1 for r in paired[column].to_list() if _bucket(r) == b) for b in buckets}
            for arm, column in (("baseline", "rank_baseline"), ("candidate", "rank_candidate"))
        },
        "rank_change": {
            "improved": change.filter(pl.col("rank_change") < 0).height,
            "unchanged": change.filter(pl.col("rank_change") == 0).height,
            "worsened": change.filter(pl.col("rank_change") > 0).height,
        },
        "largest_regressions": change.filter(pl.col("rank_change") > 0)
        .sort(["rank_change", "player_id"], descending=[True, False])
        .head(5)
        .to_dicts(),
        "decision": decide(metrics_base, metrics_cand, delta),
    }
