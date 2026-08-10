"""Acceptance criteria for `scoutlens-qop.3`.

The load-bearing ones: the gate is read from qop.2's artifact rather than
restated (AC1), a STOP decision trains nothing (AC2), training is
deterministic with recorded checkpoint provenance (AC3), and nothing in the
training loop can see the test split (AC7).
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from scoutlens.benchmark import run_neural as run_neural_module
from scoutlens.benchmark.neural import (
    SPEC,
    checkpoint_digest,
    embed,
    forward,
    init_params,
    loss_and_grads,
    parameter_count,
    spec_hash,
    train_neural,
)
from scoutlens.benchmark.protocol import protocol_hash
from scoutlens.benchmark.run_neural import read_gate_evidence

FEATURES = 9


def _batch(seed: int = 0, n: int = 6, k: int = 4):
    rng = np.random.default_rng(seed)
    return (
        rng.normal(size=(n, FEATURES)),
        rng.normal(size=(n, FEATURES)),
        rng.normal(size=(n, k, FEATURES)),
    )


# --- gradients and shapes --------------------------------------------------


def test_analytic_gradients_match_numerical_ones() -> None:
    anchors, positives, negatives = _batch()
    params = init_params(FEATURES, 7, 5, seed=1)
    _, grads = loss_and_grads(anchors, positives, negatives, params, 0.05)

    step = 1e-6
    worst = 0.0
    for key in params:
        flat = params[key].ravel()
        for index in range(min(flat.size, 20)):
            original = flat[index]
            flat[index] = original + step
            up, _ = loss_and_grads(anchors, positives, negatives, params, 0.05)
            flat[index] = original - step
            down, _ = loss_and_grads(anchors, positives, negatives, params, 0.05)
            flat[index] = original
            worst = max(worst, abs((up - down) / (2 * step) - grads[key].ravel()[index]))
    assert worst < 1e-6


def test_forward_shapes_handle_batched_and_stacked_inputs() -> None:
    params = init_params(FEATURES, 8, 4, seed=0)
    flat = np.zeros((5, FEATURES))
    stacked = np.zeros((5, 3, FEATURES))
    assert embed(flat, params).shape == (5, 4)
    assert embed(stacked, params).shape == (5, 3, 4)
    hidden, _ = forward(flat, params)
    assert hidden.shape == (5, 8)


def test_parameter_count_matches_the_architecture() -> None:
    params = init_params(FEATURES, 8, 4, seed=0)
    assert parameter_count(params) == FEATURES * 8 + 8 + 8 * 4 + 4


# --- determinism and provenance -------------------------------------------


def test_initialisation_is_deterministic_per_seed() -> None:
    first = init_params(FEATURES, 8, 4, seed=3)
    second = init_params(FEATURES, 8, 4, seed=3)
    other = init_params(FEATURES, 8, 4, seed=4)
    assert all(np.array_equal(first[k], second[k]) for k in first)
    assert not np.array_equal(first["W1"], other["W1"])


def test_training_is_deterministic() -> None:
    batch = _batch()
    scores = iter([0.1, 0.2, 0.3] * 20)
    first = train_neural(
        *batch, hidden=6, embedding=4, evaluate=lambda p: next(scores),
        max_epochs=20, evaluate_every=5, patience=99,
    )
    scores = iter([0.1, 0.2, 0.3] * 20)
    second = train_neural(
        *batch, hidden=6, embedding=4, evaluate=lambda p: next(scores),
        max_epochs=20, evaluate_every=5, patience=99,
    )
    assert checkpoint_digest(first["params"]) == checkpoint_digest(second["params"])
    assert first["learning_curve"] == second["learning_curve"]


def test_checkpoint_digest_is_stable_and_sensitive() -> None:
    params = init_params(FEATURES, 6, 3, seed=0)
    before = checkpoint_digest(params)
    assert before == checkpoint_digest(params)
    params["b2"][0] += 1e-9
    assert checkpoint_digest(params) != before


# --- early stopping --------------------------------------------------------


def test_early_stopping_restores_the_best_checkpoint_not_the_last() -> None:
    """Monitored score peaks then declines; the returned weights must be the
    peak's, otherwise early stopping would report a model nobody selected."""
    batch = _batch()
    scores = iter([0.10, 0.50, 0.20, 0.10, 0.05, 0.01])
    result = train_neural(
        *batch, hidden=6, embedding=4, evaluate=lambda p: next(scores),
        max_epochs=60, evaluate_every=10, patience=2,
    )
    assert result["best_validation_mrr"] == pytest.approx(0.50)
    assert result["best_epoch"] == 20
    assert result["stopped_early"] is True


def test_training_runs_to_the_cap_when_the_score_keeps_improving() -> None:
    batch = _batch()
    scores = iter([0.1, 0.2, 0.3, 0.4])
    result = train_neural(
        *batch, hidden=6, embedding=4, evaluate=lambda p: next(scores),
        max_epochs=40, evaluate_every=10, patience=2,
    )
    assert result["stopped_early"] is False
    assert result["best_epoch"] == 40


def test_the_monitor_is_never_shown_the_test_split() -> None:
    """AC7 by construction: `train_neural` only ever calls the callable it is
    handed, and the runner hands it a validation-only closure. Recorded here
    so a future refactor that widens the callback is a failing test."""
    seen: list[str] = []
    batch = _batch()
    train_neural(
        *batch, hidden=4, embedding=3,
        evaluate=lambda p: (seen.append("called"), 0.5)[1],
        max_epochs=10, evaluate_every=5, patience=99,
    )
    assert seen, "the monitor never ran, so this test proves nothing"

    # The real guard: training receives a callable and no data of its own, so
    # the only split it can see is the one the caller closed over. The runner
    # builds that closure from `validation_rows`.
    import inspect

    source = inspect.getsource(run_neural_module.run)
    monitor = source.split("def evaluate(")[1].split("return")[0]
    assert "validation_rows" in monitor
    assert "TEST" not in monitor


# --- the gate --------------------------------------------------------------


def _artifact(tmp_path, decision: str, protocol: str | None = None):
    path = tmp_path / "diagonal-results.json"
    path.write_text(
        json.dumps({
            "protocol_hash": protocol or protocol_hash(),
            "spec_hash": "deadbeef",
            "weights": [],
            "continuation_gate": {
                "decision": decision,
                "validation_delta": 0.2174,
                "validation_ci_low": 0.1686,
                "required_delta": 0.010,
                "required_ci_low_above": -0.005,
            },
        }),
        encoding="utf-8",
    )
    return path


def test_gate_evidence_is_read_from_the_qop2_artifact(tmp_path) -> None:
    evidence = read_gate_evidence(_artifact(tmp_path, "CONTINUE_NEURAL"))
    assert evidence["decision"] == "CONTINUE_NEURAL"
    assert evidence["validation_delta"] == pytest.approx(0.2174)
    assert evidence["protocol_hash"] == protocol_hash()


def test_gate_evidence_fails_closed_on_a_protocol_mismatch(tmp_path) -> None:
    """A qop.2 artifact produced under a different preregistration is not
    evidence about this one."""
    with pytest.raises(ValueError, match="was produced under protocol"):
        read_gate_evidence(_artifact(tmp_path, "CONTINUE_NEURAL", protocol="0" * 64))


def test_gate_evidence_fails_closed_when_the_artifact_is_absent(tmp_path) -> None:
    with pytest.raises(FileNotFoundError, match="run scoutlens.benchmark.run_diagonal"):
        read_gate_evidence(tmp_path / "absent.json")


def test_stop_decision_trains_nothing(tmp_path, monkeypatch) -> None:
    """AC2: on STOP the run records why complexity was not earned and never
    loads data or fits a model. Guarded by pointing the processed-data
    directory at an empty path — if the STOP path touched it, this would
    raise instead of returning."""
    monkeypatch.setattr(run_neural_module, "DIAGONAL_ARTIFACT", _artifact(tmp_path, "STOP_NEURAL"))
    monkeypatch.setattr(run_neural_module, "PROCESSED_DIR", tmp_path / "no-such-directory")

    results = run_neural_module.run(with_test=True)
    assert results["trained"] is False
    assert results["outcome"] == "NO_GO"
    assert "STOP_NEURAL" in results["reason"]
    assert "not earned" in results["reason"]
    assert "arms" not in results


# --- the declared search limit ---------------------------------------------


def test_the_architecture_grid_is_small_and_declared() -> None:
    combinations = len(SPEC["hidden_width_grid"]) * len(SPEC["embedding_dim_grid"])
    assert combinations == 4
    assert SPEC["depth"] == 1


def test_spec_hash_is_stable_and_distinct_from_the_other_frozen_objects() -> None:
    from scoutlens.benchmark.diagonal import spec_hash as diagonal_spec_hash

    assert spec_hash() == spec_hash()
    assert spec_hash() != diagonal_spec_hash()
    assert spec_hash() != protocol_hash()
