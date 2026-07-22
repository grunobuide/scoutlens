"""Transferred-players follow-up (feasibility-report.md's Recommended
Next Experiment #1, priority 1 after the robustness battery — see D010 /
robustness-checks.md).

Baseline C (role + team + minutes, no event data) beat Baseline B by
more than 2x in the main population, because eligible players
essentially never change clubs mid-season. This script isolates the
players who *did* change their primary team between period A and B and
re-runs all three baselines on just that subset, against the same
global period-B candidate pool used everywhere else — the direct test of
what Baseline B's event-derived features are worth once Baseline C's
team-continuity shortcut structurally cannot apply.

Run with:

    uv run python -m scoutlens.evaluation.run_transfer_analysis

Writes artifacts/transfer_analysis_results.json.
"""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl

from scoutlens.evaluation.diagnostics import compute_primary_team, identify_transferred_players
from scoutlens.evaluation.retrieval import (
    bootstrap_mrr_delta,
    compute_metrics,
    run_baseline_a_retrieval,
    run_baseline_b_retrieval,
    run_baseline_c_retrieval,
    select_eligible_both_periods,
)
from scoutlens.evaluation.similarity import impute_and_standardize
from scoutlens.evaluation.temporal import assign_periods, build_period_profiles
from scoutlens.features.aggregation import FEATURE_COLUMNS

REPO_ROOT = Path(__file__).resolve().parents[3]
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
ARTIFACTS_DIR = REPO_ROOT / "artifacts"

DOMESTIC_LEAGUES = [364, 412, 426, 524, 795]
PRIMARY_MINUTES_THRESHOLD = 450


def _role_lookup(players: pl.DataFrame) -> pl.DataFrame:
    return players.select(pl.col("wyId").alias("player_id"), pl.col("role").struct.field("name").alias("role"))


def run() -> dict:
    players = pl.read_parquet(PROCESSED_DIR / "players.parquet")
    matches = pl.read_parquet(PROCESSED_DIR / "matches.parquet")
    minutes = pl.read_parquet(PROCESSED_DIR / "minutes.parquet")
    events = pl.read_parquet(PROCESSED_DIR / "events.parquet")
    role_lookup = _role_lookup(players)

    period_assignment = assign_periods(matches)
    period_profiles = build_period_profiles(events, minutes, period_assignment)

    eligible = select_eligible_both_periods(period_profiles, PRIMARY_MINUTES_THRESHOLD, DOMESTIC_LEAGUES)
    eligible = eligible.join(role_lookup, on="player_id", how="left")

    primary_team = compute_primary_team(minutes, period_assignment)
    transferred = identify_transferred_players(eligible, primary_team)
    transferred_keys = transferred.select("player_id", "competitionId")

    eligible_with_team = eligible.join(
        primary_team.select("player_id", "competitionId", "period", pl.col("team_id")),
        on=["player_id", "competitionId", "period"], how="left",
    )

    query_a_full = eligible_with_team.filter(pl.col("period") == "A")
    candidates_b_full = eligible_with_team.filter(pl.col("period") == "B")  # same global pool as the main experiment

    query_a_transferred = query_a_full.join(transferred_keys, on=["player_id", "competitionId"], how="inner")

    def _run_all_baselines(query_a: pl.DataFrame, label: str) -> dict:
        ranks_a = run_baseline_a_retrieval(query_a, candidates_b_full)
        ranks_c = run_baseline_c_retrieval(query_a, candidates_b_full)

        combined_std = impute_and_standardize(eligible_with_team, FEATURE_COLUMNS)  # fit on the FULL population
        # combined_std still has BOTH periods' rows per player -- filter to
        # period A *before* joining, or the join (on player_id+competitionId
        # alone) pulls in each player's period-B row too, leaking the
        # candidate pool's own rows into the query set (self-similarity=1.0,
        # guaranteed rank 1 -- caught by a suspiciously perfect MRR here).
        query_a_std = combined_std.filter(pl.col("period") == "A").join(
            query_a.select("player_id", "competitionId"), on=["player_id", "competitionId"], how="inner"
        )
        candidates_b_std = combined_std.filter(pl.col("period") == "B")
        ranks_b = run_baseline_b_retrieval(query_a_std, candidates_b_std)

        result = {
            "label": label,
            "n_queries": query_a.height,
            "baseline_a": compute_metrics(ranks_a["rank"].to_list()).__dict__ if ranks_a.height else None,
            "baseline_b": compute_metrics(ranks_b["rank"].to_list()).__dict__ if ranks_b.height else None,
            "baseline_c": compute_metrics(ranks_c["rank"].to_list()).__dict__ if ranks_c.height else None,
        }
        if ranks_a.height and ranks_b.height:
            result["mrr_delta_b_minus_a"] = bootstrap_mrr_delta(ranks_a, ranks_b, n_resamples=1000, seed=0)
        return result

    return {
        "config": {"domestic_leagues": DOMESTIC_LEAGUES, "minutes_threshold": PRIMARY_MINUTES_THRESHOLD},
        "n_eligible_total": eligible.select("player_id", "competitionId").unique().height,
        "n_transferred": transferred.height,
        "transferred_pairs": transferred.to_dicts(),
        "full_population": _run_all_baselines(query_a_full, "full population (reference)"),
        "transferred_only": _run_all_baselines(query_a_transferred, "transferred players only"),
    }


if __name__ == "__main__":
    results = run()
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = ARTIFACTS_DIR / "transfer_analysis_results.json"
    out_path.write_text(json.dumps(results, indent=2))
    print(f"wrote {out_path}")
    print(json.dumps(results, indent=2))
