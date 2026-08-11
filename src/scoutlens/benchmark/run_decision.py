"""Cross-provider evaluation and the final KEEP / DROP decision (`scoutlens-qop.4`).

    uv run --frozen python -m scoutlens.benchmark.run_decision

Evaluates frozen cosine and the frozen diagonal representation on untouched
StatsBomb 2015/16, then applies every preregistered KEEP clause conjunctively.

**Nothing is fitted on StatsBomb.** The diagonal weights come from the Wyscout
training split exactly as `scoutlens-qop.2` recorded them.

Standardization *is* computed provider-natively, because a z-score is how a
provider's raw counts are made comparable at all — Wyscout means and standard
deviations are meaningless applied to StatsBomb's event taxonomy. That is the
same convention the published replication uses (D020/D021), and it is applied
**identically to both arms**, so it cannot move the delta between them, which
is the quantity the KEEP clause tests.

Writes `artifacts/benchmark/decision-results.json`.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import polars as pl

from scoutlens.benchmark.decide import (
    D041_PROTOCOL_HASH,
    decide,
    diagonal_weight_vector,
    evaluate_clauses,
    reconcile_lineage,
)
from scoutlens.benchmark.diagonal import sqrt_scaled
from scoutlens.benchmark.features import CANONICAL_28
from scoutlens.benchmark.protocol import PROTOCOL, protocol_hash
from scoutlens.evaluation.retrieval import (
    bootstrap_mrr_delta,
    compute_metrics,
    run_baseline_b_retrieval,
    select_eligible_both_periods,
)
from scoutlens.evaluation.run_manifest import build_run_manifest, load_experiment_config
from scoutlens.evaluation.similarity import impute_and_standardize
from scoutlens.evaluation.temporal import assign_periods
from scoutlens.statsbomb.aggregation import CANONICAL_FEATURES
from scoutlens.statsbomb.replication import build_period_profiles, derive_roles
from scoutlens.uncertainty.run import peak_resident_memory_bytes

REPO_ROOT = Path(__file__).resolve().parents[3]
STATSBOMB_DIR = REPO_ROOT / "data" / "processed" / "statsbomb"
ARTIFACTS_DIR = REPO_ROOT / "artifacts" / "benchmark"
DIAGONAL_ARTIFACT = ARTIFACTS_DIR / "diagonal-results.json"
NEURAL_ARTIFACT = ARTIFACTS_DIR / "neural-results.json"

COLUMNS = list(CANONICAL_28)


def assert_feature_sets_align() -> dict[str, Any]:
    """The frozen weights are applied positionally, so the two providers must
    agree on the canonical set *and its order*. A silent mismatch would score
    the wrong feature with the wrong weight and never raise."""
    statsbomb = list(CANONICAL_FEATURES)
    if statsbomb != COLUMNS:
        raise AssertionError(
            "StatsBomb and Wyscout canonical-28 feature lists differ; the frozen "
            "diagonal weights cannot be applied positionally"
        )
    return {"n_features": len(COLUMNS), "identical_set_and_order": True}


def build_budget_evidence(
    diagonal_artifact: dict[str, Any],
    neural_artifact: dict[str, Any],
    *,
    harness_wall_seconds: float,
    harness_peak_rss: int,
) -> dict[str, Any]:
    """Operational cost of **adopting the diagonal representation**.

    The protocol's budgets are per benchmark *arm* (D041 §11). The clause must
    therefore test what adoption costs: fitting the weights, applying them, and
    the artifact that has to be versioned.

    It must **not** test this decision harness's own footprint. That footprint
    is dominated by reading StatsBomb's 166 MB event table, it is incurred
    identically whether the winner is cosine or diagonal, and a clause whose
    value does not depend on which representation you choose cannot inform a
    choice between them — it would force DROP no matter what the measurement
    said. The harness figures are still reported below, as observations.

    Peak RSS for the diagonal arm is taken as an upper bound from the neural
    arm's recorded measurement: `qop.3` ran the same Wyscout pipeline plus a
    strictly heavier model and peaked at that value, so the diagonal arm
    cannot exceed it. Stated as a bound rather than presented as a direct
    measurement.
    """
    limits = PROTOCOL["budgets"]
    train_seconds = diagonal_artifact["cost"]["train_seconds_selected"]
    grid_seconds = diagonal_artifact["cost"]["train_seconds_total"]
    inference_seconds = diagonal_artifact["cost"]["validation_inference_seconds"]
    artifact_bytes = DIAGONAL_ARTIFACT.stat().st_size
    rss_upper_bound = neural_artifact["cost"]["peak_rss_bytes"]

    checks = {
        "train_seconds_within_budget": grid_seconds <= limits["max_wall_clock_seconds_per_arm"],
        "peak_rss_within_budget": rss_upper_bound <= limits["max_peak_rss_bytes"],
        "artifact_within_budget": artifact_bytes <= limits["max_artifact_bytes"],
    }

    return {
        "measures": "cost of adopting the diagonal representation (per-arm, per D041 section 11)",
        "adoption_cost": {
            "weights_to_version": 28,
            "train_seconds_selected_arm": train_seconds,
            "train_seconds_full_grid": grid_seconds,
            "inference_seconds": inference_seconds,
            "artifact_bytes": artifact_bytes,
            "peak_rss_upper_bound_bytes": rss_upper_bound,
            "peak_rss_bound_source": (
                "qop.3 recorded this running the strictly heavier neural arm over "
                "the same Wyscout pipeline; the diagonal arm is bounded above by it"
            ),
        },
        "limits": limits,
        "checks": checks,
        "within_budget": all(checks.values()),
        "decision_harness_observation": {
            "wall_seconds": harness_wall_seconds,
            "peak_rss_bytes": harness_peak_rss,
            "note": (
                "This cross-provider run reads StatsBomb's 166 MB event table and "
                "scores both arms over it. The footprint is attributable to provider "
                "data ingestion, is incurred identically by cosine and diagonal, and "
                "is therefore not the arm cost the budget clause tests. Reported so "
                "the number is on the record, not used to decide."
            ),
        },
    }


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"missing recorded evidence: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate_statsbomb(weights) -> dict[str, Any]:
    """Frozen cosine vs frozen diagonal on the untouched StatsBomb population."""
    config = load_experiment_config()["statsbomb_replication"]
    leagues = config["domestic_leagues"]
    threshold = config["minutes_threshold"]
    n_resamples = config["bootstrap"]["n_resamples"]
    seed = config["bootstrap"]["seed"]

    events = pl.read_parquet(STATSBOMB_DIR / "events.parquet")
    minutes = pl.read_parquet(STATSBOMB_DIR / "minutes.parquet")
    matches = pl.read_parquet(STATSBOMB_DIR / "matches.parquet")

    period_assignment = assign_periods(matches)
    profiles = build_period_profiles(events, minutes, period_assignment)
    eligible = select_eligible_both_periods(profiles, threshold, leagues)
    eligible = eligible.join(derive_roles(events), on="player_id", how="left")
    missing = eligible.filter(pl.col("role").is_null())
    if missing.height:
        raise ValueError(f"{missing.height} StatsBomb rows have no derived role")

    standardized = impute_and_standardize(eligible, COLUMNS)
    scaled = sqrt_scaled(standardized, COLUMNS, weights)

    def ranks(frame: pl.DataFrame) -> pl.DataFrame:
        return run_baseline_b_retrieval(
            frame.filter(pl.col("period") == "A"),
            frame.filter(pl.col("period") == "B"),
            COLUMNS,
            scope_column="role",
        )

    cosine_ranks = ranks(standardized)
    diagonal_ranks = ranks(scaled)

    keys = [
        set(zip(r["player_id"].to_list(), r["competitionId"].to_list()))
        for r in (cosine_ranks, diagonal_ranks)
    ]
    if keys[0] != keys[1]:
        raise AssertionError("cosine and diagonal did not score identical StatsBomb queries")

    cosine_mrr = compute_metrics(cosine_ranks["rank"].to_list()).mrr
    diagonal_mrr = compute_metrics(diagonal_ranks["rank"].to_list()).mrr
    delta = bootstrap_mrr_delta(cosine_ranks, diagonal_ranks, n_resamples=n_resamples, seed=seed)

    minimum = PROTOCOL["subgroups"]["reportable_minimum_queries"]
    queries = standardized.filter(pl.col("period") == "A")
    by_role: dict[str, Any] = {}
    for role in sorted(queries["role"].unique().to_list()):
        role_keys = queries.filter(pl.col("role") == role).select("player_id", "competitionId")
        cosine_role = cosine_ranks.join(role_keys, on=["player_id", "competitionId"], how="inner")
        diagonal_role = diagonal_ranks.join(role_keys, on=["player_id", "competitionId"], how="inner")
        if not cosine_role.height:
            continue
        role_cosine = compute_metrics(cosine_role["rank"].to_list()).mrr
        role_diagonal = compute_metrics(diagonal_role["rank"].to_list()).mrr
        by_role[role] = {
            "n_queries": cosine_role.height,
            "cosine_mrr": role_cosine,
            "diagonal_mrr": role_diagonal,
            "delta": role_diagonal - role_cosine,
            "gates_decision": cosine_role.height >= minimum,
        }

    return {
        "provider": "statsbomb",
        "season": config["season"],
        "competitions": leagues,
        "minutes_threshold": threshold,
        "nothing_fitted_on_statsbomb": True,
        "standardization": (
            "provider-native, shared identically by both arms; the diagonal "
            "weights are frozen from the Wyscout training split"
        ),
        "n_queries": cosine_ranks.height,
        "cosine_mrr": cosine_mrr,
        "diagonal_mrr": diagonal_mrr,
        "delta_vs_cosine": delta,
        "by_role": by_role,
    }


def run() -> dict[str, Any]:
    started = time.perf_counter()
    config = load_experiment_config()

    alignment = assert_feature_sets_align()
    lineage = reconcile_lineage()

    diagonal_artifact = _load(DIAGONAL_ARTIFACT)
    neural_artifact = _load(NEURAL_ARTIFACT)

    for name, artifact in (("diagonal", diagonal_artifact), ("neural", neural_artifact)):
        if artifact["protocol_hash"] != D041_PROTOCOL_HASH:
            raise ValueError(
                f"{name} artifact was recorded under {artifact['protocol_hash']}, "
                f"expected the D041 hash {D041_PROTOCOL_HASH}"
            )

    wyscout_test = diagonal_artifact["test"]
    recorded_by_role = diagonal_artifact["test"]["by_role"]
    weights = diagonal_weight_vector(diagonal_artifact["weights"], COLUMNS)

    statsbomb = evaluate_statsbomb(weights)

    budgets = build_budget_evidence(
        diagonal_artifact,
        neural_artifact,
        harness_wall_seconds=time.perf_counter() - started,
        harness_peak_rss=peak_resident_memory_bytes(),
    )

    clauses = evaluate_clauses(
        wyscout_test_delta=wyscout_test["delta_vs_cosine"]["point_estimate"],
        wyscout_test_ci_low=wyscout_test["delta_vs_cosine"]["ci_low"],
        by_role={
            role: {"n_queries": row["n_queries"], "delta": row["delta"]}
            for role, row in recorded_by_role.items()
        },
        statsbomb_delta=statsbomb["delta_vs_cosine"]["point_estimate"],
        statsbomb_ci_low=statsbomb["delta_vs_cosine"]["ci_low"],
        budgets=budgets,
    )
    decision = decide(clauses)

    return {
        "_manifest": build_run_manifest(
            config,
            [
                STATSBOMB_DIR / "events.parquet",
                STATSBOMB_DIR / "minutes.parquet",
                STATSBOMB_DIR / "matches.parquet",
            ],
        ),
        "protocol_hash": protocol_hash(),
        "lineage": lineage,
        "feature_alignment": alignment,
        "wyscout_test_recorded": {
            "source": "artifacts/benchmark/diagonal-results.json",
            "protocol_hash": diagonal_artifact["protocol_hash"],
            "cosine_mrr": wyscout_test["baseline_b_cosine_mrr"],
            "diagonal_mrr": wyscout_test["diagonal_mrr"],
            "delta_vs_cosine": wyscout_test["delta_vs_cosine"],
            "by_role": recorded_by_role,
        },
        "neural_arm": {
            "source": "artifacts/benchmark/neural-results.json",
            "status": "DROP, final under D043",
            "test_vs_diagonal": neural_artifact["test"]["neural_vs_diagonal"],
        },
        "statsbomb": statsbomb,
        "budgets": budgets,
        "clauses": clauses,
        "decision": decision,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()

    results = run()
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = ARTIFACTS_DIR / "decision-results.json"
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    print(f"lineage ok        {results['lineage']['only_the_subgroup_clause_changed']}")
    sb = results["statsbomb"]
    print(f"statsbomb         n={sb['n_queries']} cosine={sb['cosine_mrr']:.4f} diagonal={sb['diagonal_mrr']:.4f}")
    print(f"  delta           {sb['delta_vs_cosine']['point_estimate']:+.4f} "
          f"[{sb['delta_vs_cosine']['ci_low']:+.4f},{sb['delta_vs_cosine']['ci_high']:+.4f}]")
    print("clauses:")
    for clause in results["clauses"]:
        mark = "PASS" if clause["passed"] else "FAIL"
        observed = clause["observed"]
        shown = f"{observed:+.4f}" if isinstance(observed, float) else "see artifact"
        print(f"  [{mark}] {clause['clause']}  ({shown})")
    print(f"DECISION          {results['decision']['outcome']}")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
