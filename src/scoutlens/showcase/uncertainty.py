"""Integration of validated match-bootstrap summaries into showcase artifacts.

Loads the deterministic match-bootstrap summaries (feature, retrieval,
neighbor) plus their run metadata, and exposes schema-compatible uncertainty
blocks for the showcase builder. Joins are strict: duplicate rows fail, an
unexpected outcome or status fails, and the builder raises when a required
key is missing for any eligible profile.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl

from scoutlens.evaluation.run_manifest import REPO_ROOT
from scoutlens.showcase.catalog import EXPECTED_PROFILE_COUNT
from scoutlens.uncertainty.config import UNCERTAINTY_CONFIG_PATH, load_uncertainty_config

DEFAULT_BOOTSTRAP_RUN_DIR = REPO_ROOT / "artifacts" / "uncertainty" / "match_bootstrap_v1"
DIAGONAL_BOOTSTRAP_RUN_DIR = REPO_ROOT / "artifacts" / "uncertainty" / "match_bootstrap_diagonal_v1"

DIAGONAL_DESIGN = "match_bootstrap_diagonal_v1"
DIAGONAL_RANKING_METHOD = "weighted_cosine_diagonal_v1"

RUN_METADATA_FILE = "run.json"
FEATURE_FILE = "feature-uncertainty.parquet"
RETRIEVAL_FILE = "retrieval-uncertainty.parquet"
NEIGHBOR_FILE = "neighbor-stability.parquet"

RANK_OUTCOMES = ("global", "within_role", "baseline_role_minutes")
NEIGHBOR_SLOTS = (1, 2, 3, 4, 5)
VALID_STATUSES = ("available", "insufficient")

FEATURE_KEY_COLUMNS = ["player_id", "competitionId", "period", "feature_id"]
RANK_KEY_COLUMNS = ["player_id", "competitionId", "outcome"]
NEIGHBOR_KEY_COLUMNS = ["player_id", "competitionId", "neighbor_slot"]


def _pair(low: float | None, high: float | None) -> list[float] | None:
    if low is None or high is None:
        return None
    return [float(low), float(high)]


def _rank_block(row: dict[str, Any]) -> dict[str, Any]:
    """Schema-exact rank uncertainty: no field outside rank_uncertainty."""
    status = str(row["status"])
    if status == "insufficient":
        return {
            "status": status,
            "valid_resamples": int(row["valid_resamples"]),
            "median_rank": None,
            "rank_ci_95": None,
            "recall_at_1_rate": None,
            "recall_at_5_rate": None,
            "recall_at_10_rate": None,
        }
    return {
        "status": status,
        "valid_resamples": int(row["valid_resamples"]),
        "median_rank": None if row["median_rank"] is None else float(row["median_rank"]),
        "rank_ci_95": _pair(row["rank_ci_95_low"], row["rank_ci_95_high"]),
        "recall_at_1_rate": None if row["recall_at_1_rate"] is None else float(row["recall_at_1_rate"]),
        "recall_at_5_rate": None if row["recall_at_5_rate"] is None else float(row["recall_at_5_rate"]),
        "recall_at_10_rate": None if row["recall_at_10_rate"] is None else float(row["recall_at_10_rate"]),
    }


def _feature_block(row: dict[str, Any]) -> dict[str, Any]:
    status = str(row["status"])
    return {
        "status": status,
        "valid_resamples": int(row["valid_resamples"]),
        "raw_ci_95": _pair(row["raw_ci_95_low"], row["raw_ci_95_high"]) if status == "available" else None,
        "within_role_percentile_ci_95": (
            _pair(row["within_role_percentile_ci_95_low"], row["within_role_percentile_ci_95_high"])
            if status == "available"
            else None
        ),
    }


def _neighbor_block(row: dict[str, Any]) -> dict[str, Any]:
    """Schema-exact neighbor stability: no field outside neighbor_stability."""
    status = str(row["status"])
    if status == "insufficient":
        return {
            "status": status,
            "valid_resamples": int(row["valid_resamples"]),
            "top_5_selection_rate": None,
            "median_rank": None,
            "rank_ci_95": None,
        }
    return {
        "status": status,
        "valid_resamples": int(row["valid_resamples"]),
        "top_5_selection_rate": None if row["top_5_selection_rate"] is None else float(row["top_5_selection_rate"]),
        "median_rank": None if row["median_rank"] is None else float(row["median_rank"]),
        "rank_ci_95": _pair(row["rank_ci_95_low"], row["rank_ci_95_high"]),
    }


def _indexed_rows(frame: pl.DataFrame, key_columns: list[str], label: str) -> dict[tuple[Any, ...], dict[str, Any]]:
    rows: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in frame.to_dicts():
        key = tuple(row[column] for column in key_columns)
        if key in rows:
            raise ValueError(f"{label}: duplicate key {key}")
        rows[key] = row
    return rows


@dataclass(frozen=True)
class BootstrapSummaries:
    """Schema-compatible uncertainty blocks keyed by the eligibility unit."""

    feature: dict[tuple[int, int, str, str], dict[str, Any]]
    rank: dict[tuple[int, int, str], dict[str, Any]]
    neighbor: dict[tuple[int, int, int], dict[str, Any]]
    profile_block: dict[tuple[int, int], dict[str, Any]]
    profile_status: dict[tuple[int, int], str]


def load_bootstrap_summaries(
    run_dir: Path = DEFAULT_BOOTSTRAP_RUN_DIR,
    uncertainty_config_path: Path = UNCERTAINTY_CONFIG_PATH,
    representation: Any = None,
) -> BootstrapSummaries:
    """Load and cross-check the complete canonical bootstrap run.

    Fails when a file is missing, a key duplicates, an outcome or slot is
    unexpected, a status is not available/insufficient, or the run metadata
    disagrees with the frozen uncertainty configuration.
    """
    metadata_path = run_dir / RUN_METADATA_FILE
    if not metadata_path.is_file():
        raise FileNotFoundError(f"missing bootstrap run metadata: {metadata_path}")

    config = load_uncertainty_config(uncertainty_config_path)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("status") != "available":
        raise ValueError(f"bootstrap run is not available: {metadata.get('status')!r}")
    run_manifest = metadata["manifest"]
    if run_manifest.get("design_version") != config["design_version"]:
        raise ValueError(
            "bootstrap design version disagrees with frozen uncertainty config: "
            f"{run_manifest.get('design_version')!r} != {config['design_version']!r}"
        )
    if int(run_manifest.get("profile_count", -1)) != EXPECTED_PROFILE_COUNT:
        raise ValueError(
            f"bootstrap cohort size disagrees with the frozen eligible population: "
            f"{run_manifest.get('profile_count')!r} != {EXPECTED_PROFILE_COUNT}"
        )

    # A v2 bundle may only carry intervals computed under its own
    # representation. v1 intervals describe the sampling stability of
    # COSINE-based ranks; attaching them to diagonal rankings would show an
    # interval that does not describe the number beside it.
    if representation is not None:
        if config["design_version"] != DIAGONAL_DESIGN:
            raise ValueError(
                f"a diagonal bundle requires design {DIAGONAL_DESIGN}, but the uncertainty "
                f"config declares {config['design_version']!r}"
            )
        if run_manifest.get("ranking_method") != DIAGONAL_RANKING_METHOD:
            raise ValueError(
                f"bootstrap run was scored with {run_manifest.get('ranking_method')!r}, not "
                f"{DIAGONAL_RANKING_METHOD!r}; cosine uncertainty cannot describe a diagonal ranking"
            )
        recorded_id = run_manifest.get("representation_id")
        if recorded_id != representation.id:
            raise ValueError(
                f"bootstrap run was computed under representation {recorded_id!r}, not "
                f"{representation.id!r}"
            )

    feature = _indexed_rows(pl.read_parquet(run_dir / FEATURE_FILE), FEATURE_KEY_COLUMNS, FEATURE_FILE)
    rank = _indexed_rows(pl.read_parquet(run_dir / RETRIEVAL_FILE), RANK_KEY_COLUMNS, RETRIEVAL_FILE)
    neighbor = _indexed_rows(pl.read_parquet(run_dir / NEIGHBOR_FILE), NEIGHBOR_KEY_COLUMNS, NEIGHBOR_FILE)

    for key, row in rank.items():
        if key[2] not in RANK_OUTCOMES:
            raise ValueError(f"{RETRIEVAL_FILE}: unexpected outcome {key[2]!r}")
        if row["status"] not in VALID_STATUSES:
            raise ValueError(f"{RETRIEVAL_FILE}: unexpected status {row['status']!r} at {key}")
    for key, row in feature.items():
        if row["status"] not in VALID_STATUSES:
            raise ValueError(f"{FEATURE_FILE}: unexpected status {row['status']!r} at {key}")
    for key, row in neighbor.items():
        if key[2] not in NEIGHBOR_SLOTS:
            raise ValueError(f"{NEIGHBOR_FILE}: unexpected neighbor slot {key[2]!r}")
        if row["status"] not in VALID_STATUSES:
            raise ValueError(f"{NEIGHBOR_FILE}: unexpected status {row['status']!r} at {key}")

    # The v2 schema requires representation_id on every uncertainty-bearing
    # block, so an interval can always be traced to the metric it was
    # computed under. v1 blocks are emitted unchanged.
    binding = {} if representation is None else {"representation_id": representation.id}
    feature_blocks = {key: {**_feature_block(row), **binding} for key, row in feature.items()}
    rank_blocks = {key: {**_rank_block(row), **binding} for key, row in rank.items()}
    neighbor_blocks = {
        key: {**_neighbor_block(row), **binding} for key, row in neighbor.items()
    }

    warning = str(config["warning"])
    profile_status: dict[tuple[int, int], str] = {}
    profile_block: dict[tuple[int, int], dict[str, Any]] = {}
    for player_id, competition_id in {(key[0], key[1]) for key in rank}:
        global_key = (player_id, competition_id, "global")
        if global_key not in rank:
            raise ValueError(f"{RETRIEVAL_FILE}: profile has no global outcome: {(player_id, competition_id)}")
        global_row = rank[global_key]
        status = str(global_row["status"])
        profile_status[(player_id, competition_id)] = status
        profile_block[(player_id, competition_id)] = {
            "status": status,
            "design_version": config["design_version"],
            "seed": config["seed"],
            "requested_resamples": config["requested_resamples"],
            "valid_resamples": int(global_row["valid_resamples"]),
            "interval": config["interval"],
            "resampling_unit": config["resampling_unit"],
            "cohort_policy": config["cohort_policy"],
            "warning": warning,
            **(
                {}
                if representation is None
                else {"representation_id": representation.id}
            ),
        }

    return BootstrapSummaries(
        feature=feature_blocks,
        rank=rank_blocks,
        neighbor=neighbor_blocks,
        profile_block=profile_block,
        profile_status=profile_status,
    )


def require_feature(summaries: BootstrapSummaries, key: tuple[int, int, str, str]) -> dict[str, Any]:
    try:
        return summaries.feature[key]
    except KeyError as exc:
        raise ValueError(f"missing bootstrap feature uncertainty row: {key}") from exc


def require_rank(summaries: BootstrapSummaries, key: tuple[int, int, str]) -> dict[str, Any]:
    try:
        return summaries.rank[key]
    except KeyError as exc:
        raise ValueError(f"missing bootstrap rank uncertainty row: {key}") from exc


def require_neighbor(summaries: BootstrapSummaries, key: tuple[int, int, int]) -> dict[str, Any]:
    try:
        return summaries.neighbor[key]
    except KeyError as exc:
        raise ValueError(f"missing bootstrap neighbor stability row: {key}") from exc
