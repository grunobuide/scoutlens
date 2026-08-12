"""Strict loader for the preregistered match-bootstrap configuration.

Two designs are loadable and they share one estimand. `match_bootstrap_v1`
scores with unweighted cosine; `match_bootstrap_diagonal_v1` scores with the
D045 diagonal representation. **Everything else is frozen identically for
both** — seed, draw count, strata, cohort policy, invalidity rules, interval
method and availability threshold — because changing the scorer is the only
thing this second design is allowed to change.

The diagonal design additionally pins the representation it describes. An
interval computed under one representation does not describe rankings produced
by another, so lineage is checked before any computation starts.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from scoutlens.evaluation.run_manifest import REPO_ROOT

UNCERTAINTY_CONFIG_PATH = REPO_ROOT / "config" / "uncertainty.json"
DIAGONAL_CONFIG_PATH = REPO_ROOT / "config" / "uncertainty-diagonal.json"

COSINE_DESIGN = "match_bootstrap_v1"
DIAGONAL_DESIGN = "match_bootstrap_diagonal_v1"
DIAGONAL_RANKING_METHOD = "weighted_cosine_diagonal_v1"
SUPPORTED_DESIGNS = (COSINE_DESIGN, DIAGONAL_DESIGN)

# Frozen for every design. `design_version` is deliberately absent: it is the
# one value a second design may differ on.
_FROZEN_VALUES: dict[str, Any] = {
    "config_version": 1,
    "seed": 1729,
    "requested_resamples": 500,
    "interval": "percentile_95",
    "interval_quantiles": [0.025, 0.975],
    "quantile_method": "linear_type_7",
    "minimum_valid_resamples": 450,
    "minimum_valid_fraction": 0.9,
    "resampling_unit": "whole_match_stratified_by_competition_and_period",
    "cohort_policy": "fixed_observed_eligible_cohort",
    "strata": ["competitionId", "period"],
    "sample_with_replacement": True,
    "stratum_sample_size": "observed_distinct_match_count",
    "duplicate_match_weighting": "integer_multiplicity_for_events_and_minutes",
    "draw_algorithm": "sha256_counter_rejection_v1",
    "absent_candidate_policy": "rank_after_present_candidates_by_identity_key",
    "absent_query_policy": "invalidate_subject_replicate",
    "zero_event_policy": "positive_minutes_zero_events_is_observed",
    "raw_null_policy": "invalidate_only_that_feature_measure",
    "identity_order": ["player_id_ascending", "competition_id_ascending"],
    "percentile_tie_method": "average_rank",
}

_REQUIRED_REPRESENTATION_FIELDS = (
    "id",
    "ranking_method",
    "weight_digest",
    "feature_order",
    "feature_order_digest",
    "feature_count",
    "weights",
    "excluded_features",
    "training",
    "lineage",
)


def _validate_representation(config: dict[str, Any], path: Path) -> None:
    """Fail before computation when the pinned representation is not coherent.

    Recomputes both digests rather than trusting them: a digest carried
    alongside the content it describes proves nothing.
    """
    from scoutlens.showcase.validation import feature_order_digest, weight_digest

    representation = config.get("representation")
    if not isinstance(representation, dict):
        raise ValueError(
            f"{path}: design {DIAGONAL_DESIGN} requires a 'representation' block; an interval "
            "that cannot name the representation it was computed under is unusable"
        )
    missing = [field for field in _REQUIRED_REPRESENTATION_FIELDS if field not in representation]
    if missing:
        raise ValueError(f"{path}: representation is missing {missing}")

    if representation["ranking_method"] != DIAGONAL_RANKING_METHOD:
        raise ValueError(
            f"{path}: representation.ranking_method must be {DIAGONAL_RANKING_METHOD}, "
            f"found {representation['ranking_method']}"
        )
    if config.get("ranking_method") != DIAGONAL_RANKING_METHOD:
        raise ValueError(
            f"{path}: ranking_method must be {DIAGONAL_RANKING_METHOD} for design {DIAGONAL_DESIGN}"
        )

    order = list(representation["feature_order"])
    weights = list(representation["weights"])
    if len(order) != representation["feature_count"] or len(weights) != representation["feature_count"]:
        raise ValueError(
            f"{path}: feature_count {representation['feature_count']} disagrees with "
            f"{len(order)} ordered features and {len(weights)} weights"
        )
    if [entry["feature_id"] for entry in weights] != order:
        raise ValueError(
            f"{path}: weights are not in feature_order; the same weights in a different order "
            "describe a different metric"
        )
    if any(float(entry["weight"]) < 0 for entry in weights):
        raise ValueError(f"{path}: diagonal weights must be non-negative")

    recomputed_weights = weight_digest(weights)
    if representation["weight_digest"] != recomputed_weights:
        raise ValueError(
            f"{path}: weight_digest {representation['weight_digest']} does not match the pinned "
            f"weights (recomputed {recomputed_weights})"
        )
    recomputed_order = feature_order_digest(order)
    if representation["feature_order_digest"] != recomputed_order:
        raise ValueError(
            f"{path}: feature_order_digest {representation['feature_order_digest']} does not match "
            f"the pinned feature order (recomputed {recomputed_order})"
        )

    lineage = representation["lineage"]
    for field in ("protocol_hash", "spec_hash", "decision_records"):
        if field not in lineage:
            raise ValueError(f"{path}: representation.lineage is missing {field}")


def load_uncertainty_config(path: Path = UNCERTAINTY_CONFIG_PATH) -> dict[str, Any]:
    """Load the config without defaults and reject analytical drift."""
    config = json.loads(path.read_text(encoding="utf-8"))

    design = config.get("design_version")
    if design not in SUPPORTED_DESIGNS:
        raise ValueError(
            f"{path}: unsupported design_version {design!r}; known designs: {list(SUPPORTED_DESIGNS)}"
        )

    for key, expected in _FROZEN_VALUES.items():
        if config.get(key) != expected:
            raise ValueError(
                f"uncertainty config drift at {key}: expected {expected!r}, found {config.get(key)!r}"
            )
    expected_minimum = config["requested_resamples"] * config["minimum_valid_fraction"]
    if not math.isclose(config["minimum_valid_resamples"], expected_minimum, rel_tol=0, abs_tol=0):
        raise ValueError("minimum_valid_resamples must equal requested_resamples * minimum_valid_fraction")

    if design == DIAGONAL_DESIGN:
        if config.get("resampling_design") != COSINE_DESIGN:
            raise ValueError(
                f"{path}: design {DIAGONAL_DESIGN} must declare resampling_design "
                f"{COSINE_DESIGN!r}; changing the scorer must not re-seed the draw plan, or feature-only summaries could no longer be compared to the frozen run"
            )
        _validate_representation(config, path)
    elif "representation" in config:
        raise ValueError(
            f"{path}: design {COSINE_DESIGN} must not pin a representation; unweighted cosine "
            "is not a learned representation"
        )

    fixture = REPO_ROOT / config["synthetic_fixture"]
    if not fixture.is_file():
        raise FileNotFoundError(f"missing uncertainty fixture: {fixture}")
    return config


def feature_weight_vector(config: dict[str, Any], feature_columns: list[str]) -> list[float] | None:
    """Diagonal weights ordered to `feature_columns`, or None for cosine.

    The representation is defined on the canonical-28 like-for-like set while
    the engine ranks over all 32 Wyscout features, so the four excluded
    features score with weight 0. They are read from the config's declared
    `excluded_features` rather than defaulted: an implicit zero would be an
    unpinned metric, and a feature that is in neither list fails closed rather
    than being silently dropped or silently weighted.
    """
    if config.get("design_version") != DIAGONAL_DESIGN:
        return None
    representation = config["representation"]
    by_feature = {entry["feature_id"]: float(entry["weight"]) for entry in representation["weights"]}
    excluded = set(representation["excluded_features"])
    overlap = excluded & set(by_feature)
    if overlap:
        raise ValueError(
            f"representation {representation['id']} both weights and excludes {sorted(overlap)}"
        )

    unpinned = [
        column for column in feature_columns if column not in by_feature and column not in excluded
    ]
    if unpinned:
        raise ValueError(
            f"representation {representation['id']} pins neither a weight nor an exclusion for "
            f"{unpinned}; scoring an unpinned feature would invent a metric"
        )
    return [by_feature.get(column, 0.0) for column in feature_columns]
