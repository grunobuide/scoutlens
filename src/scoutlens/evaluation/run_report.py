"""Single-command reproduction of every number in feasibility-report.md's
Temporal Stability Results and Position/Minutes/League Diagnostics
sections.

Run with:

    uv run python -m scoutlens.evaluation.run_report

Requires data/processed/*.parquet to already exist (see
`scoutlens.data.ingestion` and `scoutlens.data.minutes`). Writes a JSON
summary to artifacts/gate2_results.json — one of the few artifacts
checked into git (see artifacts/README.md), so the published numbers in
feasibility-report.md/context-diagnostics.md are inspectable without
re-running anything, and `tests/evaluation/test_artifacts.py` can catch
drift between this file and the docs that quote it.

Configuration comes from the versioned `config/experiment.json` (D015 —
see `run_manifest.py`), and the emitted artifact embeds a `_manifest`
tying the numbers to the exact config, code commit, environment, and
input-file checksums that produced them.

Reproducibility note: `bootstrap_mrr_delta` explicitly sorts its paired
query set by `(player_id, competitionId)` before resampling (fixed after
review — see decisions-log.md D013), so every number here, including
bootstrap CI bounds, is exactly reproducible run to run for a fixed seed,
not just the point estimates.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import polars as pl

from scoutlens.evaluation.diagnostics import compute_primary_team, neighbor_concentration
from scoutlens.evaluation.run_manifest import build_run_manifest, load_experiment_config
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

INPUT_FILES = ("competitions", "teams", "players", "matches", "minutes", "events")


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
    config = load_experiment_config()
    leagues = config["domestic_leagues"]
    minutes_threshold = config["primary_minutes_threshold"]
    n_resamples = config["bootstrap"]["n_resamples"]
    seed = config["bootstrap"]["seed"]

    data = _load_processed()
    events = pl.read_parquet(PROCESSED_DIR / "events.parquet")
    role_lookup = _role_lookup(data["players"])

    period_assignment = assign_periods(data["matches"])
    period_profiles = build_period_profiles(events, data["minutes"], period_assignment)

    global_result = run_global_retrieval_experiment(
        period_profiles, role_lookup, minutes_threshold, leagues, n_resamples=n_resamples, seed=seed
    )
    within_role_result = run_within_role_retrieval_experiment(
        period_profiles, role_lookup, minutes_threshold, leagues, n_resamples=n_resamples, seed=seed
    )

    # --- context diagnostics (team/league concentration, true matches excluded) ---
    eligible = select_eligible_both_periods(period_profiles, minutes_threshold, leagues)
    eligible = eligible.join(role_lookup, on="player_id", how="left")
    combined_std = impute_and_standardize(eligible, FEATURE_COLUMNS)
    query_a_std = combined_std.filter(pl.col("period") == "A")
    candidates_b_std = combined_std.filter(pl.col("period") == "B")
    top_k = get_top_k_neighbors(query_a_std, candidates_b_std, FEATURE_COLUMNS, k=config["top_k_for_diagnostics"])

    # compute_primary_team runs over EVERY competition a player appears in
    # (Euro/WC included, and a player can even have minutes in two
    # different *domestic* leagues in the same period after a mid-season
    # inter-league transfer). Selecting player_id+team_id from that table
    # directly, at any scope broader than "exactly this eligible
    # population's own (player_id, competitionId, period)", risks
    # duplicate player_id rows and a silently inflated join in
    # neighbor_concentration -- found in review; neighbor_concentration
    # now raises instead of silently miscounting. The correct fix is to
    # join primary_team onto `eligible` on the full key, not re-derive a
    # broader team table and hope it happens to be unique.
    primary_team = compute_primary_team(data["minutes"], period_assignment)
    eligible_with_team = eligible.join(
        primary_team, on=["player_id", "competitionId", "period"], how="left"
    )
    query_team = eligible_with_team.filter(pl.col("period") == "A").select("player_id", "team_id")
    neighbor_team = eligible_with_team.filter(pl.col("period") == "B").select("player_id", "team_id")
    team_concentration = neighbor_concentration(top_k, query_team, neighbor_team, "team_id")

    query_league = eligible.filter(pl.col("period") == "A").select("player_id", pl.col("competitionId").alias("league_id"))
    neighbor_league = eligible.filter(pl.col("period") == "B").select("player_id", pl.col("competitionId").alias("league_id"))
    league_concentration = neighbor_concentration(top_k, query_league, neighbor_league, "league_id")

    # --- minutes sensitivity curve ---
    sensitivity = []
    for threshold in config["sensitivity_thresholds"]:
        r = run_global_retrieval_experiment(
            period_profiles, role_lookup, threshold, leagues, n_resamples=n_resamples, seed=seed
        )
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
        "_manifest": build_run_manifest(
            config, [PROCESSED_DIR / f"{name}.parquet" for name in INPUT_FILES]
        ),
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
