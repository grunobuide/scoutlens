"""External replication experiment on StatsBomb 2015/16 (8mc.3).

Re-runs the v0.1 temporal-stability battery (Baselines A/B/C, within-role,
context diagnostics, transferred players) on the StatsBomb four-league
2015/16 processed set, using the frozen canonical 28-feature set (D020)
so the result is a like-for-like test of whether the Wyscout signal
replicates on a different provider and season. The evaluation layer
(`scoutlens.evaluation.*`) is provider-agnostic — it takes period
profiles, a role lookup, and an explicit feature-column list — so only
the StatsBomb-native aggregation and role derivation live here.

Run with:

    uv run python -m scoutlens.statsbomb.replication

Requires the processed StatsBomb set (see `scoutlens.statsbomb.ingestion`).
Writes artifacts/statsbomb_replication_results.json.
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
    run_global_retrieval_experiment,
    run_within_role_retrieval_experiment,
    select_eligible_both_periods,
)
from scoutlens.evaluation.similarity import impute_and_standardize
from scoutlens.evaluation.temporal import assign_periods
from scoutlens.statsbomb.aggregation import (
    CANONICAL_FEATURES,
    CANONICAL_PLUS_CARRY,
    compute_player_features,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
PROCESSED_DIR = REPO_ROOT / "data" / "processed" / "statsbomb"
ARTIFACTS_DIR = REPO_ROOT / "artifacts"

DOMESTIC_LEAGUES = [2, 7, 11, 12]  # Premier League, Ligue 1, La Liga, Serie A
PRIMARY_MINUTES_THRESHOLD = 450

# Wyscout v0.1 headline numbers (artifacts/gate2_results.json) for side-by-side.
WYSCOUT_V01 = {
    "global": {"baseline_a_mrr": 0.0256, "baseline_b_mrr": 0.2539, "baseline_b_median_rank": 16},
    "within_role": {"baseline_b_mrr": 0.2787, "baseline_b_median_rank": 12},
}


def derive_roles(events: pl.DataFrame) -> pl.DataFrame:
    """player_id → nominal role in {Goalkeeper, Defender, Midfielder,
    Forward} (the 4 Wyscout buckets), from each player's modal event
    position. StatsBomb's fine-grained positions collapse by substring:
    'Back' → Defender (incl. Wing Back), 'Midfield' → Midfielder,
    'Goalkeeper' → Goalkeeper, everything else (Wing, Forward) → Forward."""
    modal = (
        events.filter(pl.col("position_name").is_not_null())
        .group_by("player_id", "position_name").agg(pl.len().alias("n"))
        .sort(["player_id", "n", "position_name"], descending=[False, True, False])
        .group_by("player_id", maintain_order=True).first()
    )
    role = (
        pl.when(pl.col("position_name").str.contains("Goalkeeper")).then(pl.lit("Goalkeeper"))
        .when(pl.col("position_name").str.contains("Back")).then(pl.lit("Defender"))
        .when(pl.col("position_name").str.contains("Midfield")).then(pl.lit("Midfielder"))
        .otherwise(pl.lit("Forward"))
    )
    return modal.select("player_id", role.alias("role"))


def build_period_profiles(events: pl.DataFrame, minutes: pl.DataFrame, period_assignment: pl.DataFrame) -> pl.DataFrame:
    """One row per (player_id, competitionId, period) with minutes + the 30
    features, computed per period from StatsBomb events (keyed `match_id`).
    Mirrors `scoutlens.evaluation.temporal.build_period_profiles` for the
    StatsBomb schema + aggregation."""
    frames = []
    groups = period_assignment.select("competitionId", "period").unique().sort(["competitionId", "period"])
    for competition_id, period in groups.iter_rows():
        match_ids = period_assignment.filter(
            (pl.col("competitionId") == competition_id) & (pl.col("period") == period)
        )["match_id"].to_list()
        period_events = events.filter(pl.col("match_id").is_in(match_ids))
        period_minutes = (
            minutes.filter(pl.col("match_id").is_in(match_ids)).group_by("player_id")
            .agg(pl.col("minutes_played").sum())
        )
        feats = compute_player_features(period_events, period_minutes).with_columns(
            pl.lit(competition_id).alias("competitionId"), pl.lit(period).alias("period")
        )
        frames.append(feats)
    combined = pl.concat(frames)
    id_cols = ["player_id", "competitionId", "period"]
    return combined.select(id_cols + [c for c in combined.columns if c not in id_cols])


def _metrics(m) -> dict:
    import dataclasses
    return dataclasses.asdict(m)


def run() -> dict:
    events = pl.read_parquet(PROCESSED_DIR / "events.parquet")
    minutes = pl.read_parquet(PROCESSED_DIR / "minutes.parquet")
    matches = pl.read_parquet(PROCESSED_DIR / "matches.parquet")

    role_lookup = derive_roles(events)
    period_assignment = assign_periods(matches)
    profiles = build_period_profiles(events, minutes, period_assignment)

    global_28 = run_global_retrieval_experiment(
        profiles, role_lookup, PRIMARY_MINUTES_THRESHOLD, DOMESTIC_LEAGUES, feature_columns=CANONICAL_FEATURES
    )
    within_role_28 = run_within_role_retrieval_experiment(
        profiles, role_lookup, PRIMARY_MINUTES_THRESHOLD, DOMESTIC_LEAGUES, feature_columns=CANONICAL_FEATURES
    )
    global_30 = run_global_retrieval_experiment(
        profiles, role_lookup, PRIMARY_MINUTES_THRESHOLD, DOMESTIC_LEAGUES, feature_columns=CANONICAL_PLUS_CARRY
    )

    # --- transferred-players follow-up (native-team, D011 analogue) ---
    eligible = select_eligible_both_periods(profiles, PRIMARY_MINUTES_THRESHOLD, DOMESTIC_LEAGUES)
    eligible = eligible.join(role_lookup, on="player_id", how="left")
    primary_team = compute_primary_team(minutes, period_assignment)
    transferred = identify_transferred_players(eligible, primary_team)
    transferred_keys = transferred.select("player_id", "competitionId")

    eligible_team = eligible.join(
        primary_team.select("player_id", "competitionId", "period", "team_id"),
        on=["player_id", "competitionId", "period"], how="left",
    )
    q_a = eligible_team.filter(pl.col("period") == "A")
    c_b = eligible_team.filter(pl.col("period") == "B")
    combined_std = impute_and_standardize(eligible_team, CANONICAL_FEATURES)
    q_a_std = combined_std.filter(pl.col("period") == "A")
    c_b_std = combined_std.filter(pl.col("period") == "B")

    def _subset(keys):
        qa = q_a.join(keys, on=["player_id", "competitionId"], how="inner")
        qa_std = q_a_std.join(keys, on=["player_id", "competitionId"], how="inner")
        ra = run_baseline_a_retrieval(qa, c_b)
        rc = run_baseline_c_retrieval(qa, c_b)
        rb = run_baseline_b_retrieval(qa_std, c_b_std, CANONICAL_FEATURES)
        out = {
            "n_queries": qa.height,
            "baseline_a": _metrics(compute_metrics(ra["rank"].to_list())) if ra.height else None,
            "baseline_b": _metrics(compute_metrics(rb["rank"].to_list())) if rb.height else None,
            "baseline_c": _metrics(compute_metrics(rc["rank"].to_list())) if rc.height else None,
        }
        if ra.height and rb.height:
            out["mrr_delta_b_minus_a"] = bootstrap_mrr_delta(ra, rb, n_resamples=1000, seed=0)
        return out

    return {
        "provider": "statsbomb",
        "season": "2015/16",
        "config": {
            "domestic_leagues": DOMESTIC_LEAGUES,
            "minutes_threshold": PRIMARY_MINUTES_THRESHOLD,
            "n_canonical_features": len(CANONICAL_FEATURES),
        },
        "wyscout_v01_reference": WYSCOUT_V01,
        "global_28": {
            "n_eligible": global_28["n_eligible_player_competition"],
            "baseline_a": _metrics(global_28["baseline_a"]),
            "baseline_b": _metrics(global_28["baseline_b"]),
            "mrr_delta": global_28["mrr_delta"],
        },
        "within_role_28": {
            "n_eligible": within_role_28["n_eligible_player_competition"],
            "baseline_a": _metrics(within_role_28["baseline_a"]),
            "baseline_b": _metrics(within_role_28["baseline_b"]),
            "mrr_delta": within_role_28["mrr_delta"],
        },
        "global_30_with_native_carry": {
            "baseline_b": _metrics(global_30["baseline_b"]),
            "mrr_delta": global_30["mrr_delta"],
        },
        "transferred_players": {
            "n_transferred": transferred.height,
            "full_population": _subset(eligible.select("player_id", "competitionId").unique()),
            "transferred_only": _subset(transferred_keys),
        },
    }


if __name__ == "__main__":
    results = run()
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = ARTIFACTS_DIR / "statsbomb_replication_results.json"
    out_path.write_text(json.dumps(results, indent=2))
    print(f"wrote {out_path}")
    print(json.dumps(results, indent=2))
