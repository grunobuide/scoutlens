"""The recorded artifact, held to the three properties `D057` section 4.6 names.

Offline, bound to its inputs, and not a model result. Each is checked here as a
behaviour rather than read back out of the file it is supposed to describe — a
report that merely *claims* `response_source: synthesised` would pass a test
that only read the field.
"""

from __future__ import annotations

import json
import socket
from pathlib import Path
from typing import Any

import pytest
from conftest import requires_showcase

from scoutlens.explanations.evals import report as report_module
from scoutlens.explanations.evals.corpus import ShowcaseArtifacts, build_corpus
from scoutlens.explanations.evals.report import GENERATED_BY, response_set_digest
from scoutlens.explanations.evals.run_report import (
    ARTIFACT_PATH,
    EXIT_DRIFTED,
    EXIT_OK,
    generate,
    main,
)
from scoutlens.explanations.prompt import PROMPT_CONTRACT_VERSION

pytestmark = requires_showcase

#: Keys and fragments that would make byte-identity impossible.
TIME_VARYING = (
    "generated_at",
    "timestamp",
    "latency",
    "latency_ms",
    "hostname",
    "elapsed",
    "duration_ms",
)


@pytest.fixture(scope="module")
def artifacts() -> ShowcaseArtifacts:
    return ShowcaseArtifacts()


@pytest.fixture(scope="module")
def generated() -> tuple[dict[str, Any], bytes]:
    return generate()


def test_two_runs_are_byte_identical() -> None:
    """Section 4.1 condition 2, and for this artifact the only thing it can mean."""
    _, first = generate()
    _, second = generate()
    assert first == second


def test_the_report_carries_nothing_time_varying(generated: tuple[dict, bytes]) -> None:
    """Checked over the rendered bytes, so a nested key cannot slip through."""
    _, payload = generated
    rendered = payload.decode("utf-8").lower()
    present = [marker for marker in TIME_VARYING if f'"{marker}"' in rendered]
    assert not present, f"time-varying keys in a byte-identical artifact: {present}"


def test_generating_needs_no_credential(monkeypatch: pytest.MonkeyPatch) -> None:
    """The default path stays offline, so CI needs nothing to run it."""
    monkeypatch.delenv("SCOUTLENS_MODEL_API_KEY", raising=False)
    report, _ = generate()
    assert report["gates"]["deterministic"]["outcome"] == "pass"


def test_generating_opens_no_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    """Offline as a property of the code, not of the reviewer's attention."""

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("the replay report opened a network connection")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    generate()


def test_the_report_binds_itself_to_its_inputs(generated: tuple[dict, bytes]) -> None:
    """Section 4.6 condition 2: digests, versions, adapter, stored responses."""
    report, _ = generated
    inputs = report["inputs"]
    assert inputs["prompt_contract_version"] == PROMPT_CONTRACT_VERSION
    assert inputs["adapter"]["adapter_id"]
    assert len(inputs["response_set_digest"]) == 64
    assert set(inputs["bundle_digests"]) == {case.case_id for case in build_corpus()}
    assert all(len(digest) == 64 for digest in inputs["bundle_digests"].values())
    assert inputs["dataset_version"]


def test_the_report_says_what_produced_it(generated: tuple[dict, bytes]) -> None:
    report, _ = generated
    assert report["generated_by"] == GENERATED_BY
    assert report["response_source"] == "synthesised"
    assert "No model produced them" in report["response_source_note"]


def test_the_report_records_no_live_result(generated: tuple[dict, bytes]) -> None:
    """Section 4.6 condition 3. A live number reaching this file would arrive
    with the authority of a reproducible one."""
    report, _ = generated
    assert report["gates"]["live"]["outcome"] == "not_run"


def test_the_response_set_digest_moves_when_a_response_does(
    artifacts: ShowcaseArtifacts, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A digest that did not change when the replay did would bind nothing."""
    before = response_set_digest(artifacts)

    original = report_module.materialise

    def tweaked(case, art):
        material = original(case, art)
        if material.response is None:
            return material
        response = json.loads(json.dumps(material.response))
        # Not every replayed response is a well-formed explanation — one case
        # exists precisely because a model can return valid JSON that is not one.
        if response.get("claims"):
            response["claims"][0]["text"] += " (tweaked)"
        else:
            response["explanation"] = "tweaked"
        return type(material)(
            case=material.case,
            bundle=material.bundle,
            response=response,
            expected_rule=material.expected_rule,
        )

    monkeypatch.setattr(report_module, "materialise", tweaked)
    assert response_set_digest(artifacts) != before


def test_failures_carry_no_model_prose(generated: tuple[dict, bytes]) -> None:
    """Diagnostics are built from validator details, which are bounded and short."""
    report, _ = generated
    for failure in report["failures"]:
        for detail in failure["details"]:
            assert len(detail) <= 160


def test_the_committed_artifact_is_what_the_command_produces(
    generated: tuple[dict, bytes],
) -> None:
    """"Regenerated, never edited" is checkable or it is a promise.

    This is the CI form of the modeling contract's condition 3: the diff is
    explainable as the bead's change because the file is not hand-writable.

    Skipped while the artifact is absent, which today means *untracked*:
    `.gitignore:3` is `artifacts/*` and the negation that would let this one
    file be committed is `scoutlens-iex.9`'s to add — `.gitignore` is Denied to
    the modeling track with no reviewer. The skip is deliberately narrow, so the
    day the file is tracked this starts guarding it without anyone remembering
    to re-enable it.
    """
    if not ARTIFACT_PATH.exists():
        pytest.skip(
            f"{ARTIFACT_PATH.name} is not present. Generate it with "
            "'python -m scoutlens.explanations.evals.run_report'; it becomes a tracked "
            "file under scoutlens-iex.9."
        )
    _, payload = generated
    assert ARTIFACT_PATH.read_bytes() == payload, (
        "the committed report differs from this command's output; regenerate it"
    )


def test_check_mode_writes_nothing(tmp_path: Path) -> None:
    target = tmp_path / "report.json"
    assert main(["--check", "--output", str(target)]) == EXIT_DRIFTED
    assert not target.exists()

    assert main(["--output", str(target)]) == EXIT_OK
    assert main(["--check", "--output", str(target)]) == EXIT_OK
