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


@pytest.mark.parametrize(
    "name",
    [
        "gate2_results.json",
        "robustness_results.json",
        "transfer_analysis_results.json",
        "statsbomb_replication_results.json",
        "shrinkage_experiment_results.json",
    ],
)
def test_published_artifact_has_full_run_manifest(name: str):
    manifest = _load(name)["_manifest"]
    assert manifest["config"]["config_version"] == 2
    assert len(manifest["config_sha256"]) == 64
    assert manifest["git_commit"] is None or len(manifest["git_commit"]) == 40
    assert isinstance(manifest["git_dirty"], bool)
    assert len(manifest["source_sha256"]) == 64
    assert manifest["inputs"]


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


def test_statsbomb_replication_results_match_documented_headline_numbers():
    data = _load("statsbomb_replication_results.json")
    # docs/statsbomb-replication.md (D022): the signal replicates at lower magnitude
    assert data["global_28"]["n_eligible"] == 1061
    assert data["global_28"]["baseline_b"]["mrr"] == pytest.approx(0.2031, abs=1e-3)
    assert data["global_28"]["baseline_b"]["median_rank"] == 19
    assert data["global_28"]["mrr_delta"]["ci_low"] > 0            # confidently non-zero
    assert data["within_role_28"]["baseline_b"]["mrr"] == pytest.approx(0.2265, abs=1e-3)
    assert data["transferred_players"]["n_transferred"] == 19
    # transferred edge is inconclusive at small n: CI includes zero
    assert data["transferred_players"]["transferred_only"]["mrr_delta_b_minus_a"]["ci_low"] < 0


def test_shrinkage_experiment_results_match_documented_headline_numbers():
    data = _load("shrinkage_experiment_results.json")
    # docs/shrinkage-experiment.md (D024): shrinkage is a wash for retrieval
    raw = data["raw_v01"]["global"]["baseline_b"]
    shrunk = data["shrunk"]["global"]["baseline_b"]
    assert raw["mrr"] == pytest.approx(0.2539, abs=1e-4)      # reproduces v0.1 exactly
    assert shrunk["mrr"] == pytest.approx(0.2512, abs=1e-3)   # negligibly different
    assert abs(raw["mrr"] - shrunk["mrr"]) < 0.01             # the null result
