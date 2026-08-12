"""Diagonal match-bootstrap design (`scoutlens-qop.6.3`).

The load-bearing claims: the scorer is the *only* thing that changes, lineage
is checked before any computation, and the cosine design is untouched.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from scoutlens.features.aggregation import FEATURE_COLUMNS
from scoutlens.uncertainty.config import (
    COSINE_DESIGN,
    DIAGONAL_CONFIG_PATH,
    DIAGONAL_DESIGN,
    DIAGONAL_RANKING_METHOD,
    UNCERTAINTY_CONFIG_PATH,
    feature_weight_vector,
    load_uncertainty_config,
)
from scoutlens.uncertainty.engine import checkpoint_dir_for, output_dir_for
from scoutlens.uncertainty.ranking import apply_diagonal_weights, compute_replicate_ranks


def _write(tmp_path, config: dict):
    path = tmp_path / "uncertainty-diagonal.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


@pytest.fixture
def diagonal_config() -> dict:
    return json.loads(DIAGONAL_CONFIG_PATH.read_text(encoding="utf-8"))


# --- the scorer is the only difference ------------------------------------


def test_unit_weights_reproduce_unweighted_cosine_exactly() -> None:
    """sqrt(1) scaling is the identity, so the diagonal path with unit weights
    must produce bit-identical ranks to the cosine path."""
    rng = np.random.default_rng(0)
    size, dimension = 12, 6
    query = rng.normal(size=(size, dimension))
    candidate = rng.normal(size=(size, dimension))
    minutes = rng.uniform(500, 3000, size=size)
    present = np.ones(size, dtype=bool)
    roles = np.array(["Midfielder"] * size)
    players = np.arange(1, size + 1)
    neighbours = np.tile(np.array([1, 2, 3, 4, 5]), (size, 1))

    shared = dict(
        query_features=query,
        candidate_features=candidate,
        query_minutes=minutes,
        candidate_minutes=minutes,
        query_present=present,
        candidate_present=present,
        roles=roles,
        player_ids=players,
        neighbor_indices=neighbours,
    )
    cosine = compute_replicate_ranks(**shared)
    unit = compute_replicate_ranks(**shared, feature_weights=np.ones(dimension))
    assert np.array_equal(cosine.global_self, unit.global_self)
    assert np.array_equal(cosine.within_role_self, unit.within_role_self)
    assert np.array_equal(cosine.neighbor_ranks, unit.neighbor_ranks)


def test_none_weights_leave_features_untouched() -> None:
    values = np.array([[1.0, -2.0, 3.0]])
    assert apply_diagonal_weights(values, None) is values


def test_weights_scale_by_their_square_root() -> None:
    values = np.array([[1.0, 1.0, 1.0]])
    scaled = apply_diagonal_weights(values, np.array([4.0, 9.0, 0.0]))
    assert np.allclose(scaled, [[2.0, 3.0, 0.0]])


def test_a_zero_weight_removes_a_feature_from_the_score() -> None:
    weights = np.array([1.0, 0.0])
    a = apply_diagonal_weights(np.array([[3.0, 99.0]]), weights)
    b = apply_diagonal_weights(np.array([[3.0, -5.0]]), weights)
    assert np.allclose(a, b)


def test_a_mismatched_weight_vector_fails_closed() -> None:
    with pytest.raises(ValueError, match="diagonal weight vector has"):
        apply_diagonal_weights(np.zeros((2, 5)), np.ones(4))


# --- the configuration ----------------------------------------------------


def test_the_diagonal_config_loads_and_pins_a_representation(diagonal_config) -> None:
    config = load_uncertainty_config(DIAGONAL_CONFIG_PATH)
    assert config["design_version"] == DIAGONAL_DESIGN
    assert config["ranking_method"] == DIAGONAL_RANKING_METHOD
    representation = config["representation"]
    assert representation["id"].startswith("rep-")
    assert representation["feature_count"] == 28
    assert len(representation["weights"]) == 28


def test_the_cosine_config_is_unchanged_and_pins_nothing() -> None:
    config = load_uncertainty_config(UNCERTAINTY_CONFIG_PATH)
    assert config["design_version"] == COSINE_DESIGN
    assert "representation" not in config
    assert feature_weight_vector(config, list(FEATURE_COLUMNS)) is None


def test_an_unknown_design_is_rejected(tmp_path, diagonal_config) -> None:
    diagonal_config["design_version"] = "match_bootstrap_v3"
    with pytest.raises(ValueError, match="unsupported design_version"):
        load_uncertainty_config(_write(tmp_path, diagonal_config))


def test_a_tampered_weight_is_caught_before_computation(tmp_path, diagonal_config) -> None:
    diagonal_config["representation"]["weights"][0]["weight"] += 0.25
    with pytest.raises(ValueError, match="weight_digest"):
        load_uncertainty_config(_write(tmp_path, diagonal_config))


def test_a_reordered_feature_list_is_caught_before_computation(tmp_path, diagonal_config) -> None:
    order = diagonal_config["representation"]["feature_order"]
    order[0], order[1] = order[1], order[0]
    with pytest.raises(ValueError, match="weights are not in feature_order|feature_order_digest"):
        load_uncertainty_config(_write(tmp_path, diagonal_config))


def test_a_missing_representation_is_rejected(tmp_path, diagonal_config) -> None:
    del diagonal_config["representation"]
    with pytest.raises(ValueError, match="requires a 'representation' block"):
        load_uncertainty_config(_write(tmp_path, diagonal_config))


def test_a_wrong_ranking_method_is_rejected(tmp_path, diagonal_config) -> None:
    diagonal_config["representation"]["ranking_method"] = "cosine_v1"
    with pytest.raises(ValueError, match="ranking_method must be"):
        load_uncertainty_config(_write(tmp_path, diagonal_config))


def test_missing_lineage_is_rejected(tmp_path, diagonal_config) -> None:
    del diagonal_config["representation"]["lineage"]["protocol_hash"]
    with pytest.raises(ValueError, match="lineage is missing protocol_hash"):
        load_uncertainty_config(_write(tmp_path, diagonal_config))


def test_the_cosine_design_may_not_pin_a_representation(tmp_path, diagonal_config) -> None:
    diagonal_config["design_version"] = COSINE_DESIGN
    diagonal_config.pop("resampling_design", None)
    with pytest.raises(ValueError, match="must not pin a representation"):
        load_uncertainty_config(_write(tmp_path, diagonal_config))


def test_changing_the_scorer_may_not_reseed_the_draw_plan(tmp_path, diagonal_config) -> None:
    """The draw plan is addressed by the resampling design. Re-seeding it would
    make feature-only summaries incomparable to the frozen run."""
    diagonal_config["resampling_design"] = DIAGONAL_DESIGN
    with pytest.raises(ValueError, match="must declare resampling_design"):
        load_uncertainty_config(_write(tmp_path, diagonal_config))


def test_frozen_resampling_values_still_cannot_drift(tmp_path, diagonal_config) -> None:
    diagonal_config["requested_resamples"] = 100
    with pytest.raises(ValueError, match="config drift at requested_resamples"):
        load_uncertainty_config(_write(tmp_path, diagonal_config))


def test_the_seed_is_the_same_1729_for_both_designs() -> None:
    assert load_uncertainty_config(UNCERTAINTY_CONFIG_PATH)["seed"] == 1729
    assert load_uncertainty_config(DIAGONAL_CONFIG_PATH)["seed"] == 1729


# --- weight vector alignment ----------------------------------------------


def test_weights_align_to_the_engine_feature_columns() -> None:
    config = load_uncertainty_config(DIAGONAL_CONFIG_PATH)
    weights = feature_weight_vector(config, list(FEATURE_COLUMNS))
    assert weights is not None
    assert len(weights) == len(FEATURE_COLUMNS)
    excluded = set(config["representation"]["excluded_features"])
    for column, weight in zip(FEATURE_COLUMNS, weights, strict=True):
        if column in excluded:
            assert weight == 0.0, column


def test_an_unpinned_feature_fails_closed(diagonal_config) -> None:
    config = load_uncertainty_config(DIAGONAL_CONFIG_PATH)
    with pytest.raises(ValueError, match="pins neither a weight nor an exclusion"):
        feature_weight_vector(config, [*FEATURE_COLUMNS, "a_feature_nobody_pinned"])


def test_a_feature_cannot_be_both_weighted_and_excluded() -> None:
    config = load_uncertainty_config(DIAGONAL_CONFIG_PATH)
    tampered = json.loads(json.dumps(config))
    tampered["representation"]["excluded_features"].append(
        tampered["representation"]["weights"][0]["feature_id"]
    )
    with pytest.raises(ValueError, match="both weights and excludes"):
        feature_weight_vector(tampered, list(FEATURE_COLUMNS))


# --- artifact isolation ---------------------------------------------------


def test_each_design_writes_to_its_own_directory() -> None:
    """A diagonal run must not be able to overwrite the frozen cosine run."""
    assert output_dir_for(COSINE_DESIGN) != output_dir_for(DIAGONAL_DESIGN)
    assert checkpoint_dir_for(COSINE_DESIGN) != checkpoint_dir_for(DIAGONAL_DESIGN)
    assert output_dir_for(DIAGONAL_DESIGN).name == DIAGONAL_DESIGN
    assert output_dir_for(COSINE_DESIGN).name == COSINE_DESIGN
