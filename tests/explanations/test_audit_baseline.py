"""AC7: the same sentence is legitimate under v1 and forbidden under v2.

The cosine term is the audit baseline `D045` preserved, so an explanation *of
the baseline* may cite it as the score. The identical citation in a diagonal
bundle is the confusion `D047` and `D049` renamed the published method to stop.

Asserting both directions is the point. A rule that only ever rejects could be
rejecting everything, and a contract that cannot express the legitimate audit
case would have quietly deleted the rollback path instead of protecting it.
"""

from __future__ import annotations

from typing import Any

from conftest import requires_showcase, requires_v1, valid_output

from scoutlens.explanations import rejection_rules, validate_output
from scoutlens.explanations.policy import CONTRACT, OUTPUT_SCHEMA_VERSION

pytestmark = [requires_showcase, requires_v1]


def _cosine_claim(bundle: dict[str, Any]) -> dict[str, Any]:
    """An explanation whose feature claim cites the unweighted cosine term."""
    feature = next(
        row
        for row in bundle["evidence"]
        if row["kind"] == "feature_contribution" and row["cosine_contribution"] is not None
    )
    return {
        "contract": CONTRACT,
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "profile_key": bundle["profile_key"],
        "bundle_digest": bundle["bundle_digest"],
        "claims": [
            {
                "surface": "provenance",
                "text": f"Computed with {bundle['provenance']['ranking_method']}.",
                "evidence_ids": [feature["evidence_id"]],
            },
            {
                "surface": "feature_contribution",
                "text": f"{feature['feature_id']} contributed to the cosine alignment.",
                "evidence_ids": [feature["evidence_id"]],
                "values": [
                    {
                        "field": "cosine_contribution",
                        "value": feature["cosine_contribution"],
                        "evidence_id": feature["evidence_id"],
                    }
                ],
            },
        ],
        "caveat_codes": sorted(caveat["code"] for caveat in bundle["caveats"]),
    }


def test_an_audit_explanation_may_cite_the_cosine_term(audit_bundle: dict[str, Any]) -> None:
    result = validate_output(_cosine_claim(audit_bundle), audit_bundle)
    assert result.accepted, [str(rejection) for rejection in result.rejections]


def test_the_same_citation_is_refused_in_a_diagonal_bundle(bundle: dict[str, Any]) -> None:
    assert "claim.cosine_as_primary" in rejection_rules(
        validate_output(_cosine_claim(bundle), bundle)
    )


def test_an_audit_explanation_still_cannot_recommend(audit_bundle: dict[str, Any]) -> None:
    """The audit path relaxes which score may be cited, and nothing else."""
    output = _cosine_claim(audit_bundle)
    output["claims"][1]["text"] = "On this evidence a club should sign the neighbour."
    assert "claim.forbidden_intent.recommendation" in rejection_rules(
        validate_output(output, audit_bundle)
    )


def test_an_audit_explanation_still_cannot_fabricate(audit_bundle: dict[str, Any]) -> None:
    output = _cosine_claim(audit_bundle)
    output["claims"][1]["evidence_ids"] = ["self-feature-invented"]
    assert "claim.fabricated_citation" in rejection_rules(validate_output(output, audit_bundle))


def test_the_two_bundles_do_not_share_a_digest(
    bundle: dict[str, Any], audit_bundle: dict[str, Any]
) -> None:
    """So an audit output can never be validated against a diagonal bundle."""
    assert bundle["bundle_digest"] != audit_bundle["bundle_digest"]
    assert not validate_output(_cosine_claim(audit_bundle), bundle).accepted


def test_a_v2_explanation_may_cite_the_weighted_contribution(bundle: dict[str, Any]) -> None:
    """The positive control for the rule above: v2 has its own citable score."""
    result = validate_output(valid_output(bundle), bundle)
    assert result.accepted, [str(rejection) for rejection in result.rejections]
