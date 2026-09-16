"""AC5: what counts as the same number, and what a digest is allowed to ignore.

These are the boundary cases. Both guards look permissive from a distance and
are not: the numeric one accepts float round-tripping and nothing else, and the
digest one changes on any content edit at all.
"""

from __future__ import annotations

import copy
import json
from typing import Any

import pytest
from conftest import first_weighted_feature, requires_showcase, valid_output

from scoutlens.explanations import rejection_rules, validate_output
from scoutlens.explanations.bundle import bundle_digest
from scoutlens.explanations.validator import NUMERIC_RELATIVE_TOLERANCE

pytestmark = requires_showcase


def _cite_value(bundle: dict[str, Any], value: float) -> dict[str, Any]:
    feature = first_weighted_feature(bundle)
    output = valid_output(bundle)
    for claim in output["claims"]:
        if claim["surface"] == "feature_contribution":
            claim["values"] = [
                {
                    "field": "weighted_contribution",
                    "value": value,
                    "evidence_id": feature["evidence_id"],
                }
            ]
    return output


def test_a_json_round_tripped_value_is_the_same_number(bundle: dict[str, Any]) -> None:
    """The tolerance exists for this and only this."""
    published = first_weighted_feature(bundle)["weighted_contribution"]
    round_tripped = json.loads(json.dumps(published))
    result = validate_output(_cite_value(bundle, round_tripped), bundle)
    assert result.accepted, [str(r) for r in result.rejections]


def test_a_value_just_inside_the_tolerance_is_accepted(bundle: dict[str, Any]) -> None:
    published = first_weighted_feature(bundle)["weighted_contribution"]
    nudged = published * (1 + NUMERIC_RELATIVE_TOLERANCE / 10)
    assert validate_output(_cite_value(bundle, nudged), bundle).accepted


def test_a_value_just_outside_the_tolerance_is_rejected(bundle: dict[str, Any]) -> None:
    published = first_weighted_feature(bundle)["weighted_contribution"]
    nudged = published * (1 + NUMERIC_RELATIVE_TOLERANCE * 100)
    assert "claim.value_mismatch" in rejection_rules(validate_output(_cite_value(bundle, nudged), bundle))


@pytest.mark.parametrize("places", [1, 2, 3, 4])
def test_a_rounded_value_is_a_different_number(bundle: dict[str, Any], places: int) -> None:
    """`D046` in one assertion.

    "0.25" for a published 0.2539 reads like a courtesy to the reader and is a
    different number. Display rounding is the consumer's job, and a contract
    that blesses it here cannot tell a rounding from a mistake.
    """
    published = first_weighted_feature(bundle)["weighted_contribution"]
    rounded = round(published, places)
    if rounded == published:
        pytest.skip(f"published value is already exact at {places} places")
    assert "claim.value_mismatch" in rejection_rules(validate_output(_cite_value(bundle, rounded), bundle))


def test_a_value_cited_as_a_string_is_rejected(bundle: dict[str, Any]) -> None:
    output = _cite_value(bundle, 0.0)
    for claim in output["claims"]:
        if claim["surface"] == "feature_contribution":
            claim["values"][0]["value"] = "0.2228"
    assert "claim.value_type" in rejection_rules(validate_output(output, bundle))


def test_a_value_cited_from_a_field_the_bundle_does_not_publish_is_rejected(
    bundle: dict[str, Any],
) -> None:
    output = _cite_value(bundle, 0.0)
    for claim in output["claims"]:
        if claim["surface"] == "feature_contribution":
            claim["values"][0]["field"] = "expected_goals_added"
    assert "claim.value_field" in rejection_rules(validate_output(output, bundle))


def test_a_value_attributed_to_an_unknown_evidence_id_is_rejected(bundle: dict[str, Any]) -> None:
    output = _cite_value(bundle, 0.0)
    for claim in output["claims"]:
        if claim["surface"] == "feature_contribution":
            claim["values"][0]["evidence_id"] = "self-feature-invented"
    assert "claim.value_source" in rejection_rules(validate_output(output, bundle))


def test_the_digest_changes_on_any_content_edit(bundle: dict[str, Any]) -> None:
    """Including edits that do not change a number."""
    baseline = bundle_digest(bundle)

    for mutate in (
        lambda b: b["caveats"].pop(),
        lambda b: b["evidence"].reverse(),
        lambda b: b.__setitem__("dataset_version", "wyscout-2017-18-v2-000000000000"),
        lambda b: b["subject"].__setitem__("role", "Goalkeeper"),
    ):
        altered = copy.deepcopy(bundle)
        mutate(altered)
        assert bundle_digest(altered) != baseline


def test_the_digest_is_independent_of_key_insertion_order(bundle: dict[str, Any]) -> None:
    """Canonical serialisation, so a reordered dict is the same bundle."""
    shuffled = {key: bundle[key] for key in sorted(bundle, reverse=True)}
    assert bundle_digest(shuffled) == bundle_digest(bundle)
