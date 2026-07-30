from __future__ import annotations

from scoutlens.uncertainty.config import UNCERTAINTY_CONFIG_PATH, load_uncertainty_config
from scoutlens.uncertainty.synthetic import validate_synthetic_fixture


def test_preregistered_synthetic_truth_cases_all_pass() -> None:
    config = load_uncertainty_config()
    fixture_path = UNCERTAINTY_CONFIG_PATH.parents[1] / config["synthetic_fixture"]
    result = validate_synthetic_fixture(fixture_path, config)

    assert result["all_passed"] is True
    assert all(result["cases"].values())
    assert result["invariant_width"] == 0
    assert result["volatile_width"] > 0
    assert result["missing_player_valid_resamples"] < config["minimum_valid_resamples"]
