"""Fresh-run drift test (D015): regenerate each result set from the real
data and compare it against the checked-in artifact, number by number.

This is the missing third leg of the reproducibility chain:

    docs  <-- test_artifacts.py -->  checked-in artifacts  <-- this file -->  fresh run

test_artifacts.py pins the checked-in artifacts to the numbers quoted in
the docs; this file proves the current code + config + local data still
produce those artifacts exactly. Together they catch drift in either
direction automatically.

Opt-in, because a full fresh run needs the real local dataset and takes
minutes (run_robustness's drop-teammates check alone iterates 1,257
queries). Reproduce with:

    SCOUTLENS_DRIFT=1 uv run pytest tests/evaluation/test_artifact_drift.py -v

Every comparison is exact for ints/strings and tight-tolerance for
floats: all randomness is seeded and `bootstrap_mrr_delta` sorts before
resampling (D013), so a same-data, same-config, same-code rerun must
reproduce every number, CI bounds included.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

ARTIFACTS_DIR = Path(__file__).resolve().parents[2] / "artifacts"
PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"

pytestmark = pytest.mark.skipif(
    os.environ.get("SCOUTLENS_DRIFT") != "1",
    reason="fresh-run drift test is opt-in (needs local data, takes minutes): set SCOUTLENS_DRIFT=1",
)

VOLATILE_KEYS = {"_manifest", "_metadata"}


def _assert_same(fresh, stored, path=""):
    if isinstance(stored, dict):
        assert isinstance(fresh, dict), f"{path}: type changed"
        f_keys = {k for k in fresh if k not in VOLATILE_KEYS}
        s_keys = {k for k in stored if k not in VOLATILE_KEYS}
        assert f_keys == s_keys, f"{path}: keys differ ({f_keys ^ s_keys})"
        for k in s_keys:
            _assert_same(fresh[k], stored[k], f"{path}.{k}")
    elif isinstance(stored, list):
        assert isinstance(fresh, list) and len(fresh) == len(stored), f"{path}: length changed"
        for i, (f, s) in enumerate(zip(fresh, stored)):
            _assert_same(f, s, f"{path}[{i}]")
    elif isinstance(stored, float):
        assert fresh == pytest.approx(stored, rel=1e-9, abs=1e-12), f"{path}: {fresh} != {stored}"
    else:
        assert fresh == stored, f"{path}: {fresh!r} != {stored!r}"


def _drift_check(module_name: str, artifact_name: str):
    if not PROCESSED_DIR.exists():
        pytest.skip("data/processed not present — build it first (see README)")
    artifact_path = ARTIFACTS_DIR / artifact_name
    if not artifact_path.exists():
        pytest.skip(f"{artifact_name} not present — run the matching run_* script first")

    import importlib

    module = importlib.import_module(f"scoutlens.evaluation.{module_name}")
    fresh = json.loads(json.dumps(module.run()))  # normalize via the same JSON round-trip the artifact went through
    stored = json.loads(artifact_path.read_text())
    _assert_same(fresh, stored)


def test_gate2_results_have_not_drifted():
    _drift_check("run_report", "gate2_results.json")


def test_robustness_results_have_not_drifted():
    _drift_check("run_robustness", "robustness_results.json")


def test_transfer_analysis_results_have_not_drifted():
    _drift_check("run_transfer_analysis", "transfer_analysis_results.json")
