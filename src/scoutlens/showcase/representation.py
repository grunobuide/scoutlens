"""The frozen D045 diagonal representation, verified before it is used.

`scoutlens-qop.6.4.1`. This module owns one question: *may these weights be
used to produce showcase-v2 rankings?* It answers by recomputing the identity
rather than reading it — a digest carried alongside the content it describes
proves nothing — and by refusing anything it cannot account for.

Two frames, and the distinction is the whole point:

- the **measurement frame** is the standardized feature frame, unchanged. Every
  stored fingerprint, ``query_global_z`` and ``candidate_global_z`` comes from
  it, because those describe the *player*;
- the **ranking frame** is that frame scaled by ``sqrt(w)``. Only it is fed to
  the audited ranking path, because cosine over ``sqrt(w)``-scaled vectors *is*
  the diagonal score.

Scaling the measurement frame would silently replace every published z-score
with a weighted number that means nothing to a reader. That is the failure this
module exists to make impossible.
"""

from __future__ import annotations

import dataclasses
import json
import math
from pathlib import Path
from typing import Any

from scoutlens.evaluation.run_manifest import REPO_ROOT

DIAGONAL_CONFIG_PATH = REPO_ROOT / "config" / "uncertainty-diagonal.json"
DIAGONAL_BENCHMARK_PATH = REPO_ROOT / "artifacts" / "benchmark" / "diagonal-results.json"

RANKING_METHOD = "weighted_cosine_diagonal_v1"
REQUIRED_DECISION_RECORDS = ("D042", "D044", "D045", "D047")

# Reconstruction tolerance shared by both evidence decompositions (D047 uses
# 1e-6 at the contract boundary; the producer holds itself to 1e-9).
CONTRIBUTION_TOLERANCE = 1e-9


@dataclasses.dataclass(frozen=True)
class DiagonalRepresentation:
    """A verified representation. Constructing one is the permission to rank."""

    id: str
    weights_by_feature: dict[str, float]
    excluded_features: tuple[str, ...]
    feature_order: tuple[str, ...]
    weight_digest: str
    feature_order_digest: str
    lineage: dict[str, Any]

    def weight_vector(self, feature_columns: list[str]) -> list[float]:
        """Weights aligned to `feature_columns`, excluded features at zero.

        Fails closed on any column that is neither weighted nor explicitly
        excluded: an implicit zero would be an unpinned metric, and silently
        dropping a feature from the score is exactly the kind of change that
        leaves no trace in the artifact.
        """
        excluded = set(self.excluded_features)
        unpinned = [
            column
            for column in feature_columns
            if column not in self.weights_by_feature and column not in excluded
        ]
        if unpinned:
            raise ValueError(
                f"representation {self.id} pins neither a weight nor an exclusion for {unpinned}; "
                "scoring an unpinned feature would invent a metric"
            )
        return [self.weights_by_feature.get(column, 0.0) for column in feature_columns]

    def sqrt_weight_vector(self, feature_columns: list[str]) -> list[float]:
        """`sqrt(w)`, the factor that turns cosine into the diagonal score."""
        return [math.sqrt(value) for value in self.weight_vector(feature_columns)]


def _verify_against_benchmark(weights: list[dict], benchmark_path: Path) -> None:
    """The pinned weights must be the ones D042 actually recorded."""
    if not benchmark_path.is_file():
        raise FileNotFoundError(f"missing D042 benchmark artifact: {benchmark_path}")
    recorded = json.loads(benchmark_path.read_text(encoding="utf-8"))
    by_feature = {row["feature"]: float(row["weight"]) for row in recorded["weights"]}
    pinned = {entry["feature_id"]: float(entry["weight"]) for entry in weights}

    missing = sorted(set(by_feature) - set(pinned))
    extra = sorted(set(pinned) - set(by_feature))
    if missing or extra:
        raise ValueError(
            f"pinned weights disagree with {benchmark_path.name}: missing {missing}, extra {extra}"
        )
    drifted = sorted(
        feature
        for feature, value in pinned.items()
        if not math.isclose(value, by_feature[feature], rel_tol=0, abs_tol=1e-12)
    )
    if drifted:
        raise ValueError(
            f"pinned weights drifted from {benchmark_path.name} for {drifted}; the representation "
            "must be the one D042 recorded, not a rounded or re-fitted copy"
        )


def load_representation(
    config_path: Path = DIAGONAL_CONFIG_PATH,
    *,
    benchmark_path: Path = DIAGONAL_BENCHMARK_PATH,
    verify_benchmark: bool = True,
) -> DiagonalRepresentation:
    """Load and fully verify the frozen representation.

    Every check runs before any weight is returned, so a caller cannot rank
    with a representation that failed verification.
    """
    # Deferred: validation imports the builder, which imports this module. The
    # digest definitions must stay in validation so the producer and the
    # contract boundary cannot drift apart.
    from scoutlens.showcase.validation import feature_order_digest, weight_digest

    config = json.loads(config_path.read_text(encoding="utf-8"))
    representation = config.get("representation")
    if not isinstance(representation, dict):
        raise ValueError(f"{config_path}: no representation block to load")

    if representation.get("ranking_method") != RANKING_METHOD:
        raise ValueError(
            f"{config_path}: ranking_method must be {RANKING_METHOD}, "
            f"found {representation.get('ranking_method')}"
        )

    order = list(representation["feature_order"])
    weights = list(representation["weights"])
    excluded = list(representation["excluded_features"])

    if len(order) != int(representation["feature_count"]):
        raise ValueError(
            f"{config_path}: feature_count {representation['feature_count']} disagrees with "
            f"{len(order)} ordered features"
        )
    declared = [entry["feature_id"] for entry in weights]
    if declared != order:
        raise ValueError(
            f"{config_path}: weights are not in feature_order; the same weights in a different "
            "order describe a different metric"
        )
    duplicated = sorted({name for name in order if order.count(name) > 1})
    if duplicated:
        raise ValueError(f"{config_path}: feature_order repeats {duplicated}")
    overlap = sorted(set(excluded) & set(order))
    if overlap:
        raise ValueError(f"{config_path}: {overlap} are both weighted and excluded")
    negative = sorted(entry["feature_id"] for entry in weights if float(entry["weight"]) < 0)
    if negative:
        raise ValueError(
            f"{config_path}: negative weights for {negative}; a diagonal metric is not defined "
            "for a negative weight"
        )

    recomputed_weights = weight_digest(weights)
    if representation["weight_digest"] != recomputed_weights:
        raise ValueError(
            f"{config_path}: weight_digest {representation['weight_digest']} does not match the "
            f"pinned weights (recomputed {recomputed_weights})"
        )
    recomputed_order = feature_order_digest(order)
    if representation["feature_order_digest"] != recomputed_order:
        raise ValueError(
            f"{config_path}: feature_order_digest {representation['feature_order_digest']} does "
            f"not match the pinned order (recomputed {recomputed_order})"
        )

    expected_id = f"rep-{recomputed_weights[:16]}"
    if representation["id"] != expected_id:
        raise ValueError(
            f"{config_path}: representation id {representation['id']} is not derived from its own "
            f"weight digest (expected {expected_id})"
        )

    lineage = representation["lineage"]
    for field in ("protocol_hash", "spec_hash", "decision_records"):
        if field not in lineage:
            raise ValueError(f"{config_path}: representation.lineage is missing {field}")
    missing_records = [
        record for record in REQUIRED_DECISION_RECORDS if record not in lineage["decision_records"]
    ]
    if missing_records:
        raise ValueError(
            f"{config_path}: representation.lineage omits {missing_records}; a v2 representation "
            "must cite the decisions that authorized it"
        )

    if verify_benchmark:
        _verify_against_benchmark(weights, benchmark_path)

    return DiagonalRepresentation(
        id=str(representation["id"]),
        weights_by_feature={entry["feature_id"]: float(entry["weight"]) for entry in weights},
        excluded_features=tuple(excluded),
        feature_order=tuple(order),
        weight_digest=recomputed_weights,
        feature_order_digest=recomputed_order,
        lineage=dict(lineage),
    )
