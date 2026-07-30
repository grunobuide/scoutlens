"""Fail-closed Parquet checkpoints for resumable uncertainty runs."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from pathlib import Path

import polars as pl

CHECKPOINT_FORMAT = "scoutlens.match-bootstrap-checkpoint/1"
_CHUNK_PATTERN = re.compile(r"replicates-(\d{5})-(\d{5})\.parquet$")


def ensure_checkpoint_manifest(directory: Path, expected: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "manifest.json"
    if path.exists():
        actual = json.loads(path.read_text(encoding="utf-8"))
        if actual != expected:
            raise ValueError("checkpoint manifest mismatch; refusing to reuse incompatible state")
        return
    unexpected = [item.name for item in directory.iterdir()]
    if unexpected:
        raise ValueError(f"checkpoint directory has no manifest but is not empty: {sorted(unexpected)}")
    payload = json.dumps(expected, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    temporary = directory / ".manifest.json.tmp"
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(path)


def checkpoint_files(directory: Path) -> list[Path]:
    files = []
    for path in directory.glob("replicates-*.parquet"):
        if not _CHUNK_PATTERN.fullmatch(path.name):
            raise ValueError(f"unrecognized checkpoint filename: {path.name}")
        files.append(path)
    return sorted(files)


def completed_replicates(
    directory: Path,
    *,
    requested_resamples: int,
    rows_per_replicate: int,
) -> set[int]:
    completed: set[int] = set()
    for path in checkpoint_files(directory):
        replicate_values = pl.read_parquet(path, columns=["replicate"])["replicate"]
        counts = replicate_values.value_counts().to_dicts()
        for item in counts:
            replicate = int(item["replicate"])
            count = int(item["count"])
            if not 0 <= replicate < requested_resamples:
                raise ValueError(f"checkpoint replicate out of range in {path.name}: {replicate}")
            if count != rows_per_replicate:
                raise ValueError(
                    f"checkpoint replicate {replicate} has {count} rows, expected {rows_per_replicate}"
                )
            if replicate in completed:
                raise ValueError(f"checkpoint replicate appears more than once: {replicate}")
            completed.add(replicate)
    return completed


def write_checkpoint_chunk(directory: Path, frame: pl.DataFrame) -> Path:
    replicates = sorted(int(value) for value in frame["replicate"].unique().to_list())
    if not replicates:
        raise ValueError("cannot write an empty checkpoint chunk")
    if replicates != list(range(replicates[0], replicates[-1] + 1)):
        raise ValueError("checkpoint chunk replicates must be contiguous")
    destination = directory / f"replicates-{replicates[0]:05d}-{replicates[-1]:05d}.parquet"
    if destination.exists():
        raise FileExistsError(f"checkpoint chunk already exists: {destination}")
    temporary = directory / f".{destination.name}.tmp"
    frame.write_parquet(temporary, compression="zstd", statistics=True)
    temporary.replace(destination)
    return destination


def read_all_checkpoints(
    directory: Path,
    *,
    columns: Sequence[str] | None = None,
) -> pl.DataFrame:
    files = checkpoint_files(directory)
    if not files:
        raise FileNotFoundError(f"no checkpoint chunks found in {directory}")
    order = ["replicate", "period_order", "profile_index"]
    projected = None if columns is None else list(dict.fromkeys([*order, *columns]))
    frame = pl.read_parquet(files, columns=projected).sort(*order)
    return frame if columns is None else frame.select(columns)
