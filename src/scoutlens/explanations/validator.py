"""Reject any explanation the bundle does not support.

The validator is deterministic and offline. It never calls a model, and it never
consults anything except the bundle it was given and the output under test. That
is what makes it usable as an eval harness later: the same function decides a
live adapter's output and a stored fixture's.

**Fail-closed means every path ends in a rejection unless a rule explicitly
accepts.** There is no "unknown, allow" branch. A claim whose kind the contract
does not recognise is rejected, not ignored; a citation to an evidence ID that
does not exist is rejected rather than dropped; a numeric value that disagrees
with the artifact is rejected even when it rounds to the same display string.

Rejections are returned rather than raised, and every one names the sentence and
the rule. An eval that only knows *that* an output failed teaches nobody which
guard did the work.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any

from scoutlens.explanations.policy import (
    CITABLE_AS_RANKING_EVIDENCE,
    CONTRACT,
    FORBIDDEN_PHRASES,
    MANDATORY_NEIGHBOUR_CAVEATS,
    OUTPUT_SCHEMA_VERSION,
    ClaimSurface,
    EvidenceStatus,
    ForbiddenIntent,
)

#: Relative tolerance when comparing a cited number to the artifact.
#:
#: Not a rounding allowance. It absorbs float round-tripping through JSON and
#: nothing else; a value that differs in the fourth decimal is a different
#: number and is rejected. `D046` is why this is not loosened: unrounded rank
#: bounds shipped once because a display path was trusted to be cosmetic.
NUMERIC_RELATIVE_TOLERANCE = 1e-9


@dataclass(frozen=True)
class Rejection:
    """One reason an output was refused, with enough detail to act on."""

    rule: str
    detail: str
    claim_index: int | None = None

    def __str__(self) -> str:
        where = "" if self.claim_index is None else f" (claim {self.claim_index})"
        return f"{self.rule}{where}: {self.detail}"


@dataclass(frozen=True)
class ValidationResult:
    """Accepted only when nothing was rejected."""

    rejections: tuple[Rejection, ...] = field(default_factory=tuple)

    @property
    def accepted(self) -> bool:
        return not self.rejections

    def __bool__(self) -> bool:
        return self.accepted

    def rules(self) -> tuple[str, ...]:
        return tuple(rejection.rule for rejection in self.rejections)


def _numbers_agree(cited: float | None, published: float | None) -> bool:
    if published is None or cited is None:
        return False
    return math.isclose(cited, published, rel_tol=NUMERIC_RELATIVE_TOLERANCE, abs_tol=0.0)


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in _SENTENCE_SPLIT.split(text.strip()) if part.strip()]


def validate_output(output: Any, bundle: dict[str, Any]) -> ValidationResult:
    """Decide whether ``output`` is an explanation ``bundle`` supports."""
    rejections: list[Rejection] = []

    if not isinstance(output, dict):
        return ValidationResult((Rejection("output.shape", "output is not an object"),))

    rejections.extend(_check_envelope(output, bundle))
    claims = output.get("claims")
    if not isinstance(claims, list) or not claims:
        rejections.append(Rejection("output.claims", "an explanation must make at least one claim"))
        return ValidationResult(tuple(rejections))

    allowed = set(bundle.get("allowed_evidence_ids", ()))
    order = {evidence_id: position for position, evidence_id in enumerate(bundle.get("allowed_evidence_ids", ()))}
    by_id = {row["evidence_id"]: row for row in bundle.get("evidence", ())}
    cited_any_neighbour = False

    for index, claim in enumerate(claims):
        if not isinstance(claim, dict):
            rejections.append(Rejection("claim.shape", "claim is not an object", index))
            continue
        rejections.extend(
            _check_claim(claim, index, allowed=allowed, by_id=by_id, bundle=bundle, order=order)
        )
        if _cites_neighbour(claim, by_id):
            cited_any_neighbour = True

    if cited_any_neighbour:
        rejections.extend(_check_mandatory_caveats(output, bundle))

    rejections.extend(_check_provenance_present(claims, bundle))
    return ValidationResult(tuple(rejections))


def _check_provenance_present(claims: list[Any], bundle: dict[str, Any]) -> list[Rejection]:
    """An explanation must say which representation produced its numbers.

    Without it a reader cannot tell a diagonal score from the cosine audit
    baseline, and the two were deliberately renamed apart by `D047`/`D049`
    precisely because they had been confused once already. An explanation that
    reports a similarity and never names the method is not auditable, however
    correct its arithmetic.
    """
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        if claim.get("surface") != str(ClaimSurface.PROVENANCE):
            continue
        representation_id = bundle.get("provenance", {}).get("representation_id")
        method = bundle.get("provenance", {}).get("ranking_method")
        text = str(claim.get("text", ""))
        if (representation_id and representation_id in text) or (method and method in text):
            return []
        return [
            Rejection(
                "provenance.unnamed",
                f"the provenance claim names neither {representation_id!r} nor {method!r}",
            )
        ]
    return [
        Rejection(
            "provenance.missing",
            "no provenance claim: the explanation never says which representation produced the numbers",
        )
    ]


def _check_envelope(output: dict[str, Any], bundle: dict[str, Any]) -> list[Rejection]:
    rejections: list[Rejection] = []
    if output.get("contract") != CONTRACT:
        rejections.append(
            Rejection("envelope.contract", f"expected contract {CONTRACT!r}, got {output.get('contract')!r}")
        )
    if output.get("schema_version") != OUTPUT_SCHEMA_VERSION:
        rejections.append(
            Rejection(
                "envelope.schema_version",
                f"expected {OUTPUT_SCHEMA_VERSION!r}, got {output.get('schema_version')!r}",
            )
        )
    # The output must name the bundle it answered. Without this an explanation
    # produced from one profile could be validated against another's evidence,
    # and every citation would resolve.
    if output.get("bundle_digest") != bundle.get("bundle_digest"):
        rejections.append(
            Rejection(
                "envelope.bundle_digest",
                "output does not cite the digest of the bundle it is being validated against",
            )
        )
    if output.get("profile_key") != bundle.get("profile_key"):
        rejections.append(
            Rejection(
                "envelope.profile_key",
                f"output describes {output.get('profile_key')!r}, bundle is {bundle.get('profile_key')!r}",
            )
        )
    return rejections


def _cites_neighbour(claim: dict[str, Any], by_id: dict[str, Any]) -> bool:
    for evidence_id in claim.get("evidence_ids", ()) or ():
        row = by_id.get(evidence_id)
        if row is not None and str(row.get("subject", "")).startswith("neighbor:"):
            return True
    return False


def _check_mandatory_caveats(output: dict[str, Any], bundle: dict[str, Any]) -> list[Rejection]:
    published = {caveat["code"] for caveat in bundle.get("caveats", ())}
    carried = set(output.get("caveat_codes", ()) or ())

    unknown = sorted(carried - published)
    if unknown:
        return [Rejection("caveats.unknown", f"output cites caveats the bundle does not publish: {unknown}")]

    missing = sorted(MANDATORY_NEIGHBOUR_CAVEATS - carried)
    if missing:
        return [
            Rejection(
                "caveats.missing",
                f"an explanation citing neighbour evidence must carry {missing}",
            )
        ]
    return []


def _check_claim(
    claim: dict[str, Any],
    index: int,
    *,
    allowed: set[str],
    by_id: dict[str, Any],
    bundle: dict[str, Any],
    order: dict[str, int],
) -> list[Rejection]:
    rejections: list[Rejection] = []

    surface = claim.get("surface")
    if surface not in {str(member) for member in ClaimSurface}:
        rejections.append(Rejection("claim.surface", f"unrecognised claim surface {surface!r}", index))

    text = claim.get("text")
    if not isinstance(text, str) or not text.strip():
        rejections.append(Rejection("claim.text", "claim has no text", index))
        text = ""

    evidence_ids = claim.get("evidence_ids")
    if not isinstance(evidence_ids, list) or not evidence_ids:
        rejections.append(Rejection("claim.ungrounded", "every claim must cite at least one evidence id", index))
        evidence_ids = []

    fabricated = [evidence_id for evidence_id in evidence_ids if evidence_id not in allowed]
    if fabricated:
        rejections.append(
            Rejection("claim.fabricated_citation", f"evidence ids not in the bundle: {sorted(fabricated)}", index)
        )

    rejections.extend(_check_ranking_evidence(claim, index, evidence_ids=evidence_ids, by_id=by_id))
    rejections.extend(_check_numbers(claim, index, by_id=by_id, bundle=bundle))
    rejections.extend(_check_forbidden(text, index))
    rejections.extend(_check_evidence_order(evidence_ids, index, order=order))
    rejections.extend(_check_cosine_not_primary(claim, index, bundle=bundle))
    return rejections


def _check_evidence_order(evidence_ids: list[str], index: int, *, order: dict[str, int]) -> list[Rejection]:
    """Cited evidence keeps the order the artifact published.

    The profile emits contributions in a fixed order, and a claim that lists
    them rearranged - most temptingly, sorted by magnitude so the "biggest"
    reads first - is describing a ranking the artifact never published. The
    values would each be correct and the claim still misleading, which is why
    this is a rule and not a formatting preference.
    """
    positions = [order[evidence_id] for evidence_id in evidence_ids if evidence_id in order]
    if positions != sorted(positions):
        return [
            Rejection(
                "claim.reordered_evidence",
                f"evidence cited out of artifact order: {evidence_ids}",
                index,
            )
        ]
    return []


def _check_cosine_not_primary(claim: dict[str, Any], index: int, *, bundle: dict[str, Any]) -> list[Rejection]:
    """Outside an audit bundle, the cosine term is never the score.

    `D045` keeps unweighted cosine as the transparent audit baseline, and the
    bundle carries it under `cosine_contribution` so an audit explanation can
    discuss it. `D047` and `D049` renamed the published method because the two
    had already been confused in shipped copy. A v2 explanation presenting the
    cosine term as the similarity or the contribution is that same confusion,
    expressed fluently.
    """
    if bundle.get("provenance", {}).get("is_audit_baseline_bundle"):
        return []
    if claim.get("surface") not in {str(ClaimSurface.SIMILARITY), str(ClaimSurface.FEATURE_CONTRIBUTION)}:
        return []
    for reference in claim.get("values", ()) or ():
        if isinstance(reference, dict) and reference.get("field") == "cosine_contribution":
            return [
                Rejection(
                    "claim.cosine_as_primary",
                    (
                        "cites cosine_contribution as the score in a diagonal bundle; "
                        "the published method is "
                        f"{bundle.get('provenance', {}).get('ranking_method')!r}. "
                        "Cosine is the audit baseline, not the ranking score."
                    ),
                    index,
                )
            ]
    return []


def _check_ranking_evidence(
    claim: dict[str, Any],
    index: int,
    *,
    evidence_ids: list[str],
    by_id: dict[str, Any],
) -> list[Rejection]:
    """A feature-contribution claim may only rest on weighted evidence.

    This is the guard the `policy` taxonomy exists for. An excluded feature is
    published for context and never entered the ranking; a learned zero entered
    it and was given nothing. Either can be *discussed* - under the `limitation`
    surface, where the claim is about the model rather than about the match -
    but neither can be offered as the reason two profiles are close.
    """
    if claim.get("surface") != str(ClaimSurface.FEATURE_CONTRIBUTION):
        return []

    rejections: list[Rejection] = []
    for evidence_id in evidence_ids:
        row = by_id.get(evidence_id)
        if row is None:
            continue
        status = row.get("status")
        if status not in {str(member) for member in CITABLE_AS_RANKING_EVIDENCE}:
            rejections.append(
                Rejection(
                    "claim.unweighted_evidence",
                    (
                        f"{evidence_id} is {status!r} and cannot support a feature-contribution claim. "
                        f"{_status_hint(status)}"
                    ),
                    index,
                )
            )
    return rejections


def _status_hint(status: Any) -> str:
    if status == str(EvidenceStatus.EXCLUDED):
        return "It is not in the representation's feature_order, so the model never saw it."
    if status == str(EvidenceStatus.LEARNED_ZERO):
        return "It is in feature_order and the fit gave it zero weight; that is a fact about the model, not the match."
    if status == str(EvidenceStatus.UNMEASURED):
        return "It has no z-score for this period; an absence is neither similarity nor difference."
    return ""


def _check_numbers(
    claim: dict[str, Any],
    index: int,
    *,
    by_id: dict[str, Any],
    bundle: dict[str, Any],
) -> list[Rejection]:
    """Every number a claim asserts must equal the published one.

    Values are compared numerically rather than as rendered strings. A model
    that writes "0.25" for a published 0.2539 has stated a different number,
    however reasonable the rounding looks, and `D046` is the record of what
    trusting display formatting costs.
    """
    rejections: list[Rejection] = []
    for reference in claim.get("values", ()) or ():
        if not isinstance(reference, dict):
            rejections.append(Rejection("claim.value_shape", "value reference is not an object", index))
            continue

        field_name = reference.get("field")
        cited = reference.get("value")
        evidence_id = reference.get("evidence_id")

        if evidence_id is not None:
            row = by_id.get(evidence_id)
            if row is None:
                rejections.append(
                    Rejection("claim.value_source", f"value cites unknown evidence id {evidence_id!r}", index)
                )
                continue
            source: dict[str, Any] = row
        else:
            source = {
                "similarity_score": bundle.get("retrieval", {}).get("similarity_score"),
                "self_rank": bundle.get("retrieval", {}).get("self_rank"),
                "candidate_count": bundle.get("retrieval", {}).get("candidate_count"),
            }

        if field_name not in source:
            rejections.append(
                Rejection("claim.value_field", f"{field_name!r} is not a field the bundle publishes", index)
            )
            continue

        published = source[field_name]
        if not isinstance(cited, (int, float)) or isinstance(cited, bool):
            rejections.append(Rejection("claim.value_type", f"{field_name} is not cited as a number", index))
            continue
        if not _numbers_agree(float(cited), None if published is None else float(published)):
            rejections.append(
                Rejection(
                    "claim.value_mismatch",
                    f"{field_name} cited as {cited!r}, artifact publishes {published!r}",
                    index,
                )
            )
    return rejections


def _check_forbidden(text: str, index: int) -> list[Rejection]:
    lowered = text.lower()
    rejections: list[Rejection] = []
    for intent, phrases in FORBIDDEN_PHRASES.items():
        for phrase in phrases:
            if phrase in lowered:
                rejections.append(
                    Rejection(
                        f"claim.forbidden_intent.{intent}",
                        f"{phrase!r} states a {str(intent).replace('_', ' ')} the study cannot support",
                        index,
                    )
                )
                break
    return rejections


def rejection_rules(result: ValidationResult) -> set[str]:
    """Convenience for tests and evals: the distinct rules that fired."""
    return {rejection.rule for rejection in result.rejections}


__all__ = [
    "ForbiddenIntent",
    "Rejection",
    "ValidationResult",
    "rejection_rules",
    "validate_output",
]
