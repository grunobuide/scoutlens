"""Showcase-v2 exporter integration (`scoutlens-qop.6.4.2`).

Bounded fixtures only: this leaf must make every semantic failure reproducible
without a production export. The tamper tests are the point — a validator that
has never been shown to reject is a validator nobody has tested.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scoutlens.showcase.export import (
    SUPPORTED_SCHEMA_VERSIONS,
    V1_SCHEMA_VERSION,
    V2_REPRESENTATION_PATH,
    V2_SCHEMA_VERSION,
    build_representation_artifact,
    export_showcase,
)
from scoutlens.showcase.representation import DIAGONAL_CONFIG_PATH, load_representation
from scoutlens.showcase.validation import (
    validate_v2_bundle,
    validate_v2_representation_binding,
    validate_v2_weighted_evidence,
)

REPRESENTATION_ID = "rep-f018e6041ccbad10"


@pytest.fixture(scope="module")
def representation():
    return load_representation()


@pytest.fixture(scope="module")
def training() -> dict:
    return json.loads(DIAGONAL_CONFIG_PATH.read_text(encoding="utf-8"))["representation"]["training"]


@pytest.fixture
def artifact(representation, training) -> dict:
    return build_representation_artifact(
        representation, "wyscout-2017-18-v2-0123456789ab", training
    )


BASE_FILES = (
    "feature-catalog.json",
    "players.index.json",
    "research-summary.json",
    "players/wy-1-c-2.json",
)


def _v2_manifest(*, files: list[str]) -> dict:
    """A schema-valid v2 manifest, so the manifest rules can be exercised
    through validate_v2_bundle itself rather than asserted around it.

    The schema requires at least four hashed files, so the standard dataset
    files are always present and `files` names anything additional.
    """
    return {
        "contract": "scoutlens.showcase",
        "schema_version": V2_SCHEMA_VERSION,
        "dataset_version": "wyscout-2017-18-v2-0123456789ab",
        "representation_id": REPRESENTATION_ID,
        "generated_at": "2026-08-12T00:00:00+00:00",
        "featured_profile": {
            "profile_key": "wy-1-c-2",
            "editorial": True,
            "reason": "fixture",
        },
        "source": {
            "provider": "wyscout_pappalardo",
            "season": "2017/18",
            "title": "Soccer match event dataset",
            "citation": "Pappalardo et al. (2019).",
            "source_url": "https://doi.org/10.6084/m9.figshare.c.4415000.v5",
            "licence": "CC BY 4.0",
            "licence_url": "https://creativecommons.org/licenses/by/4.0/",
            "redistribution_note": "Aggregates only.",
        },
        "population": {
            "analytical_unit": "player_competition",
            "chronological_periods": ["a", "b"],
            "domestic_competition_ids": [364],
            "minutes_threshold_per_period": 450,
            "profile_count": 1257,
            "feature_count": 32,
        },
        "producer": {
            "git_commit": "0" * 40,
            "git_dirty": False,
            "source_sha256": "0" * 64,
            "config_path": "config/experiment.json",
            "config_sha256": "0" * 64,
            "python_version": "3.14.4",
            "polars_version": "1.42.1",
        },
        "inputs": [
            {"logical_name": "processed/events.parquet", "sha256": "0" * 64, "bytes": 1, "public": False}
        ],
        "files": [
            {
                "path": path,
                "media_type": "application/json",
                "sha256": "0" * 64,
                "bytes": 1,
                "records": 1,
            }
            for path in [*BASE_FILES, *files]
        ],
    }


# --- AC1: dispatch --------------------------------------------------------


def test_both_majors_are_dispatchable() -> None:
    assert SUPPORTED_SCHEMA_VERSIONS == (V1_SCHEMA_VERSION, V2_SCHEMA_VERSION)


def test_an_unsupported_schema_version_is_rejected(tmp_path) -> None:
    with pytest.raises(ValueError, match="unsupported schema version"):
        export_showcase(schema_version="3.0.0", output_dir=tmp_path)


def test_v2_requires_a_representation_artifact(tmp_path) -> None:
    """A v2 bundle that cannot name the representation that produced its
    rankings is unpublishable."""
    with pytest.raises(ValueError, match="requires --representation-artifact"):
        export_showcase(schema_version=V2_SCHEMA_VERSION, output_dir=tmp_path)


def test_v2_refuses_the_default_cosine_bootstrap_directory(tmp_path) -> None:
    """The v1 run describes cosine rank stability; it cannot describe a
    diagonal ranking."""
    with pytest.raises(ValueError, match="requires --bootstrap-run-dir"):
        export_showcase(
            schema_version=V2_SCHEMA_VERSION,
            representation_artifact=Path("artifacts/benchmark/diagonal-results.json"),
            output_dir=tmp_path,
        )


# --- AC2: the assembled representation artifact ---------------------------


def test_the_representation_artifact_is_contract_shaped(artifact) -> None:
    assert artifact["schema_version"] == V2_SCHEMA_VERSION
    representation = artifact["representation"]
    assert representation["id"] == REPRESENTATION_ID
    assert representation["ranking_method"] == "weighted_cosine_diagonal_v1"
    assert representation["uncertainty_design"] == "match_bootstrap_diagonal_v1"
    assert representation["feature_count"] == 28
    assert len(representation["weights"]) == 28


def test_the_assembled_weights_are_in_feature_order(artifact) -> None:
    representation = artifact["representation"]
    declared = [entry["feature_id"] for entry in representation["weights"]]
    assert declared == representation["feature_order"]


def test_the_assembled_artifact_passes_its_own_validator(artifact) -> None:
    bundle = {V2_REPRESENTATION_PATH: artifact}
    assert validate_v2_bundle(bundle) == REPRESENTATION_ID


def test_the_artifact_retains_cosine_as_the_audit_baseline(artifact) -> None:
    audit = artifact["representation"]["audit_baseline"]
    assert audit["method"] == "cosine_v1"
    assert audit["contract"] == "scoutlens.showcase/1.0.0"


def test_the_artifact_declares_prohibited_claims(artifact) -> None:
    claims = " ".join(artifact["representation"]["prohibited_claims"]).lower()
    assert "causal" in claims
    assert "recruitment" in claims


def test_lineage_cites_the_authorizing_decisions(artifact) -> None:
    records = artifact["representation"]["lineage"]["decision_records"]
    for record in ("D042", "D044", "D045"):
        assert record in records


# --- AC4: fail-closed tampering -------------------------------------------


def test_a_one_weight_tamper_is_rejected(artifact) -> None:
    artifact["representation"]["weights"][7]["weight"] += 1e-6
    with pytest.raises(ValueError, match="weight_digest"):
        validate_v2_bundle({V2_REPRESENTATION_PATH: artifact})


def test_a_reordered_weight_list_is_rejected(artifact) -> None:
    weights = artifact["representation"]["weights"]
    weights[0], weights[1] = weights[1], weights[0]
    with pytest.raises(ValueError, match="weight_digest|not in feature_order"):
        validate_v2_bundle({V2_REPRESENTATION_PATH: artifact})


def test_a_wrong_scorer_is_rejected(artifact) -> None:
    artifact["representation"]["ranking_method"] = "cosine_v1"
    with pytest.raises(ValueError, match="JSON Schema violation|ranking_method"):
        validate_v2_bundle({V2_REPRESENTATION_PATH: artifact})


def test_a_cosine_uncertainty_design_is_rejected(artifact) -> None:
    artifact["representation"]["uncertainty_design"] = "match_bootstrap_v1"
    with pytest.raises(ValueError, match="JSON Schema violation|uncertainty_design"):
        validate_v2_bundle({V2_REPRESENTATION_PATH: artifact})


def test_a_representation_id_mismatch_is_rejected(artifact) -> None:
    """Exercised through the binding rule validate_v2_bundle delegates to: a
    stub profile cannot pass full schema validation, and schema-complete
    profile fixtures are out of scope for this leaf."""
    bundle = {
        "manifest.json": {"representation_id": REPRESENTATION_ID},
        "players/wy-1-c-2.json": {
            "retrieval": {"global": {"representation_id": "rep-ffffffffffffffff"}}
        },
    }
    with pytest.raises(ValueError, match="representation_id mismatch"):
        validate_v2_representation_binding(bundle, REPRESENTATION_ID)


def test_a_manifest_that_does_not_hash_the_representation_is_rejected(artifact) -> None:
    """An unhashed representation could be swapped without detection."""
    bundle = {
        V2_REPRESENTATION_PATH: artifact,
        "manifest.json": _v2_manifest(files=[]),
    }
    with pytest.raises(ValueError, match="does not hash representation.json"):
        validate_v2_bundle(bundle)


def test_a_manifest_that_hashes_the_representation_is_accepted(artifact) -> None:
    bundle = {
        V2_REPRESENTATION_PATH: artifact,
        "manifest.json": _v2_manifest(files=[V2_REPRESENTATION_PATH]),
    }
    assert validate_v2_bundle(bundle) == REPRESENTATION_ID


def test_a_manifest_naming_a_different_representation_is_rejected(artifact) -> None:
    manifest = _v2_manifest(files=[V2_REPRESENTATION_PATH])
    manifest["representation_id"] = "rep-ffffffffffffffff"
    with pytest.raises(ValueError, match="does not match representation.json"):
        validate_v2_bundle({V2_REPRESENTATION_PATH: artifact, "manifest.json": manifest})


def test_a_weighted_contribution_mismatch_is_rejected() -> None:
    """Evidence that does not reconstruct the number it explains is not
    evidence. Exercised through the rule validate_v2_bundle delegates to."""
    profile = {
        "retrieval": {"global": {"representation_id": REPRESENTATION_ID, "similarity_score": 0.5}},
        "neighbors": [],
        "evidence_index": [
            {
                "subject": "self_retrieval",
                "kind": "feature_contribution",
                "representation_id": REPRESENTATION_ID,
                "weighted_contribution": 0.9,
            }
        ],
    }
    with pytest.raises(ValueError, match="does not reconstruct similarity_score"):
        validate_v2_weighted_evidence(profile, "players/wy-1-c-2.json")


def test_a_bundle_without_a_representation_is_rejected() -> None:
    with pytest.raises(ValueError, match="must publish representation.json"):
        validate_v2_bundle({"manifest.json": {"representation_id": REPRESENTATION_ID}})


# --- AC5/AC6: determinism and v1 compatibility ----------------------------


def test_assembly_is_deterministic(representation, training) -> None:
    first = build_representation_artifact(representation, "wyscout-2017-18-v2-0123456789ab", training)
    second = build_representation_artifact(representation, "wyscout-2017-18-v2-0123456789ab", training)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_assembly_is_not_hand_authored(representation, training, artifact) -> None:
    """Every weight must come from the verified representation, not a literal."""
    for entry in artifact["representation"]["weights"]:
        assert entry["weight"] == representation.weights_by_feature[entry["feature_id"]]
    assert artifact["representation"]["weight_digest"] == representation.weight_digest
    assert artifact["representation"]["feature_order_digest"] == representation.feature_order_digest


def test_v1_export_defaults_are_unchanged() -> None:
    """Omitting the new flags must preserve documented v1 behaviour, so the
    default schema version stays 1.0.0 and needs no representation."""
    import inspect

    signature = inspect.signature(export_showcase)
    assert signature.parameters["schema_version"].default == V1_SCHEMA_VERSION
    assert signature.parameters["representation_artifact"].default is None


# --- AC3: the uncertainty merge only accepts its own representation --------


def _run_metadata(tmp_path, **overrides):
    """A minimal bootstrap run.json good enough to reach the representation
    gate. The gate must fire before any parquet is read, so the summary files
    deliberately do not exist."""
    metadata = {
        "status": "available",
        "manifest": {
            "design_version": "match_bootstrap_diagonal_v1",
            "ranking_method": "weighted_cosine_diagonal_v1",
            "representation_id": REPRESENTATION_ID,
            "profile_count": 1257,
            **overrides,
        },
    }
    (tmp_path / "run.json").write_text(json.dumps(metadata), encoding="utf-8")
    return tmp_path


def test_a_cosine_scored_run_cannot_carry_a_diagonal_bundle(tmp_path, representation) -> None:
    """v1 intervals describe the sampling stability of cosine ranks; attaching
    them to diagonal rankings would show an interval that does not describe the
    number beside it."""
    from scoutlens.showcase.representation import DIAGONAL_CONFIG_PATH as config_path
    from scoutlens.showcase.uncertainty import load_bootstrap_summaries

    run_dir = _run_metadata(tmp_path, ranking_method="cosine_v1")
    with pytest.raises(ValueError, match="cosine uncertainty cannot describe a diagonal ranking"):
        load_bootstrap_summaries(run_dir, config_path, representation=representation)


def test_a_run_under_another_representation_is_refused(tmp_path, representation) -> None:
    from scoutlens.showcase.representation import DIAGONAL_CONFIG_PATH as config_path
    from scoutlens.showcase.uncertainty import load_bootstrap_summaries

    run_dir = _run_metadata(tmp_path, representation_id="rep-ffffffffffffffff")
    with pytest.raises(ValueError, match="computed under representation"):
        load_bootstrap_summaries(run_dir, config_path, representation=representation)


def test_a_run_with_no_representation_recorded_is_refused(tmp_path, representation) -> None:
    from scoutlens.showcase.representation import DIAGONAL_CONFIG_PATH as config_path
    from scoutlens.showcase.uncertainty import load_bootstrap_summaries

    metadata = {
        "status": "available",
        "manifest": {
            "design_version": "match_bootstrap_diagonal_v1",
            "ranking_method": "weighted_cosine_diagonal_v1",
            "profile_count": 1257,
        },
    }
    (tmp_path / "run.json").write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(ValueError, match="computed under representation"):
        load_bootstrap_summaries(tmp_path, config_path, representation=representation)


def test_the_v1_uncertainty_path_is_unchanged_by_the_gate(tmp_path) -> None:
    """With no representation the gate is inert: a v1 run reaches its usual
    failure (missing summary files), not a representation error."""
    from scoutlens.showcase.uncertainty import load_bootstrap_summaries
    from scoutlens.uncertainty.config import UNCERTAINTY_CONFIG_PATH

    metadata = {
        "status": "available",
        "manifest": {"design_version": "match_bootstrap_v1", "profile_count": 1257},
    }
    (tmp_path / "run.json").write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(Exception) as caught:
        load_bootstrap_summaries(tmp_path, UNCERTAINTY_CONFIG_PATH)
    assert "representation" not in str(caught.value).lower()
