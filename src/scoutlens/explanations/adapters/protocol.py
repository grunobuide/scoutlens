"""The adapter boundary: what a model must accept, return, and fail as.

An adapter is the only thing in this package that talks to a model. Everything
on either side of it — the bundle, the validator, the evals — is deterministic
and offline, so the adapter is where non-determinism is quarantined and where a
project user plugs in whatever they run locally.

**Typed failures, not exceptions in the caller's face.** Every way a model call
can fail resolves to one `AdapterFailure` with a `reason` from a closed set. An
eval that knows only "it failed" cannot tell a flat network from an expired key
from a model that returned prose where JSON was required, and those three call
for completely different responses. The taxonomy is the point.

**One retry, transport only.** A timeout or a dropped connection is worth
retrying once because the request never landed. A response that failed
validation is *not*: the model already answered, the answer was wrong, and
asking again turns a measurable refusal into a slot machine. `jtt.6.1`'s
validator is the arbiter of correctness, and nothing here may retry past it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

ADAPTER_PROTOCOL_VERSION = "1.0.0"
"""Bumped when this boundary changes shape. Recorded in every response."""


class FailureReason(StrEnum):
    """Why a call did not produce a usable response.

    Distinct members because each one implies a different action: retry the
    transport, fix a credential, back off, or treat the model as unsuitable.
    """

    TIMEOUT = "timeout"
    """No response within the configured deadline. Transport; retryable once."""

    NETWORK = "network"
    """Connection refused, DNS failure, reset. Transport; retryable once."""

    AUTHENTICATION = "authentication"
    """Rejected credentials (401/403). Never retried — a second identical call fails identically."""

    RATE_LIMIT = "rate_limit"
    """Throttled (429). Never retried here; backoff is the caller's policy, not the adapter's."""

    INVALID_RESPONSE = "invalid_response"
    """The model answered, and the answer was not usable JSON of the required shape."""

    CONFIGURATION = "configuration"
    """The adapter cannot run at all: no endpoint, no model id, no credential."""


#: Failures worth exactly one more attempt.
#:
#: Transport only. The request never reached the model, so repeating it is not
#: asking the same question twice — it is asking it once.
RETRYABLE: frozenset[FailureReason] = frozenset({FailureReason.TIMEOUT, FailureReason.NETWORK})


class AdapterError(RuntimeError):
    """Raised only for programmer error — never for a model or transport fault."""


@dataclass(frozen=True)
class AdapterRequest:
    """What every adapter receives. Provider-neutral by construction."""

    system: str
    user: str
    bundle_digest: str
    prompt_contract_version: str
    schema_version: str
    max_output_tokens: int = 2048
    temperature: float = 0.0
    """Zero by default. A grounded explanation has no use for sampling variety."""


@dataclass(frozen=True)
class AdapterUsage:
    """Observability that carries no secret and no personal data.

    Token counts are optional because not every endpoint reports them, and an
    adapter must not invent a number to fill a field. `cost_usd` appears only
    when the caller configured a price; an adapter never guesses what a model
    charges.
    """

    latency_ms: float
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None


@dataclass(frozen=True)
class AdapterResponse:
    """A successful call. `content` is unvalidated — that is the validator's job."""

    content: dict[str, Any]
    adapter_id: str
    adapter_version: str
    model_id: str
    usage: AdapterUsage
    protocol_version: str = ADAPTER_PROTOCOL_VERSION
    from_cache: bool = False
    attempts: int = 1

    def telemetry(self) -> dict[str, Any]:
        """The recordable summary. Deliberately excludes `content` and any credential."""
        return {
            "adapter_id": self.adapter_id,
            "adapter_version": self.adapter_version,
            "model_id": self.model_id,
            "protocol_version": self.protocol_version,
            "latency_ms": round(self.usage.latency_ms, 3),
            "input_tokens": self.usage.input_tokens,
            "output_tokens": self.usage.output_tokens,
            "cost_usd": self.usage.cost_usd,
            "from_cache": self.from_cache,
            "attempts": self.attempts,
        }


@dataclass(frozen=True)
class AdapterFailure:
    """A call that produced no usable response.

    Returned, not raised. A failure is an outcome an eval records alongside its
    successes; making it an exception would push callers toward a bare `except`
    that erases the reason.
    """

    reason: FailureReason
    detail: str
    adapter_id: str
    model_id: str | None = None
    attempts: int = 1
    retryable: bool = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "retryable", self.reason in RETRYABLE)

    def __str__(self) -> str:
        return f"{self.adapter_id}: {self.reason} after {self.attempts} attempt(s) — {self.detail}"


AdapterResult = AdapterResponse | AdapterFailure


@runtime_checkable
class ExplanationAdapter(Protocol):
    """What a project user implements to plug their own model in.

    Four members, and none of them mention a provider. An implementation that
    needs a fifth to work is telling you the contract does not fit it, which is
    `scoutlens-jtt.6.2`'s stop condition: the adapter is unsupported, and the
    neutral interface does not grow to accommodate it.
    """

    @property
    def adapter_id(self) -> str:
        """Stable identifier. Part of the cache key, so it must change when behaviour does."""
        ...

    @property
    def adapter_version(self) -> str:
        """Implementation version. Also part of the cache key."""
        ...

    @property
    def model_id(self) -> str:
        """The model this instance targets."""
        ...

    def complete(self, request: AdapterRequest) -> AdapterResult:
        """Call the model once, applying the adapter's own retry policy.

        Must never raise for a model or transport fault — return an
        `AdapterFailure`. Must never retry a response that parsed but was
        semantically wrong; that is the validator's territory.
        """
        ...


__all__ = [
    "ADAPTER_PROTOCOL_VERSION",
    "RETRYABLE",
    "AdapterError",
    "AdapterFailure",
    "AdapterRequest",
    "AdapterResponse",
    "AdapterResult",
    "AdapterUsage",
    "ExplanationAdapter",
    "FailureReason",
]
