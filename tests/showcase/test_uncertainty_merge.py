"""Integration of validated match-bootstrap summaries into the showcase."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

from scoutlens.showcase.builder import profile_key
from scoutlens.showcase.catalog import EXPECTED_PROFILE_COUNT, FEATURE_COLUMNS
from scoutlens.showcase.uncertainty import (
    FEATURE_FILE,
    NEIGHBOR_FILE,
    RETRIEVAL_FILE,
    RUN_METADATA_FILE,
    BootstrapSummaries,
    load_bootstrap_summaries,
    require_feature,
    require_neighbor,
    require_rank,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
RUN_DIR = REPO_ROOT / "artifacts" / "uncertainty" / "match_bootstrap_v1"
HAS_RUN = (RUN_DIR / RUN_METADATA_FILE).is_file()


def _feature_frame(rows: list[dict]) -> pl.DataFrame:
    return pl.DataFrame(
        [
            {
                "player_id": 1,
                "competitionId": 364,
                "period": "A",
                "feature_id": FEATURE_COLUMNS[0],
                "status": "available",
                "valid_resamples": 500,
                "raw_ci_95_low": 0.1,
                "raw_ci_95_high": 0.9,
                "within_role_percentile_ci_95_low": 10.0,
                "within_role_percentile_ci_95_high": 90.0,
            }
        ]
        + rows
    )


def _rank_frame(rows: list[dict]) -> pl.DataFrame:
    return pl.DataFrame(
        [
            {
                "player_id": 1,
                "competitionId": 364,
                "outcome": outcome,
                "status": "available",
                "valid_resamples": 500,
                "median_rank": 4.0,
                "rank_ci_95_low": 1.0,
                "rank_ci_95_high": 37.0,
                "recall_at_1_rate": 0.2,
                "recall_at_5_rate": 0.6,
                "recall_at_10_rate": 0.7,
            }
            for outcome in ("global", "within_role", "baseline_role_minutes")
        ]
        + rows
    )


def _neighbor_frame(rows: list[dict]) -> pl.DataFrame:
    return pl.DataFrame(
        [
            {
                "player_id": 1,
                "competitionId": 364,
                "neighbor_slot": slot,
                "neighbor_player_id": 2,
                "neighbor_competitionId": 364,
                "status": "available",
                "valid_resamples": 500,
                "top_5_selection_rate": 0.8,
                "median_rank": 2.0,
                "rank_ci_95_low": 1.0,
                "rank_ci_95_high": 5.0,
            }
            for slot in (1, 2, 3, 4, 5)
        ]
        + rows
    )


def _write_run(tmp_path: Path, *, profile_count: int = EXPECTED_PROFILE_COUNT) -> Path:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _feature_frame([]).write_parquet(run_dir / FEATURE_FILE)
    _rank_frame([]).write_parquet(run_dir / RETRIEVAL_FILE)
    _neighbor_frame([]).write_parquet(run_dir / NEIGHBOR_FILE)
    run_dir.joinpath(RUN_METADATA_FILE).write_text(
        json.dumps(
            {
                "status": "available",
                "manifest": {
                    "design_version": "match_bootstrap_v1",
                    "profile_count": profile_count,
                },
            }
        ),
        encoding="utf-8",
    )
    return run_dir


def test_real_run_loads_complete_canonical_summaries() -> None:
    if not HAS_RUN:
        pytest.skip("canonical bootstrap run not present locally")
    summaries = load_bootstrap_summaries()
    assert len(summaries.feature) == EXPECTED_PROFILE_COUNT * 2 * len(FEATURE_COLUMNS)
    assert len(summaries.rank) == EXPECTED_PROFILE_COUNT * 3
    assert len(summaries.neighbor) == EXPECTED_PROFILE_COUNT * 5
    assert len(summaries.profile_block) == EXPECTED_PROFILE_COUNT
    assert len(summaries.profile_status) == EXPECTED_PROFILE_COUNT
    assert set(summaries.profile_status.values()) <= {"available", "insufficient"}


def test_real_run_blocks_are_schema_shape_safe() -> None:
    if not HAS_RUN:
        pytest.skip("canonical bootstrap run not present locally")
    summaries = load_bootstrap_summaries()
    rank = next(iter(summaries.rank.values()))
    assert set(rank) == {
        "status",
        "valid_resamples",
        "median_rank",
        "rank_ci_95",
        "recall_at_1_rate",
        "recall_at_5_rate",
        "recall_at_10_rate",
    }
    neighbor = next(iter(summaries.neighbor.values()))
    assert set(neighbor) == {
        "status",
        "valid_resamples",
        "top_5_selection_rate",
        "median_rank",
        "rank_ci_95",
    }
    feature = next(iter(summaries.feature.values()))
    assert set(feature) == {
        "status",
        "valid_resamples",
        "raw_ci_95",
        "within_role_percentile_ci_95",
    }
    block = next(iter(summaries.profile_block.values()))
    assert block["design_version"] == "match_bootstrap_v1"
    assert block["seed"] == 1729
    assert block["requested_resamples"] == 500
    assert block["interval"] == "percentile_95"
    assert block["warning"]


def test_feature_keys_use_canonical_uppercase_periods(tmp_path: Path) -> None:
    run_dir = _write_run(tmp_path)
    summaries = load_bootstrap_summaries(run_dir)
    key = (1, 364, "A", FEATURE_COLUMNS[0])
    assert key in summaries.feature
    assert require_feature(summaries, key)["status"] == "available"
    with pytest.raises(ValueError, match="missing bootstrap feature"):
        require_feature(summaries, (1, 364, "a", FEATURE_COLUMNS[0]))


def test_duplicate_rows_fail(tmp_path: Path) -> None:
    run_dir = _write_run(tmp_path)
    duplicated = _feature_frame(
        [
            {
                "player_id": 1,
                "competitionId": 364,
                "period": "A",
                "feature_id": FEATURE_COLUMNS[1],
                "status": "available",
                "valid_resamples": 500,
                "raw_ci_95_low": 0.1,
                "raw_ci_95_high": 0.9,
                "within_role_percentile_ci_95_low": 10.0,
                "within_role_percentile_ci_95_high": 90.0,
            }
            for _ in range(2)
        ]
    )
    duplicated.write_parquet(run_dir / FEATURE_FILE)
    with pytest.raises(ValueError, match="duplicate key"):
        load_bootstrap_summaries(run_dir)


def test_unexpected_outcome_fails(tmp_path: Path) -> None:
    run_dir = _write_run(tmp_path)
    frame = _rank_frame(
        [
            {
                "player_id": 2,
                "competitionId": 364,
                "outcome": "browser_computed",
                "status": "available",
                "valid_resamples": 500,
                "median_rank": 1.0,
                "rank_ci_95_low": 1.0,
                "rank_ci_95_high": 1.0,
                "recall_at_1_rate": 1.0,
                "recall_at_5_rate": 1.0,
                "recall_at_10_rate": 1.0,
            }
        ]
    )
    frame.write_parquet(run_dir / RETRIEVAL_FILE)
    with pytest.raises(ValueError, match="unexpected outcome"):
        load_bootstrap_summaries(run_dir)


def test_missing_global_outcome_fails(tmp_path: Path) -> None:
    run_dir = _write_run(tmp_path)
    frame = _rank_frame(
        [
            {
                "player_id": 2,
                "competitionId": 364,
                "outcome": "within_role",
                "status": "available",
                "valid_resamples": 500,
                "median_rank": 1.0,
                "rank_ci_95_low": 1.0,
                "rank_ci_95_high": 1.0,
                "recall_at_1_rate": 1.0,
                "recall_at_5_rate": 1.0,
                "recall_at_10_rate": 1.0,
            }
        ]
    )
    frame.write_parquet(run_dir / RETRIEVAL_FILE)
    with pytest.raises(ValueError, match="no global outcome"):
        load_bootstrap_summaries(run_dir)


def test_insufficient_blocks_null_values(tmp_path: Path) -> None:
    run_dir = _write_run(tmp_path)
    frame = _rank_frame(
        [
            {
                "player_id": 2,
                "competitionId": 364,
                "outcome": "global",
                "status": "insufficient",
                "valid_resamples": 4,
                "median_rank": 3.0,
                "rank_ci_95_low": 1.0,
                "rank_ci_95_high": 9.0,
                "recall_at_1_rate": 0.1,
                "recall_at_5_rate": 0.2,
                "recall_at_10_rate": 0.3,
            }
        ]
    )
    frame.write_parquet(run_dir / RETRIEVAL_FILE)
    summaries = load_bootstrap_summaries(run_dir)
    block = summaries.rank[(2, 364, "global")]
    assert block["status"] == "insufficient"
    assert block["valid_resamples"] == 4
    assert block["median_rank"] is None
    assert block["rank_ci_95"] is None
    assert block["recall_at_1_rate"] is None
    assert summaries.profile_status[(2, 364)] == "insufficient"
    assert summaries.profile_block[(2, 364)]["valid_resamples"] == 4


def test_cohort_size_mismatch_fails(tmp_path: Path) -> None:
    run_dir = _write_run(tmp_path, profile_count=EXPECTED_PROFILE_COUNT - 1)
    with pytest.raises(ValueError, match="cohort size"):
        load_bootstrap_summaries(run_dir)


def test_missing_required_rows_raise_from_helpers() -> None:
    summaries = BootstrapSummaries(
        feature={},
        rank={},
        neighbor={},
        profile_block={},
        profile_status={},
    )
    with pytest.raises(ValueError, match="missing bootstrap feature"):
        require_feature(summaries, (1, 364, "A", FEATURE_COLUMNS[0]))
    with pytest.raises(ValueError, match="missing bootstrap rank"):
        require_rank(summaries, (1, 364, "global"))
    with pytest.raises(ValueError, match="missing bootstrap neighbor"):
        require_neighbor(summaries, (1, 364, 1))
    assert profile_key(1, 364) == "wy-1-c-364"
