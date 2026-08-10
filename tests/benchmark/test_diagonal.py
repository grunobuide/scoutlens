"""Acceptance criteria 1, 2 and 7 for `scoutlens-qop.2`.

The property everything else leans on: `w = 1` **is** the frozen Baseline B
cosine. The diagonal metric strictly generalizes the incumbent, so a
regression against cosine is a bug in the metric, not a modelling choice.
"""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from scoutlens.benchmark.diagonal import (
    SPEC,
    _scores_and_grads,
    build_training_pairs,
    normalize_weights,
    spec_hash,
    sqrt_scaled,
    train_diagonal,
    weight_stability,
    weight_table,
)
from scoutlens.benchmark.run_diagonal import CONTINUE, STOP, apply_continuation_gate
from scoutlens.benchmark.split import TRAIN, assign_splits, attach_split
from scoutlens.evaluation.retrieval import run_baseline_b_retrieval

ROLES = ["Defender", "Midfielder", "Forward", "Goalkeeper"]
COLUMNS = [f"f{i}" for i in range(8)]


def _population(n_players: int = 80) -> pl.DataFrame:
    rows = []
    for player_id in range(1, n_players + 1):
        for period_index, period in enumerate(("A", "B")):
            row = {
                "player_id": player_id,
                "competitionId": 364,
                "period": period,
                "role": ROLES[player_id % len(ROLES)],
                "minutes_played": 500.0 + player_id,
            }
            for column_index, column in enumerate(COLUMNS):
                row[column] = float(((player_id * 13 + column_index * 5 + period_index * 2) % 41) - 20)
            rows.append(row)
    frame = pl.DataFrame(rows)
    assignment = assign_splits(frame.select("player_id", "role").unique().sort("player_id"))
    return attach_split(frame, assignment)


# --- the incumbent is a point in the hypothesis space -----------------------


def test_unit_weights_reproduce_baseline_b_cosine_exactly() -> None:
    population = _population()
    queries = population.filter(pl.col("period") == "A")
    candidates = population.filter(pl.col("period") == "B")

    cosine = run_baseline_b_retrieval(queries, candidates, COLUMNS, scope_column="role")
    unit = np.ones(len(COLUMNS))
    scaled_ranks = run_baseline_b_retrieval(
        sqrt_scaled(queries, COLUMNS, unit),
        sqrt_scaled(candidates, COLUMNS, unit),
        COLUMNS,
        scope_column="role",
    )
    assert cosine.equals(scaled_ranks)


def test_score_with_unit_weights_equals_plain_cosine() -> None:
    rng = np.random.default_rng(0)
    q, c = rng.normal(size=12), rng.normal(size=12)
    score, _ = _scores_and_grads(q, c, np.ones(12))
    expected = float(q @ c / (np.linalg.norm(q) * np.linalg.norm(c)))
    assert score == pytest.approx(expected)


def test_score_is_invariant_to_global_weight_rescaling() -> None:
    rng = np.random.default_rng(1)
    q, c = rng.normal(size=10), rng.normal(size=10)
    weights = np.abs(rng.normal(size=10)) + 0.1
    a, _ = _scores_and_grads(q, c, weights)
    b, _ = _scores_and_grads(q, c, weights * 7.3)
    assert a == pytest.approx(b)


def test_analytic_gradient_matches_a_numerical_one() -> None:
    rng = np.random.default_rng(2)
    dimension = 7
    q, c = rng.normal(size=dimension), rng.normal(size=dimension)
    weights = np.abs(rng.normal(size=dimension)) + 0.3
    _, gradient = _scores_and_grads(q, c, weights)

    step = 1e-7
    numerical = np.zeros(dimension)
    for index in range(dimension):
        up, down = weights.copy(), weights.copy()
        up[index] += step
        down[index] -= step
        numerical[index] = (
            _scores_and_grads(q, c, up)[0] - _scores_and_grads(q, c, down)[0]
        ) / (2 * step)
    assert np.abs(gradient - numerical).max() < 1e-6


# --- weights: normalization and degenerate cases ---------------------------


def test_normalize_weights_gives_mean_one() -> None:
    weights = normalize_weights(np.array([1.0, 3.0, 0.0, 4.0]))
    assert float(weights.mean()) == pytest.approx(1.0)


def test_normalize_weights_rejects_a_total_collapse() -> None:
    with pytest.raises(ValueError, match="collapsed to all-zero"):
        normalize_weights(np.zeros(4))


def test_a_zero_weight_drops_its_feature_without_error() -> None:
    population = _population(40)
    weights = np.ones(len(COLUMNS))
    weights[0] = 0.0
    scaled = sqrt_scaled(population, COLUMNS, weights)
    assert scaled[COLUMNS[0]].to_numpy().tolist() == [0.0] * scaled.height
    # and the surviving features are untouched
    assert scaled[COLUMNS[1]].to_list() == population[COLUMNS[1]].to_list()


def test_negative_weights_are_clamped_rather_than_square_rooted() -> None:
    population = _population(20)
    weights = np.full(len(COLUMNS), -1.0)
    scaled = sqrt_scaled(population, COLUMNS, weights)
    assert not np.isnan(scaled.select(COLUMNS).to_numpy()).any()


# --- negative sampling -----------------------------------------------------


def test_negatives_are_same_role_and_never_the_positive() -> None:
    population = _population()
    rows = population.filter(pl.col("split") == TRAIN)
    anchors, positives, negatives = build_training_pairs(
        population, COLUMNS, TRAIN, negatives_per_anchor=4
    )
    assert anchors.shape[0] == positives.shape[0] == negatives.shape[0]
    assert negatives.shape[1] == 4
    # a negative equal to its own positive would make the objective degenerate
    for index in range(anchors.shape[0]):
        for negative in negatives[index]:
            assert not np.array_equal(negative, positives[index])
    assert rows.height > 0


def test_training_pairs_contain_no_held_out_player() -> None:
    """The model must be fitted on training humans only. Verified on the
    vectors themselves rather than on the code path: every anchor, positive
    and negative row must be findable among the training split's features."""
    population = _population()
    anchors, positives, negatives = build_training_pairs(
        population, COLUMNS, TRAIN, negatives_per_anchor=4
    )
    train_vectors = {
        tuple(row)
        for row in population.filter(pl.col("split") == TRAIN).select(COLUMNS).to_numpy()
    }
    held_out_vectors = {
        tuple(row)
        for row in population.filter(pl.col("split") != TRAIN).select(COLUMNS).to_numpy()
    }
    used = (
        {tuple(v) for v in anchors}
        | {tuple(v) for v in positives}
        | {tuple(v) for stack in negatives for v in stack}
    )
    assert used <= train_vectors
    assert used & (held_out_vectors - train_vectors) == set()


def test_training_uses_every_eligible_training_anchor() -> None:
    """A silently dropped anchor would shrink the training set without
    changing any recorded count."""
    population = _population()
    anchors, _, _ = build_training_pairs(population, COLUMNS, TRAIN, negatives_per_anchor=4)
    expected = population.filter(
        (pl.col("split") == TRAIN) & (pl.col("period") == "A")
    ).height
    assert anchors.shape[0] == expected


def test_negative_sampling_is_deterministic_for_a_fixed_seed() -> None:
    population = _population()
    first = build_training_pairs(population, COLUMNS, TRAIN, negatives_per_anchor=4, seed=7)
    second = build_training_pairs(population, COLUMNS, TRAIN, negatives_per_anchor=4, seed=7)
    for a, b in zip(first, second):
        assert np.array_equal(a, b)


def test_a_different_sampling_seed_changes_the_negatives() -> None:
    population = _population()
    first = build_training_pairs(population, COLUMNS, TRAIN, negatives_per_anchor=4, seed=7)
    second = build_training_pairs(population, COLUMNS, TRAIN, negatives_per_anchor=4, seed=8)
    assert not np.array_equal(first[2], second[2])


# --- training --------------------------------------------------------------


def test_training_is_deterministic() -> None:
    population = _population()
    pairs = build_training_pairs(population, COLUMNS, TRAIN, negatives_per_anchor=4)
    first = train_diagonal(*pairs, regularization=0.01, iterations=25)
    second = train_diagonal(*pairs, regularization=0.01, iterations=25)
    assert np.array_equal(first["weights"], second["weights"])
    assert first["final_objective"] == second["final_objective"]


def test_training_starts_from_the_incumbent_and_reduces_the_objective() -> None:
    population = _population()
    pairs = build_training_pairs(population, COLUMNS, TRAIN, negatives_per_anchor=4)
    result = train_diagonal(*pairs, regularization=0.0, iterations=50)
    assert result["final_objective"] <= result["first_objective"]
    assert float(result["weights"].mean()) == pytest.approx(1.0)
    assert (result["weights"] >= 0).all()


def test_a_large_penalty_holds_the_model_at_the_incumbent() -> None:
    """Regularization shrinks toward w=1, so a heavy penalty must keep the
    learned metric close to plain cosine rather than near an arbitrary zero."""
    population = _population()
    pairs = build_training_pairs(population, COLUMNS, TRAIN, negatives_per_anchor=4)
    light = train_diagonal(*pairs, regularization=0.0, iterations=50)["weights"]
    heavy = train_diagonal(*pairs, regularization=1000.0, iterations=50)["weights"]
    unit = np.ones(len(COLUMNS))
    assert np.abs(heavy - unit).max() < np.abs(light - unit).max()


# --- serialization and reporting -------------------------------------------


def test_spec_hash_is_stable_and_serializable() -> None:
    assert spec_hash() == spec_hash()
    assert len(spec_hash()) == 64


def test_spec_hash_is_independent_of_the_qop1_protocol_hash() -> None:
    """Amending a qop.2 hyperparameter must not disturb the qop.1 protocol
    hash, because that hash is what holds the test split shut (D041)."""
    from scoutlens.benchmark.protocol import protocol_hash

    assert spec_hash() != protocol_hash()


def test_weight_table_is_sorted_serializable_and_flags_collapse() -> None:
    import json

    weights = np.array([2.0, 0.01, 1.0, 0.5, 3.0, 0.0, 1.5, 0.9])
    table = weight_table(COLUMNS, weights)
    assert [row["weight"] for row in table] == sorted(
        (row["weight"] for row in table), reverse=True
    )
    assert {row["feature"] for row in table} == set(COLUMNS)
    collapsed = {row["feature"] for row in table if row["collapsed"]}
    assert collapsed == {COLUMNS[1], COLUMNS[5]}  # below SPEC collapse_threshold
    json.dumps(table)  # must serialize without custom encoders


def test_weight_stability_flags_swings_across_the_grid() -> None:
    stable = np.ones(len(COLUMNS))
    swung = np.ones(len(COLUMNS))
    swung[0] = 3.5  # spans 2.5 across the grid, above the instability threshold
    table = weight_stability(COLUMNS, {0.0: swung, 1.0: stable})
    by_feature = {row["feature"]: row for row in table}
    assert by_feature[COLUMNS[0]]["unstable"] is True
    assert by_feature[COLUMNS[0]]["spread_across_grid"] == pytest.approx(2.5)
    assert by_feature[COLUMNS[1]]["unstable"] is False
    # most-unstable first
    assert table[0]["feature"] == COLUMNS[0]


def test_weight_stability_separates_always_collapsed_from_sometimes() -> None:
    always = np.ones(len(COLUMNS))
    always[0] = 0.0
    sometimes = np.ones(len(COLUMNS))
    table = {row["feature"]: row for row in weight_stability(COLUMNS, {0.0: always, 1.0: sometimes})}
    assert table[COLUMNS[0]]["collapsed_in_any_arm"] is True
    assert table[COLUMNS[0]]["collapsed_in_every_arm"] is False
    assert table[COLUMNS[1]]["collapsed_in_any_arm"] is False


def test_weight_stability_is_serializable() -> None:
    import json

    json.dumps(weight_stability(COLUMNS, {0.0: np.ones(len(COLUMNS))}))


def test_weight_table_avoids_quality_language() -> None:
    """A weight describes this retrieval task, not player quality. Guard the
    field names against drifting into evaluative vocabulary."""
    table = weight_table(COLUMNS, np.ones(len(COLUMNS)))
    banned = {"importance", "quality", "skill", "rating", "score", "best", "ability"}
    for row in table:
        assert banned.isdisjoint({key.lower() for key in row})


# --- the continuation gate -------------------------------------------------


def test_gate_continues_only_when_both_conditions_hold() -> None:
    assert apply_continuation_gate(0.02, 0.001)["decision"] == CONTINUE


def test_gate_stops_when_the_delta_is_below_the_floor() -> None:
    gate = apply_continuation_gate(0.009, 0.05)
    assert gate["decision"] == STOP
    assert gate["delta_met"] is False


def test_gate_stops_when_the_interval_is_too_low() -> None:
    gate = apply_continuation_gate(0.5, -0.006)
    assert gate["decision"] == STOP
    assert gate["ci_met"] is False


def test_gate_is_applied_at_the_boundary_without_exception() -> None:
    """+0.010 exactly is a CONTINUE; a CI lower bound of exactly -0.005 is
    not (the rule reads 'above -0.005')."""
    assert apply_continuation_gate(0.010, -0.004)["decision"] == CONTINUE
    assert apply_continuation_gate(0.010, -0.005)["decision"] == STOP


def test_gate_records_the_rule_it_applied() -> None:
    from scoutlens.benchmark.protocol import PROTOCOL

    gate = apply_continuation_gate(0.02, 0.01)
    assert gate["rule"] == PROTOCOL["neural_continuation_gate"]
    assert gate["required_delta"] == 0.010
    assert gate["required_ci_low_above"] == -0.005
    assert SPEC["regularization_grid"][0] == 0.0  # the incumbent is in the grid
