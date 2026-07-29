from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "config" / "uncertainty.json"
FIXTURE_PATH = REPO_ROOT / "tests" / "uncertainty" / "fixtures" / "match_bootstrap_v1.json"
METHOD_PATH = REPO_ROOT / "docs" / "uncertainty-method.md"
DECISIONS_PATH = REPO_ROOT / "docs" / "decisions-log.md"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_match_bootstrap_config_pins_the_preregistered_design() -> None:
    config = _load(CONFIG_PATH)

    assert config["config_version"] == 1
    assert config["design_version"] == "match_bootstrap_v1"
    assert config["seed"] == 1729
    assert config["requested_resamples"] == 500
    assert config["interval"] == "percentile_95"
    assert config["interval_quantiles"] == [0.025, 0.975]
    assert config["quantile_method"] == "linear_type_7"
    assert config["minimum_valid_resamples"] == 450
    assert config["minimum_valid_fraction"] == 0.9
    assert config["minimum_valid_resamples"] == (config["requested_resamples"] * config["minimum_valid_fraction"])
    assert config["resampling_unit"] == "whole_match_stratified_by_competition_and_period"
    assert config["cohort_policy"] == "fixed_observed_eligible_cohort"
    assert config["sample_with_replacement"] is True
    assert config["identity_order"] == ["player_id_ascending", "competition_id_ascending"]
    assert config["warning"] == (
        "Match-bootstrap intervals describe sampling stability in observed matches, not causal effects, "
        "provider annotation error, or future performance."
    )
    assert config["synthetic_fixture"] == FIXTURE_PATH.relative_to(REPO_ROOT).as_posix()


def test_assertion_tolerances_and_ordering_are_frozen() -> None:
    config = _load(CONFIG_PATH)

    assert config["assertion_tolerances"] == {
        "raw_feature_abs": 1e-12,
        "percentile_abs": 1e-9,
        "similarity_abs": 1e-12,
        "cosine_reconstruction_abs": 1e-9,
        "interval_bound_abs": 1e-12,
        "rate_abs": 1e-12,
        "rank_exact": True,
        "ordering_exact": True,
    }
    assert config["stratum_order"] == ["competitionId_ascending", "period_a_before_b"]
    assert config["source_match_order"] == "match_id_ascending"
    assert config["draw_algorithm"] == "sha256_counter_rejection_v1"
    assert config["percentile_tie_method"] == "average_rank"

    vector = config["draw_algorithm_test_vector"]
    digest = hashlib.sha256(vector["payload"].encode("utf-8")).digest()
    unsigned = int.from_bytes(digest[:8], "big")
    assert digest.hex() == vector["sha256"]
    assert unsigned == vector["uint64_big_endian"]
    assert unsigned % vector["source_size"] == vector["selected_source_index"]


def test_synthetic_fixture_covers_every_preregistered_truth_case() -> None:
    fixture = _load(FIXTURE_PATH)
    case_ids = {case["case_id"] for case in fixture["truth_cases"]}

    assert fixture["fixture_version"] == "match_bootstrap_v1-fixture-1"
    assert {
        "invariant_player",
        "high_variance_low_support",
        "missing_in_resample",
        "tied_candidates",
        "multi_competition_strata",
        "duplicate_match_weighting",
    } <= case_ids

    tie_case = next(case for case in fixture["truth_cases"] if case["case_id"] == "tied_candidates")
    assert tie_case["expected_order"] == sorted(
        tie_case["candidates"], key=lambda item: (item["player_id"], item["competition_id"])
    )


def test_forced_draws_preserve_strata_size_and_allow_multiplicity() -> None:
    fixture = _load(FIXTURE_PATH)
    matches_by_stratum: dict[str, set[int]] = defaultdict(set)
    for match in fixture["matches"]:
        matches_by_stratum[f"{match['competition_id']}:{match['period']}"].add(match["match_id"])

    saw_duplicate = False
    for plan in fixture["forced_draw_plans"]:
        assert set(plan["draws"]) == set(matches_by_stratum)
        for stratum, draws in plan["draws"].items():
            assert len(draws) == len(matches_by_stratum[stratum])
            assert set(draws) <= matches_by_stratum[stratum]
            saw_duplicate |= len(set(draws)) < len(draws)
    assert saw_duplicate


def test_method_review_checklist_covers_every_showcase_uncertainty_field() -> None:
    method = METHOD_PATH.read_text(encoding="utf-8")
    qualified_fields = (
        "uncertainty.status",
        "uncertainty.design_version",
        "uncertainty.seed",
        "uncertainty.requested_resamples",
        "uncertainty.valid_resamples",
        "uncertainty.interval",
        "uncertainty.resampling_unit",
        "uncertainty.cohort_policy",
        "uncertainty.warning",
        "feature.uncertainty.status",
        "feature.uncertainty.valid_resamples",
        "feature.uncertainty.raw_ci_95",
        "feature.uncertainty.within_role_percentile_ci_95",
        "retrieval.uncertainty.status",
        "retrieval.uncertainty.valid_resamples",
        "retrieval.uncertainty.median_rank",
        "retrieval.uncertainty.rank_ci_95",
        "retrieval.uncertainty.recall_at_1_rate",
        "retrieval.uncertainty.recall_at_5_rate",
        "retrieval.uncertainty.recall_at_10_rate",
        "neighbor.stability.status",
        "neighbor.stability.valid_resamples",
        "neighbor.stability.top_5_selection_rate",
        "neighbor.stability.median_rank",
        "neighbor.stability.rank_ci_95",
        "players.index.uncertainty_status",
    )
    for field in qualified_fields:
        assert f"`{field}`" in method

    decisions = DECISIONS_PATH.read_text(encoding="utf-8")
    assert "## D031 — 2026-07-29 — Match-bootstrap v1 is frozen before execution" in decisions
    assert "`match_bootstrap_v1`" in decisions
