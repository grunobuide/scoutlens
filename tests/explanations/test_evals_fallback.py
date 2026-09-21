"""The fallback has to hold on every bundle shape, including the broken ones.

It runs precisely when something else has already failed, so "it works on the
happy path" is the one guarantee that is worth nothing here. Every bundle the
corpus can produce is put through it, and the result is held to the same
validator a model's answer would face.
"""

from __future__ import annotations

from typing import Any

import pytest
from conftest import requires_showcase, requires_v1

from scoutlens.explanations import validate_output, validate_output_schema
from scoutlens.explanations.evals import degrade
from scoutlens.explanations.evals.corpus import ShowcaseArtifacts, build_corpus, materialise
from scoutlens.explanations.evals.fallback import FallbackReason, deterministic_fallback
from scoutlens.explanations.policy import MANDATORY_NEIGHBOUR_CAVEATS

pytestmark = requires_showcase


@pytest.fixture(scope="module")
def artifacts() -> ShowcaseArtifacts:
    return ShowcaseArtifacts()


@requires_v1
@pytest.mark.parametrize("case", build_corpus(), ids=lambda case: case.case_id)
def test_the_fallback_validates_against_every_bundle_in_the_corpus(
    case: Any, artifacts: ShowcaseArtifacts
) -> None:
    bundle = materialise(case, artifacts).bundle
    fallback = deterministic_fallback(
        bundle, reason=FallbackReason.ADAPTER_FAILURE, detail="synthetic"
    )
    validate_output_schema(fallback.output)
    result = validate_output(fallback.output, bundle)
    assert result.accepted, [str(rejection) for rejection in result.rejections]


@pytest.mark.parametrize("reason", list(FallbackReason))
def test_the_fallback_names_why_it_was_needed(
    reason: FallbackReason, bundle: dict[str, Any]
) -> None:
    """Typed, because the operational response differs per reason."""
    fallback = deterministic_fallback(bundle, reason=reason, detail="because")
    assert fallback.reason is reason
    assert fallback.detail == "because"


def test_the_fallback_makes_no_similarity_or_contribution_claim(
    bundle: dict[str, Any],
) -> None:
    """Those are the judgements a model was being asked for.

    Nothing here is in a position to make them, and a fallback that quietly did
    would be asserting from the bundle exactly what the model was refused for
    asserting from the bundle.
    """
    fallback = deterministic_fallback(
        bundle, reason=FallbackReason.VALIDATION_REJECTED, detail="refused"
    )
    surfaces = {claim["surface"] for claim in fallback.output["claims"]}
    assert surfaces <= {"provenance", "retrieval_outcome", "limitation"}


def test_the_fallback_says_that_no_model_text_is_included(bundle: dict[str, Any]) -> None:
    fallback = deterministic_fallback(
        bundle, reason=FallbackReason.ADAPTER_FAILURE, detail="timeout"
    )
    text = " ".join(claim["text"] for claim in fallback.output["claims"])
    assert "No model text is included here" in text


def test_the_fallback_reports_insufficient_uncertainty_rather_than_omitting_it(
    v2_profile: dict[str, Any], representation: dict[str, Any]
) -> None:
    """Silence about a missing interval reads as an interval that was fine."""
    from scoutlens.explanations import build_bundle

    degraded = degrade.insufficient_rank_uncertainty(v2_profile)
    bundle = build_bundle(degraded, representation)
    fallback = deterministic_fallback(
        bundle, reason=FallbackReason.ADAPTER_FAILURE, detail="synthetic"
    )
    text = " ".join(claim["text"] for claim in fallback.output["claims"])
    assert "insufficient" in text
    assert validate_output(fallback.output, bundle).accepted


def test_the_fallback_carries_the_published_caveats(bundle: dict[str, Any]) -> None:
    fallback = deterministic_fallback(
        bundle, reason=FallbackReason.ADAPTER_FAILURE, detail="synthetic"
    )
    carried = set(fallback.output["caveat_codes"])
    assert MANDATORY_NEIGHBOUR_CAVEATS <= carried
    assert carried <= {caveat["code"] for caveat in bundle["caveats"]}


def test_the_fallback_invents_no_number(
    v2_profile: dict[str, Any], representation: dict[str, Any]
) -> None:
    """A gap filled with a plausible number is the failure it exists to prevent."""
    from scoutlens.explanations import build_bundle

    profile = {**v2_profile}
    profile["retrieval"] = {
        **v2_profile["retrieval"],
        "global": {**v2_profile["retrieval"]["global"], "self_rank": None},
    }
    bundle = build_bundle(profile, representation)
    fallback = deterministic_fallback(
        bundle, reason=FallbackReason.ADAPTER_FAILURE, detail="synthetic"
    )
    surfaces = [claim["surface"] for claim in fallback.output["claims"]]
    assert "retrieval_outcome" not in surfaces
    assert validate_output(fallback.output, bundle).accepted


def test_the_fallback_detail_is_redacted(bundle: dict[str, Any]) -> None:
    """Nothing here ever puts a credential in a detail; the guard runs anyway."""
    from scoutlens.explanations.evals.diagnostics import redact

    assert redact("Authorization: Bearer sk-live-123").startswith("[redacted")
    assert redact("  a   b  ") == "a b"
    assert len(redact("x" * 500)) <= 160
