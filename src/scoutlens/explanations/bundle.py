"""Build the deterministic evidence bundle a model is allowed to see.

The bundle is the whole trust boundary. A model receives this and nothing else,
so anything absent here cannot be cited, and anything present here can be
checked against the published artifact by a validator that never calls a model.

Three properties make that work:

* **Derived, never authored.** Every value is copied from an already-validated
  showcase-v2 profile. This module computes no statistic and rounds nothing; it
  classifies and selects.
* **Ordered by the artifact.** Evidence keeps the order the profile published.
  A bundle that sorted by contribution would quietly re-rank the evidence and an
  explanation reading "the top three" would mean something the artifact never
  said.
* **Deterministic.** The same profile and the same options produce byte-identical
  bundles. The digest over the bundle is what an output cites back, so a model
  cannot be handed one set of evidence and validated against another.

The v1 path exists only for the cosine audit baseline. It is explicit, and it is
never reached by omission: a v1 profile requires ``audit_baseline=True``, and a
v2 profile with that flag is refused. Silently accepting either would let a v2
explanation describe v1 semantics, which is the failure `D047` and `D049` renamed
the method to prevent.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from scoutlens.explanations.policy import (
    BUNDLE_SCHEMA_VERSION,
    CONTRACT,
    MANDATORY_NEIGHBOUR_CAVEATS,
    EvidenceStatus,
)
from scoutlens.showcase.io import canonical_json_bytes

V2_CONTRACT_MAJOR = 2
V1_CONTRACT_MAJOR = 1


class BundleError(ValueError):
    """The profile cannot produce a bundle under this contract."""


@dataclass(frozen=True)
class BundleOptions:
    """What the caller is asking for, stated rather than inferred."""

    audit_baseline: bool = False
    """True only for an explicit v1 cosine audit or rollback comparison."""

    include_neighbours: bool = True
    """Neighbour evidence pulls in the mandatory caveats; omit it for a self-only bundle."""


def _profile_major(profile: dict[str, Any]) -> int:
    version = profile.get("schema_version")
    if not isinstance(version, str) or not version:
        raise BundleError("profile has no schema_version; refusing to guess a contract major")
    head = version.split(".", 1)[0]
    if not head.isdigit():
        raise BundleError(f"profile schema_version {version!r} has no numeric major")
    return int(head)


def _require(profile: dict[str, Any], key: str) -> Any:
    if key not in profile:
        raise BundleError(
            f"profile is missing {key!r}. The contract does not add fields to a profile: "
            "record a dependency on the showcase workstream instead."
        )
    return profile[key]


def classify_evidence(
    entry: dict[str, Any],
    *,
    feature_order: frozenset[str] | None,
) -> EvidenceStatus:
    """Place one evidence row in the taxonomy `policy` defines.

    **Family rows are aggregates, not features.** A ``family_contribution`` row
    carries ``feature_id: null``, ``feature_weight: null`` and null z-scores by
    design, and its ``weighted_contribution`` is the exact sum of its members'.
    Verified against the published artifact: the "passing" family's 0.3524 is
    the sum of its five members' weighted contributions. So a family row is
    real ranking evidence whenever that sum is present, and reading its null
    ``feature_weight`` as "the fit gave it no weight" would label 48 of 240 rows
    with a statement about the model that is simply false.

    For feature rows, order matters. ``unmeasured`` first, because a missing
    z-score makes the weight irrelevant - there is nothing to be similar
    *about*. Then ``excluded`` before ``learned_zero``: both carry weight
    ``0.0``, and only membership in ``feature_order`` separates "the model never
    saw it" from "the model saw it and gave it nothing".
    """
    if feature_order is None:
        # Audit baseline: unweighted cosine gives every catalogued feature the
        # same unit weight (`D045`), so there is no excluded/learned-zero split
        # to make. Only an absent measurement can demote a row.
        measured = entry.get("query_global_z") is not None and entry.get("candidate_global_z") is not None
        if entry.get("kind") == "family_contribution":
            return EvidenceStatus.WEIGHTED if entry.get("contribution") is not None else EvidenceStatus.UNMEASURED
        return EvidenceStatus.WEIGHTED if measured else EvidenceStatus.UNMEASURED

    if entry.get("kind") == "family_contribution":
        return (
            EvidenceStatus.WEIGHTED
            if entry.get("weighted_contribution") is not None
            else EvidenceStatus.UNMEASURED
        )

    feature_id = entry.get("feature_id")
    if feature_id is None:
        return EvidenceStatus.UNMEASURED
    if entry.get("query_global_z") is None or entry.get("candidate_global_z") is None:
        return EvidenceStatus.UNMEASURED
    if feature_id not in feature_order:
        return EvidenceStatus.EXCLUDED
    if not entry.get("feature_weight"):
        return EvidenceStatus.LEARNED_ZERO
    return EvidenceStatus.WEIGHTED


def _v2_provenance(representation: dict[str, Any] | None) -> dict[str, Any]:
    if representation is None:
        raise BundleError(
            "a v2 bundle needs the representation artifact: without it the explanation "
            "cannot name what produced the score, and cannot tell a weighted feature from "
            "one the model never saw."
        )
    block = representation.get("representation", representation)
    for key in ("id", "ranking_method", "feature_order", "feature_order_digest"):
        if key not in block:
            raise BundleError(f"representation artifact is missing {key!r}")

    provenance = {
        "representation_id": block["id"],
        "ranking_method": block["ranking_method"],
        "feature_count": len(block["feature_order"]),
        "feature_order_digest": block["feature_order_digest"],
        "prohibited_claims": list(block.get("prohibited_claims", ())),
        "is_audit_baseline_bundle": False,
    }
    audit = block.get("audit_baseline")
    if isinstance(audit, dict):
        # Carried so an explanation can say what the cosine baseline *is*
        # without being able to present it as the score that produced the rank.
        provenance["audit_baseline_method"] = audit.get("method")
    return provenance


def _v1_provenance(profile: dict[str, Any]) -> dict[str, Any]:
    """Provenance for the frozen cosine audit path.

    There is no v1 representation artifact, and inventing one would be the
    silent downgrade this contract exists to prevent. The v1 method is a
    property of the profile, so it is read from the profile: unweighted cosine
    over the full catalogued feature set, which `D045` records as the baseline
    that unit weights reproduce exactly.
    """
    method = profile.get("retrieval", {}).get("method")
    if not method:
        raise BundleError("v1 profile publishes no retrieval.method to attribute the score to")
    features = {
        entry["feature_id"]
        for entry in profile.get("evidence_index", ())
        if entry.get("feature_id") is not None
    }
    return {
        "representation_id": None,
        "ranking_method": method,
        "feature_count": len(features),
        "feature_order_digest": None,
        "prohibited_claims": [],
        "audit_baseline_method": method,
        "is_audit_baseline_bundle": True,
    }


def _evidence_rows(
    profile: dict[str, Any],
    *,
    feature_order: frozenset[str] | None,
    include_neighbours: bool,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in _require(profile, "evidence_index"):
        subject = entry.get("subject", "")
        if not include_neighbours and subject.startswith("neighbor:"):
            continue

        status = classify_evidence(entry, feature_order=feature_order)
        rows.append(
            {
                "evidence_id": entry["evidence_id"],
                "kind": entry["kind"],
                "subject": subject,
                "family": entry.get("family"),
                "feature_id": entry.get("feature_id"),
                "status": str(status),
                # `contribution` is the unweighted cosine term and
                # `weighted_contribution` the diagonal one. Both travel, under
                # names that cannot be confused, because an audit explanation
                # legitimately discusses the first and a v2 explanation must
                # never present it as the score behind the rank.
                "cosine_contribution": entry.get("contribution"),
                "weighted_contribution": entry.get("weighted_contribution"),
                "feature_weight": entry.get("feature_weight"),
                "query_global_z": entry.get("query_global_z"),
                "candidate_global_z": entry.get("candidate_global_z"),
                "interpretation": entry.get("interpretation"),
                "representation_id": entry.get("representation_id"),
            }
        )
    return rows


def _neighbour_rows(profile: dict[str, Any]) -> list[dict[str, Any]]:
    neighbours = []
    for neighbour in profile.get("neighbors", ()):
        stability = neighbour.get("stability", {})
        neighbours.append(
            {
                "profile_key": neighbour["profile_key"],
                "display_name": neighbour["display_name"],
                "rank": neighbour["rank"],
                "similarity_score": neighbour.get("similarity_score", neighbour.get("cosine_similarity")),
                "representation_id": neighbour.get("representation_id"),
                "evidence_refs": list(neighbour.get("evidence_refs", ())),
                "stability_status": stability.get("status"),
                "median_rank": stability.get("median_rank"),
                "rank_ci_95": list(stability.get("rank_ci_95", ()) or ()),
            }
        )
    return neighbours


def _caveat_rows(profile: dict[str, Any], *, include_neighbours: bool) -> list[dict[str, Any]]:
    published = {caveat["code"]: caveat for caveat in _require(profile, "caveats")}
    if include_neighbours:
        missing = sorted(MANDATORY_NEIGHBOUR_CAVEATS - published.keys())
        if missing:
            raise BundleError(
                "profile does not publish the caveats a neighbour explanation must carry: "
                f"{missing}. The contract does not invent caveat copy."
            )
    return [
        {"code": code, "severity": published[code]["severity"], "message": published[code]["message"]}
        for code in sorted(published)
    ]


def build_bundle(
    profile: dict[str, Any],
    representation: dict[str, Any] | None = None,
    *,
    options: BundleOptions | None = None,
) -> dict[str, Any]:
    """Assemble the bundle for one validated showcase profile.

    ``profile`` must already have passed showcase schema validation. This
    function re-checks the contract major and the fields it reads, and refuses
    anything it cannot ground - it never fills a gap.
    """
    options = options or BundleOptions()
    major = _profile_major(profile)

    if options.audit_baseline and major != V1_CONTRACT_MAJOR:
        raise BundleError(
            f"audit_baseline bundles describe the v1 cosine baseline, but this profile is "
            f"major {major}. Asking for an audit bundle from a v2 profile would present the "
            "diagonal score as a cosine one."
        )
    if not options.audit_baseline and major != V2_CONTRACT_MAJOR:
        raise BundleError(
            f"profile is contract major {major}; v2 is required unless audit_baseline is set "
            "explicitly. A v1 profile is never silently upgraded to v2 semantics."
        )

    if options.audit_baseline:
        provenance = _v1_provenance(profile)
        feature_order: frozenset[str] | None = None
    else:
        provenance = _v2_provenance(representation)
        block = (representation or {}).get("representation", representation or {})
        feature_order = frozenset(block.get("feature_order", ()))
    identity = _require(profile, "identity")

    bundle = {
        "contract": CONTRACT,
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "dataset_version": _require(profile, "dataset_version"),
        "profile_key": _require(profile, "profile_key"),
        "subject": {
            "display_name": identity["display_name"],
            "role": identity["role"],
            "season": identity["season"],
            "competition": identity["competition"]["name"],
        },
        "provenance": provenance,
        "retrieval": _retrieval_block(profile),
        "neighbours": _neighbour_rows(profile) if options.include_neighbours else [],
        "evidence": _evidence_rows(
            profile, feature_order=feature_order, include_neighbours=options.include_neighbours
        ),
        "caveats": _caveat_rows(profile, include_neighbours=options.include_neighbours),
    }
    bundle["allowed_evidence_ids"] = [row["evidence_id"] for row in bundle["evidence"]]
    bundle["bundle_digest"] = bundle_digest(bundle)
    return bundle


def _retrieval_block(profile: dict[str, Any]) -> dict[str, Any]:
    retrieval = _require(profile, "retrieval")
    published = retrieval.get("global", {})
    uncertainty = published.get("uncertainty", {})
    return {
        "method": retrieval.get("method"),
        "query_period": retrieval.get("query_period"),
        "candidate_period": retrieval.get("candidate_period"),
        "self_rank": published.get("self_rank"),
        "candidate_count": published.get("candidate_count"),
        # v1 publishes `cosine_similarity`, v2 `similarity_score`. The bundle
        # exposes one field so an explanation cites the same name either way,
        # while `provenance.ranking_method` keeps saying which one produced it.
        "similarity_score": published.get("similarity_score", published.get("cosine_similarity")),
        "representation_id": published.get("representation_id"),
        "uncertainty_status": uncertainty.get("status"),
    }


def bundle_digest(bundle: dict[str, Any]) -> str:
    """SHA-256 over the canonical bundle, excluding the digest field itself.

    An accepted output cites this. It is what stops a model being shown one
    bundle and its answer being checked against another - the pairing is
    asserted, not assumed from call order.
    """
    payload = {key: value for key, value in bundle.items() if key != "bundle_digest"}
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
