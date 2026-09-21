"""The numbers, and exactly which cases each one is computed over.

Every metric here is two-sided. "100% supported entities" is not the claim that
accepted explanations happened to cite real ids — a validator that accepted
nothing would score that perfectly. It is the conjunction of two things: no
explanation carrying an unsupported entity was accepted, and every explanation
carrying only supported ones was. A metric that measured one direction could be
maxed by a guard that had stopped working in the other, which is the specific
way eval suites rot.

So each rate's denominator is stated in the record beside it. A rate over an
empty denominator is reported as 1.0 and its `count` as 0, because pretending
otherwise would hide a vacuous pass behind a number; `tests/explanations`
asserts no denominator in the shipped corpus is empty.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from scoutlens.explanations.evals.corpus import Expectation, build_corpus
from scoutlens.explanations.evals.mutations import SAFETY_CRITICAL
from scoutlens.explanations.evals.runner import CaseResult, CorpusRun

#: Rules that fire when an explanation names something the bundle does not carry.
ENTITY_RULES: frozenset[str] = frozenset(
    {
        "envelope.profile_key",
        "envelope.bundle_digest",
        "claim.fabricated_citation",
        "claim.value_source",
        "claim.ungrounded",
    }
)

#: Rules that fire when an explanation states a number the artifact does not publish.
NUMBER_RULES: frozenset[str] = frozenset(
    {
        "claim.value_mismatch",
        "claim.value_field",
        "claim.value_type",
        "claim.value_shape",
    }
)

#: Rules that fire when the mandatory caveat set is not carried intact.
CAVEAT_RULES: frozenset[str] = frozenset({"caveats.missing", "caveats.unknown"})


@dataclass(frozen=True)
class Rate:
    """A proportion with the population it was taken over.

    Carried together on purpose. A bare 1.0 does not distinguish "sixty-one
    cases, all correct" from "no cases, nothing checked", and only one of those
    is a result.
    """

    value: float
    passed: int
    count: int

    def as_record(self) -> dict[str, Any]:
        return {"value": round(self.value, 6), "passed": self.passed, "count": self.count}

    def __float__(self) -> float:
        return self.value


def _rate(results: Iterable[CaseResult], predicate: Callable[[CaseResult], bool]) -> Rate:
    selected = list(results)
    passed = sum(1 for result in selected if predicate(result))
    if not selected:
        return Rate(value=1.0, passed=0, count=0)
    return Rate(value=passed / len(selected), passed=passed, count=len(selected))


@lru_cache(maxsize=1)
def _mutation_by_case() -> dict[str, str | None]:
    return {case.case_id: case.mutation for case in build_corpus()}


def _mutation_of(case_id: str) -> str | None:
    return _mutation_by_case().get(case_id)


def _rule_family(expected_rule: str | None, family: frozenset[str]) -> bool:
    return expected_rule is not None and expected_rule in family


def _two_sided(results: list[CaseResult], family: frozenset[str]) -> Rate:
    """Accepted cases must be accepted; cases built to trip ``family`` must trip it."""
    relevant = [
        result
        for result in results
        if result.expectation == str(Expectation.ACCEPT)
        or _rule_family(result.expected_rule, family)
    ]
    return _rate(relevant, lambda result: result.as_expected)


@dataclass(frozen=True)
class CorpusMetrics:
    """Every rate, plus the counts a reader needs to size them."""

    case_count: int
    as_expected: Rate
    supported_entity: Rate
    supported_number: Rate
    caveat_retention: Rate
    forbidden_rejection: Rate
    fallback_correctness: Rate
    rule_precision: Rate
    structured_validity: Rate

    # `thresholds` reads these names; keeping them as plain floats lets the gate
    # compare without knowing what a `Rate` is.
    @property
    def supported_entity_rate(self) -> float:
        return self.supported_entity.value

    @property
    def supported_number_rate(self) -> float:
        return self.supported_number.value

    @property
    def critical_caveat_retention(self) -> float:
        return self.caveat_retention.value

    @property
    def forbidden_claim_rejection(self) -> float:
        return self.forbidden_rejection.value

    @property
    def degraded_fallback_correctness(self) -> float:
        return self.fallback_correctness.value

    @property
    def expected_rule_precision(self) -> float:
        return self.rule_precision.value

    def as_record(self) -> dict[str, Any]:
        return {
            "case_count": self.case_count,
            "as_expected": self.as_expected.as_record(),
            "supported_entity_rate": self.supported_entity.as_record(),
            "supported_number_rate": self.supported_number.as_record(),
            "critical_caveat_retention": self.caveat_retention.as_record(),
            "forbidden_claim_rejection": self.forbidden_rejection.as_record(),
            "degraded_fallback_correctness": self.fallback_correctness.as_record(),
            "expected_rule_precision": self.rule_precision.as_record(),
            "structured_validity_rate": self.structured_validity.as_record(),
        }


def compute_metrics(run: CorpusRun) -> CorpusMetrics:
    """Reduce a run to the numbers the gate reads."""
    results = list(run.results)
    rejects = [result for result in results if result.expectation == str(Expectation.REJECT)]

    # Broader than the five `ForbiddenIntent` members on purpose. A fabricated
    # citation and a suppressed caveat are just as much claims a reader must
    # never see, and grouping them by consequence rather than by grammar is what
    # makes the bar mean "nothing unsupported reached the page".
    safety = [
        result
        for result in rejects
        if (_mutation_of(result.case_id) or "") in SAFETY_CRITICAL
    ]

    fallback_relevant = [
        result
        for result in results
        if result.used_fallback or result.expectation == str(Expectation.FALLBACK)
    ]

    answered = [result for result in results if result.fallback_reason != "adapter_failure"]

    return CorpusMetrics(
        case_count=len(results),
        as_expected=_rate(results, lambda result: result.as_expected),
        supported_entity=_two_sided(results, ENTITY_RULES),
        supported_number=_two_sided(results, NUMBER_RULES),
        caveat_retention=_two_sided(results, CAVEAT_RULES),
        forbidden_rejection=_rate(safety, lambda result: result.as_expected),
        fallback_correctness=_rate(
            fallback_relevant,
            lambda result: bool(result.used_fallback and result.fallback_valid and result.as_expected),
        ),
        rule_precision=_rate(rejects, lambda result: result.as_expected),
        structured_validity=_rate(answered, lambda result: result.schema_valid),
    )


def structured_validity_rate(run: CorpusRun) -> float:
    """The live headline: how often the model returned something schema-shaped.

    Structural only. Whether the content was *grounded* is the deterministic
    gate's question, and conflating the two would let a model that reliably
    emits well-formed fabrications look like a passing one.
    """
    return compute_metrics(run).structured_validity.value


__all__ = [
    "CAVEAT_RULES",
    "ENTITY_RULES",
    "NUMBER_RULES",
    "CorpusMetrics",
    "Rate",
    "compute_metrics",
    "structured_validity_rate",
]
