import polars as pl
import pytest

from scoutlens.evaluation.retrieval import (
    bootstrap_mrr_delta,
    bootstrap_mrr_delta_clustered,
    compute_metrics,
    run_baseline_a_retrieval,
    run_baseline_b_retrieval,
    run_baseline_c_retrieval,
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
        "player_id": [1, 2], "competitionId": [100, 100],
        "role": ["Forward", "Forward"], "minutes_played": [1000, 200],
    })
    result = run_baseline_a_retrieval(query, candidates)
    assert result.row(0, named=True)["rank"] == 1


def test_run_baseline_a_retrieval_disambiguates_same_player_id_across_competitions():
    """Regression test for D007: a player_id appearing in the candidate
    pool under two different competitions (e.g. a domestic league and a
    tournament) must be matched by (player_id, competitionId) together,
    not player_id alone -- otherwise the wrong row's rank could be
    reported, or the first matching row picked arbitrarily."""
    query = pl.DataFrame({
        "player_id": [1], "competitionId": [200], "role": ["Forward"], "minutes_played": [1000],
    })
    candidates = pl.DataFrame({
        "player_id": [1, 1, 2],
        "competitionId": [100, 200, 200],  # same player_id=1 in two competitions
        "role": ["Forward", "Forward", "Forward"],
        "minutes_played": [50, 1000, 999],  # competition 100's row would rank badly if matched by mistake
    })
    result = run_baseline_a_retrieval(query, candidates)
    row = result.row(0, named=True)
    assert row["competitionId"] == 200
    assert row["rank"] == 1  # matches the competition-200 row (minutes_played=1000), not competition-100's


def test_run_baseline_b_retrieval_finds_own_rank():
    query = pl.DataFrame({"player_id": [1], "competitionId": [100], "f1": [1.0], "f2": [0.0]})
    candidates = pl.DataFrame({
        "player_id": [1, 2], "competitionId": [100, 100], "f1": [1.0, -1.0], "f2": [0.0, 0.0],
    })
    result = run_baseline_b_retrieval(query, candidates, feature_columns=["f1", "f2"])
    assert result.row(0, named=True)["rank"] == 1


def test_run_baseline_b_retrieval_disambiguates_same_player_id_across_competitions():
    query = pl.DataFrame({"player_id": [1], "competitionId": [200], "f1": [1.0], "f2": [0.0]})
    candidates = pl.DataFrame({
        "player_id": [1, 1, 2],
        "competitionId": [100, 200, 200],
        "f1": [-1.0, 1.0, 0.9], "f2": [0.0, 0.0, 0.1],
    })
    result = run_baseline_b_retrieval(query, candidates, feature_columns=["f1", "f2"])
    row = result.row(0, named=True)
    assert row["competitionId"] == 200
    assert row["rank"] == 1  # matches the competition-200 row (identical vector), not competition-100's (opposite)


def test_bootstrap_mrr_delta_is_deterministic_with_fixed_seed():
    ranks_a = pl.DataFrame({"player_id": [1, 2, 3], "competitionId": [100, 100, 100], "rank": [5, 3, 10]})
    ranks_b = pl.DataFrame({"player_id": [1, 2, 3], "competitionId": [100, 100, 100], "rank": [1, 1, 2]})
    result1 = bootstrap_mrr_delta(ranks_a, ranks_b, n_resamples=200, seed=42)
    result2 = bootstrap_mrr_delta(ranks_a, ranks_b, n_resamples=200, seed=42)
    assert result1 == result2


def test_bootstrap_mrr_delta_is_independent_of_input_row_order():
    """Regression test for a real bug: the paired query set wasn't
    explicitly sorted before resampling, so CI bounds (not the point
    estimate) could vary run to run depending on incidental row order
    from upstream joins -- not just theoretically, observed as ~0.002
    jitter across real runs. A fixed seed must now give bit-identical
    results regardless of the order ranks_a/ranks_b arrive in."""
    ranks_a_forward = pl.DataFrame({
        "player_id": [1, 2, 3], "competitionId": [100, 100, 100], "rank": [5, 3, 10],
    })
    ranks_b_forward = pl.DataFrame({
        "player_id": [1, 2, 3], "competitionId": [100, 100, 100], "rank": [1, 1, 2],
    })
    ranks_a_shuffled = pl.DataFrame({
        "player_id": [3, 1, 2], "competitionId": [100, 100, 100], "rank": [10, 5, 3],
    })
    ranks_b_shuffled = pl.DataFrame({
        "player_id": [2, 3, 1], "competitionId": [100, 100, 100], "rank": [1, 2, 1],
    })
    result_forward = bootstrap_mrr_delta(ranks_a_forward, ranks_b_forward, n_resamples=200, seed=7)
    result_shuffled = bootstrap_mrr_delta(ranks_a_shuffled, ranks_b_shuffled, n_resamples=200, seed=7)
    assert result_forward == result_shuffled


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
        "competitionId": [100, 100, 100],
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
        "competitionId": [100, 100, 100],
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
        "player_id": [1, 2], "competitionId": [100, 100], "role": ["Forward", "Defender"], "minutes_played": [1000, 999],
    })
    result = run_baseline_a_retrieval(query, candidates)
    assert result.row(0, named=True)["pool_size"] == 2


def test_run_baseline_c_retrieval_finds_own_rank():
    query = pl.DataFrame({
        "player_id": [1], "competitionId": [100], "role": ["Forward"], "team_id": [500], "minutes_played": [1000],
    })
    candidates = pl.DataFrame({
        "player_id": [1, 2, 3],
        "competitionId": [100, 100, 100],
        "role": ["Forward", "Forward", "Defender"],
        "team_id": [500, 600, 500],
        "minutes_played": [1000, 999, 998],
    })
    result = run_baseline_c_retrieval(query, candidates)
    row = result.row(0, named=True)
    assert row["rank"] == 1  # same role AND same team beats same-role-only and same-team-only
    assert row["pool_size"] == 3


def test_run_baseline_c_retrieval_disambiguates_same_player_id_across_competitions():
    query = pl.DataFrame({
        "player_id": [1], "competitionId": [200], "role": ["Forward"], "team_id": [500], "minutes_played": [1000],
    })
    candidates = pl.DataFrame({
        "player_id": [1, 1],
        "competitionId": [100, 200],
        "role": ["Forward", "Forward"],
        "team_id": [999, 500],
        "minutes_played": [1, 1000],
    })
    result = run_baseline_c_retrieval(query, candidates)
    row = result.row(0, named=True)
    assert row["competitionId"] == 200
    assert row["rank"] == 1


def _ranks_fixture():
    ranks_a = pl.DataFrame({
        "player_id": [1, 2, 3, 4, 5, 6],
        "competitionId": [100] * 6,
        "rank": [10, 20, 5, 40, 8, 2],
    })
    ranks_b = pl.DataFrame({
        "player_id": [1, 2, 3, 4, 5, 6],
        "competitionId": [100] * 6,
        "rank": [1, 3, 2, 10, 4, 1],
    })
    clusters = pl.DataFrame({
        "player_id": [1, 2, 3, 4, 5, 6],
        "competitionId": [100] * 6,
        "cluster": [500, 500, 600, 600, 700, 700],
    })
    return ranks_a, ranks_b, clusters


def test_bootstrap_mrr_delta_clustered_is_deterministic_and_order_independent():
    ranks_a, ranks_b, clusters = _ranks_fixture()
    r1 = bootstrap_mrr_delta_clustered(ranks_a, ranks_b, clusters, n_resamples=200, seed=7)
    shuffled = ranks_a.sort("player_id", descending=True)
    r2 = bootstrap_mrr_delta_clustered(shuffled, ranks_b, clusters.sort("cluster", descending=True), n_resamples=200, seed=7)
    assert r1 == r2
    assert r1["n_clusters"] == 3
    assert r1["n_queries"] == 6
    assert r1["ci_low"] <= r1["point_estimate"] <= r1["ci_high"]


def test_bootstrap_mrr_delta_clustered_single_cluster_collapses_to_point():
    ranks_a, ranks_b, clusters = _ranks_fixture()
    one_cluster = clusters.with_columns(pl.lit(1).alias("cluster"))
    r = bootstrap_mrr_delta_clustered(ranks_a, ranks_b, one_cluster, n_resamples=50, seed=0)
    # every resample draws the single cluster once: all deltas equal the full-sample delta
    assert r["ci_low"] == r["ci_high"] == pytest.approx(r["point_estimate"])


def test_bootstrap_mrr_delta_clustered_rejects_unmapped_queries():
    ranks_a, ranks_b, clusters = _ranks_fixture()
    incomplete = clusters.filter(pl.col("player_id") != 3)
    with pytest.raises(ValueError, match="no cluster assignment"):
        bootstrap_mrr_delta_clustered(ranks_a, ranks_b, incomplete, n_resamples=10, seed=0)


def test_bootstrap_mrr_delta_clustered_point_estimate_matches_iid_bootstrap():
    ranks_a, ranks_b, clusters = _ranks_fixture()
    clustered = bootstrap_mrr_delta_clustered(ranks_a, ranks_b, clusters, n_resamples=100, seed=0)
    iid = bootstrap_mrr_delta(ranks_a, ranks_b, n_resamples=100, seed=0)
    assert clustered["point_estimate"] == pytest.approx(iid["point_estimate"])
