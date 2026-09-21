"""The gate has to be able to fail, and these tests are the proof that it can.

Every deterministic bar passed on the first run of the suite. That is the
expected result — the cases are the failures the validator was written to catch
— and it is also exactly what a suite that measured nothing would report. So
each bar is tampered with here: a guard is removed, and the gate must drop.

The tampers are monkeypatches rather than edits, so the shipped validator is
never weakened to prove that weakening it is detectable.
"""

from __future__ import annotations

import pytest
from conftest import requires_showcase

from scoutlens.explanations import validator
from scoutlens.explanations.evals import runner
from scoutlens.explanations.evals.corpus import ShowcaseArtifacts
from scoutlens.explanations.evals.fallback import Fallback, FallbackReason
from scoutlens.explanations.evals.metrics import compute_metrics
from scoutlens.explanations.evals.report import replay
from scoutlens.explanations.evals.thresholds import (
    DETERMINISTIC_METRICS,
    PREREGISTERED,
    GateOutcome,
    evaluate_deterministic_gate,
    evaluate_live_gate,
)

pytestmark = requires_showcase


@pytest.fixture(scope="module")
def artifacts() -> ShowcaseArtifacts:
    return ShowcaseArtifacts()


def _gate(artifacts: ShowcaseArtifacts):
    return evaluate_deterministic_gate(compute_metrics(replay(artifacts)))


def test_the_untampered_gate_passes(artifacts: ShowcaseArtifacts) -> None:
    result = _gate(artifacts)
    assert result.outcome is GateOutcome.PASS, result.misses


def test_no_metric_is_computed_over_an_empty_population(
    artifacts: ShowcaseArtifacts,
) -> None:
    """A rate over nothing reports 1.0, which is how a vacuous pass hides."""
    metrics = compute_metrics(replay(artifacts))
    record = metrics.as_record()
    empty = [
        name
        for name, entry in record.items()
        if isinstance(entry, dict) and entry.get("count") == 0
    ]
    assert not empty, f"metrics with no cases behind them: {empty}"


def test_the_preregistered_bars_are_what_was_registered() -> None:
    """A silent loosening of a bar is the one change this suite cannot otherwise see."""
    assert PREREGISTERED.supported_entity_rate == 1.0
    assert PREREGISTERED.supported_number_rate == 1.0
    assert PREREGISTERED.critical_caveat_retention == 1.0
    assert PREREGISTERED.forbidden_claim_rejection == 1.0
    assert PREREGISTERED.degraded_fallback_correctness == 1.0
    assert PREREGISTERED.expected_rule_precision == 1.0
    assert PREREGISTERED.live_structured_validity == 0.95
    assert PREREGISTERED.live_runs_required == 3


# --- tampers ---------------------------------------------------------------


def test_removing_the_forbidden_phrase_guard_drops_the_gate(
    artifacts: ShowcaseArtifacts, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(validator, "_check_forbidden", lambda text, index: [])
    result = _gate(artifacts)
    assert result.outcome is GateOutcome.DROP
    assert "forbidden_claim_rejection" in result.misses


def test_accepting_any_citation_drops_the_gate(
    artifacts: ShowcaseArtifacts, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The single most important guard: an id that does not exist must not resolve."""
    original = validator._check_claim

    def lax(claim, index, *, allowed, by_id, bundle, order):
        invented = {str(evidence_id) for evidence_id in claim.get("evidence_ids", ()) or ()}
        return original(
            claim, index, allowed=set(allowed) | invented, by_id=by_id, bundle=bundle, order=order
        )

    monkeypatch.setattr(validator, "_check_claim", lax)
    result = _gate(artifacts)
    assert result.outcome is GateOutcome.DROP
    assert "supported_entity_rate" in result.misses


def test_removing_the_numeric_check_drops_the_gate(
    artifacts: ShowcaseArtifacts, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        validator, "_check_numbers", lambda claim, index, *, by_id, bundle: []
    )
    result = _gate(artifacts)
    assert result.outcome is GateOutcome.DROP
    assert "supported_number_rate" in result.misses


def test_removing_the_caveat_check_drops_the_gate(
    artifacts: ShowcaseArtifacts, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(validator, "_check_mandatory_caveats", lambda output, bundle: [])
    result = _gate(artifacts)
    assert result.outcome is GateOutcome.DROP
    assert "critical_caveat_retention" in result.misses


def test_a_fallback_that_does_not_validate_drops_the_gate(
    artifacts: ShowcaseArtifacts, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The fallback is held to the same validator as a model's answer.

    If it were exempt it would be the one unchecked path in the system, and the
    one an incident would travel down — it runs precisely when something has
    already gone wrong.
    """

    def broken(bundle, *, reason: FallbackReason, detail: str) -> Fallback:
        return Fallback(
            output={"contract": "scoutlens.explanation", "claims": []},
            reason=reason,
            detail=detail,
        )

    monkeypatch.setattr(runner, "deterministic_fallback", broken)
    result = _gate(artifacts)
    assert result.outcome is GateOutcome.DROP
    assert "degraded_fallback_correctness" in result.misses


def test_every_deterministic_metric_has_a_bar_and_a_record(
    artifacts: ShowcaseArtifacts,
) -> None:
    """A metric the gate does not read is a number nobody is held to."""
    metrics = compute_metrics(replay(artifacts))
    record = metrics.as_record()
    for name in DETERMINISTIC_METRICS:
        assert hasattr(PREREGISTERED, name), f"{name} has no preregistered bar"
        assert hasattr(metrics, name), f"{name} is not computed"
        assert name in record, f"{name} is computed and never recorded"


# --- the live gate ---------------------------------------------------------


def test_no_live_run_is_not_a_pass_and_not_a_drop() -> None:
    """`NOT_RUN` exists so an unmeasured model cannot be read as a passing one."""
    assert evaluate_live_gate(()).outcome is GateOutcome.NOT_RUN


def test_a_partial_series_decides_nothing() -> None:
    assert evaluate_live_gate((1.0, 1.0)).outcome is GateOutcome.NOT_RUN


def test_three_clearing_runs_pass() -> None:
    assert evaluate_live_gate((0.96, 0.98, 0.95)).outcome is GateOutcome.PASS


def test_one_run_below_the_bar_is_a_drop_for_the_whole_series() -> None:
    """Not averaged. Two good runs do not buy back the one that could not be relied on."""
    result = evaluate_live_gate((1.0, 1.0, 0.90))
    assert result.outcome is GateOutcome.DROP
    assert "live_structured_validity" in result.misses
    assert "new preregistered decision" in result.detail
