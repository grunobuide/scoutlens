"""Named single-property degradations of a validated profile.

Some conditions the contract has to handle do not occur anywhere in the
published showcase. Every one of the 1,257 v2 profiles reports `available` rank
uncertainty, and not one of their 301,680 evidence rows is missing a z-score. An
eval that only used published profiles would therefore never once exercise the
`unmeasured` branch of the taxonomy, the insufficient-uncertainty path, or an
explanation of a bundle whose evidence was cut down - and would report full
coverage while doing it.

So those cases are **derived**, by degrading a real profile one property at a
time. Two properties keep them honest:

* **Each degradation is schema-legal.** `query_global_z` is nullable and
  `status` admits `insufficient` in `showcase-2.0.0`, so a degraded profile is
  still a profile the exporter could have published; `tests/explanations`
  asserts that against the real schema rather than taking it on trust.
* **Each changes exactly one thing**, and says which. A case that degraded two
  properties could not tell you which one the validator reacted to.

What this does not do is invent evidence. Nothing here adds a feature, a
neighbour, a caveat or a number; every degradation removes or marks, and the
subject, provenance and representation stay whatever the export said they were.
"""

from __future__ import annotations

import copy
from typing import Any

#: Marker written into a degraded profile's representation id.
#:
#: Never matches a real `rep-…` identifier, so a degraded artifact cannot be
#: mistaken for a published one if it ever escapes a test directory.
MISMATCH_REPRESENTATION_ID = "rep-mismatched-eval-degradation"


def _feature_rows(profile: dict[str, Any], family: str) -> list[dict[str, Any]]:
    return [
        entry
        for entry in profile.get("evidence_index", ())
        if entry.get("kind") == "feature_contribution"
        and entry.get("feature_id") is not None
        and entry.get("family") == family
    ]


def unmeasure_family(profile: dict[str, Any], family: str) -> dict[str, Any]:
    """Drop both z-scores for every feature in ``family``.

    Produces `unmeasured` rows: a period for which the measurement does not
    exist. The weights stay exactly as the fit left them, which is the point -
    an unmeasured feature can carry a large weight and still say nothing, and an
    explanation that reads weight as evidence of similarity has to fail on it.

    **Only the z-scores go.** The first draft of this also nulled the family
    aggregate, on the reasoning that a sum over unmeasured members is not a
    number the exporter could produce. The schema disagreed, and it is right:
    `contribution` and `weighted_contribution` are non-nullable, family rows are
    named in `evidence_refs`, and `evidence_index` carries a `minItems` of 240,
    so there is no legal way to remove or blank one. What is left is the
    smallest possible change and a fully self-consistent artifact — every family
    sum still equals its members' contributions, and the only thing missing is
    the one field `showcase-2.0.0` declares nullable.
    """
    degraded = copy.deepcopy(profile)
    rows = _feature_rows(degraded, family)
    if not rows:
        raise ValueError(f"profile has no feature evidence in family {family!r}")
    for entry in rows:
        entry["query_global_z"] = None
        entry["candidate_global_z"] = None
    return degraded


def impute_query_period(profile: dict[str, Any], family: str) -> dict[str, Any]:
    """Drop only the query-period z-score for every feature in ``family``.

    The one-sided case, which is what imputation actually looks like: the
    candidate period has a value and the query period does not. It classifies as
    `unmeasured` for the same reason as the two-sided case, and it is cased
    separately because a model shown one populated number is far more tempted to
    treat the row as evidence than one shown two nulls.
    """
    degraded = copy.deepcopy(profile)
    rows = _feature_rows(degraded, family)
    if not rows:
        raise ValueError(f"profile has no feature evidence in family {family!r}")
    for entry in rows:
        entry["query_global_z"] = None
    return degraded


def insufficient_rank_uncertainty(profile: dict[str, Any]) -> dict[str, Any]:
    """Mark the global rank uncertainty insufficient and null what it derived.

    An insufficient run publishes the status and no bounds - leaving a 95%
    interval next to `insufficient` would be a state the exporter never emits,
    and a case built on an impossible artifact proves nothing about the real
    one.
    """
    degraded = copy.deepcopy(profile)
    uncertainty = degraded.get("retrieval", {}).get("global", {}).get("uncertainty")
    if uncertainty is None:
        raise ValueError("profile publishes no global rank uncertainty to degrade")
    uncertainty["status"] = "insufficient"
    for derived in ("valid_resamples", "median_rank", "rank_ci_95"):
        uncertainty[derived] = None
    for rate in ("recall_at_1_rate", "recall_at_5_rate", "recall_at_10_rate"):
        uncertainty[rate] = None
    return degraded


def insufficient_neighbour_stability(profile: dict[str, Any]) -> dict[str, Any]:
    """Mark every neighbour's stability insufficient and null what it derived."""
    degraded = copy.deepcopy(profile)
    if not degraded.get("neighbors"):
        raise ValueError("profile publishes no neighbours to degrade")
    for neighbour in degraded["neighbors"]:
        stability = neighbour.get("stability")
        if stability is None:
            continue
        stability["status"] = "insufficient"
        for derived in ("valid_resamples", "top_5_selection_rate", "median_rank", "rank_ci_95"):
            stability[derived] = None
    return degraded


def mismatch_representation(representation: dict[str, Any]) -> dict[str, Any]:
    """Rename the representation without touching its feature order.

    Models the drift that matters: a bundle ranked under one representation
    while its evidence rows are stamped with another. Every number stays right
    and every citation still resolves, so only the provenance surface can catch
    it - which is what `stale_representation_provenance` is for.
    """
    degraded = copy.deepcopy(representation)
    block = degraded.get("representation", degraded)
    block["id"] = MISMATCH_REPRESENTATION_ID
    return degraded


__all__ = [
    "MISMATCH_REPRESENTATION_ID",
    "impute_query_period",
    "insufficient_neighbour_stability",
    "insufficient_rank_uncertainty",
    "mismatch_representation",
    "unmeasure_family",
]
