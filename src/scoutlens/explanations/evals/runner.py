"""Drive one adapter over the corpus and record what happened.

The loop is the same one the shipped system runs: build the bundle, render the
versioned prompt, call the adapter, check the shape, check the grounding, fall
back if either refuses. Nothing here shortcuts to the validator — a suite that
validated a response it never sent through an adapter would stop measuring the
path that actually runs.

**Replay and live differ in exactly one place: which adapter answers.**
Everything downstream is identical, which is what lets the same metrics judge
both. In replay the answer is the deterministic response `corpus` synthesised
for that case, served through `ScriptedAdapter` or refused by `FaultAdapter`. In
a live run it is whatever the model said.

Live runs use only the `ACCEPT` cases. The rest of the corpus prescribes an
answer — a specific fabrication, a specific dropped caveat — and you cannot ask
a model to produce one on demand without writing it yourself, at which point you
are measuring your own prose. A provider failure is the same problem in the
other direction: nobody should be making a real endpoint rate-limit them to fill
a cell in a matrix.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from scoutlens.explanations.adapters.fake import FaultAdapter, ScriptedAdapter
from scoutlens.explanations.adapters.protocol import (
    AdapterFailure,
    AdapterRequest,
    AdapterResponse,
    FailureReason,
)
from scoutlens.explanations.evals.corpus import (
    EvalCase,
    Expectation,
    MaterialisedCase,
    ShowcaseArtifacts,
    build_corpus,
    materialise,
)
from scoutlens.explanations.evals.diagnostics import FailureDiagnostic, redact, scrub_rejections
from scoutlens.explanations.evals.fallback import (
    Fallback,
    FallbackReason,
    deterministic_fallback,
)
from scoutlens.explanations.policy import OUTPUT_SCHEMA_VERSION
from scoutlens.explanations.prompt import PROMPT_CONTRACT_VERSION, prompt_contract
from scoutlens.explanations.schema import validate_output_schema
from scoutlens.explanations.validator import validate_output

AdapterFactory = Callable[[MaterialisedCase], Any]

#: How the responses under test were produced. Recorded on every run.
SYNTHESISED = "synthesised"
"""Deterministic responses this package derived from the bundle. No model involved."""

LIVE = "live"
"""A model answered. Reproducible only as telemetry, never as a recorded result."""


@dataclass(frozen=True)
class CaseResult:
    """What one case did, in terms a report can carry without qualification."""

    case_id: str
    expectation: str
    dimensions: tuple[str, ...]
    bundle_digest: str
    as_expected: bool
    accepted: bool
    schema_valid: bool
    rules_fired: tuple[str, ...] = ()
    expected_rule: str | None = None
    used_fallback: bool = False
    fallback_reason: str | None = None
    fallback_valid: bool | None = None
    diagnostic: FailureDiagnostic | None = None
    telemetry: dict[str, Any] | None = None

    def as_record(self) -> dict[str, Any]:
        """The replay-report form. Deliberately excludes telemetry.

        Latency is real and it is not reproducible. A recorded artifact that
        carried it could never be byte-identical between runs, and `D057` 4.6
        makes byte-identity the only thing this artifact's determinism can mean.
        """
        return {
            "case_id": self.case_id,
            "expectation": self.expectation,
            "dimensions": list(self.dimensions),
            "bundle_digest": self.bundle_digest,
            "as_expected": self.as_expected,
            "accepted": self.accepted,
            "schema_valid": self.schema_valid,
            "rules_fired": list(self.rules_fired),
            "expected_rule": self.expected_rule,
            "used_fallback": self.used_fallback,
            "fallback_reason": self.fallback_reason,
            "fallback_valid": self.fallback_valid,
        }


@dataclass(frozen=True)
class CorpusRun:
    """One pass over the corpus with one adapter."""

    results: tuple[CaseResult, ...]
    adapter_id: str
    adapter_version: str
    model_id: str
    response_source: str
    prompt_contract_version: str = PROMPT_CONTRACT_VERSION
    output_schema_version: str = OUTPUT_SCHEMA_VERSION

    @property
    def failures(self) -> tuple[CaseResult, ...]:
        return tuple(result for result in self.results if not result.as_expected)

    def adapter_record(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "adapter_version": self.adapter_version,
            "model_id": self.model_id,
        }


def _request(bundle: dict[str, Any]) -> AdapterRequest:
    contract = prompt_contract(bundle)
    return AdapterRequest(
        system=contract["system"],
        user=contract["user"],
        bundle_digest=contract["bundle_digest"],
        prompt_contract_version=contract["version"],
        schema_version=OUTPUT_SCHEMA_VERSION,
    )


def replay_adapter(material: MaterialisedCase) -> Any:
    """The offline adapter a case's plan calls for.

    A fresh single-entry `ScriptedAdapter` per case rather than one keyed over
    the whole corpus: twenty-five cases share the canonical bundle and must get
    twenty-five different answers, so a digest-keyed map could not express them.
    """
    reason = material.case.failure_reason
    if reason is not None and reason in {str(member) for member in FailureReason}:
        return FaultAdapter(reason=FailureReason(reason))
    if material.response is None:  # pragma: no cover - defensive
        raise ValueError(f"{material.case.case_id} has neither a response nor a failure reason")
    return ScriptedAdapter({material.bundle["bundle_digest"]: material.response})


def _schema_ok(content: Any) -> bool:
    try:
        validate_output_schema(content)
    except ValueError:
        return False
    return True


def _fallback_for(bundle: dict[str, Any], reason: FallbackReason, detail: str) -> Fallback:
    return deterministic_fallback(bundle, reason=reason, detail=redact(detail))


def run_case(
    case: EvalCase,
    artifacts: ShowcaseArtifacts,
    *,
    adapter_factory: AdapterFactory = replay_adapter,
) -> CaseResult:
    """Run one case end to end and decide whether it did what it said it would."""
    material = materialise(case, artifacts)
    bundle = material.bundle
    adapter = adapter_factory(material)
    result = adapter.complete(_request(bundle))

    schema_valid = False
    accepted = False
    rules: tuple[str, ...] = ()
    details: tuple[str, ...] = ()
    fallback: Fallback | None = None

    if isinstance(result, AdapterFailure):
        fallback = _fallback_for(bundle, FallbackReason.ADAPTER_FAILURE, str(result))
    elif isinstance(result, AdapterResponse):
        schema_valid = _schema_ok(result.content)
        if not schema_valid:
            fallback = _fallback_for(
                bundle, FallbackReason.SCHEMA_INVALID, "content did not match the output schema"
            )
        else:
            validation = validate_output(result.content, bundle)
            accepted = validation.accepted
            rules = tuple(sorted(validation.rules()))
            details = scrub_rejections(validation)
            if not accepted:
                fallback = _fallback_for(
                    bundle,
                    FallbackReason.VALIDATION_REJECTED,
                    f"refused by {len(validation.rejections)} rule(s)",
                )
    else:  # pragma: no cover - the adapter contract admits no third outcome
        raise TypeError(f"adapter returned {type(result).__name__}, not an adapter result")

    fallback_valid: bool | None = None
    if fallback is not None:
        fallback_valid = _schema_ok(fallback.output) and validate_output(
            fallback.output, bundle
        ).accepted

    as_expected, summary = _judge(
        case,
        accepted=accepted,
        rules=rules,
        fallback=fallback,
        expected_rule=material.expected_rule,
    )
    diagnostic = (
        None
        if as_expected
        else FailureDiagnostic(
            case_id=case.case_id,
            expectation=str(case.expectation),
            summary=summary,
            expected_rule=material.expected_rule,
            rules_fired=rules,
            details=details,
            evidence_count=len(bundle.get("allowed_evidence_ids", ())),
            used_fallback=fallback is not None,
        )
    )

    return CaseResult(
        case_id=case.case_id,
        expectation=str(case.expectation),
        dimensions=tuple(str(dimension) for dimension in case.dimensions),
        bundle_digest=str(bundle["bundle_digest"]),
        as_expected=as_expected,
        accepted=accepted,
        schema_valid=schema_valid,
        rules_fired=rules,
        expected_rule=material.expected_rule,
        used_fallback=fallback is not None,
        fallback_reason=None if fallback is None else str(fallback.reason),
        fallback_valid=fallback_valid,
        diagnostic=diagnostic,
        telemetry=None if isinstance(result, AdapterFailure) else result.telemetry(),
    )


def _judge(
    case: EvalCase,
    *,
    accepted: bool,
    rules: tuple[str, ...],
    fallback: Fallback | None,
    expected_rule: str | None,
) -> tuple[bool, str]:
    """Did the case do what the corpus said it would, and if not, what instead.

    A `REJECT` case is judged on whether its named rule fired, not on whether it
    was the only one. Insisting on exactly one rule would make the suite fail
    when a guard got *stronger*, and the full rule set travels into the report
    anyway, so drift stays visible without being fatal.
    """
    if case.expectation is Expectation.ACCEPT:
        if accepted:
            return True, "accepted"
        return False, f"expected acceptance, refused by {list(rules) or ['schema or adapter']}"

    if case.expectation is Expectation.REJECT:
        if accepted:
            return False, "expected a rejection and the output was accepted"
        if expected_rule and expected_rule not in rules:
            return False, f"expected {expected_rule!r}, fired {list(rules)}"
        return True, "rejected"

    if fallback is None:
        return False, "expected the deterministic fallback and a usable answer was produced"
    return True, f"fell back ({fallback.reason})"


def run_corpus(
    artifacts: ShowcaseArtifacts,
    *,
    cases: Iterable[EvalCase] | None = None,
    adapter_factory: AdapterFactory = replay_adapter,
    adapter_id: str = "scripted",
    adapter_version: str = "1.0.0",
    model_id: str = "scripted-offline",
    response_source: str = SYNTHESISED,
) -> CorpusRun:
    """Run every case, in corpus order."""
    selected = tuple(cases) if cases is not None else build_corpus()
    results = tuple(
        run_case(case, artifacts, adapter_factory=adapter_factory) for case in selected
    )
    return CorpusRun(
        results=results,
        adapter_id=adapter_id,
        adapter_version=adapter_version,
        model_id=model_id,
        response_source=response_source,
    )


def live_cases(cases: Iterable[EvalCase] | None = None) -> tuple[EvalCase, ...]:
    """The cases a live model can meaningfully be asked to answer.

    `ACCEPT` only. See the module docstring for why the rest cannot be put to a
    model without the suite writing the model's answer for it.
    """
    selected = tuple(cases) if cases is not None else build_corpus()
    return tuple(case for case in selected if case.expectation is Expectation.ACCEPT)


__all__ = [
    "LIVE",
    "SYNTHESISED",
    "AdapterFactory",
    "CaseResult",
    "CorpusRun",
    "live_cases",
    "replay_adapter",
    "run_case",
    "run_corpus",
]
