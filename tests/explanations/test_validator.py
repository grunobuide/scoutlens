"""The fail-closed guarantee: every adversarial fixture is rejected, valid ones accepted."""

from __future__ import annotations

from typing import Any

import pytest
from adversarial import ADVERSARIAL, build_case
from conftest import requires_showcase, valid_output

from scoutlens.explanations import rejection_rules, validate_output, validate_output_schema

pytestmark = requires_showcase


def test_the_canonical_explanation_is_accepted(bundle: dict[str, Any]) -> None:
    output = valid_output(bundle)
    validate_output_schema(output)
    result = validate_output(output, bundle)
    assert result.accepted, f"canonical output rejected: {[str(r) for r in result.rejections]}"


@pytest.mark.parametrize("case", sorted(ADVERSARIAL))
def test_every_adversarial_fixture_is_rejected(case: str, bundle: dict[str, Any]) -> None:
    """AC4: 100 percent of the invalid fixtures, with the expected rule firing.

    Asserting the *rule* rather than merely "rejected" is what keeps the suite
    honest. A fixture that fails for an unrelated reason — a typo in the JSON,
    say — would still be "rejected" and would report the guard as working when
    it never ran.
    """
    output, expected_rule = build_case(case, valid_output(bundle), bundle)
    result = validate_output(output, bundle)

    assert not result.accepted, f"{case} was accepted"
    assert expected_rule in rejection_rules(result), (
        f"{case} was rejected, but not by {expected_rule}. Fired: {sorted(rejection_rules(result))}"
    )


def test_an_unrecognised_claim_surface_is_rejected_not_ignored(bundle: dict[str, Any]) -> None:
    """Fail-closed has no 'unknown, allow' branch."""
    output = valid_output(bundle)
    output["claims"][0]["surface"] = "speculation"
    assert "claim.surface" in rejection_rules(validate_output(output, bundle))


def test_an_uncited_claim_is_rejected(bundle: dict[str, Any]) -> None:
    output = valid_output(bundle)
    output["claims"][0]["evidence_ids"] = []
    assert "claim.ungrounded" in rejection_rules(validate_output(output, bundle))


def test_a_caveat_the_bundle_does_not_publish_is_rejected(bundle: dict[str, Any]) -> None:
    """Carrying extra caveats is not a safe direction: an invented caveat is invented copy."""
    output = valid_output(bundle)
    output["caveat_codes"] = [*output["caveat_codes"], "invented_caveat_code"]
    assert "caveats.unknown" in rejection_rules(validate_output(output, bundle))


def test_rejections_name_the_claim_they_came_from(bundle: dict[str, Any]) -> None:
    output, _ = build_case("style_proof", valid_output(bundle), bundle)
    result = validate_output(output, bundle)
    indexed = [rejection for rejection in result.rejections if rejection.claim_index is not None]
    assert indexed, "no rejection identified which claim failed"
    assert str(indexed[0]).startswith("claim.")


def test_a_non_object_output_is_rejected(bundle: dict[str, Any]) -> None:
    assert not validate_output("an explanation, honestly", bundle).accepted
    assert not validate_output(None, bundle).accepted
