"""Tests for empirical-Bayes ratio shrinkage (D024, scoutlens-dul)."""

from __future__ import annotations

import polars as pl
import pytest

from scoutlens.features.shrinkage import RATIO_SPECS, fit_beta_prior, shrink_ratios


def test_fit_beta_prior_recovers_population_mean():
    # rates spread around 0.5 -> prior mean alpha/(alpha+beta) ~ 0.5
    nums = [1, 4, 5, 2, 7, 3, 6, 8]
    dens = [10] * 8
    alpha, beta = fit_beta_prior(nums, dens)
    assert alpha > 0 and beta > 0
    assert alpha / (alpha + beta) == pytest.approx(sum(nums) / sum(dens) / 1.0, abs=0.15)


def test_fit_beta_prior_falls_back_when_degenerate():
    # identical rates -> zero variance -> weak uniform prior
    assert fit_beta_prior([5, 5, 5], [10, 10, 10]) == (1.0, 1.0)
    assert fit_beta_prior([1], [1]) == (1.0, 1.0)   # too few


def _counts_frame(rows):
    # minimal profiles_with_counts: id cols + the pass-completion count pair,
    # other ratio count columns zeroed so only pass_completion is exercised
    cols = {c for (_f, (n, ds)) in RATIO_SPECS.items() for c in [n, *ds]}
    base = {c: 0 for c in cols}
    out = []
    for r in rows:
        d = dict(base)
        d.update(r)
        d.update({"player_id": r["player_id"], "competitionId": 1, "period": "A",
                  "pass_completion_pct": None})
        out.append(d)
    return pl.DataFrame(out)


def test_shrink_pulls_low_n_toward_mean_and_leaves_high_n():
    # population: many high-volume ~0.8 passers + one 1-of-1 = 1.0
    rows = []
    for pid in range(1, 21):
        rows.append({"player_id": pid, "_sum_pass_accurate": 80, "_sum_pass_not_accurate": 20})  # 0.8, high n
    rows.append({"player_id": 99, "_sum_pass_accurate": 1, "_sum_pass_not_accurate": 0})          # 1.0, n=1
    df = _counts_frame(rows)
    shrunk = shrink_ratios(df)
    by = {r["player_id"]: r["pass_completion_pct"] for r in shrunk.to_dicts()}
    # the 1-of-1 player is pulled well below 1.0, toward the ~0.8 population mean
    assert by[99] < 0.95 and by[99] > 0.75
    # a high-n 0.8 passer barely moves
    assert by[1] == pytest.approx(0.8, abs=0.02)
    # count columns are dropped
    assert not any(c.startswith("_sum_") for c in shrunk.columns)


def test_ratio_count_columns_cover_every_shrunk_ratio():
    # every column shrink_ratios needs must be in the aggregation's
    # with_counts output contract (RATIO_COUNT_COLUMNS)
    from scoutlens.features.aggregation import RATIO_COUNT_COLUMNS
    needed = {c for (_f, (num, dens)) in RATIO_SPECS.items() for c in [num, *dens]}
    assert needed <= set(RATIO_COUNT_COLUMNS)
    # and the 7 ratio names shrink_ratios rewrites are exactly the ratio
    # features in the v0.1 catalog (guards against a silent rename)
    from scoutlens.features.aggregation import FEATURE_COLUMNS
    assert set(RATIO_SPECS) <= set(FEATURE_COLUMNS)
    assert all(f.endswith("_pct") for f in RATIO_SPECS)
