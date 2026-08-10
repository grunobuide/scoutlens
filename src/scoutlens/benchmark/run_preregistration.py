"""Produce the preregistration artifacts for `scoutlens-qop.1`.

    uv run --frozen python -m scoutlens.benchmark.run_preregistration
    uv run --frozen python -m scoutlens.benchmark.run_preregistration --with-test

Writes two artifacts under `artifacts/benchmark/`:

- `split-manifest.json` — the frozen population and the player-disjoint
  split: seed, protocol hash, assignment digest, and counts.
- `frozen-baselines.json` — Baseline A and Baseline B reproduced on each
  split under the protocol's train-only scaler.

Requires `data/processed/*.parquet` (see `scoutlens.data.ingestion`).

The test split is skipped unless `--with-test` is passed *and* the protocol
hash is recorded in the decision ledger. Both gates are deliberate: the
whole point of a preregistration is that the decision rule is fixed before
the answer is visible.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import polars as pl

from scoutlens.benchmark.evaluate import (
    build_evaluation_population,
    evaluate_split,
    fit_train_scaler,
)
from scoutlens.benchmark.features import CANONICAL_28, CANONICAL_PLUS_CARRY
from scoutlens.benchmark.protocol import (
    PROTOCOL,
    SPLIT_SEED,
    is_protocol_registered,
    protocol_hash,
)
from scoutlens.benchmark.split import (
    TEST,
    TRAIN,
    VALIDATION,
    assign_splits,
    assignment_digest,
    attach_split,
    split_counts,
)
from scoutlens.evaluation.run_manifest import build_run_manifest, load_experiment_config
from scoutlens.evaluation.temporal import assign_periods, build_period_profiles

REPO_ROOT = Path(__file__).resolve().parents[3]
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
ARTIFACTS_DIR = REPO_ROOT / "artifacts" / "benchmark"

INPUT_FILES = ("competitions", "teams", "players", "matches", "minutes", "events")


def _role_lookup(players: pl.DataFrame) -> pl.DataFrame:
    return players.select(
        pl.col("wyId").alias("player_id"), pl.col("role").struct.field("name").alias("role")
    )


def build() -> tuple[dict, pl.DataFrame, pl.DataFrame]:
    """Returns (split manifest, population with split, role-per-player)."""
    config = load_experiment_config()
    leagues = PROTOCOL["population"]["competitions"]
    minutes_threshold = PROTOCOL["population"]["minutes_threshold_per_period"]

    players = pl.read_parquet(PROCESSED_DIR / "players.parquet")
    matches = pl.read_parquet(PROCESSED_DIR / "matches.parquet")
    minutes = pl.read_parquet(PROCESSED_DIR / "minutes.parquet")
    events = pl.read_parquet(PROCESSED_DIR / "events.parquet")

    role_lookup = _role_lookup(players)
    period_assignment = assign_periods(matches)
    period_profiles = build_period_profiles(events, minutes, period_assignment)

    population = build_evaluation_population(
        period_profiles, role_lookup, minutes_threshold, leagues
    )

    population_players = (
        population.select("player_id", "role").unique().sort("player_id")
    )
    assignment = assign_splits(population_players, seed=SPLIT_SEED)
    population_with_split = attach_split(population, assignment)

    manifest = {
        "_manifest": build_run_manifest(
            config, [PROCESSED_DIR / f"{name}.parquet" for name in INPUT_FILES]
        ),
        "protocol_version": PROTOCOL["protocol_version"],
        "protocol_hash": protocol_hash(),
        "protocol_registered": is_protocol_registered(),
        "protocol": PROTOCOL,
        "split_seed": SPLIT_SEED,
        "assignment_digest": assignment_digest(assignment),
        "counts": split_counts(assignment),
        "population": {
            "profile_rows": population.height,
            "player_competition_pairs": population.select("player_id", "competitionId")
            .unique()
            .height,
            "distinct_players": population["player_id"].n_unique(),
        },
        "feature_sets": {
            "canonical_28": list(CANONICAL_28),
            "canonical_plus_carry": list(CANONICAL_PLUS_CARRY),
        },
    }
    return manifest, population_with_split, assignment


def run(with_test: bool = False) -> tuple[dict, dict]:
    manifest, population_with_split, _ = build()

    scaler = fit_train_scaler(population_with_split, list(CANONICAL_28))
    splits = [TRAIN, VALIDATION] + ([TEST] if with_test else [])

    baselines = {
        "_manifest": manifest["_manifest"],
        "protocol_hash": manifest["protocol_hash"],
        "assignment_digest": manifest["assignment_digest"],
        "feature_set": "CANONICAL_28",
        "scaler_fit_on": TRAIN,
        "scaler": {
            column: (None if fit is None else {"mean": fit[0], "std": fit[1]})
            for column, fit in scaler.items()
        },
        "splits": {
            split: evaluate_split(
                population_with_split, scaler, split, allow_test=(split == TEST)
            )
            for split in splits
        },
        "test_evaluated": with_test,
    }
    return manifest, baselines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--with-test",
        action="store_true",
        help="also evaluate the held-out test split (requires the protocol hash on record)",
    )
    args = parser.parse_args()

    manifest, baselines = run(with_test=args.with_test)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    manifest_path = ARTIFACTS_DIR / "split-manifest.json"
    baselines_path = ARTIFACTS_DIR / "frozen-baselines.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    baselines_path.write_text(json.dumps(baselines, indent=2), encoding="utf-8")

    print(f"protocol_hash      {manifest['protocol_hash']}")
    print(f"protocol_registered {manifest['protocol_registered']}")
    print(f"assignment_digest  {manifest['assignment_digest']}")
    print(f"counts             {json.dumps(manifest['counts']['by_split'])}")
    print(f"wrote {manifest_path}")
    print(f"wrote {baselines_path}")


if __name__ == "__main__":
    main()
