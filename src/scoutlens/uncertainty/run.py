"""Run the preregistered deterministic match-bootstrap uncertainty pipeline."""

from __future__ import annotations

import argparse
import ctypes
import importlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from scoutlens.evaluation.run_manifest import REPO_ROOT
from scoutlens.uncertainty.config import UNCERTAINTY_CONFIG_PATH, load_uncertainty_config
from scoutlens.uncertainty.engine import (
    DEFAULT_CHECKPOINT_DIR,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_PROCESSED_DIR,
    prepare_bootstrap,
    run_replicates,
    summarize_checkpoints,
    write_summary_metadata,
)
from scoutlens.uncertainty.synthetic import validate_synthetic_fixture

RUNTIME_TARGET_SECONDS = 15 * 60
MEMORY_TARGET_BYTES = 4 * 1024**3


def peak_resident_memory_bytes() -> int:
    """Return native-process peak RSS, including Polars/Arrow allocations."""
    if os.name == "nt":
        ctypes_windows: Any = ctypes
        size_type = ctypes.c_size_t

        class ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong),
                ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", size_type),
                ("WorkingSetSize", size_type),
                ("QuotaPeakPagedPoolUsage", size_type),
                ("QuotaPagedPoolUsage", size_type),
                ("QuotaPeakNonPagedPoolUsage", size_type),
                ("QuotaNonPagedPoolUsage", size_type),
                ("PagefileUsage", size_type),
                ("PeakPagefileUsage", size_type),
            ]

        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        kernel32 = ctypes_windows.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes_windows.WinDLL("psapi", use_last_error=True)
        get_current_process = kernel32.GetCurrentProcess
        get_current_process.restype = ctypes.c_void_p
        get_process_memory_info = psapi.GetProcessMemoryInfo
        get_process_memory_info.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ProcessMemoryCounters),
            ctypes.c_ulong,
        ]
        get_process_memory_info.restype = ctypes.c_int
        process = get_current_process()
        if not get_process_memory_info(process, ctypes.byref(counters), counters.cb):
            raise ctypes_windows.WinError(ctypes_windows.get_last_error())
        return int(counters.PeakWorkingSetSize)

    resource_module = importlib.import_module("resource")
    peak = int(resource_module.getrusage(resource_module.RUSAGE_SELF).ru_maxrss)
    return peak if sys.platform == "darwin" else peak * 1024


def _directory_bytes(directory: Path) -> int:
    if not directory.exists():
        return 0
    return sum(path.stat().st_size for path in directory.rglob("*") if path.is_file())


def run_uncertainty(
    *,
    processed_dir: Path = DEFAULT_PROCESSED_DIR,
    checkpoint_dir: Path = DEFAULT_CHECKPOINT_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    uncertainty_config_path: Path = UNCERTAINTY_CONFIG_PATH,
    workers: int = 1,
    chunk_size: int = 10,
) -> dict[str, Any]:
    """Validate the truth fixture, execute/resume, summarize and record limits."""
    total_started = time.perf_counter()
    config = load_uncertainty_config(uncertainty_config_path)
    fixture_path = Path(str(config["synthetic_fixture"]))
    if not fixture_path.is_absolute():
        fixture_path = REPO_ROOT / fixture_path
    synthetic = validate_synthetic_fixture(fixture_path, config)
    if not synthetic["all_passed"]:
        failed = sorted(case for case, passed in synthetic["cases"].items() if not passed)
        raise ValueError(f"synthetic pre-production gate failed: {failed}")

    preparation_started = time.perf_counter()
    prepared = prepare_bootstrap(
        processed_dir=processed_dir,
        uncertainty_config_path=uncertainty_config_path,
    )
    preparation_elapsed = time.perf_counter() - preparation_started
    run_result = run_replicates(
        prepared,
        checkpoint_dir=checkpoint_dir,
        workers=workers,
        chunk_size=chunk_size,
    )
    execution: dict[str, Any] = {
        "workers": workers,
        "chunk_size": chunk_size,
        "preparation_elapsed_seconds": preparation_elapsed,
        "replicate_elapsed_seconds": run_result["elapsed_seconds"],
        "resumed_resamples": run_result["already_completed"],
        "written_resamples": run_result["written_resamples"],
    }
    summary_started = time.perf_counter()
    metadata = summarize_checkpoints(
        prepared,
        checkpoint_dir=checkpoint_dir,
        output_dir=output_dir,
        execution=execution,
    )
    execution["summary_elapsed_seconds"] = time.perf_counter() - summary_started
    execution["total_elapsed_seconds"] = time.perf_counter() - total_started
    execution["peak_resident_memory_bytes"] = peak_resident_memory_bytes()
    execution["checkpoint_bytes"] = _directory_bytes(checkpoint_dir)
    execution["final_output_bytes"] = sum(
        int(item["bytes"]) for item in metadata["outputs"].values()
    )
    execution["performance_targets"] = {
        "runtime_limit_seconds": RUNTIME_TARGET_SECONDS,
        "runtime_within_target": execution["total_elapsed_seconds"] <= RUNTIME_TARGET_SECONDS,
        "memory_limit_bytes": MEMORY_TARGET_BYTES,
        "memory_within_target": execution["peak_resident_memory_bytes"] <= MEMORY_TARGET_BYTES,
    }
    metadata["synthetic_validation"] = synthetic
    write_summary_metadata(metadata, output_dir)
    return {
        "status": metadata["status"],
        "completed_resamples": metadata["completed_resamples"],
        "profile_count": prepared.profile_count,
        "draw_plan_sha256": prepared.draw_plan.sha256,
        "execution": execution,
        "run_path": metadata["run_path"],
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed-dir", type=Path, default=DEFAULT_PROCESSED_DIR)
    parser.add_argument("--checkpoint-dir", type=Path, default=DEFAULT_CHECKPOINT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--uncertainty-config", type=Path, default=UNCERTAINTY_CONFIG_PATH)
    parser.add_argument("--workers", type=int, choices=(1, 2), default=1)
    parser.add_argument("--chunk-size", type=int, default=10)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = run_uncertainty(
        processed_dir=args.processed_dir,
        checkpoint_dir=args.checkpoint_dir,
        output_dir=args.output_dir,
        uncertainty_config_path=args.uncertainty_config,
        workers=args.workers,
        chunk_size=args.chunk_size,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
