"""Chance-level control for every published retrieval MRR (SLS-024).

Answers a question none of the existing artifacts state explicitly: how far
above the *design's own floor* is each Baseline A/B/C MRR? The floor is the
MRR a method would expect if the same-player link carried zero signal but
it still ranked a pool of the same composition — H_N/N per query (see
`chance_level.py`). A 41x lift and a 1.6x lift mean very different things,
so the control normalizes every absolute number by this floor.

Run with:

    uv run python -m scoutlens.evaluation.run_chance_control

Writes artifacts/chance_control_results.json, with the same config/manifest
contract as run_report.py (parameters from config/experiment.json, D015
`_manifest`). Reuses the published populations exactly: the five domestic
leagues, >=450 minutes in both periods, 1,257 eligible
player x competition units, and the same 26 transferred players from
`identify_transferred_players` — so every observed MRR here must equal the
already-published artifacts number-for-number, and the *new* numbers are
the chance levels and lifts next to them.

Each condition (global / within-role / transferred) and each baseline
records:

- `mrr` — the observed MRR (identical to gate2/transfer artifacts).
- `chance_level_mrr` — exact design floor using per-query pool sizes.
- `lift` — mrr / chance_level_mrr.
- `random_target_null` — empirical permutation null: mean of MRR under
  uniform-random target draws per query (seed-fixed), 95% central interval,
  and an empirical p-value for the observed MRR.

Determinism: all randomness is seeded from config/experiment.json and
permutation draws operate on sorted per-query pool sizes (D013 contract),
so the artifact reproduces exactly.
"""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl

from scoutlens.evaluation.chance_level import chance_level_mrr, lift, random_target_null
from scoutlens.evaluation.diagnostics import compute_primary_team, identify_transferred_players
from scoutlens.evaluation.retrieval import (
    compute_metrics,
    run_baseline_a_retrieval,
    run_baseline_b_retrieval,
    run_baseline_c_retrieval,
    select_eligible_both_periods,
)
from scoutlens.evaluation.run_manifest import build_run_manifest, load_experiment_config
from scoutlens.evaluation.similarity import impute_and_standardize
from scoutlens.evaluation.temporal import assign_periods, build_period_profiles
from scoutlens.features.aggregation import FEATURE_COLUMNS

REPO_ROOT = Path(__file__).resolve().parents[3]
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
ARTIFACTS_DIR = REPO_ROOT / "artifacts"

INPUT_FILES = ("players", "matches", "minutes", "events")

# Enough resamples for a well-measured null mean/CI while keeping the run
# comfortably inside minutes; independent of config/experiment.json's
# 1000-resample bootstrap (that one estimates the B-A delta CI, not the null).
NULL_N_RESAMPLES = 10_000


def _role_lookup(players: pl.DataFrame) -> pl.DataFrame:
    return players.select(pl.col("wyId").alias("player_id"), pl.col("role").struct.field("name").alias("role"))


def _baseline_block(label: str, ranks: pl.DataFrame, seed: int) -> dict:
    """Observed MRR + chance level + lift + permutation null for one ranked
    query set. `ranks` must carry the `pool_size` column that
    `run_baseline_*_retrieval` attaches per query."""
    pool_sizes = ranks["pool_size"].to_list()
    metrics = compute_metrics(ranks["rank"].to_list())
    floor = chance_level_mrr(pool_sizes)
    null = random_target_null(pool_sizes, metrics.mrr, n_resamples=NULL_N_RESAMPLES, seed=seed)
    return {
        "label": label,
        "n_queries": len(pool_sizes),
        "mrr": metrics.mrr,
        "median_rank": metrics.median_rank,
        "chance_level_mrr": floor,
        "lift": lift(metrics.mrr, floor),
        "random_target_null": null,
    }


def _all_baselines(query_a: pl.DataFrame, candidates_b: pl.DataFrame,
                   query_a_std: pl.DataFrame, candidates_b_std: pl.DataFrame,
                   transferred_keys: pl.DataFrame | None, seed: int) -> dict:
    """Runs Baselines A, B, and C for one query/candidate layout and returns
    their chance-level blocks. `transferred_keys`, when given, restricts the
    queries (not the candidate pool) to transferred players."""
    if transferred_keys is not None:
        query_a = query_a.join(transferred_keys, on=["player_id", "competitionId"], how="inner")
        query_a_std = query_a_std.join(transferred_keys, on=["player_id", "competitionId"], how="inner")

    ranks_a = run_baseline_a_retrieval(query_a, candidates_b)
    ranks_c = run_baseline_c_retrieval(query_a, candidates_b)
    ranks_b = run_baseline_b_retrieval(query_a_std, candidates_b_std)

    return {
        "baseline_a": _baseline_block("role + minutes", ranks_a, seed),
        "baseline_b": _baseline_block("32 features + cosine", ranks_b, seed),
        "baseline_c": _baseline_block("role + team + minutes", ranks_c, seed),
    }


def _within_role_baselines(
    query_a: pl.DataFrame, candidates_b: pl.DataFrame,
    query_a_std: pl.DataFrame, candidates_b_std: pl.DataFrame, seed: int,
) -> dict:
    """Within-role condition: candidate pool scoped to the query's nominal
    role. Mirrors the published within-role artifact (Baselines A and B only
    — the published within-role result predates Baseline C, and adding C
    here would invent a comparison the existing pipeline never defined)."""
    ranks_a = run_baseline_a_retrieval(query_a, candidates_b, scope_column="role")
    ranks_b = run_baseline_b_retrieval(query_a_std, candidates_b_std, scope_column="role")
    return {
        "baseline_a": _baseline_block("within-role role + minutes", ranks_a, seed),
        "baseline_b": _baseline_block("within-role 32 features + cosine", ranks_b, seed),
    }


def run() -> dict:
    config = load_experiment_config()
    leagues = config["domestic_leagues"]
    minutes_threshold = config["primary_minutes_threshold"]
    seed = config["bootstrap"]["seed"]

    players = pl.read_parquet(PROCESSED_DIR / "players.parquet")
    matches = pl.read_parquet(PROCESSED_DIR / "matches.parquet")
    minutes = pl.read_parquet(PROCESSED_DIR / "minutes.parquet")
    events = pl.read_parquet(PROCESSED_DIR / "events.parquet")
    role_lookup = _role_lookup(players)

    period_assignment = assign_periods(matches)
    period_profiles = build_period_profiles(events, minutes, period_assignment)

    eligible = select_eligible_both_periods(period_profiles, minutes_threshold, leagues)
    eligible = eligible.join(role_lookup, on="player_id", how="left")

    primary_team = compute_primary_team(minutes, period_assignment)
    eligible_with_team = eligible.join(
        primary_team, on=["player_id", "competitionId", "period"], how="left"
    )
    transferred = identify_transferred_players(eligible, primary_team)
    transferred_keys = transferred.select("player_id", "competitionId")

    query_a = eligible_with_team.filter(pl.col("period") == "A")
    candidates_b = eligible_with_team.filter(pl.col("period") == "B")

    combined_std = impute_and_standardize(eligible_with_team, FEATURE_COLUMNS)
    query_a_std = combined_std.filter(pl.col("period") == "A")
    candidates_b_std = combined_std.filter(pl.col("period") == "B")

    global_blocks = _all_baselines(query_a, candidates_b, query_a_std, candidates_b_std, None, seed)
    role_blocks = _within_role_baselines(query_a, candidates_b, query_a_std, candidates_b_std, seed)
    transferred_blocks = _all_baselines(
        query_a, candidates_b, query_a_std, candidates_b_std, transferred_keys, seed
    )

    return {
        "_manifest": build_run_manifest(
            config, [PROCESSED_DIR / f"{name}.parquet" for name in INPUT_FILES]
        ),
        "method": {
            "chance_level_formula": "H_N / N per query, pooled as the mean over queries "
            "(H_n = harmonic number); lift = observed_mrr / chance_level_mrr",
            "random_target_null": "10,000 seeded uniform-target draws per query; "
            "p-value = fraction of draws with MRR >= observed (+1 smoothing)",
            "populations_match_published_artifacts": True,
        },
        "n_eligible": eligible.select("player_id", "competitionId").unique().height,
        "n_transferred": transferred.height,
        "global": global_blocks,
        "within_role": role_blocks,
        "transferred": transferred_blocks,
    }


if __name__ == "__main__":
    results = run()
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = ARTIFACTS_DIR / "chance_control_results.json"
    out_path.write_text(json.dumps(results, indent=2))
    print(f"wrote {out_path}")
    print(json.dumps(results, indent=2))
