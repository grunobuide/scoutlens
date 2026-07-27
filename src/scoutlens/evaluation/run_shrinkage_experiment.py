"""Ratio-shrinkage experiment (D024, beads scoutlens-dul): does empirical-
Bayes shrinkage of the 7 low-sample ratio features (Known Limitation #11)
improve the temporal-retrieval signal, or is it a wash?

An **additive comparison** that leaves the v0.1 catalog frozen: it builds
the same 32-feature Baseline B two ways — raw ratios (v0.1) and shrunk
ratios (`features.shrinkage`) — and runs the identical retrieval battery
on each. The raw arm reproduces the published v0.1 numbers as a sanity
check; the shrunk arm is the experiment.

Run with:

    uv run python -m scoutlens.evaluation.run_shrinkage_experiment

Writes artifacts/shrinkage_experiment_results.json.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import polars as pl

from scoutlens.evaluation.retrieval import (
    run_global_retrieval_experiment,
    run_within_role_retrieval_experiment,
)
from scoutlens.evaluation.temporal import assign_periods, build_period_profiles
from scoutlens.features.aggregation import FEATURE_COLUMNS, RATIO_COUNT_COLUMNS, compute_player_features
from scoutlens.features.shrinkage import RATIO_SPECS, shrink_ratios

REPO_ROOT = Path(__file__).resolve().parents[3]
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
ARTIFACTS_DIR = REPO_ROOT / "artifacts"

DOMESTIC_LEAGUES = [364, 412, 426, 524, 795]
MINUTES_THRESHOLD = 450


def _role_lookup(players: pl.DataFrame) -> pl.DataFrame:
    return players.select(pl.col("wyId").alias("player_id"), pl.col("role").struct.field("name").alias("role"))


def build_profiles_with_counts(events, minutes, period_assignment) -> pl.DataFrame:
    """Like temporal.build_period_profiles, but keeps the ratio count
    columns so shrinkage can rebuild the ratios."""
    frames = []
    groups = period_assignment.select("competitionId", "period").unique().sort(["competitionId", "period"])
    for competition_id, period in groups.iter_rows():
        match_ids = period_assignment.filter(
            (pl.col("competitionId") == competition_id) & (pl.col("period") == period)
        )["match_id"].to_list()
        period_events = events.filter(pl.col("matchId").is_in(match_ids))
        period_minutes = (
            minutes.filter(pl.col("match_id").is_in(match_ids)).group_by("player_id")
            .agg(pl.col("minutes_played").sum())
        )
        feats = compute_player_features(period_events, period_minutes, with_counts=True).with_columns(
            pl.lit(competition_id).alias("competitionId"), pl.lit(period).alias("period")
        )
        frames.append(feats)
    combined = pl.concat(frames)
    id_cols = ["player_id", "competitionId", "period"]
    return combined.select(id_cols + [c for c in combined.columns if c not in id_cols])


def _summ(result: dict) -> dict:
    return {
        "n_eligible": result["n_eligible_player_competition"],
        "baseline_b": dataclasses.asdict(result["baseline_b"]),
        "mrr_delta_b_minus_a": result["mrr_delta"],
    }


def run() -> dict:
    players = pl.read_parquet(PROCESSED_DIR / "players.parquet")
    matches = pl.read_parquet(PROCESSED_DIR / "matches.parquet")
    minutes = pl.read_parquet(PROCESSED_DIR / "minutes.parquet")
    events = pl.read_parquet(PROCESSED_DIR / "events.parquet")

    role_lookup = _role_lookup(players)
    period_assignment = assign_periods(matches)
    with_counts = build_profiles_with_counts(events, minutes, period_assignment)

    raw = with_counts.drop(RATIO_COUNT_COLUMNS)             # v0.1 profiles
    shrunk = shrink_ratios(with_counts)                      # experiment profiles

    # how far did shrinkage move each ratio, and for whom (low-n vs high-n)?
    movement = {}
    for feat in RATIO_SPECS:
        j = raw.select("player_id", "competitionId", "period", feat).join(
            shrunk.select("player_id", "competitionId", "period", pl.col(feat).alias("shrunk")),
            on=["player_id", "competitionId", "period"],
        ).filter(pl.col(feat).is_not_null())
        movement[feat] = {
            "mean_abs_shift": float(j.select((pl.col(feat) - pl.col("shrunk")).abs().mean()).item() or 0.0),
            "max_abs_shift": float(j.select((pl.col(feat) - pl.col("shrunk")).abs().max()).item() or 0.0),
        }

    results = {"raw_v01": {}, "shrunk": {}, "ratio_movement": movement}
    for label, profiles in (("raw_v01", raw), ("shrunk", shrunk)):
        results[label]["global"] = _summ(run_global_retrieval_experiment(
            profiles, role_lookup, MINUTES_THRESHOLD, DOMESTIC_LEAGUES, feature_columns=FEATURE_COLUMNS))
        results[label]["within_role"] = _summ(run_within_role_retrieval_experiment(
            profiles, role_lookup, MINUTES_THRESHOLD, DOMESTIC_LEAGUES, feature_columns=FEATURE_COLUMNS))
    return results


if __name__ == "__main__":
    out = run()
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS_DIR / "shrinkage_experiment_results.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))
