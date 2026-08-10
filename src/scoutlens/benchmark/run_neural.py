"""Conditional neural contrastive benchmark (`scoutlens-qop.3`).

    uv run --frozen python -m scoutlens.benchmark.run_neural
    uv run --frozen python -m scoutlens.benchmark.run_neural --with-test

Reads the recorded continuation decision first. On `STOP_NEURAL` it writes
the no-go evidence and trains nothing. On `CONTINUE_NEURAL` it trains the
four declared configurations, selects on validation, and — only with
`--with-test` — evaluates the selected checkpoint once on test.

Cosine, diagonal and neural are scored on the *same* query set and the *same*
candidate pools, asserted rather than assumed.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

from scoutlens.benchmark.diagonal import sqrt_scaled
from scoutlens.benchmark.evaluate import (
    build_evaluation_population,
    fit_train_scaler,
    quantize_float,
)
from scoutlens.benchmark.features import CANONICAL_28
from scoutlens.benchmark.neural import (
    SPEC,
    checkpoint_digest,
    embed,
    parameter_count,
    spec_hash,
    train_neural,
)
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
from scoutlens.uncertainty.run import peak_resident_memory_bytes

REPO_ROOT = Path(__file__).resolve().parents[3]
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
ARTIFACTS_DIR = REPO_ROOT / "artifacts" / "benchmark"
DIAGONAL_ARTIFACT = ARTIFACTS_DIR / "diagonal-results.json"
INPUT_FILES = ("competitions", "teams", "players", "matches", "minutes", "events")

COLUMNS = list(CANONICAL_28)
CONTINUE = "CONTINUE_NEURAL"


def read_gate_evidence(path: Path | None = None) -> dict[str, Any]:
    """Acceptance criterion 1: the gate decision is read from qop.2's machine
    -readable artifact, and its protocol hash must match the one this run is
    operating under. A mismatch means the two beads are not talking about the
    same preregistration.

    The path is resolved at call time, not bound as a default: a default
    argument would freeze the module constant at import and make the STOP
    branch untestable.
    """
    path = DIAGONAL_ARTIFACT if path is None else path
    if not path.is_file():
        raise FileNotFoundError(
            f"no qop.2 artifact at {path}; run scoutlens.benchmark.run_diagonal first"
        )
    artifact = json.loads(path.read_text(encoding="utf-8"))
    recorded = artifact.get("protocol_hash")
    if recorded != protocol_hash():
        raise ValueError(
            f"qop.2 artifact was produced under protocol {recorded}, but this run "
            f"is under {protocol_hash()}; re-run qop.2 before continuing"
        )
    gate = artifact["continuation_gate"]
    try:
        source = path.relative_to(REPO_ROOT).as_posix()
    except ValueError:  # artifact outside the repo (tests, ad-hoc runs)
        source = path.as_posix()
    return {
        "source": source,
        "decision": gate["decision"],
        "validation_delta": gate["validation_delta"],
        "validation_ci_low": gate["validation_ci_low"],
        "required_delta": gate["required_delta"],
        "required_ci_low_above": gate["required_ci_low_above"],
        "diagonal_spec_hash": artifact["spec_hash"],
        "protocol_hash": recorded,
    }


def diagonal_weights_from_artifact(path: Path | None = None) -> np.ndarray:
    """Reuse qop.2's selected weights rather than retraining, so the diagonal
    arm compared here is exactly the one that was recorded."""
    path = DIAGONAL_ARTIFACT if path is None else path
    artifact = json.loads(path.read_text(encoding="utf-8"))
    by_feature = {row["feature"]: row["weight"] for row in artifact["weights"]}
    return np.array([by_feature[column] for column in COLUMNS], dtype=float)


def _embedding_frame(rows: pl.DataFrame, params: dict[str, np.ndarray]) -> tuple[pl.DataFrame, list[str]]:
    vectors = embed(rows.select(COLUMNS).to_numpy(), params)
    names = [f"e{index}" for index in range(vectors.shape[1])]
    return (
        rows.select("player_id", "competitionId", "period", "role").with_columns(
            [pl.Series(name, vectors[:, index]) for index, name in enumerate(names)]
        ),
        names,
    )


def _ranks_for(frame: pl.DataFrame, columns: list[str]) -> pl.DataFrame:
    queries = frame.filter(pl.col("period") == "A")
    candidates = frame.filter(pl.col("period") == "B")
    return run_baseline_b_retrieval(queries, candidates, columns, scope_column="role")


def _calibration(frame: pl.DataFrame, columns: list[str], bins: int = 5) -> list[dict[str, Any]]:
    """Reliability of the top-1 similarity: within each score bin, how often is
    the top-ranked candidate actually the same player?

    A retrieval score is only useful downstream if a high score means a
    likely-correct match. This reports that directly instead of assuming it.
    """
    queries = frame.filter(pl.col("period") == "A")
    candidates = frame.filter(pl.col("period") == "B")
    matrix = candidates.select(columns).to_numpy()
    normalized = matrix / np.maximum(np.linalg.norm(matrix, axis=1, keepdims=True), 1e-12)
    candidate_roles = np.asarray(candidates["role"].to_list())
    candidate_keys = list(zip(candidates["player_id"].to_list(), candidates["competitionId"].to_list()))

    scores: list[float] = []
    correct: list[bool] = []
    query_matrix = queries.select(columns).to_numpy()
    for index, (player_id, competition_id, role) in enumerate(
        zip(queries["player_id"].to_list(), queries["competitionId"].to_list(), queries["role"].to_list())
    ):
        mask = candidate_roles == role
        if not mask.any():
            continue
        vector = query_matrix[index]
        vector = vector / max(float(np.linalg.norm(vector)), 1e-12)
        similarity = normalized[mask] @ vector
        best = int(np.argmax(similarity))
        chosen = [key for key, keep in zip(candidate_keys, mask) if keep][best]
        scores.append(float(similarity[best]))
        correct.append(chosen == (player_id, competition_id))

    if not scores:
        return []
    score_array = np.asarray(scores)
    correct_array = np.asarray(correct)
    edges = np.quantile(score_array, np.linspace(0, 1, bins + 1))
    edges[0] -= 1e-9
    out = []
    for lower, upper in zip(edges[:-1], edges[1:]):
        mask = (score_array > lower) & (score_array <= upper)
        if not mask.any():
            continue
        out.append({
            "score_range": [quantize_float(float(lower)), quantize_float(float(upper))],
            "n": int(mask.sum()),
            "mean_top1_score": quantize_float(float(score_array[mask].mean())),
            "top1_accuracy": quantize_float(float(correct_array[mask].mean())),
        })
    return out


def _failure_cases(frame: pl.DataFrame, columns: list[str], limit: int = 10) -> list[dict[str, Any]]:
    """The worst-ranked queries, described by role and minutes only.

    Deliberately free of evaluative language: a high rank here means the
    method failed to re-identify that player across the two halves, which is a
    statement about the measurement, not about the player.
    """
    ranks = _ranks_for(frame, columns)
    queries = frame.filter(pl.col("period") == "A").select(
        "player_id", "competitionId", "role"
    )
    joined = ranks.join(queries, on=["player_id", "competitionId"], how="left")
    worst = joined.sort(["rank", "player_id"], descending=[True, False]).head(limit)
    return [
        {
            "player_id": row["player_id"],
            "competitionId": row["competitionId"],
            "role": row["role"],
            "rank": row["rank"],
            "pool_size": row["pool_size"],
        }
        for row in worst.iter_rows(named=True)
    ]


def _by_role(ranks: pl.DataFrame, queries: pl.DataFrame) -> dict[str, Any]:
    minimum = PROTOCOL["subgroups"]["reportable_minimum_queries"]
    joined = ranks.join(queries.select("player_id", "competitionId", "role"), on=["player_id", "competitionId"])
    out = {}
    for role in sorted(joined["role"].unique().to_list()):
        subset = joined.filter(pl.col("role") == role)
        out[role] = {
            "n_queries": subset.height,
            "mrr": compute_metrics(subset["rank"].to_list()).mrr,
            "gates_decision": subset.height >= minimum,
        }
    return out


def run(with_test: bool = False) -> dict[str, Any]:
    started = time.perf_counter()
    config = load_experiment_config()
    gate = read_gate_evidence()

    results: dict[str, Any] = {
        "protocol_hash": protocol_hash(),
        "spec_hash": spec_hash(),
        "spec": SPEC,
        "gate_evidence": gate,
    }

    if gate["decision"] != CONTINUE:
        # Acceptance criterion 2: the STOP path trains nothing.
        results["_manifest"] = build_run_manifest(config, [])
        results["trained"] = False
        results["outcome"] = "NO_GO"
        results["reason"] = (
            "scoutlens-qop.2 recorded "
            f"{gate['decision']}: validation delta {gate['validation_delta']} did not clear "
            f"{gate['required_delta']} with a CI lower bound above "
            f"{gate['required_ci_low_above']}. The preregistered rule says record the null "
            "and stop, so no neural model was trained. Additional complexity was not earned."
        )
        return results

    leagues = PROTOCOL["population"]["competitions"]
    threshold = PROTOCOL["population"]["minutes_threshold_per_period"]

    players = pl.read_parquet(PROCESSED_DIR / "players.parquet")
    matches = pl.read_parquet(PROCESSED_DIR / "matches.parquet")
    minutes = pl.read_parquet(PROCESSED_DIR / "minutes.parquet")
    events = pl.read_parquet(PROCESSED_DIR / "events.parquet")

    period_profiles = build_period_profiles(events, minutes, assign_periods(matches))
    population = build_evaluation_population(period_profiles, _role_lookup(players), threshold, leagues)
    assignment = assign_splits(population.select("player_id", "role").unique().sort("player_id"))
    population = attach_split(population, assignment)

    scaler = fit_train_scaler(population, COLUMNS)
    standardized = apply_scaler(population, COLUMNS, scaler)

    from scoutlens.benchmark.diagonal import build_training_pairs

    anchors, positives, negatives = build_training_pairs(standardized, COLUMNS, TRAIN)

    validation_rows = standardized.filter(pl.col("split") == VALIDATION)

    def evaluate(params: dict[str, np.ndarray]) -> float:
        frame, names = _embedding_frame(validation_rows, params)
        return compute_metrics(_ranks_for(frame, names)["rank"].to_list()).mrr

    arms = []
    trained: dict[tuple[int, int], dict[str, Any]] = {}
    for hidden in SPEC["hidden_width_grid"]:
        for embedding_dim in SPEC["embedding_dim_grid"]:
            train_started = time.perf_counter()
            result = train_neural(
                anchors, positives, negatives, hidden=hidden, embedding=embedding_dim, evaluate=evaluate
            )
            train_seconds = time.perf_counter() - train_started
            trained[(hidden, embedding_dim)] = result
            arms.append({
                "hidden": hidden,
                "embedding_dim": embedding_dim,
                "best_validation_mrr": result["best_validation_mrr"],
                "best_epoch": result["best_epoch"],
                "epochs_run": result["epochs_run"],
                "stopped_early": result["stopped_early"],
                "parameters": parameter_count(result["params"]),
                "checkpoint_sha256": checkpoint_digest(result["params"]),
                "learning_curve": result["learning_curve"],
                "train_seconds": train_seconds,
            })

    best_arm = max(arms, key=lambda arm: (arm["best_validation_mrr"], -arm["parameters"]))
    best_params = trained[(best_arm["hidden"], best_arm["embedding_dim"])]["params"]

    diagonal_weights = diagonal_weights_from_artifact()

    def three_way(split: str) -> dict[str, Any]:
        rows = standardized.filter(pl.col("split") == split)
        queries = rows.filter(pl.col("period") == "A")

        cosine_ranks = _ranks_for(rows, COLUMNS)
        diagonal_ranks = _ranks_for(sqrt_scaled(rows, COLUMNS, diagonal_weights), COLUMNS)
        neural_frame, names = _embedding_frame(rows, best_params)
        neural_ranks = _ranks_for(neural_frame, names)

        # Acceptance criterion 4: identical queries and identical pools.
        keys = [
            set(zip(r["player_id"].to_list(), r["competitionId"].to_list()))
            for r in (cosine_ranks, diagonal_ranks, neural_ranks)
        ]
        if not (keys[0] == keys[1] == keys[2]):
            raise AssertionError(f"{split}: the three methods did not score identical query sets")
        pools = {
            tuple(sorted(r["pool_size"].to_list()))
            for r in (cosine_ranks, diagonal_ranks, neural_ranks)
        }
        if len(pools) != 1:
            raise AssertionError(f"{split}: candidate pool sizes differ across methods")

        return {
            "n_queries": cosine_ranks.height,
            "shared_query_set": True,
            "shared_pool_sizes": sorted(set(pools.pop())),
            "cosine_mrr": compute_metrics(cosine_ranks["rank"].to_list()).mrr,
            "diagonal_mrr": compute_metrics(diagonal_ranks["rank"].to_list()).mrr,
            "neural_mrr": compute_metrics(neural_ranks["rank"].to_list()).mrr,
            "neural_vs_cosine": bootstrap_mrr_delta(cosine_ranks, neural_ranks, n_resamples=1000, seed=0),
            "neural_vs_diagonal": bootstrap_mrr_delta(diagonal_ranks, neural_ranks, n_resamples=1000, seed=0),
            "by_role_neural": _by_role(neural_ranks, queries),
            "calibration_neural": _calibration(neural_frame, names),
            "failure_cases_neural": _failure_cases(neural_frame, names),
        }

    inference_started = time.perf_counter()
    validation_comparison = three_way(VALIDATION)
    inference_seconds = time.perf_counter() - inference_started

    results.update({
        "_manifest": build_run_manifest(
            config, [PROCESSED_DIR / f"{name}.parquet" for name in INPUT_FILES]
        ),
        "trained": True,
        "outcome": "TRAINED",
        "arms": arms,
        "selected": {
            "hidden": best_arm["hidden"],
            "embedding_dim": best_arm["embedding_dim"],
            "parameters": best_arm["parameters"],
            "checkpoint_sha256": best_arm["checkpoint_sha256"],
            "best_epoch": best_arm["best_epoch"],
            "validation_mrr": best_arm["best_validation_mrr"],
        },
        "validation": validation_comparison,
        "test_evaluated": False,
    })

    if with_test:
        assert_test_set_unlocked()
        results["test"] = {
            "note": "one final evaluation of the checkpoint selected on validation; no retraining follows",
            **three_way(TEST),
        }
        results["test_evaluated"] = True

    results["cost"] = {
        "train_seconds_total": sum(arm["train_seconds"] for arm in arms),
        "train_seconds_selected": next(
            arm["train_seconds"]
            for arm in arms
            if (arm["hidden"], arm["embedding_dim"]) == (best_arm["hidden"], best_arm["embedding_dim"])
        ),
        "validation_inference_seconds": inference_seconds,
        "wall_seconds_total": time.perf_counter() - started,
        "peak_rss_bytes": peak_resident_memory_bytes(),
        "peak_rss_budget_bytes": PROTOCOL["budgets"]["max_peak_rss_bytes"],
    }
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--with-test", action="store_true", help="one final test evaluation")
    args = parser.parse_args()

    results = run(with_test=args.with_test)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = ARTIFACTS_DIR / "neural-results.json"
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    results["artifact_bytes"] = out_path.stat().st_size
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    print(f"gate            {results['gate_evidence']['decision']}")
    if not results["trained"]:
        print(f"outcome         {results['outcome']}")
        print(results["reason"])
    else:
        for arm in results["arms"]:
            print(
                f"  h={arm['hidden']:<3} d={arm['embedding_dim']:<3} "
                f"val_mrr={arm['best_validation_mrr']:.4f} best_epoch={arm['best_epoch']:<4} "
                f"params={arm['parameters']:<6} early_stop={arm['stopped_early']}"
            )
        v = results["validation"]
        print(f"selected        h={results['selected']['hidden']} d={results['selected']['embedding_dim']}")
        print(f"validation      cosine={v['cosine_mrr']:.4f} diagonal={v['diagonal_mrr']:.4f} neural={v['neural_mrr']:.4f}")
        print(f"  vs cosine     {v['neural_vs_cosine']['point_estimate']:+.4f} "
              f"[{v['neural_vs_cosine']['ci_low']:+.4f},{v['neural_vs_cosine']['ci_high']:+.4f}]")
        print(f"  vs diagonal   {v['neural_vs_diagonal']['point_estimate']:+.4f} "
              f"[{v['neural_vs_diagonal']['ci_low']:+.4f},{v['neural_vs_diagonal']['ci_high']:+.4f}]")
        if results["test_evaluated"]:
            t = results["test"]
            print(f"test            cosine={t['cosine_mrr']:.4f} diagonal={t['diagonal_mrr']:.4f} neural={t['neural_mrr']:.4f}")
            print(f"  vs diagonal   {t['neural_vs_diagonal']['point_estimate']:+.4f} "
                  f"[{t['neural_vs_diagonal']['ci_low']:+.4f},{t['neural_vs_diagonal']['ci_high']:+.4f}]")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
