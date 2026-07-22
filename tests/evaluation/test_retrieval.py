import polars as pl
import pytest

from scoutlens.evaluation.retrieval import (
    bootstrap_mrr_delta,
    compute_metrics,
    run_baseline_a_retrieval,
    run_baseline_b_retrieval,
    select_eligible_both_periods,
)


def test_compute_metrics_basic_values():
    metrics = compute_metrics([1, 2, 4, 1])
    assert metrics.n == 4
    assert metrics.mrr == pytest.approx((1 + 0.5 + 0.25 + 1) / 4)
    assert metrics.median_rank == 1.5
    assert metrics.recall_at_1 == 0.5
    assert metrics.recall_at_5 == 1.0


def test_compute_metrics_rejects_empty_list():
    with pytest.raises(ValueError):
        compute_metrics([])


def _period_profiles(*rows):
    """rows of (player_id, competitionId, period, minutes_played, f1)."""
    return pl.DataFrame({
        "player_id": [r[0] for r in rows],
        "competitionId": [r[1] for r in rows],
        "period": [r[2] for r in rows],
        "minutes_played": [r[3] for r in rows],
        "f1": [r[4] for r in rows],
    })


def test_select_eligible_both_periods_requires_threshold_in_both_periods():
    profiles = _period_profiles(
        (1, 100, "A", 500, 1.0), (1, 100, "B", 500, 1.0),  # eligible both periods
        (2, 100, "A", 500, 1.0), (2, 100, "B", 100, 1.0),  # fails threshold in B
        (3, 100, "A", 100, 1.0),  # fails threshold in A, missing from B entirely
    )
    result = select_eligible_both_periods(profiles, minutes_threshold=450, competition_ids=[100])
    assert set(result["player_id"].to_list()) == {1}


def test_select_eligible_both_periods_restricts_to_given_competitions():
    profiles = _period_profiles(
        (1, 100, "A", 500, 1.0), (1, 100, "B", 500, 1.0),
        (2, 200, "A", 500, 1.0), (2, 200, "B", 500, 1.0),
    )
    result = select_eligible_both_periods(profiles, minutes_threshold=450, competition_ids=[100])
    # both periods' rows for player 1 are kept -- one row per (player, period)
    assert set(result["player_id"].to_list()) == {1}
    assert result.height == 2


def test_run_baseline_a_retrieval_finds_own_rank():
    query = pl.DataFrame({
        "player_id": [1], "competitionId": [100], "role": ["Forward"], "minutes_played": [1000],
    })
    candidates = pl.DataFrame({
        "player_id": [1, 2], "role": ["Forward", "Forward"], "minutes_played": [1000, 200],
    })
    result = run_baseline_a_retrieval(query, candidates)
    assert result.row(0, named=True)["rank"] == 1


def test_run_baseline_b_retrieval_finds_own_rank():
    query = pl.DataFrame({"player_id": [1], "competitionId": [100], "f1": [1.0], "f2": [0.0]})
    candidates = pl.DataFrame({"player_id": [1, 2], "f1": [1.0, -1.0], "f2": [0.0, 0.0]})
    result = run_baseline_b_retrieval(query, candidates, feature_columns=["f1", "f2"])
    assert result.row(0, named=True)["rank"] == 1


def test_bootstrap_mrr_delta_is_deterministic_with_fixed_seed():
    ranks_a = pl.DataFrame({"player_id": [1, 2, 3], "competitionId": [100, 100, 100], "rank": [5, 3, 10]})
    ranks_b = pl.DataFrame({"player_id": [1, 2, 3], "competitionId": [100, 100, 100], "rank": [1, 1, 2]})
    result1 = bootstrap_mrr_delta(ranks_a, ranks_b, n_resamples=200, seed=42)
    result2 = bootstrap_mrr_delta(ranks_a, ranks_b, n_resamples=200, seed=42)
    assert result1 == result2


def test_bootstrap_mrr_delta_positive_when_b_strictly_better():
    """B ranks everyone at 1 (perfect), A ranks everyone worse -- the point
    estimate and the whole CI must be positive."""
    ranks_a = pl.DataFrame({"player_id": [1, 2, 3], "competitionId": [100, 100, 100], "rank": [10, 10, 10]})
    ranks_b = pl.DataFrame({"player_id": [1, 2, 3], "competitionId": [100, 100, 100], "rank": [1, 1, 1]})
    result = bootstrap_mrr_delta(ranks_a, ranks_b, n_resamples=200, seed=1)
    assert result["point_estimate"] > 0
    assert result["ci_low"] > 0


def test_baseline_a_scope_column_excludes_other_scope_candidates():
    query = pl.DataFrame({
        "player_id": [1], "competitionId": [100], "role": ["Forward"], "minutes_played": [1000],
    })
    candidates = pl.DataFrame({
        "player_id": [1, 2, 3],
        "role": ["Forward", "Forward", "Defender"],
        "minutes_played": [1000, 500, 999],
    })
    result = run_baseline_a_retrieval(query, candidates, scope_column="role")
    row = result.row(0, named=True)
    assert row["rank"] == 1
    assert row["pool_size"] == 2  # the Defender candidate is excluded from the pool entirely


def test_baseline_b_scope_column_excludes_other_scope_candidates():
    query = pl.DataFrame({
        "player_id": [1], "competitionId": [100], "role": ["Forward"], "f1": [1.0], "f2": [0.0],
    })
    candidates = pl.DataFrame({
        "player_id": [1, 2, 3],
        "role": ["Forward", "Forward", "Defender"],
        "f1": [1.0, 0.5, 1.0], "f2": [0.0, 0.0, 0.0],
    })
    result = run_baseline_b_retrieval(query, candidates, feature_columns=["f1", "f2"], scope_column="role")
    row = result.row(0, named=True)
    assert row["rank"] == 1
    assert row["pool_size"] == 2


def test_scope_column_none_is_unaffected_and_omits_no_candidates():
    query = pl.DataFrame({
        "player_id": [1], "competitionId": [100], "role": ["Forward"], "minutes_played": [1000],
    })
    candidates = pl.DataFrame({
        "player_id": [1, 2], "role": ["Forward", "Defender"], "minutes_played": [1000, 999],
    })
    result = run_baseline_a_retrieval(query, candidates)
    assert result.row(0, named=True)["pool_size"] == 2
