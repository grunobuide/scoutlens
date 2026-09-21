"""What the system says when the model cannot be trusted to say it.

A grounded-explanation system that has no answer when the model fails has not
removed the risk, it has moved it: the pressure then lands on shipping the
unvalidated output "just this once". So refusal has to produce something usable,
and the only material available is the bundle - which is also the only material
that was ever trustworthy.

The fallback is therefore deliberately dull. It states where the numbers came
from, what the retrieval outcome was, and that no model contributed to the text.
It makes no feature-contribution claim and no similarity claim, because those
are the judgements a model was being asked for and nothing here is in a position
to make them.

**It passes the same validator as a model's answer.** Not as a formality: a
fallback exempted from validation would be the one unchecked path in the system,
and the one an incident would travel down.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from scoutlens.explanations.policy import CONTRACT, OUTPUT_SCHEMA_VERSION


class FallbackReason(StrEnum):
    """Why the model's answer was not used.

    Separate members because the operational response differs: a transport
    failure is worth another run later, a refused output is a finding about the
    model, and an unusable shape is a finding about the adapter.
    """

    ADAPTER_FAILURE = "adapter_failure"
    """The adapter returned a typed failure; no content ever arrived."""

    SCHEMA_INVALID = "schema_invalid"
    """Content arrived and did not match the output schema."""

    VALIDATION_REJECTED = "validation_rejected"
    """Content matched the schema and the validator refused it."""


@dataclass(frozen=True)
class Fallback:
    """The deterministic explanation, with the reason it was needed.

    The reason lives here rather than inside `output` on purpose: the output
    schema is closed, and a caller that could not tell a fallback from a model's
    answer by its type would eventually fail to tell them apart at all.
    """

    output: dict[str, Any]
    reason: FallbackReason
    detail: str


def _grounding_evidence_id(bundle: dict[str, Any]) -> str:
    """An evidence id to hang the fallback's claims on, preferring a self row.

    Preferring `self_retrieval` keeps the fallback from citing neighbour
    evidence, which would pull in the mandatory caveat set for an explanation
    that makes no comparison at all.
    """
    allowed = bundle.get("allowed_evidence_ids") or ()
    for row in bundle.get("evidence", ()):
        if not str(row.get("subject", "")).startswith("neighbor:"):
            return str(row["evidence_id"])
    if not allowed:
        raise ValueError("bundle publishes no evidence; nothing can be grounded in it")
    return str(allowed[0])


def deterministic_fallback(
    bundle: dict[str, Any],
    *,
    reason: FallbackReason,
    detail: str,
) -> Fallback:
    """Build the no-model explanation for ``bundle``."""
    evidence_id = _grounding_evidence_id(bundle)
    retrieval = bundle["retrieval"]
    provenance = bundle["provenance"]

    named = (
        f"{provenance['ranking_method']} ({provenance['representation_id']})"
        if provenance.get("representation_id")
        else str(provenance["ranking_method"])
    )

    claims: list[dict[str, Any]] = [
        {
            "surface": "provenance",
            "text": f"These numbers come from {named}.",
            "evidence_ids": [evidence_id],
        },
        {
            "surface": "limitation",
            "text": (
                "No model text is included here: the generated explanation was not accepted, "
                "so only values copied from the published profile appear below."
            ),
            "evidence_ids": [evidence_id],
        },
    ]

    # Stated only when the profile publishes both halves. A fallback that filled
    # a gap with a plausible number would be the exact failure it exists to
    # prevent, committed by the component that is supposed to be safe.
    if retrieval.get("self_rank") is not None and retrieval.get("candidate_count") is not None:
        claims.append(
            {
                "surface": "retrieval_outcome",
                "text": (
                    f"The player's own second-half profile was ranked {retrieval['self_rank']} "
                    f"of {retrieval['candidate_count']} candidates."
                ),
                "evidence_ids": [evidence_id],
                "values": [
                    {"field": "self_rank", "value": retrieval["self_rank"]},
                    {"field": "candidate_count", "value": retrieval["candidate_count"]},
                ],
            }
        )

    if retrieval.get("uncertainty_status") != "available":
        claims.append(
            {
                "surface": "limitation",
                "text": (
                    "The rank uncertainty for this profile is "
                    f"{retrieval.get('uncertainty_status')!r}, so no interval is reported."
                ),
                "evidence_ids": [evidence_id],
            }
        )

    output = {
        "contract": CONTRACT,
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "profile_key": bundle["profile_key"],
        "bundle_digest": bundle["bundle_digest"],
        "claims": claims,
        "caveat_codes": sorted(caveat["code"] for caveat in bundle["caveats"]),
    }
    return Fallback(output=output, reason=reason, detail=detail)


__all__ = ["Fallback", "FallbackReason", "deterministic_fallback"]
