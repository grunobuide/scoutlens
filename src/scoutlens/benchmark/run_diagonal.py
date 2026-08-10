"""Train and evaluate the interpretable diagonal metric (`scoutlens-qop.2`).

    uv run --frozen python -m scoutlens.benchmark.run_diagonal
    uv run --frozen python -m scoutlens.benchmark.run_diagonal --with-test

Trains one model per preregistered regularization value on the **train**
split, selects on **validation**, applies the D041 continuation gate, and —
only with `--with-test` — evaluates the selected model **once** on test.

Selection never consults test. The test split additionally stays shut behind
the D041 lock, so `--with-test` is not by itself sufficient to open it.

Writes `artifacts/benchmark/diagonal-results.json`.
"""

from __future__ import annotations

import argparse
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
    train_diagonal,
    weight_stability,
    weight_table,
)
from scoutlens.benchmark.evaluate import build_evaluation_population, fit_train_scaler
from scoutlens.benchmark.features import CANONICAL_28
from scoutlens.benchmark.protocol import PROTOCOL, assert_test_set_unlocked, protocol_hash
from scoutlens.benchmark.run_preregistration import _role_lookup
from scoutlens.benchmark.split import TEST, TRAIN, VALIDATION, assign_splits, attach_split
from scoutlens.evaluation.retrieval import (
    bootstrap_mrr_delta,
    compute_metrics,
    run_baseline_b_retrieval,
)
from scoutlens.evaluation.run_manifest import build_run_manifest, load_experiment_config
from scoutlens.evaluation.similarity import apply_scaler
from scoutlens.evaluation.temporal import assign_periods, build_period_profiles

REPO_ROOT = Path(__file__).resolve().parents[3]
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
ARTIFACTS_DIR = REPO_ROOT / "artifacts" / "benchmark"
INPUT_FILES = ("competitions", "teams", "players", "matches", "minutes", "events")

COLUMNS = list(CANONICAL_28)
CONTINUE = "CONTINUE_NEURAL"
STOP = "STOP_NEURAL"


def _ranks(standardized: pl.DataFrame, split: str, weights: np.ndarray | None) -> pl.DataFrame:
    """Within-role retrieval ranks on one split.

    `weights=None` is the frozen cosine reference. Otherwise features are
    scaled by `sqrt(w)` first, which makes plain cosine compute the diagonal
    score — so the audited ranking path is reused rather than reimplemented.
    """
    rows = standardized.filter(pl.col("split") == split)
    if weights is not None:
        rows = sqrt_scaled(rows, COLUMNS, weights)
    queries = rows.filter(pl.col("period") == "A")
    candidates = rows.filter(pl.col("period") == "B")
    return run_baseline_b_retrieval(queries, candidates, COLUMNS, scope_column="role")


def _by_role(standardized: pl.DataFrame, split: str, weights: np.ndarray) -> dict[str, Any]:
    """Per-role cosine vs diagonal on one split, with the reportable-minimum
    flag from the protocol. Every role is reported; only roles at or above the
    minimum may gate a decision (see D041 and scoutlens-qop.5)."""
    minimum = PROTOCOL["subgroups"]["reportable_minimum_queries"]
    rows = standardized.filter(pl.col("split") == split)
    scaled = sqrt_scaled(rows, COLUMNS, weights)
    out: dict[str, Any] = {}
    for role in sorted(rows["role"].unique().to_list()):
        cosine_queries = rows.filter((pl.col("period") == "A") & (pl.col("role") == role))
        diagonal_queries = scaled.filter((pl.col("period") == "A") & (pl.col("role") == role))
        cosine_ranks = run_baseline_b_retrieval(
            cosine_queries, rows.filter(pl.col("period") == "B"), COLUMNS, scope_column="role"
        )
        diagonal_ranks = run_baseline_b_retrieval(
            diagonal_queries, scaled.filter(pl.col("period") == "B"), COLUMNS, scope_column="role"
        )
        if not cosine_ranks.height or not diagonal_ranks.height:
            continue
        cosine_mrr = compute_metrics(cosine_ranks["rank"].to_list()).mrr
        diagonal_mrr = compute_metrics(diagonal_ranks["rank"].to_list()).mrr
        out[role] = {
            "n_queries": cosine_queries.height,
            "baseline_b_cosine_mrr": cosine_mrr,
            "diagonal_mrr": diagonal_mrr,
            "delta": diagonal_mrr - cosine_mrr,
            "gates_decision": cosine_queries.height >= minimum,
        }
    return out


def apply_continuation_gate(delta: float, ci_low: float) -> dict[str, Any]:
    """The D041 gate, applied mechanically and without exception."""
    minimum_delta = 0.010
    minimum_ci_low = -0.005
    delta_ok = delta >= minimum_delta
    ci_ok = ci_low > minimum_ci_low
    return {
        "decision": CONTINUE if (delta_ok and ci_ok) else STOP,
        "validation_delta": delta,
        "validation_ci_low": ci_low,
        "required_delta": minimum_delta,
        "required_ci_low_above": minimum_ci_low,
        "delta_met": delta_ok,
        "ci_met": ci_ok,
        "rule": PROTOCOL["neural_continuation_gate"],
    }


def run(with_test: bool = False) -> dict[str, Any]:
    config = load_experiment_config()
    leagues = PROTOCOL["population"]["competitions"]
    threshold = PROTOCOL["population"]["minutes_threshold_per_period"]

    players = pl.read_parquet(PROCESSED_DIR / "players.parquet")
    matches = pl.read_parquet(PROCESSED_DIR / "matches.parquet")
    minutes = pl.read_parquet(PROCESSED_DIR / "minutes.parquet")
    events = pl.read_parquet(PROCESSED_DIR / "events.parquet")

    period_profiles = build_period_profiles(events, minutes, assign_periods(matches))
    population = build_evaluation_population(
        period_profiles, _role_lookup(players), threshold, leagues
    )
    assignment = assign_splits(population.select("player_id", "role").unique().sort("player_id"))
    population = attach_split(population, assignment)

    scaler = fit_train_scaler(population, COLUMNS)
    standardized = apply_scaler(population, COLUMNS, scaler)

    anchors, positives, negatives = build_training_pairs(standardized, COLUMNS, TRAIN)

    cosine_validation = _ranks(standardized, VALIDATION, None)
    cosine_validation_mrr = compute_metrics(cosine_validation["rank"].to_list()).mrr

    interval = PROTOCOL["metrics"]["paired_interval"]
    arms: list[dict[str, Any]] = []
    trained: dict[float, np.ndarray] = {}

    for regularization in SPEC["regularization_grid"]:
        started = time.perf_counter()
        result = train_diagonal(anchors, positives, negatives, regularization=regularization)
        train_seconds = time.perf_counter() - started

        weights = result["weights"]
        trained[regularization] = weights

        inference_started = time.perf_counter()
        ranks = _ranks(standardized, VALIDATION, weights)
        inference_seconds = time.perf_counter() - inference_started

        metrics = compute_metrics(ranks["rank"].to_list())
        delta = bootstrap_mrr_delta(
            cosine_validation, ranks, n_resamples=interval["n_resamples"], seed=interval["seed"]
        )
        arms.append({
            "regularization": regularization,
            "validation": {
                "mrr": metrics.mrr,
                "median_rank": metrics.median_rank,
                "recall_at_1": metrics.recall_at_1,
                "recall_at_5": metrics.recall_at_5,
                "recall_at_10": metrics.recall_at_10,
            },
            "delta_vs_cosine": delta,
            "final_objective": result["final_objective"],
            "first_objective": result["first_objective"],
            "collapsed_features": sum(
                1 for row in weight_table(COLUMNS, weights) if row["collapsed"]
            ),
            "cost": {
                "train_seconds": train_seconds,
                "validation_inference_seconds": inference_seconds,
            },
        })

    # selection: best validation MRR, ties broken toward the larger penalty
    best = max(arms, key=lambda arm: (arm["validation"]["mrr"], arm["regularization"]))
    best_weights = trained[best["regularization"]]

    gate = apply_continuation_gate(
        best["delta_vs_cosine"]["point_estimate"], best["delta_vs_cosine"]["ci_low"]
    )

    results: dict[str, Any] = {
        "_manifest": build_run_manifest(
            config, [PROCESSED_DIR / f"{name}.parquet" for name in INPUT_FILES]
        ),
        "protocol_hash": protocol_hash(),
        "spec_hash": spec_hash(),
        "spec": SPEC,
        "feature_set": "CANONICAL_28",
        "training_pairs": {
            "anchors": int(anchors.shape[0]),
            "negatives_per_anchor": int(negatives.shape[1]),
            "features": int(anchors.shape[1]),
        },
        "reference": {
            "split": VALIDATION,
            "metric": "within_role_mrr",
            "baseline_b_cosine_mrr": cosine_validation_mrr,
        },
        "arms": arms,
        "selected": {
            "regularization": best["regularization"],
            "validation_mrr": best["validation"]["mrr"],
            "delta_vs_cosine": best["delta_vs_cosine"],
        },
        "continuation_gate": gate,
        "weights": weight_table(COLUMNS, best_weights),
        "weight_stability": weight_stability(COLUMNS, trained),
        "by_role_validation": _by_role(standardized, VALIDATION, best_weights),
        "cost": {
            "train_seconds_total": sum(arm["cost"]["train_seconds"] for arm in arms),
            "train_seconds_selected": next(
                arm["cost"]["train_seconds"]
                for arm in arms
                if arm["regularization"] == best["regularization"]
            ),
            "validation_inference_seconds": next(
                arm["cost"]["validation_inference_seconds"]
                for arm in arms
                if arm["regularization"] == best["regularization"]
            ),
            "maintenance_delta": {
                "new_versioned_artifact": "artifacts/benchmark/diagonal-results.json, carrying 28 learned weights",
                "refit_required_when": [
                    "the canonical feature set changes",
                    "the eligible population or minutes threshold changes",
                    "the split seed or fractions change",
                ],
                "note": (
                    "Baseline B has no fitted parameters and needs no refit. "
                    "Adopting the diagonal metric adds a weight vector that "
                    "must be versioned, regenerated and kept in step with the "
                    "feature set - that recurring cost is the thing the "
                    "+0.020 practical floor exists to justify."
                ),
            },
        },
        "test_evaluated": False,
    }

    if with_test:
        assert_test_set_unlocked()
        cosine_test = _ranks(standardized, TEST, None)
        diagonal_test = _ranks(standardized, TEST, best_weights)
        test_delta = bootstrap_mrr_delta(
            cosine_test, diagonal_test, n_resamples=interval["n_resamples"], seed=interval["seed"]
        )
        results["test"] = {
            "note": "one-time evaluation of the model selected on validation; test was not consulted for selection",
            "baseline_b_cosine_mrr": compute_metrics(cosine_test["rank"].to_list()).mrr,
            "diagonal_mrr": compute_metrics(diagonal_test["rank"].to_list()).mrr,
            "delta_vs_cosine": test_delta,
            "by_role": _by_role(standardized, TEST, best_weights),
        }
        results["test_evaluated"] = True

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--with-test", action="store_true", help="one-time test evaluation of the selected model")
    args = parser.parse_args()

    results = run(with_test=args.with_test)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = ARTIFACTS_DIR / "diagonal-results.json"
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    results["artifact_bytes"] = out_path.stat().st_size
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    reference = results["reference"]["baseline_b_cosine_mrr"]
    print(f"spec_hash        {results['spec_hash']}")
    print(f"cosine reference {reference:.4f} (validation within-role MRR)")
    for arm in results["arms"]:
        print(
            f"  lambda={arm['regularization']:<7} mrr={arm['validation']['mrr']:.4f} "
            f"delta={arm['delta_vs_cosine']['point_estimate']:+.4f} "
            f"CI=[{arm['delta_vs_cosine']['ci_low']:+.4f},{arm['delta_vs_cosine']['ci_high']:+.4f}] "
            f"collapsed={arm['collapsed_features']}"
        )
    print(f"selected         lambda={results['selected']['regularization']}")
    print(f"DECISION         {results['continuation_gate']['decision']}")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
