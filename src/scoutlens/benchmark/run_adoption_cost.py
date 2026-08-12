"""Measure the diagonal representation's adoption cost (`scoutlens-qop.6.1`).

    uv run --frozen python -m scoutlens.benchmark.run_adoption_cost --repeat 3

Each repetition runs in a **fresh child process**. Peak RSS is a per-process
high-water mark, so repetitions sharing a process would carry each other's
memory and the second and third measurements would be meaningless.

The parent binds every run to the recorded D042 model — weight digest, spec
hash, split digest, selected lambda — and refuses to evaluate budgets if any
run measured something other than the adopted path. It then gates on the
**maximum** across runs.

Writes nothing to `artifacts/`. The recorded benchmark artifacts are
read-only inputs here; the model this command serializes goes to a temporary
directory purely so its size can be measured.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from scoutlens.benchmark.adoption_cost import (
    check_identity,
    evaluate_budgets,
    measure_once,
    recorded_identity,
)

CHILD_MARKER = "--__child"


def _run_child() -> int:
    """One measurement, emitted as JSON on stdout."""
    with tempfile.TemporaryDirectory() as directory:
        measurement = measure_once(Path(directory) / "diagonal-model.json")
    sys.stdout.write("<<<MEASUREMENT>>>" + json.dumps(measurement))
    return 0


def _spawn_measurement(index: int) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, "-m", "scoutlens.benchmark.run_adoption_cost", CHILD_MARKER],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"measurement {index} failed (exit {completed.returncode}):\n{completed.stderr[-2000:]}"
        )
    marker = completed.stdout.rfind("<<<MEASUREMENT>>>")
    if marker < 0:
        raise RuntimeError(f"measurement {index} produced no result:\n{completed.stdout[-2000:]}")
    return json.loads(completed.stdout[marker + len("<<<MEASUREMENT>>>") :])


def run(repeat: int = 3) -> dict[str, Any]:
    expected = recorded_identity()
    runs: list[dict[str, Any]] = []
    identity: list[dict[str, Any]] = []

    for index in range(1, repeat + 1):
        measurement = _spawn_measurement(index)
        bound = check_identity(measurement["produced"], expected)
        measurement["identity"] = bound
        identity.append(bound)
        runs.append(measurement)

    all_bound = all(entry["bound"] for entry in identity)
    result: dict[str, Any] = {
        "expected_identity": expected,
        "runs": runs,
        "identity_bound": all_bound,
    }
    if not all_bound:
        result["outcome"] = "STOP"
        result["reason"] = (
            "at least one measurement did not reproduce the recorded D042 model; "
            "a cost measured for a different model is not evidence about this one"
        )
        return result

    result.update(evaluate_budgets(runs))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeat", type=int, default=3, help="number of fresh-process repetitions")
    parser.add_argument(CHILD_MARKER, action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if getattr(args, CHILD_MARKER.lstrip("-")):
        raise SystemExit(_run_child())

    results = run(repeat=args.repeat)

    print(f"identity bound     {results['identity_bound']}")
    for index, entry in enumerate(results["runs"], start=1):
        print(
            f"  run {index}: wall={entry['wall_seconds']:7.1f}s  "
            f"peak_rss={entry['peak_rss_bytes'] / 1024**3:5.2f} GiB  "
            f"serialized={entry['serialized_bytes']:,} B  "
            f"grid={entry['grid_seconds']:.1f}s infer={entry['inference_seconds']:.1f}s"
        )
    if results.get("outcome") == "STOP" and not results["identity_bound"]:
        print(f"OUTCOME            STOP — {results['reason']}")
        raise SystemExit(1)

    maximum = results["maximum"]
    limits = results["limits"]
    print(
        f"maximum            wall={maximum['wall_seconds']:.1f}s / {limits['max_wall_clock_seconds_per_arm']}s  "
        f"peak_rss={maximum['peak_rss_bytes'] / 1024**3:.2f} / {limits['max_peak_rss_bytes'] / 1024**3:.0f} GiB  "
        f"serialized={maximum['serialized_bytes']:,} / {limits['max_artifact_bytes']:,} B"
    )
    for name, ok in results["checks"].items():
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    print(f"OUTCOME            {results['outcome']}")
    if results["outcome"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
