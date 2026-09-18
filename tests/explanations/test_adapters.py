"""The adapter boundary: identity, typed failures, retry discipline, clean telemetry.

Every test here runs offline. The reference adapter is exercised through a stub
session that returns whatever the test wants — no socket is opened, no
credential is read from a real environment, and the suite passes on a machine
with no network at all. That is the property `flagship-ai-delivery` asks for,
and a test that quietly needed the internet would hide its loss.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
import requests

from scoutlens.explanations.adapters import (
    RETRYABLE,
    AdapterFailure,
    AdapterRequest,
    AdapterResponse,
    ExplanationAdapter,
    FailureReason,
    FaultAdapter,
    OpenAICompatibleAdapter,
    ResponseCache,
    ScriptedAdapter,
    cache_key,
)
from scoutlens.explanations.adapters.conformance import run_conformance
from scoutlens.explanations.adapters.openai_compat import MAX_TRANSPORT_ATTEMPTS

DIGEST = "a" * 64
OTHER_DIGEST = "b" * 64


def request_for(digest: str = DIGEST, **overrides: Any) -> AdapterRequest:
    fields: dict[str, Any] = {
        "system": "system",
        "user": "user",
        "bundle_digest": digest,
        "prompt_contract_version": "1.0.0",
        "schema_version": "1.0.0",
    }
    fields.update(overrides)
    return AdapterRequest(**fields)


class StubResponse:
    """Minimal stand-in for `requests.Response`."""

    def __init__(self, status_code: int, body: Any = None, *, text_body: str | None = None) -> None:
        self.status_code = status_code
        self._body = body
        self._text = text_body

    def json(self) -> Any:
        if self._text is not None:
            raise ValueError("not JSON")
        return self._body


class StubSession:
    """Returns queued responses, or raises queued exceptions, in order.

    Once the queue is down to its last entry that entry repeats, so a stub can
    be handed to something like the conformance suite that calls `complete`
    several times without the test having to know how many.
    """

    def __init__(self, *outcomes: Any) -> None:
        if not outcomes:
            raise ValueError("a stub session needs at least one outcome")
        self.outcomes = list(outcomes)
        self.calls: list[dict[str, Any]] = []

    def post(self, url: str, **kwargs: Any) -> StubResponse:
        self.calls.append({"url": url, **kwargs})
        outcome = self.outcomes.pop(0) if len(self.outcomes) > 1 else self.outcomes[0]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def completion(content: Any, usage: dict[str, int] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {
        "choices": [{"message": {"content": content if isinstance(content, str) else json.dumps(content)}}]
    }
    if usage is not None:
        body["usage"] = usage
    return body


def reference(session: StubSession, **overrides: Any) -> OpenAICompatibleAdapter:
    fields: dict[str, Any] = {
        "base_url": "http://127.0.0.1:11434/v1",
        "model": "local-model",
        "session": session,
    }
    fields.update(overrides)
    return OpenAICompatibleAdapter(**fields)


# --------------------------------------------------------------------------
# AC1 — the same suite passes for offline, reference and external adapters
# --------------------------------------------------------------------------


def _external_factory() -> Any:
    """Stands in for an adapter a project user wrote in their own package."""

    class ExternalAdapter:
        adapter_id = "external-example"
        adapter_version = "0.1.0"
        model_id = "whatever-they-run"

        def complete(self, request: AdapterRequest) -> AdapterFailure:
            return AdapterFailure(
                reason=FailureReason.INVALID_RESPONSE,
                detail="no stored response for this bundle",
                adapter_id=self.adapter_id,
                model_id=self.model_id,
            )

    return ExternalAdapter()


@pytest.mark.parametrize(
    "build",
    [
        pytest.param(lambda: ScriptedAdapter(responses={}), id="offline-scripted"),
        pytest.param(lambda: reference(StubSession(requests.Timeout("slow"), requests.Timeout("slow"))), id="reference"),
        pytest.param(_external_factory, id="external"),
    ],
)
def test_every_adapter_passes_the_same_conformance_suite(build: Any) -> None:
    """AC1. One suite, three very different implementations, no special cases."""
    results = run_conformance(build())
    failed = [result for result in results if not result.passed]
    assert not failed, [str(result) for result in failed]


def test_an_adapter_missing_a_member_fails_conformance() -> None:
    """The suite has teeth: a positive result elsewhere must mean something."""

    class Incomplete:
        adapter_id = "incomplete"
        # no adapter_version, no model_id, no complete()

    failed = [result for result in run_conformance(Incomplete()) if not result.passed]
    assert failed, "an adapter with no complete() passed conformance"


def test_the_protocol_is_structural_not_inherited() -> None:
    """A user's adapter need not import a base class to satisfy the contract."""
    assert isinstance(_external_factory(), ExplanationAdapter)


# --------------------------------------------------------------------------
# AC2 / AC3 — configuration, credentials, and no provider SDK
# --------------------------------------------------------------------------


def test_base_url_and_model_are_configurable_with_no_vendor_default() -> None:
    """AC2. A default endpoint would send a user's evidence somewhere they did not choose."""
    adapter = reference(StubSession(StubResponse(200, completion({"ok": True}))), base_url="http://elsewhere/v1", model="other")
    result = adapter.complete(request_for())
    assert isinstance(result, AdapterResponse)
    assert adapter.session is not None
    assert adapter.session.calls[0]["url"] == "http://elsewhere/v1/chat/completions"
    assert adapter.session.calls[0]["json"]["model"] == "other"


def test_missing_configuration_is_a_typed_failure_not_a_crash() -> None:
    result = OpenAICompatibleAdapter(base_url="", model="").complete(request_for())
    assert isinstance(result, AdapterFailure)
    assert result.reason is FailureReason.CONFIGURATION


def test_the_credential_comes_from_the_environment_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC2. Never an argument — a key in argv is visible in every process listing."""
    monkeypatch.setenv("SCOUTLENS_MODEL_API_KEY", "secret-value")
    session = StubSession(StubResponse(200, completion({"ok": True})))
    reference(session).complete(request_for())

    assert session.calls[0]["headers"]["Authorization"] == "Bearer secret-value"
    assert "secret-value" not in json.dumps(session.calls[0]["json"])


def test_no_credential_is_fine_for_a_local_server(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SCOUTLENS_MODEL_API_KEY", raising=False)
    session = StubSession(StubResponse(200, completion({"ok": True})))
    assert isinstance(reference(session).complete(request_for()), AdapterResponse)
    assert "Authorization" not in session.calls[0]["headers"]


def test_the_base_runtime_imports_no_provider_sdk() -> None:
    """AC3. Asserted on the module, not just the manifest.

    `fireworks-ai` left `pyproject.toml` and the lock in this bead. This catches
    the other direction: an import sneaking back in would make the package
    depend on a vendor again even if the manifest still looked clean.
    """
    import scoutlens.explanations.adapters.openai_compat as module

    source = module.__file__
    assert source is not None
    text = __import__("pathlib").Path(source).read_text(encoding="utf-8")
    for vendor in ("fireworks", "openai", "anthropic", "cohere", "google.generativeai"):
        assert f"import {vendor}" not in text, f"reference adapter imports {vendor}"


# --------------------------------------------------------------------------
# AC4 — five distinct typed failures
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("outcome", "expected"),
    [
        (requests.Timeout("deadline"), FailureReason.TIMEOUT),
        (requests.ConnectionError("refused"), FailureReason.NETWORK),
        (StubResponse(401), FailureReason.AUTHENTICATION),
        (StubResponse(403), FailureReason.AUTHENTICATION),
        (StubResponse(429), FailureReason.RATE_LIMIT),
        (StubResponse(500), FailureReason.NETWORK),
        (StubResponse(200, None, text_body="not json"), FailureReason.INVALID_RESPONSE),
        (StubResponse(200, {"choices": []}), FailureReason.INVALID_RESPONSE),
        (StubResponse(200, completion("plain prose, not JSON")), FailureReason.INVALID_RESPONSE),
        (StubResponse(200, completion([1, 2, 3])), FailureReason.INVALID_RESPONSE),
    ],
)
def test_each_fault_maps_to_its_own_reason(outcome: Any, expected: FailureReason) -> None:
    """AC4. The taxonomy is only useful if the members are actually distinguishable."""
    # Two outcomes queued so a retryable fault can exhaust its one retry.
    result = reference(StubSession(outcome, outcome)).complete(request_for())
    assert isinstance(result, AdapterFailure)
    assert result.reason is expected


def test_a_model_answering_in_prose_is_a_model_outcome_not_a_transport_one() -> None:
    """The distinction that matters most: it is recorded, and never retried."""
    session = StubSession(StubResponse(200, completion("I think this player is great!")))
    result = reference(session).complete(request_for())
    assert isinstance(result, AdapterFailure)
    assert result.reason is FailureReason.INVALID_RESPONSE
    assert result.retryable is False
    assert len(session.calls) == 1


# --------------------------------------------------------------------------
# AC5 — at most one retry, transport only
# --------------------------------------------------------------------------


def test_a_transport_fault_is_retried_exactly_once() -> None:
    session = StubSession(requests.Timeout("slow"), requests.Timeout("slow"))
    result = reference(session).complete(request_for())
    assert isinstance(result, AdapterFailure)
    assert len(session.calls) == MAX_TRANSPORT_ATTEMPTS == 2
    assert result.attempts == 2


def test_a_retried_transport_fault_can_succeed_on_the_second_attempt() -> None:
    session = StubSession(requests.ConnectionError("reset"), StubResponse(200, completion({"ok": True})))
    result = reference(session).complete(request_for())
    assert isinstance(result, AdapterResponse)
    assert result.attempts == 2


@pytest.mark.parametrize("outcome", [StubResponse(401), StubResponse(429)])
def test_a_non_transport_failure_is_never_retried(outcome: Any) -> None:
    """Retrying a 401 produces the same 401; retrying a wrong answer rolls dice."""
    session = StubSession(outcome, outcome)
    result = reference(session).complete(request_for())
    assert isinstance(result, AdapterFailure)
    assert len(session.calls) == 1
    assert result.attempts == 1


def test_the_retry_set_is_exactly_the_transport_faults() -> None:
    assert RETRYABLE == {FailureReason.TIMEOUT, FailureReason.NETWORK}
    for reason in FailureReason:
        failure = AdapterFailure(reason=reason, detail="x", adapter_id="a")
        assert failure.retryable is (reason in RETRYABLE)


def test_the_fault_adapter_proves_the_policy_is_observable() -> None:
    adapter = FaultAdapter(reason=FailureReason.TIMEOUT, succeed_after=1, response={"ok": True})
    assert isinstance(adapter.complete(request_for()), AdapterFailure)
    assert isinstance(adapter.complete(request_for()), AdapterResponse)


# --------------------------------------------------------------------------
# AC6 — cache identity
# --------------------------------------------------------------------------


def _key(**overrides: Any) -> str:
    fields: dict[str, Any] = {
        "adapter_id": "a",
        "adapter_version": "1.0.0",
        "model_id": "m",
        "request": request_for(),
    }
    fields.update(overrides)
    return cache_key(**fields)


@pytest.mark.parametrize(
    "overrides",
    [
        {"adapter_id": "other"},
        {"adapter_version": "2.0.0"},
        {"model_id": "other-model"},
        {"request": request_for(OTHER_DIGEST)},
        {"request": request_for(prompt_contract_version="2.0.0")},
        {"request": request_for(schema_version="2.0.0")},
    ],
    ids=["adapter", "adapter_version", "model", "evidence", "prompt_version", "schema_version"],
)
def test_every_part_of_the_identity_changes_the_key(overrides: dict[str, Any]) -> None:
    """AC6. Six parts, and leaving any one out lets a stale answer through.

    Drop the prompt version and a rewritten instruction serves yesterday's
    answers; drop the schema version and an output shaped for the old contract
    passes as current.
    """
    assert _key(**overrides) != _key()


def test_the_same_identity_is_the_same_key() -> None:
    assert _key() == _key()


def test_the_cache_round_trips_and_persists(tmp_path: Any) -> None:
    cache = ResponseCache(directory=tmp_path)
    key = _key()
    assert cache.get(key) is None
    cache.put(key, {"claims": []})
    assert cache.get(key) == {"claims": []}
    assert ResponseCache(directory=tmp_path).get(key) == {"claims": []}


def test_a_corrupt_cache_entry_is_a_miss_not_a_crash(tmp_path: Any) -> None:
    """A damaged cache file must not decide the outcome of a run."""
    cache = ResponseCache(directory=tmp_path)
    key = _key()
    (tmp_path / f"{key}.json").write_text("{ this is not json", encoding="utf-8")
    assert cache.get(key) is None


# --------------------------------------------------------------------------
# AC7 — telemetry carries no secret
# --------------------------------------------------------------------------


def test_telemetry_reports_latency_tokens_and_cost_when_configured() -> None:
    session = StubSession(
        StubResponse(200, completion({"ok": True}, usage={"prompt_tokens": 1000, "completion_tokens": 500}))
    )
    adapter = reference(session, cost_per_1k_input=0.002, cost_per_1k_output=0.004)
    result = adapter.complete(request_for())
    assert isinstance(result, AdapterResponse)

    telemetry = result.telemetry()
    assert telemetry["input_tokens"] == 1000
    assert telemetry["output_tokens"] == 500
    assert telemetry["cost_usd"] == pytest.approx(0.002 + 0.002)
    assert telemetry["latency_ms"] >= 0
    assert "content" not in telemetry


def test_token_counts_are_absent_rather_than_invented() -> None:
    """An endpoint that reports no usage must not acquire a made-up number."""
    session = StubSession(StubResponse(200, completion({"ok": True})))
    result = reference(session).complete(request_for())
    assert isinstance(result, AdapterResponse)
    assert result.usage.input_tokens is None
    assert result.usage.output_tokens is None
    assert result.usage.cost_usd is None


def test_cost_is_absent_unless_a_price_was_configured() -> None:
    """The adapter never guesses what a model charges."""
    session = StubSession(
        StubResponse(200, completion({"ok": True}, usage={"prompt_tokens": 10, "completion_tokens": 5}))
    )
    result = reference(session).complete(request_for())
    assert isinstance(result, AdapterResponse)
    assert result.usage.cost_usd is None


def test_telemetry_never_carries_the_credential(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCOUTLENS_MODEL_API_KEY", "super-secret-token")
    session = StubSession(StubResponse(200, completion({"ok": True})))
    result = reference(session).complete(request_for())
    assert isinstance(result, AdapterResponse)
    assert "super-secret-token" not in repr(result.telemetry())


def test_a_failure_never_echoes_the_credential(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 401's detail names the variable to check, not its value."""
    monkeypatch.setenv("SCOUTLENS_MODEL_API_KEY", "super-secret-token")
    result = reference(StubSession(StubResponse(401))).complete(request_for())
    assert isinstance(result, AdapterFailure)
    assert "super-secret-token" not in str(result)
    assert "SCOUTLENS_MODEL_API_KEY" in result.detail


# --------------------------------------------------------------------------
# Offline replay
# --------------------------------------------------------------------------


def test_the_scripted_adapter_replays_by_digest() -> None:
    adapter = ScriptedAdapter(responses={DIGEST: {"claims": ["stored"]}})
    result = adapter.complete(request_for())
    assert isinstance(result, AdapterResponse)
    assert result.content == {"claims": ["stored"]}
    assert adapter.calls[0].bundle_digest == DIGEST


def test_the_scripted_adapter_refuses_a_digest_it_has_no_answer_for() -> None:
    """A replay corpus that has drifted from its bundles is a condition to record."""
    result = ScriptedAdapter(responses={DIGEST: {}}).complete(request_for(OTHER_DIGEST))
    assert isinstance(result, AdapterFailure)
    assert result.reason is FailureReason.INVALID_RESPONSE


def test_replay_is_deterministic() -> None:
    """The property `D057` §4.6 requires of the recorded eval report."""
    adapter = ScriptedAdapter(responses={DIGEST: {"claims": ["stored"]}})
    first = adapter.complete(request_for())
    second = adapter.complete(request_for())
    assert isinstance(first, AdapterResponse) and isinstance(second, AdapterResponse)
    assert first.content == second.content
