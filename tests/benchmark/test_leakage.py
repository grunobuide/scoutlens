"""Acceptance criterion 2, second half: no fitted statistic reads
validation or test.

The published experiments fit the scaler on the whole population being
compared (D008), which is correct for a descriptive result and wrong for a
confirmatory one. These tests prove the benchmark does not inherit that
behaviour — not by reading the code, but by corrupting the held-out rows
and showing the fitted statistics do not move.
"""

from __future__ import annotations

import polars as pl
import pytest

from scoutlens.benchmark.evaluate import evaluate_split, fit_train_scaler
from scoutlens.benchmark.features import CANONICAL_28
from scoutlens.benchmark.split import TEST, TRAIN, VALIDATION, assign_splits, attach_split

ROLES = ["Defender", "Midfielder", "Forward", "Goalkeeper"]
COLUMNS = list(CANONICAL_28)


def _population(n_players: int = 120) -> pl.DataFrame:
    """Two rows (period A and B) per player, with deterministic, distinct
    feature values so a corrupted subset is unmistakable."""
    rows = []
    for player_id in range(1, n_players + 1):
        for period_index, period in enumerate(("A", "B")):
            row = {
                "player_id": player_id,
                "competitionId": 364,
                "period": period,
                "role": ROLES[player_id % len(ROLES)],
                "minutes_played": 500.0 + player_id + period_index,
            }
            for column_index, column in enumerate(COLUMNS):
                row[column] = float((player_id * 7 + column_index * 3 + period_index) % 97)
            rows.append(row)
    frame = pl.DataFrame(rows)
    assignment = assign_splits(frame.select("player_id", "role").unique().sort("player_id"))
    return attach_split(frame, assignment)


def test_scaler_is_unchanged_when_validation_and_test_are_corrupted() -> None:
    population = _population()
    clean = fit_train_scaler(population, COLUMNS)

    corrupted = population.with_columns(
        [
            pl.when(pl.col("split") == TRAIN)
            .then(pl.col(column))
            .otherwise(pl.col(column) * 1_000_000 + 12345)
            .alias(column)
            for column in COLUMNS
        ]
    )
    after = fit_train_scaler(corrupted, COLUMNS)

    assert clean == after, "the fitted scaler moved when held-out rows changed"


def test_scaler_matches_one_fit_on_the_training_rows_alone() -> None:
    """Independent derivation: fitting on a frame that physically contains
    only training rows must give the identical result."""
    from scoutlens.benchmark.evaluate import quantize_scaler
    from scoutlens.evaluation.similarity import fit_scaler

    population = _population()
    via_helper = fit_train_scaler(population, COLUMNS)
    train_only = population.filter(pl.col("split") == TRAIN)
    # same quantization on both sides: the claim under test is "only training
    # rows were read", not "the precision pin does not exist"
    assert via_helper == quantize_scaler(fit_scaler(train_only, COLUMNS))


def test_dropping_validation_and_test_entirely_does_not_change_the_scaler() -> None:
    population = _population()
    full = fit_train_scaler(population, COLUMNS)
    train_only = population.filter(pl.col("split") == TRAIN)
    assert full == fit_train_scaler(train_only, COLUMNS)


def test_training_metrics_do_not_move_when_held_out_rows_are_corrupted() -> None:
    """End to end: the whole train evaluation is independent of the content
    of validation and test, not just the scaler."""
    population = _population()
    scaler = fit_train_scaler(population, COLUMNS)
    clean = evaluate_split(population, scaler, TRAIN, n_resamples=25, seed=0)

    corrupted = population.with_columns(
        [
            pl.when(pl.col("split") == TRAIN)
            .then(pl.col(column))
            .otherwise(pl.col(column) * -3.5)
            .alias(column)
            for column in COLUMNS
        ]
    )
    after = evaluate_split(
        corrupted, fit_train_scaler(corrupted, COLUMNS), TRAIN, n_resamples=25, seed=0
    )
    assert clean == after


def test_candidate_pools_never_cross_a_split() -> None:
    population = _population()
    scaler = fit_train_scaler(population, COLUMNS)
    for split in (TRAIN, VALIDATION):
        result = evaluate_split(population, scaler, split, n_resamples=10, seed=0)
        expected_pool = population.filter(
            (pl.col("split") == split) & (pl.col("period") == "B")
        ).height
        assert result["candidate_pool_size"] == expected_pool


def test_evaluating_test_requires_an_explicit_opt_in() -> None:
    population = _population()
    scaler = fit_train_scaler(population, COLUMNS)
    with pytest.raises(PermissionError, match="allow_test=True"):
        evaluate_split(population, scaler, TEST, n_resamples=10, seed=0)


def test_fitted_statistics_are_quantized_and_idempotent() -> None:
    """Polars sums in parallel, so an unquantized mean/std can wobble by 1-2
    ULPs between runs and make the published scaler irreproducible. The fitted
    scaler must already be at its final precision."""
    from scoutlens.benchmark.evaluate import quantize_scaler

    population = _population()
    scaler = fit_train_scaler(population, COLUMNS)
    assert quantize_scaler(scaler) == scaler

    perturbed = {
        column: None if fit is None else (fit[0] + 1e-15, fit[1] + 1e-15)
        for column, fit in scaler.items()
    }
    assert quantize_scaler(perturbed) == scaler


def test_evaluation_is_deterministic_for_a_fixed_seed() -> None:
    population = _population()
    scaler = fit_train_scaler(population, COLUMNS)
    first = evaluate_split(population, scaler, VALIDATION, n_resamples=50, seed=0)
    second = evaluate_split(population, scaler, VALIDATION, n_resamples=50, seed=0)
    assert first == second
