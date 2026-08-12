"""Direct measurement of what adopting the diagonal representation costs.

`D045` accepted an *interpretation*: the 4.35 GiB peak of the qop.4 decision
harness is StatsBomb ingestion shared by both arms, not the cost of the
diagonal representation, and the diagonal arm's own peak was quoted as an
upper bound taken from the neural run. `scoutlens-qop.6.1` replaces that
proxy with a direct measurement before anything is promoted publicly.

What is measured (the adoption path):

- fitting the frozen regularization grid on the training split,
- serializing the model that adoption would have to version,
- scoring the selected arm over the validation split.

What is deliberately excluded, because both representations pay it equally
and charging it to one of them would be measuring the pipeline rather than
the choice:

- StatsBomb ingestion and cross-provider scoring,
- the qop.4 dual-arm decision harness,
- cosine scoring as a comparison arm.

Wyscout loading and standardization *are* included: adoption cannot happen
without them.

Nothing here re-decides KEEP, and nothing overwrites a recorded artifact.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

from scoutlens.benchmark.diagonal import (
    SPEC,
    build_training_pairs,
    spec_hash,
    sqrt_scaled,
    weight_table,
)
from scoutlens.benchmark.evaluate import build_evaluation_population, fit_train_scaler
from scoutlens.benchmark.features import CANONICAL_28
from scoutlens.benchmark.protocol import PROTOCOL, protocol_hash
from scoutlens.benchmark.split import TRAIN, VALIDATION, assign_splits, assignment_digest, attach_split
from scoutlens.evaluation.retrieval import compute_metrics, run_baseline_b_retrieval
from scoutlens.evaluation.run_manifest import sha256_file
from scoutlens.evaluation.similarity import apply_scaler
from scoutlens.evaluation.temporal import assign_periods, build_period_profiles
from scoutlens.uncertainty.run import peak_resident_memory_bytes

REPO_ROOT = Path(__file__).resolve().parents[3]
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
DIAGONAL_ARTIFACT = REPO_ROOT / "artifacts" / "benchmark" / "diagonal-results.json"
SPLIT_MANIFEST = REPO_ROOT / "artifacts" / "benchmark" / "split-manifest.json"

COLUMNS = list(CANONICAL_28)

INPUT_FILES = ("players", "matches", "minutes", "events")

EXCLUSIONS = (
    "StatsBomb ingestion and cross-provider scoring",
    "the qop.4 dual-arm decision harness",
    "cosine scoring as a comparison arm",
)

INCLUSIONS = (
    "Wyscout load, period profiles, eligible population and split",
    "train-only scaler fit",
    "training pair and hard-negative construction",
    "the full frozen regularization grid",
    "serialization of the model adoption would version",
    "selected-arm inference over the validation split",
)


def weight_digest(weights: np.ndarray) -> str:
    """Identity of a weight vector, rounded to the published precision so the
    digest matches what a consumer would read from the artifact."""
    payload = [round(float(value), 12) for value in weights]
    return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode("utf-8")).hexdigest()


def recorded_identity() -> dict[str, Any]:
    """The D042/D044 anchors this measurement must bind to."""
    diagonal = json.loads(DIAGONAL_ARTIFACT.read_text(encoding="utf-8"))
    manifest = json.loads(SPLIT_MANIFEST.read_text(encoding="utf-8"))
    weights = np.array([row["weight"] for row in diagonal["weights"]], dtype=float)
    by_feature = {row["feature"]: float(row["weight"]) for row in diagonal["weights"]}
    ordered = np.array([by_feature[column] for column in COLUMNS], dtype=float)
    return {
        "d042_spec_hash": diagonal["spec_hash"],
        "d041_protocol_hash_of_record": diagonal["protocol_hash"],
        "split_assignment_digest": manifest["assignment_digest"],
        "selected_regularization": diagonal["selected"]["regularization"],
        "weight_digest": weight_digest(ordered),
        "n_weights": int(weights.size),
    }


def _input_hashes() -> dict[str, str]:
    return {name: sha256_file(PROCESSED_DIR / f"{name}.parquet") for name in INPUT_FILES}


def measure_once(serialize_to: Path) -> dict[str, Any]:
    """One fresh-process measurement of the adoption path.

    Returns wall time, peak RSS, serialized bytes and the identity of what was
    produced. Must be called in a dedicated process: peak RSS is a per-process
    high-water mark, so sharing a process with anything else would attribute
    that memory to the representation.
    """
    from scoutlens.benchmark.diagonal import train_diagonal
    from scoutlens.benchmark.run_preregistration import _role_lookup

    started = time.perf_counter()

    players = pl.read_parquet(PROCESSED_DIR / "players.parquet")
    matches = pl.read_parquet(PROCESSED_DIR / "matches.parquet")
    minutes = pl.read_parquet(PROCESSED_DIR / "minutes.parquet")
    events = pl.read_parquet(PROCESSED_DIR / "events.parquet")

    profiles = build_period_profiles(events, minutes, assign_periods(matches))
    population = build_evaluation_population(
        profiles,
        _role_lookup(players),
        PROTOCOL["population"]["minutes_threshold_per_period"],
        PROTOCOL["population"]["competitions"],
    )
    assignment = assign_splits(population.select("player_id", "role").unique().sort("player_id"))
    population = attach_split(population, assignment)

    scaler = fit_train_scaler(population, COLUMNS)
    standardized = apply_scaler(population, COLUMNS, scaler)
    anchors, positives, negatives = build_training_pairs(standardized, COLUMNS, TRAIN)

    grid_started = time.perf_counter()
    trained: dict[float, np.ndarray] = {}
    for regularization in SPEC["regularization_grid"]:
        result = train_diagonal(anchors, positives, negatives, regularization=regularization)
        trained[regularization] = result["weights"]
    grid_seconds = time.perf_counter() - grid_started

    selected_lambda = float(
        json.loads(DIAGONAL_ARTIFACT.read_text(encoding="utf-8"))["selected"]["regularization"]
    )
    selected = trained[selected_lambda]

    # Serialization: what adoption must version and ship.
    serialize_started = time.perf_counter()
    model_payload = {
        "spec_hash": spec_hash(),
        "protocol_hash": protocol_hash(),
        "split_assignment_digest": assignment_digest(assignment),
        "selected_regularization": selected_lambda,
        "scaler": {
            column: (None if fit is None else {"mean": fit[0], "std": fit[1]})
            for column, fit in scaler.items()
        },
        "weights": weight_table(COLUMNS, selected),
    }
    serialize_to.parent.mkdir(parents=True, exist_ok=True)
    serialize_to.write_text(json.dumps(model_payload, indent=2, sort_keys=True), encoding="utf-8")
    serialize_seconds = time.perf_counter() - serialize_started
    serialized_bytes = serialize_to.stat().st_size

    # Selected-arm inference over validation.
    inference_started = time.perf_counter()
    rows = standardized.filter(pl.col("split") == VALIDATION)
    scaled = sqrt_scaled(rows, COLUMNS, selected)
    ranks = run_baseline_b_retrieval(
        scaled.filter(pl.col("period") == "A"),
        scaled.filter(pl.col("period") == "B"),
        COLUMNS,
        scope_column="role",
    )
    mrr = compute_metrics(ranks["rank"].to_list()).mrr
    inference_seconds = time.perf_counter() - inference_started

    wall_seconds = time.perf_counter() - started
    return {
        "wall_seconds": wall_seconds,
        "grid_seconds": grid_seconds,
        "serialize_seconds": serialize_seconds,
        "inference_seconds": inference_seconds,
        "peak_rss_bytes": peak_resident_memory_bytes(),
        "serialized_bytes": serialized_bytes,
        "validation_mrr": mrr,
        "produced": {
            "selected_regularization": selected_lambda,
            "weight_digest": weight_digest(selected),
            "split_assignment_digest": assignment_digest(assignment),
            "spec_hash": spec_hash(),
            "protocol_hash": protocol_hash(),
        },
        "input_hashes": _input_hashes(),
    }


def check_identity(produced: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    """Bind a measurement to the recorded model. A mismatch means the measured
    path is not the adopted one, and the measurement must be rejected before
    any budget is evaluated — a cost measured for a different model says
    nothing about this one."""
    checks = {
        "weight_digest_matches": produced["weight_digest"] == expected["weight_digest"],
        "spec_hash_matches": produced["spec_hash"] == expected["d042_spec_hash"],
        "split_digest_matches": produced["split_assignment_digest"] == expected["split_assignment_digest"],
        "selected_regularization_matches": (
            float(produced["selected_regularization"]) == float(expected["selected_regularization"])
        ),
        "protocol_hash_is_current": produced["protocol_hash"] == protocol_hash(),
    }
    return {"checks": checks, "bound": all(checks.values())}


def evaluate_budgets(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Gate on the **maximum** observed cost, not the best run.

    Reporting a best-of-three would understate what adoption costs on a bad
    day, which is precisely the number a budget exists to bound.
    """
    limits = PROTOCOL["budgets"]
    max_wall = max(run["wall_seconds"] for run in runs)
    max_rss = max(run["peak_rss_bytes"] for run in runs)
    max_bytes = max(run["serialized_bytes"] for run in runs)

    checks = {
        "wall_seconds_within_budget": max_wall <= limits["max_wall_clock_seconds_per_arm"],
        "peak_rss_within_budget": max_rss <= limits["max_peak_rss_bytes"],
        "artifact_bytes_within_budget": max_bytes <= limits["max_artifact_bytes"],
    }
    passed = all(checks.values())
    return {
        "n_runs": len(runs),
        "maximum": {
            "wall_seconds": max_wall,
            "peak_rss_bytes": max_rss,
            "serialized_bytes": max_bytes,
        },
        "limits": limits,
        "checks": checks,
        "outcome": "PASS" if passed else "STOP",
        "rule": (
            "Gated on the maximum across repetitions. A miss stops promotion "
            "and is not rounded or reinterpreted."
        ),
        "measured_path": {"includes": list(INCLUSIONS), "excludes": list(EXCLUSIONS)},
    }
