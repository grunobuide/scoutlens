from __future__ import annotations

import json

import polars as pl
import pytest

from scoutlens.uncertainty.checkpoint import (
    completed_replicates,
    ensure_checkpoint_manifest,
    read_all_checkpoints,
    write_checkpoint_chunk,
)


def test_checkpoint_manifest_reuses_only_exact_state(tmp_path) -> None:
    manifest = {"format": "test/1", "source_sha256": "abc"}
    ensure_checkpoint_manifest(tmp_path, manifest)
    ensure_checkpoint_manifest(tmp_path, manifest)
    assert json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8")) == manifest

    with pytest.raises(ValueError, match="manifest mismatch"):
        ensure_checkpoint_manifest(tmp_path, {**manifest, "source_sha256": "changed"})


def test_checkpoint_chunks_are_atomic_complete_and_non_overlapping(tmp_path) -> None:
    ensure_checkpoint_manifest(tmp_path, {"format": "test/1"})
    frame = pl.DataFrame(
        {
            "replicate": [0, 0, 1, 1],
            "period_order": [0, 1, 0, 1],
            "profile_index": [0, 0, 0, 0],
        }
    )
    path = write_checkpoint_chunk(tmp_path, frame)
    assert path.name == "replicates-00000-00001.parquet"
    assert completed_replicates(tmp_path, requested_resamples=2, rows_per_replicate=2) == {0, 1}
    assert read_all_checkpoints(tmp_path).to_dicts() == frame.to_dicts()
    assert read_all_checkpoints(tmp_path, columns=["replicate"]).columns == ["replicate"]

    with pytest.raises(FileExistsError):
        write_checkpoint_chunk(tmp_path, frame)
