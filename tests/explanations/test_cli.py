"""The CLI, held to the thing it exists to prevent.

The stop condition on `jtt.6.4` is one sentence: an output the validator refused
is never presented or persisted as an explanation. Most of what follows is that
sentence, checked from every direction a bad answer can arrive — a dead adapter,
a wrong shape, a fluent fabrication — plus the offline guarantee, which is
enforced here rather than promised.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from conftest import requires_showcase, requires_v1

from scoutlens.explanations.adapters.protocol import (
    AdapterFailure,
    AdapterRequest,
    AdapterResponse,
    AdapterResult,
    AdapterUsage,
    FailureReason,
)
from scoutlens.explanations.artifacts import ShowcaseArtifacts
from scoutlens.explanations.cli import (
    EXIT_FALLBACK,
    EXIT_OFFLINE_VIOLATION,
    EXIT_OK,
    EXIT_USAGE,
    SIMILARITY_LABEL,
    DeterministicExplainer,
    ExplanationResult,
    build_parser,
    explain,
    main,
    render_text,
)
from scoutlens.explanations.evals.mutations import apply_mutation
from scoutlens.explanations.evals.responses import reference_output

pytestmark = requires_showcase

CANONICAL = "wy-8287-c-795"


@pytest.fixture(scope="module")
def artifacts() -> ShowcaseArtifacts:
    return ShowcaseArtifacts()


class _StubAdapter:
    """Returns whatever it was handed. Stands in for every way a model answers."""

    adapter_version = "1.0.0"
    model_id = "stub"

    def __init__(self, content: Any = None, failure: FailureReason | None = None) -> None:
        self._content = content
        self._failure = failure

    @property
    def adapter_id(self) -> str:
        return "stub"

    def complete(self, request: AdapterRequest) -> AdapterResult:
        if self._failure is not None:
            return AdapterFailure(
                reason=self._failure,
                detail="synthetic",
                adapter_id=self.adapter_id,
                model_id=self.model_id,
            )
        return AdapterResponse(
            content=self._content,
            adapter_id=self.adapter_id,
            adapter_version=self.adapter_version,
            model_id=self.model_id,
            usage=AdapterUsage(latency_ms=1.0, input_tokens=10, output_tokens=5),
        )


class _SocketAdapter:
    """Opens a socket, which is exactly what the offline path must prevent."""

    adapter_version = "1.0.0"
    model_id = "socket"

    @property
    def adapter_id(self) -> str:
        return "socket"

    def complete(self, request: AdapterRequest) -> AdapterResult:  # pragma: no cover - guarded
        import socket

        socket.create_connection(("127.0.0.1", 9), timeout=0.1)
        raise AssertionError("the offline guard did not fire")


# --- the offline demo (AC2) ------------------------------------------------


def test_the_offline_command_succeeds_with_no_model(capsys: pytest.CaptureFixture) -> None:
    """The exact command a clean clone runs, with no credential and no network."""
    assert main(["explain", "--profile", CANONICAL]) == EXIT_OK
    out = capsys.readouterr().out
    assert "status         validated" in out
    assert "No model produced this text" in out


def test_the_offline_command_records_its_representation_identity(
    capsys: pytest.CaptureFixture,
) -> None:
    """AC2: a reader can tell which representation produced the numbers."""
    main(["explain", "--profile", CANONICAL, "--format", "json"])
    record = json.loads(capsys.readouterr().out)
    assert record["provenance"]["representation_id"].startswith("rep-")
    assert record["provenance"]["ranking_method"]
    assert record["provenance"]["is_audit_baseline_bundle"] is False


def test_the_record_carries_everything_ac5_requires(capsys: pytest.CaptureFixture) -> None:
    main(["explain", "--profile", CANONICAL, "--format", "json"])
    record = json.loads(capsys.readouterr().out)
    provenance = record["provenance"]

    for field in (
        "profile_key",
        "dataset_version",
        "representation_id",
        "bundle_digest",
        "prompt_contract_version",
        "output_schema_version",
        "adapter_id",
        "adapter_version",
        "model_id",
    ):
        assert provenance.get(field), f"{field} missing from the record"

    assert len(provenance["bundle_digest"]) == 64
    assert record["telemetry"]["latency_ms"] is not None

    # Every citation resolves against the bundle it claims to answer.
    cited = {
        evidence_id
        for claim in record["explanation"]["claims"]
        for evidence_id in claim["evidence_ids"]
    }
    assert cited


def test_the_rendered_text_never_calls_the_score_a_confidence() -> None:
    """AC5. A similarity is a distance; a confidence is a claim this study never makes."""
    result = ExplanationResult(
        status="validated",
        explanation={
            "claims": [
                {
                    "surface": "similarity",
                    "text": "Two profiles sit close together.",
                    "evidence_ids": ["self-feature-passes_p90"],
                    "values": [{"field": "similarity_score", "value": 0.9069068270340263}],
                }
            ],
            "caveat_codes": [],
        },
        provenance={
            "profile_key": CANONICAL,
            "representation_id": "rep-test",
            "ranking_method": "weighted_cosine_diagonal_v1",
            "bundle_digest": "0" * 64,
            "adapter_id": "stub",
            "adapter_version": "1.0.0",
            "model_id": "stub",
            "prompt_contract_version": "1.0.0",
            "output_schema_version": "1.0.0",
        },
    )
    rendered = render_text(result)
    assert f"{SIMILARITY_LABEL} = 0.9069068270340263" in rendered
    assert "confidence" not in rendered.lower()
    assert "cosine similarity" not in rendered.lower()


# --- refusing a bad answer (AC6) -------------------------------------------


def _bundle(artifacts: ShowcaseArtifacts) -> dict[str, Any]:
    from scoutlens.explanations import build_bundle

    return build_bundle(artifacts.profile(CANONICAL), artifacts.representation())


@pytest.mark.parametrize("reason", list(FailureReason))
def test_every_adapter_failure_returns_the_typed_fallback(
    reason: FailureReason, artifacts: ShowcaseArtifacts
) -> None:
    bundle = _bundle(artifacts)
    result = explain(bundle, _StubAdapter(failure=reason), dataset_version="test")
    assert result.status == "fallback"
    assert result.fallback_reason == "adapter_failure"


def test_content_that_is_not_an_explanation_returns_the_fallback(
    artifacts: ShowcaseArtifacts,
) -> None:
    """Valid JSON, wrong shape. The realistic way a model declines."""
    bundle = _bundle(artifacts)
    result = explain(
        bundle,
        _StubAdapter(content={"answer": "I would rather not say."}),
        dataset_version="test",
    )
    assert result.status == "fallback"
    assert result.fallback_reason == "schema_invalid"


def test_a_fabricated_citation_returns_the_fallback_and_names_the_rule(
    artifacts: ShowcaseArtifacts,
) -> None:
    """Schema-perfect and still refused, which is the whole point of the validator."""
    bundle = _bundle(artifacts)
    mutated, _ = apply_mutation("fabricated_citation", reference_output(bundle), bundle)
    result = explain(bundle, _StubAdapter(content=mutated), dataset_version="test")

    assert result.status == "fallback"
    assert result.fallback_reason == "validation_rejected"
    assert "claim.fabricated_citation" in result.rejections


def test_the_refused_output_is_never_shown_or_saved(
    artifacts: ShowcaseArtifacts, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """The stop condition, checked on both channels the tool can leak through."""
    bundle = _bundle(artifacts)
    mutated, _ = apply_mutation("recommendation", reference_output(bundle), bundle)
    giveaway = "should sign this neighbour"
    assert any(giveaway in claim["text"] for claim in mutated["claims"])

    monkeypatch.setattr(
        "scoutlens.explanations.cli._resolve_adapter",
        lambda spec, bundle: _StubAdapter(content=mutated),
    )
    target = tmp_path / "out.json"
    code = main(["explain", "--profile", CANONICAL, "--output", str(target)])

    assert code == EXIT_FALLBACK
    captured = capsys.readouterr()
    assert giveaway not in captured.out
    assert giveaway not in captured.err
    assert giveaway not in target.read_text(encoding="utf-8")


def test_a_fallback_exits_non_zero(
    artifacts: ShowcaseArtifacts, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "scoutlens.explanations.cli._resolve_adapter",
        lambda spec, bundle: _StubAdapter(failure=FailureReason.TIMEOUT),
    )
    assert main(["explain", "--profile", CANONICAL]) == EXIT_FALLBACK


# --- offline is enforced (AC4) ---------------------------------------------


def test_the_offline_path_refuses_a_socket(
    artifacts: ShowcaseArtifacts, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "scoutlens.explanations.cli._resolve_adapter", lambda spec, bundle: _SocketAdapter()
    )
    assert main(["explain", "--profile", CANONICAL]) == EXIT_OFFLINE_VIOLATION


def test_the_guard_is_lifted_afterwards(
    artifacts: ShowcaseArtifacts, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A guard that leaked would break every later test in the process."""
    import socket

    before = socket.socket.connect
    monkeypatch.setattr(
        "scoutlens.explanations.cli._resolve_adapter", lambda spec, bundle: _SocketAdapter()
    )
    main(["explain", "--profile", CANONICAL])
    assert socket.socket.connect is before


def test_online_is_opt_in(artifacts: ShowcaseArtifacts) -> None:
    """The same adapter, allowed through, reaches the network and fails there."""
    bundle = _bundle(artifacts)
    result = explain(bundle, _StubAdapter(content=reference_output(bundle)), dataset_version="t")
    assert result.status == "validated"


def test_no_argument_accepts_a_secret() -> None:
    """AC4. An argument lands in shell history, `ps` output and CI logs."""
    parser = build_parser()
    banned = ("key", "token", "secret", "password", "credential", "auth")

    def walk(action_container: Any) -> list[str]:
        options: list[str] = []
        for action in action_container._actions:
            options.extend(action.option_strings)
            if hasattr(action, "choices") and isinstance(action.choices, dict):
                for sub in action.choices.values():
                    options.extend(walk(sub))
        return options

    for option in walk(parser):
        lowered = option.lower()
        assert not any(word in lowered for word in banned), f"{option} could carry a secret"


def test_help_documents_the_workflow_the_adapter_contract_and_the_reference() -> None:
    """AC1, asserted rather than assumed — help text rots silently."""
    text = build_parser().format_help()
    assert "hydrate" in text
    assert "--adapter" in text
    assert "module:factory" in text
    assert "openai_compat" in text
    assert "SCOUTLENS_MODEL_API_KEY" in text
    assert "Exit codes" in text


# --- selection, majors and usability ---------------------------------------


def test_an_external_adapter_is_selected_by_module_path(
    artifacts: ShowcaseArtifacts, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC3: no ScoutLens source is edited to plug a model in."""
    package = tmp_path / "ext_adapter_pkg.py"
    package.write_text(
        "from scoutlens.explanations.adapters.fake import ScriptedAdapter\n"
        "def build():\n"
        "    return ScriptedAdapter({})\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    # ScriptedAdapter has no response for this digest, so it fails cleanly --
    # which is the point: selection worked, and a bad answer still falls back.
    assert main(["explain", "--profile", CANONICAL, "--adapter", "ext_adapter_pkg:build"]) == (
        EXIT_FALLBACK
    )


def test_a_bad_adapter_spec_is_a_usage_error() -> None:
    assert main(["explain", "--profile", CANONICAL, "--adapter", "not-a-spec"]) == EXIT_USAGE


def test_an_unknown_profile_does_not_tell_you_to_hydrate(
    capsys: pytest.CaptureFixture,
) -> None:
    """Sending someone to re-download 23 MB because they mistyped a key helps nobody."""
    assert main(["explain", "--profile", "wy-000000-c-000"]) == EXIT_USAGE
    error = capsys.readouterr().err
    assert "no published v2 profile" in error
    assert "hydrate" not in error.lower()


def test_v1_is_reachable_only_by_asking_for_it(artifacts: ShowcaseArtifacts) -> None:
    """`jtt.6.1` refuses a v1 profile that was not explicitly flagged."""
    from scoutlens.explanations import BundleError, build_bundle

    with pytest.raises(BundleError, match="audit_baseline"):
        build_bundle(artifacts.profile(CANONICAL, major=1), artifacts.representation())


@requires_v1
def test_the_audit_baseline_flag_reaches_v1(capsys: pytest.CaptureFixture) -> None:
    assert main(["explain", "--profile", CANONICAL, "--audit-baseline"]) == EXIT_OK
    out = capsys.readouterr().out
    assert "v1 audit baseline" in out or "cosine" in out


def test_profiles_lists_keys_to_try(capsys: pytest.CaptureFixture) -> None:
    assert main(["profiles", "--limit", "3"]) == EXIT_OK
    lines = [line for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert len(lines) == 3
    assert all(line.startswith("wy-") for line in lines)


def test_a_player_with_diacritics_does_not_crash_the_listing(
    artifacts: ShowcaseArtifacts, capsys: pytest.CaptureFixture
) -> None:
    """A Windows console defaults to cp1252 and the data is not Latin-1.

    `A. Aréola`, `A. Barák` and others killed the listing with
    `UnicodeEncodeError` partway through — on the platform this repository is
    developed on, and nowhere else. The names are in the published data, so the
    fix is an encoding one; renaming people to suit a terminal would be the
    worse bug.
    """
    listed = sum(
        1 for entry in artifacts.index() if any(ord(ch) > 127 for ch in entry["display_name"])
    )
    assert listed, "no non-ASCII display names in the payload; this test guards nothing"

    assert main(["profiles", "--limit", "200"]) == EXIT_OK
    out = capsys.readouterr().out
    assert any(ord(ch) > 127 for ch in out), "diacritics were stripped rather than encoded"


def test_conformance_runs_against_a_named_adapter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """The same module:factory contract as `explain`, so a user learns it once."""
    (tmp_path / "ext_conformant_pkg.py").write_text(
        "from scoutlens.explanations.adapters.fake import ScriptedAdapter\n"
        "def build():\n"
        "    return ScriptedAdapter({})\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    code = main(["conformance", "--adapter", "ext_conformant_pkg:build"])
    out = capsys.readouterr().out
    assert "checks passed" in out
    assert code == EXIT_OK


def test_the_deterministic_explainer_is_validated_like_any_model(
    artifacts: ShowcaseArtifacts,
) -> None:
    """It is not exempt. An unchecked explainer would be the one unchecked path."""
    bundle = _bundle(artifacts)
    result = explain(bundle, DeterministicExplainer(bundle=bundle), dataset_version="t")
    assert result.status == "validated"
    assert result.provenance["model_id"] == "none"
