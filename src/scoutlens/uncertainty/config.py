"""Strict loader for the preregistered match-bootstrap configuration."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from scoutlens.evaluation.run_manifest import REPO_ROOT

UNCERTAINTY_CONFIG_PATH = REPO_ROOT / "config" / "uncertainty.json"

_FROZEN_VALUES: dict[str, Any] = {
    "config_version": 1,
    "design_version": "match_bootstrap_v1",
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


def load_uncertainty_config(path: Path = UNCERTAINTY_CONFIG_PATH) -> dict[str, Any]:
    """Load the config without defaults and reject analytical drift."""
    config = json.loads(path.read_text(encoding="utf-8"))
    for key, expected in _FROZEN_VALUES.items():
        if config.get(key) != expected:
            raise ValueError(f"uncertainty config drift at {key}: expected {expected!r}, found {config.get(key)!r}")
    expected_minimum = config["requested_resamples"] * config["minimum_valid_fraction"]
    if not math.isclose(config["minimum_valid_resamples"], expected_minimum, rel_tol=0, abs_tol=0):
        raise ValueError("minimum_valid_resamples must equal requested_resamples * minimum_valid_fraction")
    fixture = REPO_ROOT / config["synthetic_fixture"]
    if not fixture.is_file():
        raise FileNotFoundError(f"missing uncertainty fixture: {fixture}")
    return config
