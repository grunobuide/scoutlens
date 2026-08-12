"""Acceptance criteria for `scoutlens-qop.6.1`.

The load-bearing ones: every budget gate must be able to **fail** (AC4), a
measurement that did not reproduce the recorded model must be rejected before
any budget is looked at (AC2), and the measured path must exclude the costs
both representations share (AC3).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from scoutlens.benchmark.adoption_cost import (
    EXCLUSIONS,
    INCLUSIONS,
    check_identity,
    evaluate_budgets,
    recorded_identity,
    weight_digest,
)
from scoutlens.benchmark.protocol import PROTOCOL, protocol_hash

GIB = 1024**3
MIB = 1024**2

WITHIN = {
    "wall_seconds": 30.0,
    "peak_rss_bytes": int(1.4 * GIB),
    "serialized_bytes": 7_500,
}


def _runs(**overrides):
    return [{**WITHIN, **overrides}]


# --- budget gating (AC4) ---------------------------------------------------


def test_a_run_inside_every_budget_passes() -> None:
    assert evaluate_budgets(_runs())["outcome"] == "PASS"


@pytest.mark.parametrize(
    "override,failing_check",
    [
        ({"wall_seconds": 1_800.1}, "wall_seconds_within_budget"),
        ({"peak_rss_bytes": 4 * GIB + 1}, "peak_rss_within_budget"),
        ({"serialized_bytes": 5 * MIB + 1}, "artifact_bytes_within_budget"),
    ],
)
def test_each_budget_gate_can_fail(override, failing_check) -> None:
    """A gate that cannot fail proves nothing."""
    result = evaluate_budgets(_runs(**override))
    assert result["outcome"] == "STOP"
    assert result["checks"][failing_check] is False


@pytest.mark.parametrize(
    "override",
    [
        {"wall_seconds": 1_800.0},
        {"peak_rss_bytes": 4 * GIB},
        {"serialized_bytes": 5 * MIB},
    ],
)
def test_the_boundary_itself_is_inside_budget(override) -> None:
    """The limits read 'at most', so exactly at the limit passes."""
    assert evaluate_budgets(_runs(**override))["outcome"] == "PASS"


def test_gating_uses_the_maximum_not_the_best_run() -> None:
    """Best-of-three would understate what adoption costs on a bad day, which
    is the number a budget exists to bound."""
    runs = [
        {**WITHIN},
        {**WITHIN, "wall_seconds": 2_000.0},
        {**WITHIN},
    ]
    result = evaluate_budgets(runs)
    assert result["maximum"]["wall_seconds"] == 2_000.0
    assert result["outcome"] == "STOP"


def test_maximum_is_reported_for_every_dimension() -> None:
    runs = [
        {"wall_seconds": 10.0, "peak_rss_bytes": 3 * GIB, "serialized_bytes": 100},
        {"wall_seconds": 20.0, "peak_rss_bytes": 1 * GIB, "serialized_bytes": 900},
    ]
    maximum = evaluate_budgets(runs)["maximum"]
    assert maximum == {
        "wall_seconds": 20.0,
        "peak_rss_bytes": 3 * GIB,
        "serialized_bytes": 900,
    }


def test_limits_come_from_the_frozen_protocol() -> None:
    result = evaluate_budgets(_runs())
    assert result["limits"] == PROTOCOL["budgets"]


# --- identity binding (AC2) ------------------------------------------------


def _produced(expected, **overrides):
    base = {
        "weight_digest": expected["weight_digest"],
        "spec_hash": expected["d042_spec_hash"],
        "split_assignment_digest": expected["split_assignment_digest"],
        "selected_regularization": expected["selected_regularization"],
        "protocol_hash": protocol_hash(),
    }
    return {**base, **overrides}


def test_a_faithful_measurement_binds_to_the_recorded_model() -> None:
    expected = recorded_identity()
    assert check_identity(_produced(expected), expected)["bound"] is True


@pytest.mark.parametrize(
    "override,failing_check",
    [
        ({"weight_digest": "0" * 64}, "weight_digest_matches"),
        ({"spec_hash": "0" * 64}, "spec_hash_matches"),
        ({"split_assignment_digest": "0" * 64}, "split_digest_matches"),
        ({"selected_regularization": 99.0}, "selected_regularization_matches"),
        ({"protocol_hash": "0" * 64}, "protocol_hash_is_current"),
    ],
)
def test_any_identity_mismatch_unbinds_the_measurement(override, failing_check) -> None:
    expected = recorded_identity()
    bound = check_identity(_produced(expected, **override), expected)
    assert bound["bound"] is False
    assert bound["checks"][failing_check] is False


def test_weight_digest_is_stable_and_sensitive() -> None:
    weights = np.array([1.0, 2.0, 3.0])
    assert weight_digest(weights) == weight_digest(weights.copy())
    assert weight_digest(weights) != weight_digest(np.array([1.0, 2.0, 3.000001]))


def test_recorded_identity_reads_the_d042_artifact() -> None:
    expected = recorded_identity()
    assert expected["n_weights"] == 28
    assert len(expected["d042_spec_hash"]) == 64
    assert expected["selected_regularization"] == 0.0


# --- what is measured (AC3) ------------------------------------------------


def test_shared_costs_are_excluded_from_the_measured_path() -> None:
    """Both representations pay StatsBomb ingestion and the dual-arm harness;
    charging them to one is measuring the pipeline, not the choice."""
    excluded = " ".join(EXCLUSIONS).lower()
    assert "statsbomb" in excluded
    assert "dual-arm" in excluded or "decision harness" in excluded
    assert "cosine" in excluded


def test_real_adoption_costs_are_included() -> None:
    included = " ".join(INCLUSIONS).lower()
    for required in ("scaler", "grid", "serial", "inference"):
        assert required in included


def test_the_report_states_both_sides_of_the_boundary() -> None:
    path = evaluate_budgets(_runs())["measured_path"]
    assert path["includes"] == list(INCLUSIONS)
    assert path["excludes"] == list(EXCLUSIONS)


# --- the recorded artifacts stay untouched (AC5) ---------------------------

ARTIFACTS = Path(__file__).resolve().parents[2] / "artifacts" / "benchmark"


@pytest.mark.parametrize(
    "name", ["diagonal-results.json", "neural-results.json", "decision-results.json"]
)
def test_measurement_modules_do_not_write_recorded_artifacts(name: str) -> None:
    """Guards the intent structurally: the measurement reads these and must
    never name them as an output."""
    import scoutlens.benchmark.adoption_cost as module
    import scoutlens.benchmark.run_adoption_cost as runner

    for source in (Path(module.__file__), Path(runner.__file__)):
        text = source.read_text(encoding="utf-8")
        for writer in ("write_text(", "to_json(", "open("):
            for line in text.splitlines():
                if writer in line and name in line:
                    pytest.fail(f"{source.name} appears to write {name}: {line.strip()}")


def test_recorded_artifacts_are_present_and_parseable() -> None:
    for name in ("diagonal-results.json", "neural-results.json"):
        path = ARTIFACTS / name
        if not path.is_file():
            pytest.skip(f"{name} not present")
        json.loads(path.read_text(encoding="utf-8"))
