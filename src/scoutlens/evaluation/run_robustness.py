"""Robustness battery for Baseline B, run against real data (SLS-023
follow-up, per feasibility-report.md's revised Recommended Next
Experiment #1 — harden the current baseline before reaching for a
learned representation).

Run with:

    uv run python -m scoutlens.evaluation.run_robustness

Writes artifacts/robustness_results.json. Same scope/config philosophy
as run_report.py: parameters come from the versioned
`config/experiment.json`, and the artifact embeds a `_manifest` (see
`run_manifest.py`, D015).

Checks:
1. Standardization fit on period A alone vs. today's A+B combined fit (D008).
2. Cosine vs. Euclidean distance.
3. Baseline C (role + team + minutes) vs. Baseline A and Baseline B —
   isolates how much of Baseline A's weakness a cheap team signal alone
   would fix.
4. Drop-teammates sensitivity check: exclude same-team-as-query candidates
   (other than the true match itself) from the pool, see if MRR moves.
5. Per-feature-family ablation: each of the 8 families run alone.
"""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl

from scoutlens.evaluation.diagnostics import compute_primary_team
from scoutlens.evaluation.run_manifest import build_run_manifest, load_experiment_config
from scoutlens.evaluation.retrieval import (
    bootstrap_mrr_delta,
    compute_metrics,
    run_baseline_a_retrieval,
    run_baseline_b_retrieval,
    run_baseline_c_retrieval,
    run_global_retrieval_experiment,
    select_eligible_both_periods,
)
from scoutlens.evaluation.similarity import apply_scaler, fit_scaler, impute_and_standardize
from scoutlens.evaluation.temporal import assign_periods, build_period_profiles
from scoutlens.features.aggregation import FEATURE_COLUMNS, FEATURE_FAMILIES

REPO_ROOT = Path(__file__).resolve().parents[3]
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
ARTIFACTS_DIR = REPO_ROOT / "artifacts"

INPUT_FILES = ("players", "matches", "minutes", "events")


def _role_lookup(players: pl.DataFrame) -> pl.DataFrame:
    return players.select(pl.col("wyId").alias("player_id"), pl.col("role").struct.field("name").alias("role"))


def _load_period_profiles():
    players = pl.read_parquet(PROCESSED_DIR / "players.parquet")
    matches = pl.read_parquet(PROCESSED_DIR / "matches.parquet")
    minutes = pl.read_parquet(PROCESSED_DIR / "minutes.parquet")
    events = pl.read_parquet(PROCESSED_DIR / "events.parquet")
    period_assignment = assign_periods(matches)
    period_profiles = build_period_profiles(events, minutes, period_assignment)
    return period_profiles, players, matches, minutes, period_assignment


def check_a_only_vs_combined_scaling(eligible: pl.DataFrame) -> dict:
    query_a = eligible.filter(pl.col("period") == "A")
    candidates_b = eligible.filter(pl.col("period") == "B")

    # today's default: fit on A+B combined
    combined_std = impute_and_standardize(eligible, FEATURE_COLUMNS)
    ranks_combined = run_baseline_b_retrieval(
        combined_std.filter(pl.col("period") == "A"), combined_std.filter(pl.col("period") == "B")
    )

    # robustness check: fit on period A alone, apply to both
    a_only_scaler = fit_scaler(query_a, FEATURE_COLUMNS)
    query_a_std = apply_scaler(query_a, FEATURE_COLUMNS, a_only_scaler)
    candidates_b_std = apply_scaler(candidates_b, FEATURE_COLUMNS, a_only_scaler)
    ranks_a_only = run_baseline_b_retrieval(query_a_std, candidates_b_std)

    return {
        "combined_fit": compute_metrics(ranks_combined["rank"].to_list()).__dict__,
        "a_only_fit": compute_metrics(ranks_a_only["rank"].to_list()).__dict__,
    }


def check_cosine_vs_euclidean(eligible: pl.DataFrame) -> dict:
    combined_std = impute_and_standardize(eligible, FEATURE_COLUMNS)
    query_a_std = combined_std.filter(pl.col("period") == "A")
    candidates_b_std = combined_std.filter(pl.col("period") == "B")

    ranks_cosine = run_baseline_b_retrieval(query_a_std, candidates_b_std, metric="cosine")
    ranks_euclidean = run_baseline_b_retrieval(query_a_std, candidates_b_std, metric="euclidean")

    return {
        "cosine": compute_metrics(ranks_cosine["rank"].to_list()).__dict__,
        "euclidean": compute_metrics(ranks_euclidean["rank"].to_list()).__dict__,
    }


def check_baseline_c(eligible_with_team: pl.DataFrame) -> dict:
    query_a = eligible_with_team.filter(pl.col("period") == "A")
    candidates_b = eligible_with_team.filter(pl.col("period") == "B")
    ranks_c = run_baseline_c_retrieval(query_a, candidates_b)
    return compute_metrics(ranks_c["rank"].to_list()).__dict__


def check_drop_teammates(eligible_with_team: pl.DataFrame) -> dict:
    """Exclude, per query, every period-B candidate on the query's own
    period-A team except the true match itself. If Baseline B's MRR barely
    moves, teammates in the pool weren't meaningfully helping or hurting."""
    query_a = eligible_with_team.filter(pl.col("period") == "A")
    combined_std = impute_and_standardize(eligible_with_team, FEATURE_COLUMNS)
    query_a_std = combined_std.filter(pl.col("period") == "A")
    candidates_b_std = combined_std.filter(pl.col("period") == "B").join(
        eligible_with_team.filter(pl.col("period") == "B").select("player_id", "competitionId", "team_id"),
        on=["player_id", "competitionId"],
    )

    from scoutlens.evaluation.similarity import baseline_b_rank

    ranks = []
    for query in query_a_std.iter_rows(named=True):
        query_team_row = query_a.filter(
            (pl.col("player_id") == query["player_id"]) & (pl.col("competitionId") == query["competitionId"])
        )
        query_team = query_team_row.row(0, named=True)["team_id"]
        pool = candidates_b_std.filter(
            (pl.col("team_id") != query_team) | (pl.col("player_id") == query["player_id"])
        )
        query_features = {c: query[c] for c in FEATURE_COLUMNS}
        ranked = baseline_b_rank(query_features, pool, FEATURE_COLUMNS)
        match = ranked.filter(
            (pl.col("player_id") == query["player_id"]) & (pl.col("competitionId") == query["competitionId"])
        )
        if match.height == 0:
            continue
        ranks.append(match.row(0, named=True)["rank"])

    return compute_metrics(ranks).__dict__


def check_feature_family_ablation(
    period_profiles: pl.DataFrame, role_lookup: pl.DataFrame, minutes_threshold: int, leagues: list[int]
) -> dict:
    results = {}
    for family, cols in FEATURE_FAMILIES.items():
        r = run_global_retrieval_experiment(
            period_profiles, role_lookup, minutes_threshold, leagues, feature_columns=cols
        )
        results[family] = {"n_features": len(cols), "mrr": r["baseline_b"].mrr, "median_rank": r["baseline_b"].median_rank}
    return results


def run() -> dict:
    config = load_experiment_config()
    leagues = config["domestic_leagues"]
    minutes_threshold = config["primary_minutes_threshold"]

    period_profiles, players, matches, minutes, period_assignment = _load_period_profiles()
    role_lookup = _role_lookup(players)

    eligible = select_eligible_both_periods(period_profiles, minutes_threshold, leagues)
    eligible = eligible.join(role_lookup, on="player_id", how="left")

    primary_team = compute_primary_team(minutes, period_assignment).select(
        "player_id", "competitionId", "period", pl.col("team_id")
    )
    eligible_with_team = eligible.join(primary_team, on=["player_id", "competitionId", "period"], how="left")

    baseline_a = run_baseline_a_retrieval(
        eligible.filter(pl.col("period") == "A"), eligible.filter(pl.col("period") == "B")
    )
    baseline_a_metrics = compute_metrics(baseline_a["rank"].to_list()).__dict__

    return {
        "_manifest": build_run_manifest(
            config, [PROCESSED_DIR / f"{name}.parquet" for name in INPUT_FILES]
        ),
        "baseline_a_reference": baseline_a_metrics,
        "check_1_standardization_fit": check_a_only_vs_combined_scaling(eligible),
        "check_2_distance_metric": check_cosine_vs_euclidean(eligible),
        "check_3_baseline_c_role_team_minutes": check_baseline_c(eligible_with_team),
        "check_4_drop_teammates": check_drop_teammates(eligible_with_team),
        "check_5_feature_family_ablation": check_feature_family_ablation(
            period_profiles, role_lookup, minutes_threshold, leagues
        ),
    }


if __name__ == "__main__":
    results = run()
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = ARTIFACTS_DIR / "robustness_results.json"
    out_path.write_text(json.dumps(results, indent=2))
    print(f"wrote {out_path}")
    print(json.dumps(results, indent=2))
