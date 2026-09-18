"""Prove an adapter obeys the contract — including one you wrote yourself.

Shipped as a module with a CLI so an external adapter can be checked without
forking this repository:

    uv run --frozen python -m scoutlens.explanations.adapters.conformance \\
        --adapter mypackage.myadapter:build

`--adapter` names a zero-argument factory. A factory rather than a class keeps
construction in the author's hands: their adapter may need a client, a local
path or an endpoint, and the suite has no business guessing.

**What this checks, and what it cannot.** Every check here is about the
*boundary* — shape, typed failures, retry discipline, honest telemetry. None of
it says a model explains well. That is `jtt.6.3`'s question, and a green
conformance run is not evidence for it.

The suite never calls a real model. It drives the adapter with synthetic
requests, so it is safe to run in CI with no credential and no network.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from scoutlens.explanations.adapters.protocol import (
    RETRYABLE,
    AdapterFailure,
    AdapterRequest,
    AdapterResponse,
    ExplanationAdapter,
    FailureReason,
)

PROBE_DIGEST = "0" * 64
"""A digest no real bundle has. An adapter must fail on it, not invent an answer."""


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    detail: str = ""

    def __str__(self) -> str:
        mark = "PASS" if self.passed else "FAIL"
        return f"[{mark}] {self.name}" + (f" — {self.detail}" if self.detail else "")


def _request(digest: str = PROBE_DIGEST) -> AdapterRequest:
    return AdapterRequest(
        system="Conformance probe. Return JSON.",
        user="Conformance probe.",
        bundle_digest=digest,
        prompt_contract_version="1.0.0",
        schema_version="1.0.0",
    )


def check_identity(adapter: Any) -> CheckResult:
    """Three stable, non-empty identifiers, because the cache key depends on them."""
    missing = [
        name
        for name in ("adapter_id", "adapter_version", "model_id")
        if not isinstance(getattr(adapter, name, None), str) or not getattr(adapter, name)
    ]
    if missing:
        return CheckResult("identity", False, f"missing or non-string: {missing}")

    if (adapter.adapter_id, adapter.adapter_version, adapter.model_id) != (
        adapter.adapter_id,
        adapter.adapter_version,
        adapter.model_id,
    ):  # pragma: no cover - defensive
        return CheckResult("identity", False, "identifiers are not stable between reads")
    return CheckResult("identity", True, f"{adapter.adapter_id}/{adapter.adapter_version}")


def check_protocol_shape(adapter: Any) -> CheckResult:
    if not isinstance(adapter, ExplanationAdapter):
        return CheckResult("protocol_shape", False, "does not satisfy ExplanationAdapter")
    return CheckResult("protocol_shape", True)


def check_returns_result(adapter: Any) -> CheckResult:
    """`complete` returns a result — it never raises for a model or transport fault."""
    try:
        result = adapter.complete(_request())
    except Exception as error:  # noqa: BLE001 - the point is that nothing escapes
        return CheckResult(
            "returns_result",
            False,
            f"raised {type(error).__name__} instead of returning AdapterFailure: {error}",
        )
    if not isinstance(result, (AdapterResponse, AdapterFailure)):
        return CheckResult("returns_result", False, f"returned {type(result).__name__}")
    return CheckResult("returns_result", True, type(result).__name__)


def check_unknown_digest_is_not_invented(adapter: Any) -> CheckResult:
    """An unknown bundle must not produce a confident answer.

    The probe digest belongs to no bundle. An adapter that returns content for
    it is fabricating, and the validator downstream would reject that content
    anyway — but by then the run has recorded a model call that looked fine.
    """
    result = adapter.complete(_request())
    if isinstance(result, AdapterFailure):
        return CheckResult("unknown_digest", True, str(result.reason))
    return CheckResult(
        "unknown_digest",
        False,
        "returned content for a digest that belongs to no bundle",
    )


def check_failure_is_typed(adapter: Any) -> CheckResult:
    result = adapter.complete(_request())
    if isinstance(result, AdapterResponse):
        return CheckResult("failure_typed", True, "no failure to inspect")
    if not isinstance(result.reason, FailureReason):
        return CheckResult("failure_typed", False, f"reason is {type(result.reason).__name__}")
    if result.retryable != (result.reason in RETRYABLE):
        return CheckResult(
            "failure_typed", False, "retryable disagrees with the reason taxonomy"
        )
    if not result.detail:
        return CheckResult("failure_typed", False, "failure carries no detail to act on")
    return CheckResult("failure_typed", True, str(result.reason))


def check_telemetry_is_clean(adapter: Any) -> CheckResult:
    """Telemetry must carry no secret and no prompt content."""
    result = adapter.complete(_request())
    if isinstance(result, AdapterFailure):
        return CheckResult("telemetry", True, "no successful call to inspect")

    telemetry = result.telemetry()
    if "content" in telemetry:
        return CheckResult("telemetry", False, "telemetry includes model output")

    rendered = repr(telemetry).lower()
    for marker in ("authorization", "api_key", "bearer ", "secret", "password", "token="):
        if marker in rendered:
            return CheckResult("telemetry", False, f"telemetry may carry a credential: {marker!r}")
    if not isinstance(telemetry.get("latency_ms"), (int, float)):
        return CheckResult("telemetry", False, "latency_ms is missing or not numeric")
    return CheckResult("telemetry", True)


def check_no_retry_past_the_validator(adapter: Any) -> CheckResult:
    """A non-transport failure is reported after one attempt, not re-rolled."""
    result = adapter.complete(_request())
    if isinstance(result, AdapterResponse):
        return CheckResult("retry_discipline", True, "no failure to inspect")
    if result.reason in RETRYABLE:
        return CheckResult("retry_discipline", True, f"{result.reason} after {result.attempts}")
    if result.attempts > 1:
        return CheckResult(
            "retry_discipline",
            False,
            f"retried a {result.reason} failure {result.attempts} times; only transport faults retry",
        )
    return CheckResult("retry_discipline", True, f"{result.reason} not retried")


CHECKS: tuple[Callable[[Any], CheckResult], ...] = (
    check_protocol_shape,
    check_identity,
    check_returns_result,
    check_unknown_digest_is_not_invented,
    check_failure_is_typed,
    check_telemetry_is_clean,
    check_no_retry_past_the_validator,
)


def run_conformance(adapter: Any) -> list[CheckResult]:
    """Every check, in order. Never raises — a crashing check is a failing check."""
    results: list[CheckResult] = []
    for check in CHECKS:
        try:
            results.append(check(adapter))
        except Exception as error:  # noqa: BLE001
            results.append(CheckResult(check.__name__, False, f"check raised {error!r}"))
    return results


def load_adapter(spec: str) -> Any:
    """Import ``module:factory`` and call it with no arguments."""
    if ":" not in spec:
        raise SystemExit(f"--adapter must be 'module:factory', got {spec!r}")
    module_name, factory_name = spec.split(":", 1)
    try:
        module = importlib.import_module(module_name)
    except ImportError as error:
        raise SystemExit(f"cannot import {module_name!r}: {error}") from error
    factory = getattr(module, factory_name, None)
    if factory is None or not callable(factory):
        raise SystemExit(f"{module_name!r} has no callable {factory_name!r}")
    return factory()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--adapter",
        required=True,
        help="module:factory returning an adapter, e.g. mypackage.myadapter:build",
    )
    args = parser.parse_args(argv)

    adapter = load_adapter(args.adapter)
    results = run_conformance(adapter)
    for result in results:
        print(result)

    failed = [result for result in results if not result.passed]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    if failed:
        print("\nThis adapter does not satisfy the contract. Fix the adapter, not the suite:")
        print("adding provider-specific behaviour to the neutral interface is the")
        print("stop condition on scoutlens-jtt.6.2.")
    return 1 if failed else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
