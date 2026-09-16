"""The bundle derives, never authors, and refuses what it cannot ground."""

from __future__ import annotations

import copy
from typing import Any

import pytest
from conftest import requires_showcase, requires_v1

from scoutlens.explanations import BundleOptions, build_bundle, validate_bundle_schema
from scoutlens.explanations.bundle import BundleError, bundle_digest, classify_evidence
from scoutlens.explanations.policy import EvidenceStatus

pytestmark = requires_showcase


def test_the_bundle_matches_its_schema(bundle: dict[str, Any]) -> None:
    validate_bundle_schema(bundle)


def test_the_same_profile_produces_the_same_bundle(
    v2_profile: dict[str, Any], representation: dict[str, Any]
) -> None:
    """The digest is what pairs an output with its evidence; it has to be stable."""
    first = build_bundle(v2_profile, representation)
    second = build_bundle(copy.deepcopy(v2_profile), copy.deepcopy(representation))
    assert first["bundle_digest"] == second["bundle_digest"]
    assert first == second


def test_evidence_keeps_the_artifact_order(
    bundle: dict[str, Any], v2_profile: dict[str, Any]
) -> None:
    """Re-ranking evidence would silently change what "the top contribution" means."""
    published = [entry["evidence_id"] for entry in v2_profile["evidence_index"]]
    assert [row["evidence_id"] for row in bundle["evidence"]] == published
    assert bundle["allowed_evidence_ids"] == published


def test_the_taxonomy_separates_excluded_from_learned_zero(bundle: dict[str, Any]) -> None:
    """Both carry weight 0.0. Only feature_order tells them apart.

    This is the distinction the whole contract turns on, so it is asserted
    against the published artifact rather than against a constructed example:
    if a repin ever removed the split, this fails rather than quietly reducing
    the taxonomy to one case.
    """
    excluded = {row["feature_id"] for row in bundle["evidence"] if row["status"] == "excluded"}
    learned_zero = {row["feature_id"] for row in bundle["evidence"] if row["status"] == "learned_zero"}

    assert excluded, "no excluded features: the taxonomy has nothing to distinguish"
    assert learned_zero, "no learned-zero features: the taxonomy has nothing to distinguish"
    assert not (excluded & learned_zero), "a feature cannot be both"

    weights = {
        row["feature_weight"]
        for row in bundle["evidence"]
        if row["status"] in {"excluded", "learned_zero"}
    }
    assert weights == {0.0}, "the two statuses are only distinguishable because weight alone is not enough"


def test_family_rows_are_weighted_evidence_not_learned_zero(bundle: dict[str, Any]) -> None:
    """A family aggregate has a null feature_weight by design.

    Reading that null as "the fit gave it no weight" would attach a false
    statement about the model to 48 of the 240 rows.
    """
    families = [row for row in bundle["evidence"] if row["kind"] == "family_contribution"]
    assert families
    assert all(row["feature_weight"] is None for row in families)
    assert all(row["status"] == str(EvidenceStatus.WEIGHTED) for row in families)


def test_a_missing_measurement_is_unmeasured_whatever_its_weight() -> None:
    """An absence is neither similarity nor difference, so weight cannot rescue it."""
    entry = {
        "kind": "feature_contribution",
        "feature_id": "passes_p90",
        "feature_weight": 3.2,
        "query_global_z": None,
        "candidate_global_z": 0.4,
    }
    assert classify_evidence(entry, feature_order=frozenset({"passes_p90"})) is EvidenceStatus.UNMEASURED


def test_a_profile_missing_a_required_field_is_refused_not_patched(
    v2_profile: dict[str, Any], representation: dict[str, Any]
) -> None:
    """The stop condition: depend on the showcase workstream, never add a field."""
    broken = copy.deepcopy(v2_profile)
    del broken["evidence_index"]
    with pytest.raises(BundleError, match="evidence_index"):
        build_bundle(broken, representation)


def test_a_v1_profile_is_not_silently_upgraded(
    v1_profile: dict[str, Any], representation: dict[str, Any]
) -> None:
    with pytest.raises(BundleError, match="audit_baseline"):
        build_bundle(v1_profile, representation)


def test_a_v2_profile_is_not_silently_downgraded(
    v2_profile: dict[str, Any], representation: dict[str, Any]
) -> None:
    with pytest.raises(BundleError, match="audit_baseline bundles describe"):
        build_bundle(v2_profile, representation, options=BundleOptions(audit_baseline=True))


def test_a_v2_bundle_requires_the_representation(v2_profile: dict[str, Any]) -> None:
    with pytest.raises(BundleError, match="representation artifact"):
        build_bundle(v2_profile)


def test_a_profile_without_the_mandatory_caveats_is_refused(
    v2_profile: dict[str, Any], representation: dict[str, Any]
) -> None:
    """The contract never invents caveat copy to fill a gap."""
    broken = copy.deepcopy(v2_profile)
    broken["caveats"] = [c for c in broken["caveats"] if c["code"] != "same_season_team_confound"]
    with pytest.raises(BundleError, match="same_season_team_confound"):
        build_bundle(broken, representation)


def test_omitting_neighbours_drops_their_evidence(
    v2_profile: dict[str, Any], representation: dict[str, Any]
) -> None:
    self_only = build_bundle(
        v2_profile, representation, options=BundleOptions(include_neighbours=False)
    )
    validate_bundle_schema(self_only)
    assert self_only["neighbours"] == []
    assert not any(row["subject"].startswith("neighbor:") for row in self_only["evidence"])


@requires_v1
def test_the_audit_bundle_reports_the_cosine_method(audit_bundle: dict[str, Any]) -> None:
    """AC7: the explicit v1 path stays supported, and says so."""
    validate_bundle_schema(audit_bundle)
    assert audit_bundle["provenance"]["is_audit_baseline_bundle"] is True
    assert "cosine" in audit_bundle["provenance"]["ranking_method"]
    # v1 has no learned weights: unit weights reproduce cosine exactly (D045),
    # so there is no excluded/learned-zero split to draw.
    assert {row["status"] for row in audit_bundle["evidence"]} == {str(EvidenceStatus.WEIGHTED)}
    assert audit_bundle["retrieval"]["similarity_score"] is not None


def test_the_digest_ignores_only_itself(bundle: dict[str, Any]) -> None:
    recomputed = bundle_digest(bundle)
    assert recomputed == bundle["bundle_digest"]

    altered = copy.deepcopy(bundle)
    altered["evidence"][0]["weighted_contribution"] = 99.0
    assert bundle_digest(altered) != recomputed
