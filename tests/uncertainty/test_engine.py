from __future__ import annotations

import numpy as np
import polars as pl
import pytest
from polars.testing import assert_frame_equal

from scoutlens.evaluation.similarity import apply_scaler, fit_scaler
from scoutlens.features.aggregation import FEATURE_COLUMNS
from scoutlens.uncertainty.engine import (
    _align_feature_frame,
    standardize_replicate,
    within_role_percentiles,
)


def test_zero_minutes_masks_every_raw_feature_even_when_events_exist() -> None:
    grid = pl.DataFrame(
        {
            "player_id": [1, 1],
            "competitionId": [10, 10],
            "role": ["M", "M"],
            "profile_index": [0, 0],
            "period": ["A", "B"],
            "period_order": [0, 1],
        }
    )
    frame = pl.DataFrame(
        {
            "player_id": [1],
            "competitionId": [10],
            "period": ["A"],
            "minutes_played": [0.0],
            **{feature: [1.0] for feature in FEATURE_COLUMNS},
        }
    )

    raw, minutes, present = _align_feature_frame(frame, grid)

    assert minutes[0, 0] == 0
    assert not present.any()
    assert np.isnan(raw).all()


def test_numpy_scaler_matches_frozen_polars_scaler() -> None:
    raw = np.array(
        [
            [[10.0, 1.0], [20.0, np.nan]],
            [[30.0, 3.0], [40.0, 5.0]],
        ]
    )
    present = np.ones((2, 2), dtype=bool)
    result = standardize_replicate(raw, present).reshape(4, 2)

    frame = pl.DataFrame(
        {
            "a": raw[:, :, 0].reshape(-1),
            "b": [1.0, None, 3.0, 5.0],
        }
    )
    expected = apply_scaler(frame, ["a", "b"], fit_scaler(frame, ["a", "b"]))
    assert_frame_equal(
        pl.DataFrame({"a": result[:, 0], "b": result[:, 1]}),
        expected,
        abs_tol=1e-12,
    )


def test_role_percentiles_use_both_periods_and_invalidate_raw_null() -> None:
    raw = np.array(
        [
            [[1.0], [2.0], [10.0]],
            [[3.0], [np.nan], [20.0]],
        ]
    )
    present = np.ones((2, 3), dtype=bool)
    roles = np.array(["M", "M", "F"])
    standardized = standardize_replicate(raw, present)
    result = within_role_percentiles(standardized, raw, present, roles)

    assert result[0, 0, 0] == 0.0
    assert result[0, 1, 0] == pytest.approx(100 / 3)
    assert result[1, 0, 0] == pytest.approx(200 / 3)
    assert np.isnan(result[1, 1, 0])
    assert result[0, 2, 0] == 0.0
    assert result[1, 2, 0] == 100.0
