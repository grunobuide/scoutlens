import pytest

from scoutlens.evaluation.chance_level import chance_level_mrr, lift, random_target_null


def _harmonic(n: int) -> float:
    return sum(1.0 / k for k in range(1, n + 1))


def test_chance_level_mrr_constant_pool_is_harmonic_over_n():
    n = 50
    pool_sizes = [n] * 100
    assert chance_level_mrr(pool_sizes) == pytest.approx(_harmonic(n) / n)


def test_chance_level_mrr_pools_varying_pool_sizes_take_the_mean_per_query():
    pool_sizes = [3, 5]
    expected = (_harmonic(3) / 3 + _harmonic(5) / 5) / 2
    assert chance_level_mrr(pool_sizes) == pytest.approx(expected)


def test_chance_level_mrr_rejects_empty_list():
    with pytest.raises(ValueError, match="empty"):
        chance_level_mrr([])


def test_chance_level_mrr_rejects_zero_pool():
    with pytest.raises(ValueError, match=">= 1"):
        chance_level_mrr([0, 5])


def test_lift_is_observed_over_chance():
    assert lift(0.25, 0.0061369) == pytest.approx(0.25 / 0.0061369)


def test_lift_rejects_nonpositive_chance():
    with pytest.raises(ValueError, match="> 0"):
        lift(0.1, 0.0)


def test_random_target_null_reproduces_design_floor_in_expectation():
    n = 1000
    pool_sizes = [n] * 300
    null = random_target_null(pool_sizes, observed_mrr=0.0, n_resamples=500, seed=0)
    # a large MRR impossible under the null
    assert null["expected_mrr"] == pytest.approx(_harmonic(n) / n)
    assert null["null_mean"] == pytest.approx(_harmonic(n) / n, rel=0.05)


def test_random_target_null_observed_far_above_null_gives_tiny_p_value():
    pool_sizes = [1000] * 300
    null = random_target_null(pool_sizes, observed_mrr=0.25, n_resamples=500, seed=0)
    assert null["observed_mrr"] == 0.25
    assert null["p_value"] < 0.01
    assert null["ci_low"] < null["ci_high"]


def test_random_target_null_is_deterministic_and_order_independent():
    pool_sizes = [1000] * 300
    a = random_target_null(pool_sizes, observed_mrr=0.2, n_resamples=200, seed=7)
    b = random_target_null(list(reversed(pool_sizes)), observed_mrr=0.2, n_resamples=200, seed=7)
    assert a == b


def test_random_target_null_observed_at_chance_gives_high_p_value():
    n = 200
    pool_sizes = [n] * 100
    obs = _harmonic(n) / n  # exactly the design floor
    null = random_target_null(pool_sizes, observed_mrr=obs, n_resamples=300, seed=1)
    assert null["p_value"] > 0.1


def test_random_target_null_rejects_invalid_input():
    with pytest.raises(ValueError, match="requires at least one query"):
        random_target_null([], observed_mrr=0.1)
    with pytest.raises(ValueError, match=">= 1"):
        random_target_null([0], observed_mrr=0.1)
