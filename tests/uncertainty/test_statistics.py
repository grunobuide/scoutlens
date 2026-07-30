from __future__ import annotations

import numpy as np
import pytest

from scoutlens.uncertainty.statistics import (
    average_rank_percentiles,
    quantile_type7,
    summarize_interval,
    summarize_neighbor_ranks,
    summarize_ranks,
)


def test_type7_quantile_interpolates_exactly() -> None:
    values = np.array([0.0, 10.0, 20.0, 30.0, np.nan])
    assert quantile_type7(values, 0.25) == pytest.approx(7.5)
    assert quantile_type7(values, 0.5) == pytest.approx(15.0)
    assert quantile_type7(values, 0.975) == pytest.approx(29.25)


def test_average_rank_percentiles_handle_ties_singletons_and_missing() -> None:
    values = np.array([10.0, 20.0, 20.0, 40.0, np.nan])
    result = average_rank_percentiles(values)
    assert result[:4].tolist() == pytest.approx([0.0, 50.0, 50.0, 100.0])
    assert np.isnan(result[4])
    assert average_rank_percentiles(np.array([3.0]))[0] == 50.0


def test_interval_is_insufficient_below_validity_threshold_or_without_point() -> None:
    values = np.array([1.0, 2.0, np.nan])
    assert summarize_interval(values, minimum_valid=3)["status"] == "insufficient"
    without_point = summarize_interval(values, minimum_valid=2, point_available=False)
    assert without_point == {"status": "insufficient", "valid_resamples": 2, "ci_95": None}


def test_rank_and_neighbor_summaries_share_valid_denominator() -> None:
    values = np.array([1.0, 2.0, 6.0, 10.0, np.nan])
    ranks = summarize_ranks(values, minimum_valid=4)
    neighbor = summarize_neighbor_ranks(values, minimum_valid=4)
    assert ranks["status"] == "available"
    assert ranks["valid_resamples"] == 4
    assert ranks["median_rank"] == pytest.approx(4.0)
    assert ranks["recall_at_1_rate"] == 0.25
    assert ranks["recall_at_5_rate"] == 0.5
    assert neighbor["top_5_selection_rate"] == 0.5
    assert neighbor["rank_ci_95"] == ranks["rank_ci_95"]
