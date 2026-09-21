"""The live path, exercised without a live model.

Every test here drives `run_live` with an offline stand-in. That is not a
compromise: what needs proving is that the live *harness* records the right
things, applies the preregistered bar mechanically, and refuses to write where
the contract forbids — and none of that is easier to see with a real endpoint
attached. Whether a particular model clears the bar is a question only a real
run answers, and its answer is telemetry.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import requires_showcase

from scoutlens.explanations.adapters.fake import ScriptedAdapter
from scoutlens.explanations.adapters.protocol import (
    AdapterRequest,
    AdapterResponse,
    AdapterResult,
    AdapterUsage,
)
from scoutlens.explanations.evals.corpus import ShowcaseArtifacts, materialise
from scoutlens.explanations.evals.run_live import (
    EXIT_REFUSED,
    build_telemetry,
    endpoint_class,
    main,
    run_once,
)
from scoutlens.explanations.evals.runner import live_cases
from scoutlens.explanations.prompt import PROMPT_CONTRACT_VERSION

pytestmark = requires_showcase


@pytest.fixture(scope="module")
def artifacts() -> ShowcaseArtifacts:
    return ShowcaseArtifacts()


@pytest.fixture()
def obedient(artifacts: ShowcaseArtifacts) -> ScriptedAdapter:
    """A stand-in for a model that follows every rule."""
    responses = {}
    for case in live_cases():
        if case.major != 2:
            continue
        material = materialise(case, artifacts)
        responses[material.bundle["bundle_digest"]] = material.response
    return ScriptedAdapter(responses, model_id="obedient-stub")


class _ProseAdapter:
    """A stand-in for a model that answers in prose when asked for JSON.

    The realistic failure. A model that has been told to return JSON and has
    something to apologise for will return an apology, and it will be valid
    JSON containing no explanation at all.
    """

    base_url = "https://private-endpoint.internal/v1"
    adapter_version = "1.0.0"
    model_id = "prose-stub"
    endpoint_class = "openai_compatible"

    @property
    def adapter_id(self) -> str:
        return "prose"

    def complete(self, request: AdapterRequest) -> AdapterResult:
        return AdapterResponse(
            content={"answer": "I would rather not commit to a number."},
            adapter_id=self.adapter_id,
            adapter_version=self.adapter_version,
            model_id=self.model_id,
            usage=AdapterUsage(latency_ms=12.5, input_tokens=900, output_tokens=12),
        )


def test_live_runs_use_only_the_accept_cases() -> None:
    """The rest prescribe an answer, which a model cannot be asked to produce."""
    assert live_cases()
    assert all(str(case.expectation) == "accept" for case in live_cases())


def test_an_obedient_model_clears_the_live_bar(
    obedient: ScriptedAdapter, artifacts: ShowcaseArtifacts
) -> None:
    runs = [run_once(obedient, artifacts) for _ in range(3)]
    telemetry = build_telemetry(obedient, runs)
    assert telemetry["gate"]["outcome"] == "pass"
    assert telemetry["structured_validity_per_run"] == [1.0, 1.0, 1.0]


def test_a_model_that_answers_in_prose_is_dropped(artifacts: ShowcaseArtifacts) -> None:
    """A `DROP` for that exact model, prompt version and schema version."""
    adapter = _ProseAdapter()
    runs = [run_once(adapter, artifacts) for _ in range(3)]
    telemetry = build_telemetry(adapter, runs)
    assert telemetry["gate"]["outcome"] == "drop"
    assert telemetry["structured_validity_per_run"] == [0.0, 0.0, 0.0]
    assert "new preregistered decision" in telemetry["gate"]["detail"]
    assert telemetry["versions"]["prompt_contract_version"] == PROMPT_CONTRACT_VERSION


def test_a_short_series_is_not_a_pass(
    obedient: ScriptedAdapter, artifacts: ShowcaseArtifacts
) -> None:
    telemetry = build_telemetry(obedient, [run_once(obedient, artifacts)])
    assert telemetry["gate"]["outcome"] == "not_run"


def test_telemetry_records_what_ac4_asks_for(
    obedient: ScriptedAdapter, artifacts: ShowcaseArtifacts
) -> None:
    telemetry = build_telemetry(obedient, [run_once(obedient, artifacts)])
    assert telemetry["model"]["adapter_id"]
    assert telemetry["model"]["model_id"]
    assert telemetry["model"]["endpoint_class"]
    assert telemetry["versions"]["output_schema_version"]

    rows = telemetry["runs"][0]["cases"]
    assert rows
    for row in rows:
        assert len(row["bundle_digest"]) == 64
        for field in ("input_tokens", "output_tokens", "latency_ms", "cost_usd"):
            assert field in row, f"{field} is not recorded even as absent"


def test_telemetry_never_records_an_endpoint_or_a_credential(
    artifacts: ShowcaseArtifacts,
) -> None:
    """A private endpoint in a file someone later shares is a disclosure."""
    adapter = _ProseAdapter()
    telemetry = build_telemetry(adapter, [run_once(adapter, artifacts)])
    rendered = json.dumps(telemetry).lower()
    assert "private-endpoint.internal" not in rendered
    assert "http://" not in rendered
    assert "https://" not in rendered
    for marker in ("authorization", "bearer ", "api_key", "secret"):
        assert marker not in rendered


def test_endpoint_class_prefers_the_declared_category() -> None:
    assert endpoint_class(_ProseAdapter()) == "openai_compatible"
    assert endpoint_class(ScriptedAdapter({})) == "ScriptedAdapter"


def test_live_output_may_not_be_written_into_the_replay_directory(tmp_path: Path) -> None:
    """The boundary is the file, and the command enforces it rather than the reviewer."""
    forbidden = tmp_path / "artifacts" / "ai-evals" / "grounded-explanations-v1.json"
    code = main(
        [
            "--adapter",
            "scoutlens.explanations.adapters.fake:ScriptedAdapter",
            "--output",
            str(forbidden),
        ]
    )
    assert code == EXIT_REFUSED
    assert not forbidden.exists()


def test_nothing_in_the_replay_path_imports_the_live_runner() -> None:
    """Opt-in by construction: the recorded report cannot reach a model."""
    from scoutlens.explanations.evals import report

    source = Path(report.__file__).read_text(encoding="utf-8")
    assert "run_live" not in source
    assert "requests" not in source
