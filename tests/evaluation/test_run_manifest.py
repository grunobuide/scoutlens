"""Unit tests for the versioned config + run manifest (D015)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scoutlens.evaluation.run_manifest import (
    CONFIG_PATH,
    build_run_manifest,
    load_experiment_config,
    sha256_file,
)


def test_sha256_file_matches_hashlib(tmp_path: Path):
    p = tmp_path / "blob.bin"
    payload = b"scoutlens" * 10_000
    p.write_bytes(payload)
    assert sha256_file(p) == hashlib.sha256(payload).hexdigest()


def test_real_config_loads_and_pins_the_published_experiment():
    """The versioned config must keep carrying the exact parameters the
    published v0.1 numbers were produced with — changing them is allowed,
    but must be a conscious act that also updates this pin (and the
    artifacts, and the docs quoting them)."""
    config = load_experiment_config()
    assert config["domestic_leagues"] == [364, 412, 426, 524, 795]
    assert config["primary_minutes_threshold"] == 450
    assert config["sensitivity_thresholds"] == [225, 450, 675, 900, 1125, 1350]
    assert config["top_k_for_diagnostics"] == 10
    assert config["bootstrap"] == {"n_resamples": 1000, "seed": 0}


def test_build_run_manifest_ties_config_and_inputs(tmp_path: Path):
    config_path = tmp_path / "experiment.json"
    config = {"threshold": 42}
    config_path.write_text(json.dumps(config), encoding="utf-8")

    input_a = tmp_path / "a.parquet"
    input_b = tmp_path / "b.parquet"
    input_a.write_bytes(b"aaa")
    input_b.write_bytes(b"bbbb")

    manifest = build_run_manifest(config, [input_b, input_a], config_path=config_path)

    assert manifest["config"] == config
    assert manifest["config_sha256"] == sha256_file(config_path)
    assert manifest["generated_at"].endswith("+00:00")
    assert manifest["git_commit"] is None or len(manifest["git_commit"]) == 40
    assert set(manifest["inputs"]) == {"a.parquet", "b.parquet"}
    assert manifest["inputs"]["a.parquet"] == {
        "sha256": hashlib.sha256(b"aaa").hexdigest(),
        "bytes": 3,
    }
    assert list(manifest["inputs"]) == ["a.parquet", "b.parquet"]  # sorted, deterministic


def test_default_config_path_is_the_versioned_file():
    assert CONFIG_PATH.name == "experiment.json"
    assert CONFIG_PATH.parent.name == "config"
    assert CONFIG_PATH.exists()
