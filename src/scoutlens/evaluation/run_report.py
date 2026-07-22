"""Single-command reproduction of every number in feasibility-report.md's
Temporal Stability Results and Position/Minutes/League Diagnostics
sections.

Run with:

    uv run python -m scoutlens.evaluation.run_report

Requires data/processed/*.parquet to already exist (see
`scoutlens.data.ingestion` and `scoutlens.data.minutes`). Writes a JSON
summary to artifacts/gate2_results.json — gitignored like the rest of
`artifacts/`, regenerated on demand rather than checked in, per the
repo's existing convention for spike outputs.

Configuration is inlined below rather than an external file — proportional
to a single-experiment spike, not a claim that this is the final shape a
multi-experiment version of this tool should take (see limitation #14 in
feasibility-report.md: a versioned config + run-manifest with checksums
is real future work, not attempted here).

Reproducibility note: MRR/Recall point estimates and the minutes
sensitivity curve are exactly reproducible run to run. Bootstrap CI
*bounds* (not the point estimate) can vary by roughly +/-0.002 between
runs — `bootstrap_mrr_delta` uses a fixed seed, but which specific
resampled index lands on which query depends on the row order the
eligible population happens to be constructed in, which polars doesn't
guarantee identically across runs unless explicitly sorted. This is
ordinary Monte Carlo noise at n_resamples=1000, not a correctness issue.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import polars as pl

from scoutlens.evaluation.diagnostics import compute_primary_team, neighbor_concentration
from scoutlens.evaluation.retrieval import (
    get_top_k_neighbors,
    run_global_retrieval_experiment,
    run_within_role_retrieval_experiment,
    select_eligible_both_periods,
)
from scoutlens.evaluation.similarity import impute_and_standardize
from scoutlens.evaluation.temporal import assign_periods, build_period_profiles
from scoutlens.features.aggregation import FEATURE_COLUMNS

REPO_ROOT = Path(__file__).resolve().parents[3]
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
ARTIFACTS_DIR = REPO_ROOT / "artifacts"

DOMESTIC_LEAGUES = [364, 412, 426, 524, 795]  # England, France, Germany, Italy, Spain
PRIMARY_MINUTES_THRESHOLD = 450
SENSITIVITY_THRESHOLDS = [225, 450, 675, 900, 1125, 1350]
TOP_K_FOR_DIAGNOSTICS = 10


def _metrics_to_dict(m) -> dict:
    return dataclasses.asdict(m)


def _load_processed():
    return {
        name: pl.read_parquet(PROCESSED_DIR / f"{name}.parquet")
        for name in ("competitions", "teams", "players", "matches", "minutes")
    }


def _role_lookup(players: pl.DataFrame) -> pl.DataFrame:
    return players.select(pl.col("wyId").alias("player_id"), pl.col("role").struct.field("name").alias("role"))


def run() -> dict:
    data = _load_processed()
    events = pl.read_parquet(PROCESSED_DIR / "events.parquet")
    role_lookup = _role_lookup(data["players"])

    period_assignment = assign_periods(data["matches"])
    period_profiles = build_period_profiles(events, data["minutes"], period_assignment)

    global_result = run_global_retrieval_experiment(
        period_profiles, role_lookup, PRIMARY_MINUTES_THRESHOLD, DOMESTIC_LEAGUES
    )
    within_role_result = run_within_role_retrieval_experiment(
        period_profiles, role_lookup, PRIMARY_MINUTES_THRESHOLD, DOMESTIC_LEAGUES
    )

    # --- context diagnostics (team/league concentration, true matches excluded) ---
    eligible = select_eligible_both_periods(period_profiles, PRIMARY_MINUTES_THRESHOLD, DOMESTIC_LEAGUES)
    eligible = eligible.join(role_lookup, on="player_id", how="left")
    combined_std = impute_and_standardize(eligible, FEATURE_COLUMNS)
    query_a_std = combined_std.filter(pl.col("period") == "A")
    candidates_b_std = combined_std.filter(pl.col("period") == "B")
    top_k = get_top_k_neighbors(query_a_std, candidates_b_std, FEATURE_COLUMNS, k=TOP_K_FOR_DIAGNOSTICS)

    primary_team = compute_primary_team(data["minutes"], period_assignment)
    query_team = primary_team.filter(pl.col("period") == "A").select("player_id", "team_id")
    neighbor_team = primary_team.filter(pl.col("period") == "B").select("player_id", "team_id")
    team_concentration = neighbor_concentration(top_k, query_team, neighbor_team, "team_id")

    query_league = eligible.filter(pl.col("period") == "A").select("player_id", pl.col("competitionId").alias("league_id"))
    neighbor_league = eligible.filter(pl.col("period") == "B").select("player_id", pl.col("competitionId").alias("league_id"))
    league_concentration = neighbor_concentration(top_k, query_league, neighbor_league, "league_id")

    # --- minutes sensitivity curve ---
    sensitivity = []
    for threshold in SENSITIVITY_THRESHOLDS:
        r = run_global_retrieval_experiment(period_profiles, role_lookup, threshold, DOMESTIC_LEAGUES)
        sensitivity.append({
            "threshold": threshold,
            "n_eligible": r["n_eligible_player_competition"],
            "mrr_a": r["baseline_a"].mrr,
            "mrr_b": r["baseline_b"].mrr,
            "delta": r["mrr_delta"]["point_estimate"],
            "ci_low": r["mrr_delta"]["ci_low"],
            "ci_high": r["mrr_delta"]["ci_high"],
        })

    return {
        "config": {
            "domestic_leagues": DOMESTIC_LEAGUES,
            "primary_minutes_threshold": PRIMARY_MINUTES_THRESHOLD,
            "sensitivity_thresholds": SENSITIVITY_THRESHOLDS,
            "top_k_for_diagnostics": TOP_K_FOR_DIAGNOSTICS,
        },
        "global": {
            "n_eligible": global_result["n_eligible_player_competition"],
            "baseline_a": _metrics_to_dict(global_result["baseline_a"]),
            "baseline_b": _metrics_to_dict(global_result["baseline_b"]),
            "mrr_delta": global_result["mrr_delta"],
        },
        "within_role": {
            "n_eligible": within_role_result["n_eligible_player_competition"],
            "baseline_a": _metrics_to_dict(within_role_result["baseline_a"]),
            "baseline_b": _metrics_to_dict(within_role_result["baseline_b"]),
            "mrr_delta": within_role_result["mrr_delta"],
        },
        "diagnostics": {
            "team_concentration_excluding_true_match": team_concentration,
            "league_concentration_excluding_true_match": league_concentration,
        },
        "minutes_sensitivity_curve": sensitivity,
    }


if __name__ == "__main__":
    results = run()
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = ARTIFACTS_DIR / "gate2_results.json"
    out_path.write_text(json.dumps(results, indent=2))
    print(f"wrote {out_path}")
    print(json.dumps(results, indent=2))
