"""Showcase 2.0.0 contract tests (`scoutlens-qop.6.2`, D047).

Acceptance criterion 3 asks for a *focused* rejection test per rule, so each
test below breaks exactly one thing in an otherwise valid payload. A rule with
no failing test is a rule nobody has shown to be enforced.

Nothing here generates a public artifact; these exercise the contract only.
"""

from __future__ import annotations

import copy

import pytest

from scoutlens.benchmark.features import CANONICAL_28
from scoutlens.showcase.schema import (
    DEFAULT_MAJOR,
    SCHEMA_FILES,
    artifact_major,
    parse_major,
    showcase_schema,
    validate_schema,
)
from scoutlens.showcase.validation import (
    V2_RANKING_METHOD,
    V2_REPRESENTATION_PATH,
    V2_UNCERTAINTY_DESIGN,
    feature_order_digest,
    validate_representation_artifact,
    validate_v2_bundle,
    validate_v2_representation_binding,
    validate_v2_weighted_evidence,
    weight_digest,
)

REPRESENTATION_ID = "rep-0123456789abcdef"
HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64


def _representation() -> dict:
    features = list(CANONICAL_28)
    weights = [{"feature_id": name, "weight": 1.0 + index / 100} for index, name in enumerate(features)]
    representation = {
        "id": REPRESENTATION_ID,
        "ranking_method": V2_RANKING_METHOD,
        "weight_digest": weight_digest(weights),
        "feature_order": features,
        "feature_order_digest": feature_order_digest(features),
        "feature_count": 28,
        "weights": weights,
        "training": {
            "provider": "wyscout_pappalardo",
            "season": "2017/18",
            "split_digest": HASH_A,
            "split": "train",
            "population": {"players": 753, "minutes_threshold_per_period": 450},
        },
        "lineage": {
            "protocol_hash": HASH_B,
            "spec_hash": HASH_C,
            "decision_records": ["D042", "D044", "D045"],
        },
        "uncertainty_design": V2_UNCERTAINTY_DESIGN,
        "audit_baseline": {
            "method": "cosine_v1",
            "contract": "scoutlens.showcase/1.0.0",
            "note": "Frozen cosine remains the transparent audit baseline (D045).",
        },
        "prohibited_claims": [
            "no causal claim",
            "no recruitment or transfer-success claim",
        ],
    }
    return {
        "contract": "scoutlens.showcase",
        "schema_version": "2.0.0",
        "dataset_version": "wyscout-2017-18-v2-0123456789ab",
        "representation": representation,
    }


# --- the representation artifact ------------------------------------------


def test_a_well_formed_representation_validates_and_returns_its_id() -> None:
    assert validate_representation_artifact(_representation()) == REPRESENTATION_ID


def test_a_tampered_weight_is_rejected_by_the_weight_digest() -> None:
    artifact = _representation()
    artifact["representation"]["weights"][0]["weight"] += 0.5
    with pytest.raises(ValueError, match="weight_digest"):
        validate_representation_artifact(artifact)


def test_a_reordered_feature_list_is_rejected_by_the_order_digest() -> None:
    """The same weights in a different order describe a different metric."""
    artifact = _representation()
    order = artifact["representation"]["feature_order"]
    order[0], order[1] = order[1], order[0]
    with pytest.raises(ValueError, match="feature_order_digest"):
        validate_representation_artifact(artifact)


def test_weights_out_of_feature_order_are_rejected() -> None:
    artifact = _representation()
    weights = artifact["representation"]["weights"]
    weights[0], weights[1] = weights[1], weights[0]
    artifact["representation"]["weight_digest"] = weight_digest(weights)
    with pytest.raises(ValueError, match="not in feature_order"):
        validate_representation_artifact(artifact)


def test_an_unweighted_cosine_ranking_method_is_rejected() -> None:
    """v2 must not claim ordinary cosine for a weighted metric."""
    artifact = _representation()
    artifact["representation"]["ranking_method"] = "cosine_v1"
    with pytest.raises(ValueError, match="JSON Schema violation|ranking_method"):
        validate_representation_artifact(artifact)


def test_a_non_diagonal_uncertainty_design_is_rejected() -> None:
    artifact = _representation()
    artifact["representation"]["uncertainty_design"] = "match_bootstrap_v1"
    with pytest.raises(ValueError, match="JSON Schema violation|uncertainty_design"):
        validate_representation_artifact(artifact)


@pytest.mark.parametrize("field", ["protocol_hash", "spec_hash"])
def test_missing_lineage_is_rejected(field: str) -> None:
    artifact = _representation()
    del artifact["representation"]["lineage"][field]
    with pytest.raises(ValueError, match="JSON Schema violation"):
        validate_representation_artifact(artifact)


def test_missing_split_digest_is_rejected() -> None:
    artifact = _representation()
    del artifact["representation"]["training"]["split_digest"]
    with pytest.raises(ValueError, match="JSON Schema violation"):
        validate_representation_artifact(artifact)


def test_a_short_feature_set_is_rejected() -> None:
    artifact = _representation()
    artifact["representation"]["feature_order"] = list(CANONICAL_28)[:-1]
    with pytest.raises(ValueError, match="JSON Schema violation"):
        validate_representation_artifact(artifact)


def test_a_negative_weight_is_rejected() -> None:
    artifact = _representation()
    artifact["representation"]["weights"][0]["weight"] = -0.1
    with pytest.raises(ValueError, match="JSON Schema violation"):
        validate_representation_artifact(artifact)


def test_an_unknown_representation_field_is_rejected() -> None:
    """No optional-field workaround may let an ambiguous payload pass."""
    artifact = _representation()
    artifact["representation"]["extra"] = "unexpected"
    with pytest.raises(ValueError, match="JSON Schema violation"):
        validate_representation_artifact(artifact)


# --- representation binding across the dataset ----------------------------


def test_binding_accepts_a_dataset_that_agrees_on_one_representation() -> None:
    artifacts = {
        "manifest.json": {"representation_id": REPRESENTATION_ID},
        "players/a.json": {"retrieval": {"global": {"representation_id": REPRESENTATION_ID}}},
    }
    validate_v2_representation_binding(artifacts, REPRESENTATION_ID)


def test_binding_rejects_a_second_representation_id() -> None:
    artifacts = {
        "manifest.json": {"representation_id": REPRESENTATION_ID},
        "players/a.json": {"retrieval": {"global": {"representation_id": "rep-ffffffffffffffff"}}},
    }
    with pytest.raises(ValueError, match="representation_id mismatch"):
        validate_v2_representation_binding(artifacts, REPRESENTATION_ID)


def test_binding_rejects_a_dataset_that_names_no_representation() -> None:
    with pytest.raises(ValueError, match="no artifact references a representation_id"):
        validate_v2_representation_binding({"players/a.json": {"retrieval": {}}}, REPRESENTATION_ID)


def test_a_bundle_without_representation_json_is_rejected() -> None:
    assert V2_REPRESENTATION_PATH == "representation.json"
    with pytest.raises(ValueError, match="must publish representation.json"):
        validate_v2_bundle({"manifest.json": {"schema_version": "2.0.0"}})


# --- weighted evidence reconstruction -------------------------------------


def _profile(total: float) -> dict:
    return {
        "retrieval": {"global": {"similarity_score": 0.5}},
        "neighbors": [{"profile_key": "wy-1-c-2", "similarity_score": total}],
        "evidence_index": [
            {
                "subject": "neighbor:wy-1-c-2",
                "kind": "feature_contribution",
                "weighted_contribution": total / 2,
            },
            {
                "subject": "neighbor:wy-1-c-2",
                "kind": "feature_contribution",
                "weighted_contribution": total / 2,
            },
        ],
    }


def test_weighted_contributions_that_reconstruct_the_score_pass() -> None:
    validate_v2_weighted_evidence(_profile(0.8), "players/a.json")


def test_weighted_contributions_that_do_not_reconstruct_the_score_are_rejected() -> None:
    profile = _profile(0.8)
    profile["evidence_index"][0]["weighted_contribution"] += 0.01
    with pytest.raises(ValueError, match="does not reconstruct similarity_score"):
        validate_v2_weighted_evidence(profile, "players/a.json")


def test_evidence_for_an_unknown_neighbor_is_rejected() -> None:
    profile = _profile(0.8)
    # Move the whole subject group, so the unknown neighbour is the only thing
    # wrong — otherwise the reconstruction rule fires first and this test would
    # pass for the wrong reason.
    for item in profile["evidence_index"]:
        item["subject"] = "neighbor:wy-999-c-999"
    with pytest.raises(ValueError, match="unknown neighbor"):
        validate_v2_weighted_evidence(profile, "players/a.json")


# --- major-version selection and compatibility ----------------------------


def test_both_known_majors_are_available() -> None:
    assert sorted(SCHEMA_FILES) == [1, 2]
    assert showcase_schema(1)["$id"].endswith("showcase-1.0.0.schema.json")
    assert showcase_schema(2)["$id"].endswith("showcase-2.0.0.schema.json")


def test_an_unknown_major_fails_closed_rather_than_using_the_newest() -> None:
    with pytest.raises(ValueError, match="unsupported showcase schema major"):
        showcase_schema(3)


def test_major_is_parsed_from_the_declared_version() -> None:
    assert parse_major("1.0.0") == 1
    assert parse_major("2.0.0") == 2
    assert parse_major("2.4.1") == 2


def test_an_unparseable_version_is_not_a_version() -> None:
    with pytest.raises(ValueError, match="unparseable schema_version"):
        parse_major("latest")


def test_an_artifact_without_a_declared_version_keeps_v1_behaviour() -> None:
    assert artifact_major({"contract": "scoutlens.showcase"}) == DEFAULT_MAJOR
    assert DEFAULT_MAJOR == 1


def test_v1_validation_still_defaults_to_the_v1_schema() -> None:
    """AC4: v1 behaviour is unchanged. A v1 manifest must still validate with
    no major argument, and a v2 artifact must not pass as v1."""
    representation = _representation()
    with pytest.raises(ValueError, match="JSON Schema violation"):
        validate_schema(representation, label="representation.json")


def test_the_v1_schema_is_untouched_by_v2() -> None:
    v1 = showcase_schema(1)
    assert v1["$defs"]["manifest"]["properties"]["schema_version"] == {"const": "1.0.0"}
    assert "representation" not in v1["$defs"]
    assert "similarity_score" not in v1["$defs"]["retrieval_outcome"]["properties"]
    assert "cosine_similarity" in v1["$defs"]["retrieval_outcome"]["properties"]


def test_v2_renames_cosine_similarity_to_a_neutral_score() -> None:
    """A weighted metric must not be published under a name that claims plain
    cosine."""
    v2 = showcase_schema(2)
    for name in ("retrieval_outcome", "statistical_neighbor"):
        properties = v2["$defs"][name]["properties"]
        assert "similarity_score" in properties
        assert "cosine_similarity" not in properties


def test_v2_requires_a_representation_id_on_every_ranking_block() -> None:
    v2 = showcase_schema(2)
    for name in (
        "retrieval_outcome",
        "statistical_neighbor",
        "evidence_item",
        "uncertainty_block",
        "rank_uncertainty",
        "neighbor_stability",
    ):
        assert "representation_id" in v2["$defs"][name]["required"], name


def test_v2_manifest_requires_the_representation_id() -> None:
    v2 = showcase_schema(2)
    assert "representation_id" in v2["$defs"]["manifest"]["required"]


def test_deep_copy_of_a_valid_payload_still_validates() -> None:
    """Guards against accidental mutation by the validator itself."""
    artifact = _representation()
    snapshot = copy.deepcopy(artifact)
    validate_representation_artifact(artifact)
    assert artifact == snapshot
