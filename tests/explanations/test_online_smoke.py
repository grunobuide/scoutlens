"""The one test that may touch a network — and only when you ask it to.

Skipped unless `SCOUTLENS_ONLINE_SMOKE=1` *and* an endpoint is configured. Both
conditions, because either alone is a foot-gun: an endpoint variable left in a
shell from yesterday should not silently start making calls, and the opt-in flag
alone should not fail a run that has nothing to call.

Default CI therefore stays network-free and credential-free without the workflow
needing to know this file exists — the skip lives with the test rather than in a
CI config someone can forget to update.

To run it against a local server:

    SCOUTLENS_ONLINE_SMOKE=1 \\
    SCOUTLENS_MODEL_BASE_URL=http://127.0.0.1:11434/v1 \\
    SCOUTLENS_MODEL_ID=llama3.1:8b \\
    uv run --frozen pytest tests/explanations/test_online_smoke.py -q

It asserts the *boundary*, not the model: that a real endpoint speaking the
OpenAI-compatible contract produces a typed result and clean telemetry. Whether
the model explains well is `scoutlens-jtt.6.3`'s question, and this test would
pass on a model that answers nonsense as long as the nonsense is shaped right.
"""

from __future__ import annotations

import os

import pytest

from scoutlens.explanations.adapters import (
    AdapterFailure,
    AdapterRequest,
    AdapterResponse,
    FailureReason,
    OpenAICompatibleAdapter,
)
from scoutlens.explanations.adapters.conformance import run_conformance

BASE_URL = os.environ.get("SCOUTLENS_MODEL_BASE_URL", "").strip()
MODEL_ID = os.environ.get("SCOUTLENS_MODEL_ID", "").strip()
OPTED_IN = os.environ.get("SCOUTLENS_ONLINE_SMOKE", "").strip() == "1"

pytestmark = pytest.mark.skipif(
    not (OPTED_IN and BASE_URL and MODEL_ID),
    reason=(
        "online smoke test is opt-in: set SCOUTLENS_ONLINE_SMOKE=1 together with "
        "SCOUTLENS_MODEL_BASE_URL and SCOUTLENS_MODEL_ID"
    ),
)


@pytest.fixture()
def adapter() -> OpenAICompatibleAdapter:
    return OpenAICompatibleAdapter(base_url=BASE_URL, model=MODEL_ID, timeout_seconds=30.0)


def test_a_real_endpoint_returns_a_typed_result(adapter: OpenAICompatibleAdapter) -> None:
    result = adapter.complete(
        AdapterRequest(
            system='Reply with JSON only: {"ok": true}. No prose.',
            user="Reply now.",
            bundle_digest="0" * 64,
            prompt_contract_version="1.0.0",
            schema_version="1.0.0",
            max_output_tokens=64,
        )
    )

    if isinstance(result, AdapterFailure):
        # A failure is a legitimate outcome for a live endpoint — it must simply
        # be one of the typed reasons rather than an exception or a surprise.
        assert isinstance(result.reason, FailureReason)
        assert result.detail
        pytest.skip(f"endpoint returned {result.reason}: {result.detail}")

    assert isinstance(result, AdapterResponse)
    assert isinstance(result.content, dict)
    assert result.usage.latency_ms > 0
    assert result.model_id == MODEL_ID


def test_a_real_endpoint_satisfies_the_conformance_suite(adapter: OpenAICompatibleAdapter) -> None:
    failed = [result for result in run_conformance(adapter) if not result.passed]
    assert not failed, [str(result) for result in failed]


def test_no_credential_reaches_the_telemetry(adapter: OpenAICompatibleAdapter) -> None:
    key = os.environ.get("SCOUTLENS_MODEL_API_KEY", "").strip()
    if not key:
        pytest.skip("no credential configured, so there is nothing that could leak")

    result = adapter.complete(
        AdapterRequest(
            system='Reply with JSON only: {"ok": true}.',
            user="Reply now.",
            bundle_digest="0" * 64,
            prompt_contract_version="1.0.0",
            schema_version="1.0.0",
            max_output_tokens=64,
        )
    )
    rendered = repr(result.telemetry()) if isinstance(result, AdapterResponse) else str(result)
    assert key not in rendered
