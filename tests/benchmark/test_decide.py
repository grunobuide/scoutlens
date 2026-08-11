"""Acceptance criteria for `scoutlens-qop.4`.

The two that carry weight: the decision is conjunctive with no override
(AC4/AC5), and the protocol lineage is *proved* rather than asserted (AC8).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from scoutlens.benchmark import decide as decide_module
from scoutlens.benchmark.decide import (
    D041_PROTOCOL_HASH,
    D041_SUBGROUPS,
    DROP,
    KEEP,
    decide,
    diagonal_weight_vector,
    evaluate_clauses,
    reconcile_lineage,
)
from scoutlens.benchmark.features import CANONICAL_28
from scoutlens.benchmark.run_decision import assert_feature_sets_align

PASSING = {
    "wyscout_test_delta": 0.2268,
    "wyscout_test_ci_low": 0.1835,
    "by_role": {
        "Defender": {"n_queries": 95, "delta": 0.2689},
        "Midfielder": {"n_queries": 90, "delta": 0.2017},
        "Forward": {"n_queries": 48, "delta": 0.2476},
        "Goalkeeper": {"n_queries": 20, "delta": 0.0898},
    },
    "statsbomb_delta": 0.05,
    "statsbomb_ci_low": 0.01,
    "budgets": {"within_budget": True},
}


def _clauses(**overrides):
    return evaluate_clauses(**{**PASSING, **overrides})


# --- lineage (AC8) ---------------------------------------------------------


def test_lineage_proves_only_the_subgroup_clause_changed() -> None:
    result = reconcile_lineage()
    assert result["only_the_subgroup_clause_changed"] is True
    assert result["reconstructed_d041_hash"] == D041_PROTOCOL_HASH


def test_lineage_fails_if_anything_beyond_the_subgroup_clause_changed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The proof must be capable of failing, otherwise it proves nothing."""
    from scoutlens.benchmark.protocol import PROTOCOL

    tampered = {**PROTOCOL, "decision": {**PROTOCOL["decision"], "otherwise": "changed"}}
    monkeypatch.setattr(decide_module, "PROTOCOL", tampered)
    result = reconcile_lineage()
    assert result["only_the_subgroup_clause_changed"] is False
    assert "RECONSTRUCTION FAILED" in result["detail"]


def test_the_recorded_d041_subgroup_block_is_the_inert_hundred() -> None:
    assert D041_SUBGROUPS["reportable_minimum_queries"] == 100


# --- conjunctivity (AC4, AC5) ---------------------------------------------


def test_all_clauses_passing_gives_keep() -> None:
    result = decide(_clauses())
    assert result["outcome"] == KEEP
    assert result["failed_clauses"] == []


@pytest.mark.parametrize(
    "override",
    [
        {"wyscout_test_delta": 0.019},
        {"wyscout_test_ci_low": 0.0},
        {"statsbomb_delta": 0.0},
        {"statsbomb_ci_low": -0.010},
        {"budgets": {"within_budget": False}},
        {"by_role": {**PASSING["by_role"], "Defender": {"n_queries": 95, "delta": -0.021}}},
    ],
)
def test_any_single_failing_clause_forces_drop(override) -> None:
    """Conjunctive with no override: one failure is enough, whatever the
    others say."""
    result = decide(_clauses(**override))
    assert result["outcome"] == DROP
    assert len(result["failed_clauses"]) >= 1


def test_the_decision_records_that_there_is_no_override() -> None:
    result = decide(_clauses())
    assert "no discretionary override" in result["rule"].lower()
    assert result["neural_arm"].startswith("DROP")


# --- clause boundaries -----------------------------------------------------


def test_wyscout_delta_boundary_is_inclusive_at_the_threshold() -> None:
    assert decide(_clauses(wyscout_test_delta=0.020))["outcome"] == KEEP
    assert decide(_clauses(wyscout_test_delta=0.0199))["outcome"] == DROP


def test_wyscout_ci_boundary_is_strict_above_zero() -> None:
    assert decide(_clauses(wyscout_test_ci_low=0.0))["outcome"] == DROP
    assert decide(_clauses(wyscout_test_ci_low=1e-9))["outcome"] == KEEP


def test_statsbomb_ci_boundary_is_strict_above_minus_one_percent() -> None:
    assert decide(_clauses(statsbomb_ci_low=-0.010))["outcome"] == DROP
    assert decide(_clauses(statsbomb_ci_low=-0.0099))["outcome"] == KEEP


# --- the subgroup clause under the D044 amendment --------------------------


def test_only_roles_at_or_above_fifty_can_fail_the_subgroup_clause() -> None:
    """Forward (48) and Goalkeeper (20) are reported but non-gating, so even a
    large drop there cannot fail the gate."""
    clauses = _clauses(
        by_role={
            **PASSING["by_role"],
            "Forward": {"n_queries": 48, "delta": -0.90},
            "Goalkeeper": {"n_queries": 20, "delta": -0.90},
        }
    )
    subgroup = next(c for c in clauses if "role subgroup" in c["clause"])
    assert subgroup["passed"] is True
    assert subgroup["gating_roles"] == ["Defender", "Midfielder"]
    assert subgroup["non_gating_roles"] == ["Forward", "Goalkeeper"]


def test_a_gating_role_dropping_too_far_fails_the_clause() -> None:
    clauses = _clauses(
        by_role={**PASSING["by_role"], "Midfielder": {"n_queries": 90, "delta": -0.0201}}
    )
    subgroup = next(c for c in clauses if "role subgroup" in c["clause"])
    assert subgroup["passed"] is False


def test_the_clause_text_states_the_amended_minimum() -> None:
    subgroup = next(c for c in _clauses() if "role subgroup" in c["clause"])
    assert ">= 50" in subgroup["clause"]


# --- the budget clause measures adoption cost, not harness cost ------------


def _artifacts(train_total=39.3, rss=1_524_000_000):
    diagonal = {
        "cost": {
            "train_seconds_selected": 5.8,
            "train_seconds_total": train_total,
            "validation_inference_seconds": 1.7,
        }
    }
    neural = {"cost": {"peak_rss_bytes": rss}}
    return diagonal, neural


def test_budget_clause_ignores_the_decision_harness_footprint() -> None:
    """The harness reads StatsBomb's 166 MB event table and scores both arms
    over it, so its footprint is identical whichever representation wins. A
    clause that consumed it would force DROP regardless of the measurement,
    which cannot inform a choice."""
    from scoutlens.benchmark.run_decision import build_budget_evidence

    diagonal, neural = _artifacts()
    evidence = build_budget_evidence(
        diagonal, neural,
        harness_wall_seconds=12.1,
        harness_peak_rss=4_734_000_000,  # 4.41 GiB, above the 4 GiB limit
    )
    assert evidence["within_budget"] is True
    assert evidence["decision_harness_observation"]["peak_rss_bytes"] == 4_734_000_000
    assert "not the arm cost" in evidence["decision_harness_observation"]["note"]


def test_budget_clause_fails_when_the_adoption_cost_actually_breaches() -> None:
    """The clause must still be capable of failing, or it proves nothing."""
    from scoutlens.benchmark.run_decision import build_budget_evidence

    diagonal, neural = _artifacts(train_total=2_000.0)
    slow = build_budget_evidence(
        diagonal, neural, harness_wall_seconds=1.0, harness_peak_rss=1_000
    )
    assert slow["checks"]["train_seconds_within_budget"] is False
    assert slow["within_budget"] is False

    diagonal, neural = _artifacts(rss=5 * 1024**3)
    heavy = build_budget_evidence(
        diagonal, neural, harness_wall_seconds=1.0, harness_peak_rss=1_000
    )
    assert heavy["checks"]["peak_rss_within_budget"] is False
    assert heavy["within_budget"] is False


def test_budget_evidence_states_the_rss_bound_is_a_bound() -> None:
    from scoutlens.benchmark.run_decision import build_budget_evidence

    diagonal, neural = _artifacts()
    evidence = build_budget_evidence(
        diagonal, neural, harness_wall_seconds=1.0, harness_peak_rss=1_000
    )
    assert "bounded above" in evidence["adoption_cost"]["peak_rss_bound_source"]


# --- cross-provider mapping (AC2) -----------------------------------------


def test_statsbomb_and_wyscout_canonical_sets_are_identical_in_order() -> None:
    """The frozen weights are applied positionally; a reordering would score
    the wrong feature with the wrong weight and never raise."""
    alignment = assert_feature_sets_align()
    assert alignment["identical_set_and_order"] is True
    assert alignment["n_features"] == 28


def test_weight_vector_is_ordered_to_the_requested_columns() -> None:
    recorded = [{"feature": column, "weight": float(index)} for index, column in enumerate(CANONICAL_28)]
    vector = diagonal_weight_vector(recorded, list(CANONICAL_28))
    assert np.array_equal(vector, np.arange(len(CANONICAL_28), dtype=float))

    reversed_columns = list(reversed(CANONICAL_28))
    reversed_vector = diagonal_weight_vector(recorded, reversed_columns)
    assert np.array_equal(reversed_vector, np.arange(len(CANONICAL_28), dtype=float)[::-1])


# --- the shipped artifact stays consistent with the rule (AC6) -------------

DECISION_ARTIFACT = (
    Path(__file__).resolve().parents[2] / "artifacts" / "benchmark" / "decision-results.json"
)


def _decision_artifact():
    if not DECISION_ARTIFACT.is_file():
        pytest.skip("decision-results.json not present — run run_decision first")
    return json.loads(DECISION_ARTIFACT.read_text(encoding="utf-8"))


def test_shipped_decision_matches_reapplying_the_rule_to_its_own_clauses() -> None:
    """Drift guard: the recorded outcome must be what the conjunctive rule
    produces from the clauses recorded alongside it. Catches an artifact whose
    headline stops matching its own evidence."""
    artifact = _decision_artifact()
    recomputed = decide(artifact["clauses"])
    assert recomputed["outcome"] == artifact["decision"]["outcome"]
    assert recomputed["failed_clauses"] == artifact["decision"]["failed_clauses"]


def test_shipped_decision_carries_a_passing_lineage_proof() -> None:
    artifact = _decision_artifact()
    assert artifact["lineage"]["only_the_subgroup_clause_changed"] is True
    assert artifact["lineage"]["d041_protocol_hash"] == D041_PROTOCOL_HASH


def test_shipped_evidence_was_recorded_under_the_d041_protocol() -> None:
    artifact = _decision_artifact()
    assert artifact["wyscout_test_recorded"]["protocol_hash"] == D041_PROTOCOL_HASH


def test_shipped_harness_observation_is_not_a_decision_input() -> None:
    artifact = _decision_artifact()
    observation = artifact["budgets"]["decision_harness_observation"]
    assert "not the arm cost" in observation["note"]
    assert artifact["budgets"]["within_budget"] is True


def test_weight_vector_fails_closed_on_a_missing_feature() -> None:
    recorded = [{"feature": column, "weight": 1.0} for column in list(CANONICAL_28)[:-1]]
    with pytest.raises(ValueError, match="missing features"):
        diagonal_weight_vector(recorded, list(CANONICAL_28))
