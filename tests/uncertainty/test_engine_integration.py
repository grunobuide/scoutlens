from __future__ import annotations

import dataclasses
import os

import pytest
from polars.testing import assert_frame_equal

from scoutlens.uncertainty.checkpoint import read_all_checkpoints
from scoutlens.uncertainty.engine import (
    prepare_bootstrap,
    run_replicates,
    summarize_checkpoints,
)

pytestmark = pytest.mark.skipif(
    os.environ.get("SCOUTLENS_UNCERTAINTY_INTEGRATION") != "1",
    reason="set SCOUTLENS_UNCERTAINTY_INTEGRATION=1 to use local processed data",
)


def test_real_data_is_deterministic_across_workers_resume_and_input_order(tmp_path) -> None:
    prepared = prepare_bootstrap()
    short_plan = dataclasses.replace(
        prepared.draw_plan,
        multiplicities=prepared.draw_plan.multiplicities[:3].copy(),
        sha256=f"{prepared.draw_plan.sha256}-first-3-integration",
    )
    short_config = {
        **prepared.config,
        "requested_resamples": 3,
        "minimum_valid_resamples": 2,
    }
    short = dataclasses.replace(prepared, config=short_config, draw_plan=short_plan)
    reversed_input = dataclasses.replace(
        short,
        player_match_statistics=short.player_match_statistics.reverse(),
    )

    checkpoint_1 = tmp_path / "workers-1"
    checkpoint_2 = tmp_path / "workers-2"
    checkpoint_reversed = tmp_path / "reversed"
    run_replicates(short, checkpoint_dir=checkpoint_1, workers=1, chunk_size=2)
    resumed = run_replicates(short, checkpoint_dir=checkpoint_1, workers=1, chunk_size=2)
    run_replicates(short, checkpoint_dir=checkpoint_2, workers=2, chunk_size=2)
    run_replicates(reversed_input, checkpoint_dir=checkpoint_reversed, workers=1, chunk_size=2)

    assert resumed["already_completed"] == 3
    assert resumed["written_resamples"] == 0
    expected = read_all_checkpoints(checkpoint_1)
    assert_frame_equal(read_all_checkpoints(checkpoint_2), expected)
    assert_frame_equal(read_all_checkpoints(checkpoint_reversed), expected)

    outputs = []
    for name, checkpoint in (
        ("workers-1", checkpoint_1),
        ("workers-2", checkpoint_2),
        ("reversed", checkpoint_reversed),
    ):
        output = tmp_path / f"output-{name}"
        summarize_checkpoints(short, checkpoint_dir=checkpoint, output_dir=output)
        outputs.append(output)
    for filename in (
        "feature-uncertainty.parquet",
        "retrieval-uncertainty.parquet",
        "neighbor-stability.parquet",
    ):
        reference = outputs[0] / filename
        assert all((output / filename).read_bytes() == reference.read_bytes() for output in outputs[1:])
