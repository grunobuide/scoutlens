"""Deterministic offline adapters — the default everywhere CI runs.

Two of them, and both are load-bearing rather than convenient:

`ScriptedAdapter` replays a fixed mapping from bundle digest to response. It is
what makes an eval a *replay*: the same digests in, the same JSON out, no
network, no credential, byte-identical between runs. `D057` §4.6 requires the
recorded eval report to be exactly that.

`FaultAdapter` produces one chosen failure. It exists because the failure
taxonomy is only worth having if something proves each member is reachable and
distinct, and you cannot get a rate-limit from a real endpoint on demand without
abusing someone's service.

Neither imports `requests`. An offline adapter that could open a socket would
make "the default CI path is offline" a claim about intent rather than about
code.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from scoutlens.explanations.adapters.protocol import (
    ADAPTER_PROTOCOL_VERSION,
    AdapterFailure,
    AdapterRequest,
    AdapterResponse,
    AdapterResult,
    AdapterUsage,
    FailureReason,
)


@dataclass
class ScriptedAdapter:
    """Replays stored responses, keyed by bundle digest."""

    responses: dict[str, dict[str, Any]]
    model_id: str = "scripted-offline"
    adapter_version: str = "1.0.0"
    _calls: list[AdapterRequest] = field(default_factory=list, init=False, repr=False)

    @property
    def adapter_id(self) -> str:
        return "scripted"

    @property
    def calls(self) -> tuple[AdapterRequest, ...]:
        """What it was asked, in order. Lets a test assert the prompt actually reached it."""
        return tuple(self._calls)

    def complete(self, request: AdapterRequest) -> AdapterResult:
        started = time.perf_counter()
        self._calls.append(request)

        stored = self.responses.get(request.bundle_digest)
        if stored is None:
            # An absent digest is `invalid_response`, not a crash: a replay whose
            # corpus has drifted from its bundles is a real condition an eval
            # must record rather than abort on.
            return AdapterFailure(
                reason=FailureReason.INVALID_RESPONSE,
                detail=f"no scripted response for bundle digest {request.bundle_digest[:12]}",
                adapter_id=self.adapter_id,
                model_id=self.model_id,
            )

        return AdapterResponse(
            content=stored,
            adapter_id=self.adapter_id,
            adapter_version=self.adapter_version,
            model_id=self.model_id,
            usage=AdapterUsage(latency_ms=(time.perf_counter() - started) * 1000.0),
            protocol_version=ADAPTER_PROTOCOL_VERSION,
        )


@dataclass
class FaultAdapter:
    """Always fails, with the reason you asked for.

    `succeed_after` makes the retry policy observable: set it to 1 and the
    adapter fails once and then succeeds, which is the only way to prove "one
    retry" means one rather than zero or many.
    """

    reason: FailureReason
    response: dict[str, Any] | None = None
    succeed_after: int | None = None
    model_id: str = "fault-offline"
    adapter_version: str = "1.0.0"
    _attempts: int = field(default=0, init=False, repr=False)

    @property
    def adapter_id(self) -> str:
        return "fault"

    @property
    def attempts(self) -> int:
        return self._attempts

    def complete(self, request: AdapterRequest) -> AdapterResult:
        self._attempts += 1
        if self.succeed_after is not None and self._attempts > self.succeed_after:
            return AdapterResponse(
                content=self.response or {},
                adapter_id=self.adapter_id,
                adapter_version=self.adapter_version,
                model_id=self.model_id,
                usage=AdapterUsage(latency_ms=0.0),
                attempts=self._attempts,
            )
        return AdapterFailure(
            reason=self.reason,
            detail=f"synthetic {self.reason} on attempt {self._attempts}",
            adapter_id=self.adapter_id,
            model_id=self.model_id,
            attempts=self._attempts,
        )


__all__ = ["FaultAdapter", "ScriptedAdapter"]
