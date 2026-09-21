"""The bars, registered before any result was looked at.

Preregistration is the whole mechanism. A threshold chosen after seeing a number
is not a threshold, it is a description of that number, and the project has
already recorded what it costs to decide a bar late. So these live in code, in
one place, with the decision that set them; changing one is a decision with a
`D`-number, not an edit.

Two tiers, because they answer different questions:

* **The deterministic gate** is about this repository. Every bar is 1.0, and
  that is not ambitious — the cases are the failures the validator was written
  to catch, so anything under 1.0 means a guard that is supposed to exist does
  not. It has no tolerance because there is no interesting value between "the
  fabrication was caught" and "it was not".
* **The live gate** is about a model, and it is the only bar with room in it.
  0.95 structured validity over three runs, and a model that misses it records
  a `DROP` for that exact model, prompt version and schema version. Not a
  prompt to try again with different wording: the human policy approved on
  2026-08-11 is explicit that a miss is recorded and the toolkit ships without
  a demonstration model.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

#: Where these bars were set, so a reader can find the argument rather than the value.
REGISTRATION = "scoutlens-jtt.6.3; human policy approved 2026-08-11"


class GateOutcome(StrEnum):
    """What a gate decided."""

    PASS = "pass"
    DROP = "drop"
    NOT_RUN = "not_run"
    """No live model was called. Distinct from `DROP`: nothing was measured."""


@dataclass(frozen=True)
class Thresholds:
    """The preregistered bars. Every field is a floor, inclusive."""

    supported_entity_rate: float = 1.0
    supported_number_rate: float = 1.0
    critical_caveat_retention: float = 1.0
    forbidden_claim_rejection: float = 1.0
    degraded_fallback_correctness: float = 1.0
    expected_rule_precision: float = 1.0
    live_structured_validity: float = 0.95
    live_runs_required: int = 3

    def as_record(self) -> dict[str, Any]:
        return {
            "registration": REGISTRATION,
            "deterministic": {
                "supported_entity_rate": self.supported_entity_rate,
                "supported_number_rate": self.supported_number_rate,
                "critical_caveat_retention": self.critical_caveat_retention,
                "forbidden_claim_rejection": self.forbidden_claim_rejection,
                "degraded_fallback_correctness": self.degraded_fallback_correctness,
                "expected_rule_precision": self.expected_rule_precision,
            },
            "live": {
                "structured_validity": self.live_structured_validity,
                "runs_required": self.live_runs_required,
            },
        }


PREREGISTERED = Thresholds()

#: The deterministic metrics, in the order a reader should meet them.
DETERMINISTIC_METRICS: tuple[str, ...] = (
    "supported_entity_rate",
    "supported_number_rate",
    "critical_caveat_retention",
    "forbidden_claim_rejection",
    "degraded_fallback_correctness",
    "expected_rule_precision",
)


@dataclass(frozen=True)
class GateResult:
    """A gate's decision, with every bar it applied and every one it missed."""

    outcome: GateOutcome
    misses: tuple[str, ...] = ()
    detail: str = ""

    def as_record(self) -> dict[str, Any]:
        return {
            "outcome": str(self.outcome),
            "misses": list(self.misses),
            "detail": self.detail,
        }


def evaluate_deterministic_gate(
    metrics: Any, thresholds: Thresholds = PREREGISTERED
) -> GateResult:
    """Apply every deterministic bar. Any miss is a `DROP`.

    ``metrics`` is a `metrics.CorpusMetrics`; taken structurally so this module
    imports nothing from it and the dependency runs one way.
    """
    misses = [
        name
        for name in DETERMINISTIC_METRICS
        if getattr(metrics, name) < getattr(thresholds, name)
    ]
    if misses:
        return GateResult(
            outcome=GateOutcome.DROP,
            misses=tuple(misses),
            detail=(
                "a deterministic bar was missed; every one of these is a guard the "
                "validator is supposed to provide, so the miss is a defect and not a "
                "tuning opportunity"
            ),
        )
    return GateResult(outcome=GateOutcome.PASS, detail="every deterministic bar met")


def evaluate_live_gate(
    structured_validity_rates: tuple[float, ...],
    thresholds: Thresholds = PREREGISTERED,
) -> GateResult:
    """Apply the live bar to one rate per recorded run.

    Not averaged. A model that clears the bar twice and misses it once has not
    cleared it: the bar is about whether the output can be relied on, and an
    average hides exactly the run where it could not.
    """
    if not structured_validity_rates:
        return GateResult(
            outcome=GateOutcome.NOT_RUN,
            detail="no live run recorded; the toolkit ships without a demonstration model",
        )
    if len(structured_validity_rates) < thresholds.live_runs_required:
        return GateResult(
            outcome=GateOutcome.NOT_RUN,
            detail=(
                f"{len(structured_validity_rates)} of {thresholds.live_runs_required} required "
                "runs recorded; a partial series decides nothing"
            ),
        )

    below = [rate for rate in structured_validity_rates if rate < thresholds.live_structured_validity]
    if below:
        return GateResult(
            outcome=GateOutcome.DROP,
            misses=("live_structured_validity",),
            detail=(
                f"{len(below)} of {len(structured_validity_rates)} runs below "
                f"{thresholds.live_structured_validity}. Recorded as DROP for this exact model, "
                "prompt-contract version and schema version. Retuning after this result "
                "requires a new preregistered decision."
            ),
        )
    return GateResult(outcome=GateOutcome.PASS, detail="every recorded run cleared the live bar")


__all__ = [
    "DETERMINISTIC_METRICS",
    "PREREGISTERED",
    "REGISTRATION",
    "GateOutcome",
    "GateResult",
    "Thresholds",
    "evaluate_deterministic_gate",
    "evaluate_live_gate",
]
