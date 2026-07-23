"""Snapshot checks: do the checked-in result artifacts (artifacts/*.json)
still match the headline numbers written into docs/*.md?

This is a lighter version of "a test that diffs published report numbers
against a freshly-generated artifact" (flagged in review) — it doesn't
re-run the full pipeline (that needs the real ~76MB dataset, which isn't
available in CI, and takes several seconds), but it does catch the
specific failure mode that matters most: someone regenerates an artifact
(after a code change) and forgets to update the prose that quotes it, or
vice versa. Skips cleanly if the artifacts aren't present (e.g. in CI)
rather than failing — these are local, regenerated-on-demand files.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ARTIFACTS_DIR = Path(__file__).resolve().parents[2] / "artifacts"


def _load(name: str) -> dict:
    path = ARTIFACTS_DIR / name
    if not path.exists():
        pytest.skip(f"{name} not present locally — run the matching scoutlens.evaluation.run_* script first")
    return json.loads(path.read_text())


def test_gate2_results_match_documented_headline_numbers():
    data = _load("gate2_results.json")
    assert data["global"]["baseline_a"]["mrr"] == pytest.approx(0.0256, abs=1e-4)
    assert data["global"]["baseline_b"]["mrr"] == pytest.approx(0.2539, abs=1e-4)
    assert data["global"]["baseline_b"]["median_rank"] == 16
    assert data["within_role"]["baseline_b"]["mrr"] == pytest.approx(0.2787, abs=1e-4)
    assert data["within_role"]["baseline_b"]["median_rank"] == 12
    # context-diagnostics.md's corrected (D013) confound figures
    assert data["diagnostics"]["team_concentration_excluding_true_match"] == pytest.approx(0.0120, abs=5e-4)
    assert data["diagnostics"]["league_concentration_excluding_true_match"] == pytest.approx(0.2164, abs=1e-3)


def test_robustness_results_match_documented_headline_numbers():
    data = _load("robustness_results.json")
    assert data["check_3_baseline_c_role_team_minutes"]["mrr"] == pytest.approx(0.5893, abs=1e-3)
    assert data["check_3_baseline_c_role_team_minutes"]["median_rank"] == 2


def test_transfer_analysis_results_match_documented_headline_numbers():
    data = _load("transfer_analysis_results.json")
    assert data["n_transferred"] == 26
    transferred = data["transferred_only"]
    assert transferred["baseline_b"]["mrr"] == pytest.approx(0.2387, abs=1e-3)
    assert transferred["baseline_b"]["median_rank"] == pytest.approx(38.5, abs=0.5)
    assert transferred["baseline_c"]["mrr"] == pytest.approx(0.0101, abs=1e-3)
