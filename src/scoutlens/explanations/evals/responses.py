"""The deterministic reference explanation for a bundle.

This is what a perfectly obedient model would return: one claim per surface the
contract defines, every number tied to the field it was copied from, the full
mandatory caveat set whenever neighbour evidence is cited. It is derived from
the bundle, so it cannot go stale when the showcase repins - a stored fixture
that still passes against data nobody publishes any more is worse than no
fixture at all.

**This is not a model, and the package never pretends it is.** Driving the
adapter path with these responses measures the validator, the corpus and the
fallback. It measures nothing about any model's behaviour. `runner` records the
distinction as `response_source`, and the recorded report carries it.
"""

from __future__ import annotations

from typing import Any

from scoutlens.explanations.policy import CONTRACT, OUTPUT_SCHEMA_VERSION, EvidenceStatus

#: Version of the synthesised response set. Part of the recorded report, so a
#: change to what "obedient" means cannot pass as a change in the validator.
RESPONSE_SET_VERSION = "1.0.0"


class NoSuchEvidence(LookupError):
    """The bundle carries no evidence row of the kind a case needs."""


def rows_with_status(bundle: dict[str, Any], status: str | EvidenceStatus) -> list[dict[str, Any]]:
    """Every evidence row in the taxonomy bucket ``status``, in artifact order."""
    return [row for row in bundle["evidence"] if row["status"] == str(status)]


def first_weighted_feature(bundle: dict[str, Any]) -> dict[str, Any]:
    """The first feature row that may support a contribution claim."""
    for row in bundle["evidence"]:
        if row["status"] == str(EvidenceStatus.WEIGHTED) and row["kind"] == "feature_contribution":
            return row
    raise NoSuchEvidence("bundle has no weighted feature evidence")


def neighbour_evidence(bundle: dict[str, Any]) -> dict[str, Any] | None:
    """The first weighted neighbour row, or ``None`` for a self-only bundle."""
    for row in bundle["evidence"]:
        if row["subject"].startswith("neighbor:") and row["status"] == str(EvidenceStatus.WEIGHTED):
            return row
    return None


def _contribution_reference(row: dict[str, Any]) -> dict[str, Any] | None:
    """Cite the contribution field this bundle's major actually publishes.

    A v2 row carries `weighted_contribution`; the v1 audit baseline carries only
    `cosine_contribution`. Citing the absent one would assert a number against a
    null and be rejected - correctly, but for a reason that says nothing about
    the case under test.
    """
    for field in ("weighted_contribution", "cosine_contribution"):
        if row.get(field) is not None:
            return {"field": field, "value": row[field], "evidence_id": row["evidence_id"]}
    return None


def reference_output(bundle: dict[str, Any]) -> dict[str, Any]:
    """The canonical accepted explanation for ``bundle``."""
    feature = first_weighted_feature(bundle)
    neighbour = neighbour_evidence(bundle)
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
            "evidence_ids": [feature["evidence_id"]],
        },
        {
            "surface": "retrieval_outcome",
            "text": (
                f"The player's own second-half profile was ranked {retrieval['self_rank']} "
                f"of {retrieval['candidate_count']} candidates."
            ),
            "evidence_ids": [feature["evidence_id"]],
            "values": [
                {"field": "self_rank", "value": retrieval["self_rank"]},
                {"field": "candidate_count", "value": retrieval["candidate_count"]},
            ],
        },
    ]

    contribution = _contribution_reference(feature)
    claims.append(
        {
            "surface": "feature_contribution",
            "text": f"{feature['feature_id']} contributed to that alignment.",
            "evidence_ids": [feature["evidence_id"]],
            **({"values": [contribution]} if contribution else {}),
        }
    )

    claims.append(
        {
            "surface": "similarity",
            "text": (
                "A neighbouring profile sits close to this one under the same representation."
                if neighbour is not None
                else "The subject's two periods sit close under the same representation."
            ),
            "evidence_ids": [(neighbour or feature)["evidence_id"]],
        }
    )

    claims.append(
        {
            "surface": "limitation",
            "text": "Same-season club continuity can make this retrieval easier than it looks.",
            "evidence_ids": [feature["evidence_id"]],
        }
    )

    return {
        "contract": CONTRACT,
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "profile_key": bundle["profile_key"],
        "bundle_digest": bundle["bundle_digest"],
        "claims": claims,
        "caveat_codes": sorted(caveat["code"] for caveat in bundle["caveats"]),
    }


#: How each non-weighted status may honestly be discussed.
#:
#: The wording is the whole point of these cases. Each sentence is true of its
#: own status and a category error about the other two, which is the confusion
#: `policy` exists to prevent and the one a fluent model is most likely to make.
_LIMITATION_TEXT: dict[str, str] = {
    str(EvidenceStatus.EXCLUDED): (
        "This measurement is not in the representation's feature order, so it entered no ranking "
        "and is shown as descriptive context only."
    ),
    str(EvidenceStatus.LEARNED_ZERO): (
        "This measurement is in the representation's feature order and the fit gave it no weight, "
        "which is a fact about the model rather than about this pair of periods."
    ),
    str(EvidenceStatus.UNMEASURED): (
        "This measurement has no value for the period, so it is an absence rather than a "
        "similarity or a difference."
    ),
}


def limitation_variant(bundle: dict[str, Any], status: str | EvidenceStatus) -> dict[str, Any]:
    """The reference output plus one honest `limitation` claim about ``status``.

    Accepted by construction: the `limitation` surface is where a fact about the
    model belongs. The matching `mutations` entry moves the same evidence id to
    `feature_contribution`, where it must be refused. The pair is what proves the
    taxonomy is load-bearing rather than decorative - a validator that rejected
    both would be useless for the same reason as one that accepted both.
    """
    rows = rows_with_status(bundle, status)
    if not rows:
        raise NoSuchEvidence(f"bundle has no evidence row with status {str(status)!r}")

    output = reference_output(bundle)
    output["claims"].append(
        {
            "surface": "limitation",
            "text": _LIMITATION_TEXT[str(status)],
            "evidence_ids": [rows[0]["evidence_id"]],
        }
    )
    return output


__all__ = [
    "RESPONSE_SET_VERSION",
    "NoSuchEvidence",
    "first_weighted_feature",
    "limitation_variant",
    "neighbour_evidence",
    "reference_output",
    "rows_with_status",
]
