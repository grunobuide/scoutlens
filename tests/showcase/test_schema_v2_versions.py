"""The two frozen halves of `scoutlens.showcase/2.0.0` must agree on
`schema_version` (`scoutlens-qop.6.4.5`).

`qop.6.2` froze the v2 contract as a schema plus a validator. The schema pinned
`schema_version` to `"1.0.0"` on the catalog, index, profile and research
artifacts, while `validate_v2_bundle` required `"2.0.0"` on anything declaring
one. Both rules are reachable on every v2 bundle and `schema_version` is
`required`, so no v2 catalog, index, profile or research summary could be
published at all. `qop.6.4.2` found it by routing the first schema-complete
artifact through `major=2`.

The first test here is deliberately generic rather than four hard-coded
assertions: it catches the whole class, including any artifact type added to
either major later. A per-artifact assertion would have to be remembered; an
invariant over `$defs` cannot be forgotten.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scoutlens.showcase.export import (
    V1_SCHEMA_VERSION,
    V2_REPRESENTATION_PATH,
    V2_SCHEMA_VERSION,
    build_representation_artifact,
)
from scoutlens.showcase.representation import DIAGONAL_CONFIG_PATH, load_representation
from scoutlens.showcase.schema import showcase_schema, validate_schema
from scoutlens.showcase.validation import validate_v2_bundle

REPO_ROOT = Path(__file__).resolve().parents[2]
PUBLISHED_V1 = REPO_ROOT / "public" / "showcase" / "v1"
V2_DATASET_VERSION = "wyscout-2017-18-v2-0123456789ab"
REPRESENTATION_ID = "rep-f018e6041ccbad10"

#: The artifact types whose v2 shape differs from v1 only by the two version
#: strings. Proven below rather than assumed.
VERSION_ONLY_TYPES = {
    "feature-catalog.json": "feature_catalog_artifact",
    "players.index.json": "player_index_artifact",
    "research-summary.json": "research_summary_artifact",
}


def _artifact_defs(major: int) -> dict[str, dict]:
    """Every `$defs` entry that is a whole published artifact, keyed by name.

    An artifact type is exactly one that declares a `schema_version`; the
    fragment types (`evidence_item`, `uncertainty_block`, …) do not.
    """
    defs = showcase_schema(major)["$defs"]
    return {
        name: body
        for name, body in defs.items()
        if isinstance(body, dict) and "schema_version" in body.get("properties", {})
    }


def test_every_v2_artifact_type_declares_the_v2_schema_version() -> None:
    """A v2 artifact pinned to `1.0.0` is unpublishable: the validator rejects
    it, and a consumer reading that field would route a diagonal payload to the
    cosine schema."""
    declared = {
        name: body["properties"]["schema_version"].get("const")
        for name, body in _artifact_defs(2).items()
    }
    assert declared, "the v2 schema declares no artifact types"
    assert set(declared.values()) == {V2_SCHEMA_VERSION}, declared


def test_every_v1_artifact_type_still_declares_the_v1_schema_version() -> None:
    """v1 is frozen and immutable; correcting v2 must not have touched it."""
    declared = {
        name: body["properties"]["schema_version"].get("const")
        for name, body in _artifact_defs(1).items()
    }
    assert declared
    assert set(declared.values()) == {V1_SCHEMA_VERSION}, declared


def test_the_two_majors_disagree_only_where_they_are_meant_to() -> None:
    """The three version-only artifact types are byte-identical between majors
    apart from `schema_version` and the `dataset_version` `$ref`.

    This is what licenses the lift used by the tests below: bumping two strings
    is provably the whole delta, not a hopeful minimum.
    """
    v1_defs = showcase_schema(1)["$defs"]
    v2_defs = showcase_schema(2)["$defs"]
    for name in VERSION_ONLY_TYPES.values():
        first = json.loads(json.dumps(v1_defs[name], sort_keys=True))
        second = json.loads(json.dumps(v2_defs[name], sort_keys=True))
        first["properties"].pop("schema_version")
        second["properties"].pop("schema_version")
        assert first == second, name


# --- Real published content, lifted --------------------------------------


def _lift(name: str) -> dict:
    """A real published v1 artifact restamped as v2.

    Real content rather than a hand-authored fixture: a fixture written to pass
    a schema proves the fixture, not the schema.
    """
    artifact = json.loads((PUBLISHED_V1 / name).read_text(encoding="utf-8"))
    artifact["schema_version"] = V2_SCHEMA_VERSION
    artifact["dataset_version"] = V2_DATASET_VERSION
    return artifact


@pytest.mark.parametrize("name", sorted(VERSION_ONLY_TYPES))
def test_a_real_artifact_restamped_as_v2_validates(name: str) -> None:
    validate_schema(_lift(name), label=name, major=2)


@pytest.mark.parametrize("name", sorted(VERSION_ONLY_TYPES))
def test_the_same_artifact_stamped_with_the_v1_version_is_rejected(name: str) -> None:
    """The fail-closed direction, and the one the frozen schema had inverted."""
    artifact = _lift(name)
    artifact["schema_version"] = V1_SCHEMA_VERSION
    with pytest.raises(ValueError, match="JSON Schema violation"):
        validate_schema(artifact, label=name, major=2)


@pytest.mark.parametrize("name", sorted(VERSION_ONLY_TYPES))
def test_the_v1_artifact_is_still_valid_under_v1(name: str) -> None:
    artifact = json.loads((PUBLISHED_V1 / name).read_text(encoding="utf-8"))
    validate_schema(artifact, label=name, major=1)


# --- Through the validator that disagreed --------------------------------


@pytest.fixture(scope="module")
def representation_artifact() -> dict:
    training = json.loads(DIAGONAL_CONFIG_PATH.read_text(encoding="utf-8"))["representation"][
        "training"
    ]
    return build_representation_artifact(load_representation(), V2_DATASET_VERSION, training)


def _lifted_manifest(representation_artifact: dict) -> dict:
    """The real published manifest restamped as v2 and made to hash the
    representation, which v2 requires."""
    manifest = json.loads((PUBLISHED_V1 / "manifest.json").read_text(encoding="utf-8"))
    manifest["schema_version"] = V2_SCHEMA_VERSION
    manifest["dataset_version"] = V2_DATASET_VERSION
    manifest["representation_id"] = REPRESENTATION_ID
    payload = json.dumps(representation_artifact, sort_keys=True).encode("utf-8")
    manifest["files"] = [
        *manifest["files"],
        {
            "path": V2_REPRESENTATION_PATH,
            "bytes": len(payload),
            "media_type": "application/json",
            "records": 1,
            "sha256": hashlib.sha256(payload).hexdigest(),
        },
    ]
    return manifest


def test_a_bundle_of_real_restamped_artifacts_passes_the_v2_validator(
    representation_artifact: dict,
) -> None:
    """`validate_v2_bundle` schema-validates every artifact at `major=2` and
    separately requires `schema_version == 2.0.0`. Before `qop.6.4.5` those two
    rules could not both hold, so this bundle was unpublishable."""
    bundle = {
        V2_REPRESENTATION_PATH: representation_artifact,
        "manifest.json": _lifted_manifest(representation_artifact),
        **{name: _lift(name) for name in VERSION_ONLY_TYPES},
    }
    assert validate_v2_bundle(bundle) == REPRESENTATION_ID


def test_one_artifact_left_at_the_v1_version_fails_the_bundle(
    representation_artifact: dict,
) -> None:
    bundle = {
        V2_REPRESENTATION_PATH: representation_artifact,
        "manifest.json": _lifted_manifest(representation_artifact),
        **{name: _lift(name) for name in VERSION_ONLY_TYPES},
    }
    bundle["feature-catalog.json"]["schema_version"] = V1_SCHEMA_VERSION
    with pytest.raises(ValueError, match="feature-catalog.json"):
        validate_v2_bundle(bundle)
