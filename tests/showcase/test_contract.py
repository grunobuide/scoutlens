import json
import math

import pytest
from jsonschema import Draft202012Validator

from scoutlens.features.aggregation import FEATURE_COLUMNS
from scoutlens.showcase.builder import _evidence_for_candidate
from scoutlens.showcase.catalog import CONTRACT, FEATURE_CATALOG, SCHEMA_VERSION
from scoutlens.showcase.io import canonical_content_digest, canonical_json_bytes
from scoutlens.showcase.schema import showcase_schema, showcase_validator, validate_schema

INTERVAL_FIELDS = (
    ("feature_uncertainty", "raw_ci_95"),
    ("feature_uncertainty", "within_role_percentile_ci_95"),
    ("rank_uncertainty", "rank_ci_95"),
    ("neighbor_stability", "rank_ci_95"),
    ("research_metric", "ci_95"),
)


def test_formal_schema_is_valid_and_accepts_catalog() -> None:
    showcase_validator()
    artifact = {
        "contract": CONTRACT,
        "schema_version": SCHEMA_VERSION,
        "dataset_version": "wyscout-2017-18-v1-0123456789ab",
        "features": FEATURE_CATALOG,
    }
    validate_schema(artifact, label="feature-catalog.json")


def test_formal_schema_rejects_unknown_contract_field() -> None:
    artifact = {
        "contract": CONTRACT,
        "schema_version": SCHEMA_VERSION,
        "dataset_version": "wyscout-2017-18-v1-0123456789ab",
        "features": FEATURE_CATALOG,
        "browser_computed_metric": 1,
    }
    with pytest.raises(ValueError, match="JSON Schema violation"):
        validate_schema(artifact, label="feature-catalog.json")


@pytest.mark.parametrize(("definition", "field"), INTERVAL_FIELDS)
@pytest.mark.parametrize("value", [None, [1.0, 2.0]])
def test_confidence_interval_fields_accept_null_or_two_bounds(
    definition: str,
    field: str,
    value: object,
) -> None:
    interval_schema = showcase_schema()["$defs"][definition]["properties"][field]
    Draft202012Validator.check_schema(interval_schema)
    assert not list(Draft202012Validator(interval_schema).iter_errors(value))


@pytest.mark.parametrize(("definition", "field"), INTERVAL_FIELDS)
@pytest.mark.parametrize("value", [[], [1.0], [1.0, 2.0, 3.0]])
def test_confidence_interval_fields_reject_non_pair_cardinality(
    definition: str,
    field: str,
    value: list[float],
) -> None:
    interval_schema = showcase_schema()["$defs"][definition]["properties"][field]
    assert list(Draft202012Validator(interval_schema).iter_errors(value))


def test_canonical_serialization_is_sorted_finite_utf8_with_newline() -> None:
    payload = canonical_json_bytes({"z": "Modrić", "a": 1})
    assert payload == '{"a":1,"z":"Modrić"}\n'.encode()
    assert json.loads(payload) == {"a": 1, "z": "Modrić"}
    with pytest.raises(ValueError):
        canonical_json_bytes({"bad": math.nan})


def test_content_digest_includes_paths_but_not_mapping_order() -> None:
    first = canonical_content_digest({"b.json": {"x": 1}, "a.json": {"x": 2}})
    second = canonical_content_digest({"a.json": {"x": 2}, "b.json": {"x": 1}})
    changed_path = canonical_content_digest({"a.json": {"x": 1}, "b.json": {"x": 2}})
    assert first == second
    assert first != changed_path


def test_additive_evidence_reconstructs_cosine_and_has_deterministic_order() -> None:
    query = {feature: 0.0 for feature in FEATURE_COLUMNS}
    candidate = {feature: 0.0 for feature in FEATURE_COLUMNS}
    query[FEATURE_COLUMNS[0]] = 2.0
    query[FEATURE_COLUMNS[1]] = -1.0
    candidate[FEATURE_COLUMNS[0]] = 3.0
    candidate[FEATURE_COLUMNS[1]] = 4.0

    cosine, similarity, evidence = _evidence_for_candidate("self_retrieval", "self", query, candidate)
    # With no representation the v1 path is unchanged, so the reported score is
    # the cosine itself and no weighted fields are emitted.
    assert similarity == cosine
    feature_rows = [item for item in evidence if item["kind"] == "feature_contribution"]
    family_rows = [item for item in evidence if item["kind"] == "family_contribution"]
    assert all("weighted_contribution" not in item for item in evidence)
    assert all("representation_id" not in item for item in evidence)

    assert len(feature_rows) == 32
    assert len(family_rows) == 8
    assert math.isclose(sum(item["contribution"] for item in feature_rows), cosine, abs_tol=1e-12)
    assert math.isclose(sum(item["contribution"] for item in family_rows), cosine, abs_tol=1e-12)
    assert feature_rows[0]["feature_id"] == FEATURE_COLUMNS[0]
    assert feature_rows[0]["interpretation"] == "alignment"
    assert feature_rows[1]["feature_id"] == FEATURE_COLUMNS[1]
    assert feature_rows[1]["interpretation"] == "disagreement"

