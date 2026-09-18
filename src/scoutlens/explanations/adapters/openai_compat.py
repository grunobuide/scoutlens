"""The reference adapter: any OpenAI-compatible `/chat/completions` endpoint.

**No provider SDK.** It speaks the wire format over `requests`, which this
project already depends on for ingestion. That is the whole point of choosing
this contract: llama.cpp, vLLM, Ollama, LM Studio, LocalAI and most hosted
services all expose it, so one small adapter reaches all of them and the base
runtime stays free of any vendor's package. `flagship-ai-delivery` requires a
clone to be able to configure its own model without a provider-specific
dependency, and an SDK here would quietly break that for everyone who uses a
different provider.

**Credentials come from the environment and nowhere else.** Never a CLI
argument, never a config file in the repo, never a log line. A key in `argv` is
visible in every process listing on the machine; a key in a log outlives the run
in whatever collects the logs.

The retry policy is `protocol.RETRYABLE` and nothing more: one extra attempt for
a timeout or a network fault, none for anything the model actually answered.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any

import requests

from scoutlens.explanations.adapters.protocol import (
    RETRYABLE,
    AdapterFailure,
    AdapterRequest,
    AdapterResponse,
    AdapterResult,
    AdapterUsage,
    FailureReason,
)

DEFAULT_TIMEOUT_SECONDS = 60.0
MAX_TRANSPORT_ATTEMPTS = 2
"""One call plus at most one retry. See the module docstring."""


@dataclass
class OpenAICompatibleAdapter:
    """Talks to a configurable OpenAI-compatible chat-completions endpoint.

    `base_url` and `model` are required and have no defaults pointing at any
    vendor — a default endpoint would make one provider the implicit standard
    and quietly send a user's evidence somewhere they did not choose.
    """

    base_url: str
    model: str
    api_key_env: str = "SCOUTLENS_MODEL_API_KEY"
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    cost_per_1k_input: float | None = None
    cost_per_1k_output: float | None = None
    adapter_version: str = "1.0.0"
    session: requests.Session | None = None

    @property
    def adapter_id(self) -> str:
        return "openai-compatible"

    @property
    def model_id(self) -> str:
        return self.model

    def _endpoint(self) -> str:
        return f"{self.base_url.rstrip('/')}/chat/completions"

    def _headers(self) -> dict[str, str] | AdapterFailure:
        headers = {"Content-Type": "application/json"}
        key = os.environ.get(self.api_key_env, "").strip()
        if key:
            headers["Authorization"] = f"Bearer {key}"
        # A missing key is not an error here: local servers routinely need none.
        # A *wrong* key is the endpoint's business, and comes back as 401.
        return headers

    def _payload(self, request: AdapterRequest) -> dict[str, Any]:
        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.user},
            ],
            "temperature": request.temperature,
            "max_tokens": request.max_output_tokens,
            # Ask for JSON where the endpoint honours it. Not relied upon:
            # `_parse` treats the body as untrusted either way, because many
            # compatible servers accept this field and ignore it.
            "response_format": {"type": "json_object"},
        }

    def complete(self, request: AdapterRequest) -> AdapterResult:
        if not self.base_url or not self.model:
            return AdapterFailure(
                reason=FailureReason.CONFIGURATION,
                detail="base_url and model are both required; there is no default endpoint",
                adapter_id=self.adapter_id,
                model_id=self.model or None,
            )

        headers = self._headers()
        if isinstance(headers, AdapterFailure):
            return headers

        session = self.session or requests.Session()
        payload = self._payload(request)
        last: AdapterFailure | None = None

        for attempt in range(1, MAX_TRANSPORT_ATTEMPTS + 1):
            started = time.perf_counter()
            try:
                response = session.post(
                    self._endpoint(),
                    headers=headers,
                    json=payload,
                    timeout=self.timeout_seconds,
                )
            except requests.Timeout as error:
                last = self._failure(FailureReason.TIMEOUT, str(error), attempt)
            except requests.RequestException as error:
                last = self._failure(FailureReason.NETWORK, str(error), attempt)
            else:
                latency_ms = (time.perf_counter() - started) * 1000.0
                result = self._interpret(response, attempt, latency_ms)
                if isinstance(result, AdapterResponse):
                    return result
                # A non-transport failure is final. Retrying a 401 produces the
                # same 401, and retrying a malformed answer asks the model to
                # roll the dice again — which the validator exists to prevent.
                if result.reason not in RETRYABLE:
                    return result
                last = result

            if last is not None and last.reason not in RETRYABLE:
                return last

        assert last is not None
        return last

    def _failure(self, reason: FailureReason, detail: str, attempts: int) -> AdapterFailure:
        return AdapterFailure(
            reason=reason,
            detail=detail,
            adapter_id=self.adapter_id,
            model_id=self.model,
            attempts=attempts,
        )

    def _interpret(
        self, response: requests.Response, attempt: int, latency_ms: float
    ) -> AdapterResult:
        if response.status_code in (401, 403):
            return self._failure(
                FailureReason.AUTHENTICATION,
                f"endpoint returned {response.status_code}; check ${self.api_key_env}",
                attempt,
            )
        if response.status_code == 429:
            return self._failure(FailureReason.RATE_LIMIT, "endpoint returned 429", attempt)
        if response.status_code >= 500:
            # Server-side and transient: the model did not answer, so this is a
            # transport fault by behaviour even though it arrived as a response.
            return self._failure(
                FailureReason.NETWORK, f"endpoint returned {response.status_code}", attempt
            )
        if response.status_code != 200:
            return self._failure(
                FailureReason.INVALID_RESPONSE,
                f"unexpected status {response.status_code}",
                attempt,
            )

        return self._parse(response, attempt, latency_ms)

    def _parse(self, response: requests.Response, attempt: int, latency_ms: float) -> AdapterResult:
        try:
            body = response.json()
        except ValueError as error:
            return self._failure(FailureReason.INVALID_RESPONSE, f"body is not JSON: {error}", attempt)

        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            return self._failure(
                FailureReason.INVALID_RESPONSE,
                f"response is not an OpenAI-compatible completion: {error}",
                attempt,
            )

        if not isinstance(content, str):
            return self._failure(
                FailureReason.INVALID_RESPONSE, "message content is not a string", attempt
            )

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as error:
            # The model answered in prose. That is a model-quality outcome, not a
            # transport one, so it is recorded and never retried.
            return self._failure(
                FailureReason.INVALID_RESPONSE,
                f"model returned text that is not JSON: {error}",
                attempt,
            )

        if not isinstance(parsed, dict):
            return self._failure(
                FailureReason.INVALID_RESPONSE,
                f"model returned a JSON {type(parsed).__name__}, not an object",
                attempt,
            )

        return AdapterResponse(
            content=parsed,
            adapter_id=self.adapter_id,
            adapter_version=self.adapter_version,
            model_id=self.model,
            usage=self._usage(body, latency_ms),
            attempts=attempt,
        )

    def _usage(self, body: dict[str, Any], latency_ms: float) -> AdapterUsage:
        """Token counts only when the endpoint reports them — never invented."""
        reported = body.get("usage")
        usage: dict[str, Any] = reported if isinstance(reported, dict) else {}
        input_tokens = usage.get("prompt_tokens")
        output_tokens = usage.get("completion_tokens")

        cost: float | None = None
        if self.cost_per_1k_input is not None and isinstance(input_tokens, int):
            cost = (input_tokens / 1000.0) * self.cost_per_1k_input
        if self.cost_per_1k_output is not None and isinstance(output_tokens, int):
            cost = (cost or 0.0) + (output_tokens / 1000.0) * self.cost_per_1k_output

        return AdapterUsage(
            latency_ms=latency_ms,
            input_tokens=input_tokens if isinstance(input_tokens, int) else None,
            output_tokens=output_tokens if isinstance(output_tokens, int) else None,
            cost_usd=cost,
        )


__all__ = ["DEFAULT_TIMEOUT_SECONDS", "MAX_TRANSPORT_ATTEMPTS", "OpenAICompatibleAdapter"]
