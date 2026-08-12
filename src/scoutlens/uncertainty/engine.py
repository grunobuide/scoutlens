"""Offline deterministic match-bootstrap engine and summary artifacts."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import time
import warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

from scoutlens.evaluation.retrieval import select_eligible_both_periods
from scoutlens.evaluation.run_manifest import (
    CONFIG_PATH,
    REPO_ROOT,
    build_run_manifest,
    load_experiment_config,
    sha256_file,
)
from scoutlens.evaluation.temporal import assign_periods
from scoutlens.features.aggregation import (
    FEATURE_COLUMNS,
    build_player_match_statistics,
    compute_weighted_player_features,
)
from scoutlens.uncertainty.checkpoint import (
    CHECKPOINT_FORMAT,
    completed_replicates,
    ensure_checkpoint_manifest,
    read_all_checkpoints,
    write_checkpoint_chunk,
)
from scoutlens.uncertainty.config import (
    UNCERTAINTY_CONFIG_PATH,
    feature_weight_vector,
    load_uncertainty_config,
)
from scoutlens.uncertainty.draws import DrawPlan, build_draw_plan
from scoutlens.uncertainty.ranking import (
    ReplicateRanks,
    apply_diagonal_weights,
    compute_replicate_ranks,
    normalize_feature_rows,
    observed_neighbor_indices,
)
from scoutlens.uncertainty.statistics import average_rank_percentiles

DEFAULT_PROCESSED_DIR = REPO_ROOT / "data" / "processed"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "uncertainty" / "match_bootstrap_v1"
DEFAULT_CHECKPOINT_DIR = REPO_ROOT / "data" / "uncertainty" / "match_bootstrap_v1"


def output_dir_for(design_version: str) -> Path:
    """Artifacts are addressed by design, so a diagonal run cannot overwrite
    the frozen cosine artifacts even if the caller forgets to redirect it."""
    return REPO_ROOT / "artifacts" / "uncertainty" / design_version


def checkpoint_dir_for(design_version: str) -> Path:
    return REPO_ROOT / "data" / "uncertainty" / design_version
RETRIEVAL_OUTCOMES = ("global", "within_role", "baseline_role_minutes")


@dataclasses.dataclass(frozen=True)
class PreparedBootstrap:
    config: dict[str, Any]
    experiment_config: dict[str, Any]
    uncertainty_config_path: Path
    cohort: pl.DataFrame
    grid: pl.DataFrame
    player_match_statistics: pl.DataFrame
    draw_plan: DrawPlan
    observed_raw: np.ndarray
    observed_minutes: np.ndarray
    observed_neighbors: np.ndarray
    roles: np.ndarray
    player_ids: np.ndarray
    competition_ids: np.ndarray
    input_paths: tuple[Path, ...]
    feature_weights: np.ndarray | None = None
    """Diagonal weights aligned to FEATURE_COLUMNS, or None for cosine."""

    @property
    def profile_count(self) -> int:
        return self.cohort.height

    @property
    def representation_id(self) -> str | None:
        representation = self.config.get("representation")
        return None if representation is None else str(representation["id"])


@dataclasses.dataclass(frozen=True)
class ReplicateResult:
    replicate: int
    raw_features: np.ndarray
    role_percentiles: np.ndarray
    minutes: np.ndarray
    present: np.ndarray
    ranks: ReplicateRanks


def _cohort_digest(cohort: pl.DataFrame) -> str:
    rows = cohort.select("player_id", "competitionId", "role").to_dicts()
    payload = json.dumps(rows, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _grid_for_cohort(cohort: pl.DataFrame) -> pl.DataFrame:
    frames = []
    for period_order, period in enumerate(("A", "B")):
        frames.append(
            cohort.with_columns(
                pl.lit(period).alias("period"),
                pl.lit(period_order).alias("period_order"),
            )
        )
    return pl.concat(frames).sort("period_order", "profile_index")


def _align_feature_frame(frame: pl.DataFrame, grid: pl.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    aligned = grid.join(
        frame,
        on=["player_id", "competitionId", "period"],
        how="left",
        maintain_order="left",
    ).sort("period_order", "profile_index")
    profile_count = grid.filter(pl.col("period") == "A").height
    raw = aligned.select(FEATURE_COLUMNS).to_numpy().astype(np.float64, copy=False)
    raw = raw.reshape(2, profile_count, len(FEATURE_COLUMNS))
    minutes = aligned["minutes_played"].to_numpy().astype(np.float64, copy=False).reshape(2, profile_count)
    present = np.isfinite(minutes) & (minutes > 0)
    raw = np.where(present[:, :, None], raw, np.nan)
    return raw, minutes, present


def standardize_replicate(raw: np.ndarray, present: np.ndarray) -> np.ndarray:
    """Apply the frozen combined A+B scaler with non-null mean imputation."""
    flattened = raw.reshape(-1, raw.shape[-1])
    flattened_present = present.reshape(-1)
    output = np.zeros_like(flattened, dtype=np.float64)
    if not np.any(flattened_present):
        return output.reshape(raw.shape)
    selected = flattened[flattened_present]
    for feature_index in range(selected.shape[1]):
        values = selected[:, feature_index]
        finite = np.isfinite(values)
        if not np.any(finite):
            continue
        mean = float(np.mean(values[finite]))
        filled = np.where(finite, values, mean)
        standard_deviation = float(np.std(filled, ddof=1)) if filled.size > 1 else 0.0
        if not np.isfinite(standard_deviation) or standard_deviation == 0:
            continue
        output[flattened_present, feature_index] = (filled - mean) / standard_deviation
    return output.reshape(raw.shape)


def within_role_percentiles(
    standardized: np.ndarray,
    raw: np.ndarray,
    present: np.ndarray,
    roles: np.ndarray,
) -> np.ndarray:
    flattened = standardized.reshape(-1, standardized.shape[-1])
    flattened_raw = raw.reshape(-1, raw.shape[-1])
    flattened_present = present.reshape(-1)
    repeated_roles = np.tile(roles, 2)
    output = np.full_like(flattened, np.nan, dtype=np.float64)
    for role in sorted(set(str(value) for value in roles)):
        role_rows = repeated_roles == role
        for feature_index in range(flattened.shape[1]):
            values = np.where(
                role_rows & flattened_present,
                flattened[:, feature_index],
                np.nan,
            )
            ranked = average_rank_percentiles(values)
            valid_raw = np.isfinite(flattened_raw[:, feature_index])
            output[role_rows & valid_raw, feature_index] = ranked[role_rows & valid_raw]
    return output.reshape(standardized.shape)


def _observed_neighbors(
    raw: np.ndarray,
    present: np.ndarray,
    roles: np.ndarray,
    player_ids: np.ndarray,
    feature_weights: np.ndarray | None = None,
) -> np.ndarray:
    """The five observed neighbours whose selection stability is tracked.

    These must be chosen by the same scorer the run reports on. Picking them
    with cosine and then measuring their stability under a diagonal ranking
    would report the stability of the wrong five players.
    """
    standardized = standardize_replicate(raw, present)
    query = normalize_feature_rows(
        apply_diagonal_weights(standardized[0], feature_weights), present[0]
    )
    candidate = normalize_feature_rows(
        apply_diagonal_weights(standardized[1], feature_weights), present[1]
    )
    similarities = query @ candidate.T
    return observed_neighbor_indices(similarities, roles=roles, player_ids=player_ids, count=5)


def prepare_bootstrap(
    *,
    processed_dir: Path = DEFAULT_PROCESSED_DIR,
    uncertainty_config_path: Path = UNCERTAINTY_CONFIG_PATH,
) -> PreparedBootstrap:
    config = load_uncertainty_config(uncertainty_config_path)
    experiment_config = load_experiment_config()
    names = ("events.parquet", "minutes.parquet", "matches.parquet", "period_profiles.parquet", "players.parquet")
    input_paths = tuple(processed_dir / name for name in names)
    missing = [str(path) for path in input_paths if not path.is_file()]
    if missing:
        raise FileNotFoundError("missing uncertainty inputs: " + ", ".join(missing))

    events = pl.read_parquet(
        processed_dir / "events.parquet",
        columns=[
            "matchId",
            "playerId",
            "eventName",
            "subEventName",
            "tags",
            "positions",
        ],
    )
    minutes = pl.read_parquet(
        processed_dir / "minutes.parquet",
        columns=["player_id", "match_id", "minutes_played"],
    )
    matches = pl.read_parquet(
        processed_dir / "matches.parquet",
        columns=["wyId", "competitionId", "dateutc"],
    ).filter(pl.col("competitionId").is_in(experiment_config["domestic_leagues"]))
    period_profiles = pl.read_parquet(processed_dir / "period_profiles.parquet")
    players = pl.read_parquet(processed_dir / "players.parquet", columns=["wyId", "role"])
    assignment = assign_periods(matches)
    match_ids = assignment["match_id"].to_list()
    events = events.filter(pl.col("matchId").is_in(match_ids))
    minutes = minutes.filter(pl.col("match_id").is_in(match_ids))

    roles = players.select(
        pl.col("wyId").alias("player_id"),
        pl.col("role").struct.field("name").alias("role"),
    )
    eligible = select_eligible_both_periods(
        period_profiles,
        experiment_config["primary_minutes_threshold"],
        experiment_config["domestic_leagues"],
    )
    cohort = (
        eligible.select("player_id", "competitionId")
        .unique()
        .join(roles, on="player_id", how="left")
        .sort("player_id", "competitionId")
        .with_row_index("profile_index")
    )
    if cohort["role"].null_count():
        raise ValueError("fixed uncertainty cohort contains missing roles")
    grid = _grid_for_cohort(cohort)

    statistics = (
        build_player_match_statistics(events, minutes)
        .join(assignment, on="match_id", how="inner")
        .join(cohort.select("player_id", "competitionId"), on=["player_id", "competitionId"], how="inner")
    )
    unit_weights = assignment.select("match_id").with_columns(pl.lit(1).alias("multiplicity"))
    observed_frame = compute_weighted_player_features(
        statistics,
        unit_weights,
        group_columns=["competitionId", "period"],
    )
    observed_raw, observed_minutes, observed_present = _align_feature_frame(observed_frame, grid)
    source_raw, source_minutes, source_present = _align_feature_frame(eligible, grid)
    if not np.array_equal(observed_present, source_present):
        raise ValueError("weighted sufficient statistics changed observed profile presence")
    if not np.allclose(observed_minutes, source_minutes, rtol=0, atol=0, equal_nan=True):
        raise ValueError("weighted sufficient statistics changed observed minutes")
    tolerance = config["assertion_tolerances"]["raw_feature_abs"]
    if not np.allclose(observed_raw, source_raw, rtol=0, atol=tolerance, equal_nan=True):
        difference = float(np.nanmax(np.abs(observed_raw - source_raw)))
        raise ValueError(f"weighted sufficient statistics changed observed features; max abs diff={difference}")

    role_values = cohort["role"].to_numpy()
    player_ids = cohort["player_id"].to_numpy().astype(np.int64, copy=False)
    competition_ids = cohort["competitionId"].to_numpy().astype(np.int64, copy=False)
    weight_values = feature_weight_vector(config, list(FEATURE_COLUMNS))
    feature_weights = None if weight_values is None else np.asarray(weight_values, dtype=np.float64)
    neighbors = _observed_neighbors(
        observed_raw, observed_present, role_values, player_ids, feature_weights
    )
    plan = build_draw_plan(
        assignment,
        requested_resamples=config["requested_resamples"],
        seed=config["seed"],
        design_version=config.get("resampling_design", config["design_version"]),
    )
    return PreparedBootstrap(
        config=config,
        experiment_config=experiment_config,
        uncertainty_config_path=uncertainty_config_path,
        cohort=cohort,
        grid=grid,
        player_match_statistics=statistics,
        draw_plan=plan,
        observed_raw=observed_raw,
        observed_minutes=observed_minutes,
        observed_neighbors=neighbors,
        roles=role_values,
        player_ids=player_ids,
        competition_ids=competition_ids,
        input_paths=input_paths,
        feature_weights=feature_weights,
    )


def checkpoint_manifest(prepared: PreparedBootstrap) -> dict[str, Any]:
    base = build_run_manifest(
        prepared.config,
        list(prepared.input_paths),
        config_path=prepared.uncertainty_config_path,
    )
    try:
        uncertainty_config_ref = prepared.uncertainty_config_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        uncertainty_config_ref = prepared.uncertainty_config_path.as_posix()
    return {
        "format": CHECKPOINT_FORMAT,
        "design_version": prepared.config["design_version"],
        "ranking_method": prepared.config.get("ranking_method", "cosine_v1"),
        "representation_id": prepared.representation_id,
        "requested_resamples": prepared.config["requested_resamples"],
        "supported_workers": [1, 2],
        "feature_columns": FEATURE_COLUMNS,
        "profile_count": prepared.profile_count,
        "cohort_sha256": _cohort_digest(prepared.cohort),
        "draw_plan_sha256": prepared.draw_plan.sha256,
        "git_commit": base["git_commit"],
        "git_dirty": base["git_dirty"],
        "source_sha256": base["source_sha256"],
        "python_version": base["python_version"],
        "polars_version": base["polars_version"],
        "numpy_version": np.__version__,
        "platform": base["platform"],
        "uncertainty_config_path": uncertainty_config_ref,
        "uncertainty_config_sha256": sha256_file(prepared.uncertainty_config_path),
        "uncertainty_config": prepared.config,
        "experiment_config_path": "config/experiment.json",
        "experiment_config_sha256": sha256_file(CONFIG_PATH),
        "experiment_config": prepared.experiment_config,
        "inputs": base["inputs"],
    }


def execute_replicate(prepared: PreparedBootstrap, replicate: int) -> ReplicateResult:
    frame = compute_weighted_player_features(
        prepared.player_match_statistics,
        prepared.draw_plan.weights(replicate),
        group_columns=["competitionId", "period"],
    )
    raw, minutes, present = _align_feature_frame(frame, prepared.grid)
    standardized = standardize_replicate(raw, present)
    percentiles = within_role_percentiles(standardized, raw, present, prepared.roles)
    ranks = compute_replicate_ranks(
        query_features=standardized[0],
        candidate_features=standardized[1],
        query_minutes=np.nan_to_num(minutes[0], nan=0.0),
        candidate_minutes=np.nan_to_num(minutes[1], nan=0.0),
        query_present=present[0],
        candidate_present=present[1],
        roles=prepared.roles,
        player_ids=prepared.player_ids,
        neighbor_indices=prepared.observed_neighbors,
        feature_weights=prepared.feature_weights,
    )
    return ReplicateResult(
        replicate=replicate,
        raw_features=raw,
        role_percentiles=percentiles,
        minutes=minutes,
        present=present,
        ranks=ranks,
    )


def replicate_frame(result: ReplicateResult, prepared: PreparedBootstrap) -> pl.DataFrame:
    profile_count = prepared.profile_count
    data: dict[str, Any] = {
        "replicate": np.full(profile_count * 2, result.replicate, dtype=np.int32),
        "period_order": np.repeat(np.array([0, 1], dtype=np.int8), profile_count),
        "profile_index": np.tile(np.arange(profile_count, dtype=np.int32), 2),
        "player_id": np.tile(prepared.player_ids, 2),
        "competitionId": np.tile(prepared.competition_ids, 2),
        "present": result.present.reshape(-1),
        "minutes": result.minutes.reshape(-1),
    }
    for feature_index, feature_id in enumerate(FEATURE_COLUMNS):
        data[f"raw__{feature_id}"] = result.raw_features[:, :, feature_index].reshape(-1)
        data[f"role_pct__{feature_id}"] = result.role_percentiles[:, :, feature_index].reshape(-1)
    missing_period = np.full(profile_count, np.nan)
    rank_values = (
        result.ranks.global_self,
        result.ranks.within_role_self,
        result.ranks.baseline_role_minutes_self,
    )
    for outcome, values in zip(RETRIEVAL_OUTCOMES, rank_values, strict=True):
        data[f"rank__{outcome}"] = np.concatenate([values, missing_period])
    for slot in range(result.ranks.neighbor_ranks.shape[1]):
        data[f"neighbor_rank__{slot + 1}"] = np.concatenate(
            [result.ranks.neighbor_ranks[:, slot], missing_period]
        )
    return pl.DataFrame(data)


def run_replicates(
    prepared: PreparedBootstrap,
    *,
    checkpoint_dir: Path = DEFAULT_CHECKPOINT_DIR,
    workers: int = 1,
    chunk_size: int = 10,
) -> dict[str, int | float | str]:
    if workers not in (1, 2):
        raise ValueError("supported worker counts are 1 and 2")
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    manifest = checkpoint_manifest(prepared)
    ensure_checkpoint_manifest(checkpoint_dir, manifest)
    completed = completed_replicates(
        checkpoint_dir,
        requested_resamples=prepared.draw_plan.requested_resamples,
        rows_per_replicate=prepared.profile_count * 2,
    )
    pending = [
        replicate
        for replicate in range(prepared.draw_plan.requested_resamples)
        if replicate not in completed
    ]
    started = time.perf_counter()
    written = 0
    for offset in range(0, len(pending), chunk_size):
        batch = pending[offset : offset + chunk_size]
        if workers == 1:
            results = [execute_replicate(prepared, replicate) for replicate in batch]
        else:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                results = list(
                    executor.map(lambda replicate: execute_replicate(prepared, replicate), batch)
                )
        results.sort(key=lambda item: item.replicate)
        frame = pl.concat([replicate_frame(result, prepared) for result in results])
        write_checkpoint_chunk(checkpoint_dir, frame)
        written += len(results)
    elapsed = time.perf_counter() - started
    return {
        "requested_resamples": prepared.draw_plan.requested_resamples,
        "already_completed": len(completed),
        "written_resamples": written,
        "elapsed_seconds": elapsed,
        "draw_plan_sha256": prepared.draw_plan.sha256,
    }


def _nan_quantiles(values: np.ndarray, probabilities: tuple[float, ...]) -> np.ndarray:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        return np.nanquantile(values, probabilities, axis=0, method="linear")


def _nullable(values: np.ndarray, available: np.ndarray) -> list[float | None]:
    return [float(value) if bool(ok) and np.isfinite(value) else None for value, ok in zip(values, available, strict=True)]


def _summarize_features(
    checkpoint_dir: Path,
    prepared: PreparedBootstrap,
    present: np.ndarray,
) -> tuple[pl.DataFrame, dict[str, int]]:
    resamples = prepared.draw_plan.requested_resamples
    shape = (resamples, 2, prepared.profile_count)
    minimum = prepared.config["minimum_valid_resamples"]
    rows: list[pl.DataFrame] = []
    raw_null_present = 0
    infinite_present = 0
    zero_event_present = 0
    for feature_index, feature_id in enumerate(FEATURE_COLUMNS):
        raw_column = f"raw__{feature_id}"
        percentile_column = f"role_pct__{feature_id}"
        projected = read_all_checkpoints(
            checkpoint_dir,
            columns=[raw_column, percentile_column],
        )
        raw = projected[raw_column].to_numpy().reshape(shape)
        percentiles = projected[percentile_column].to_numpy().reshape(shape)
        raw_null_present += int(np.sum(present & np.isnan(raw.reshape(-1))))
        infinite_present += int(np.sum(present & np.isinf(raw.reshape(-1))))
        if feature_id == "events_p90":
            zero_event_present = int(np.sum(present & (raw.reshape(-1) == 0)))
        raw_valid = np.sum(np.isfinite(raw), axis=0)
        percentile_valid = np.sum(np.isfinite(percentiles), axis=0)
        if not np.array_equal(raw_valid, percentile_valid):
            raise ValueError(f"raw/percentile validity denominator drift for {feature_id}")
        point_available = np.isfinite(prepared.observed_raw[:, :, feature_index])
        available = (raw_valid >= minimum) & point_available
        raw_bounds = _nan_quantiles(raw, (0.025, 0.975))
        percentile_bounds = _nan_quantiles(percentiles, (0.025, 0.975))
        flattened_available = available.reshape(-1)
        rows.append(
            pl.DataFrame(
                {
                    "player_id": np.tile(prepared.player_ids, 2),
                    "competitionId": np.tile(prepared.competition_ids, 2),
                    "period": np.repeat(["A", "B"], prepared.profile_count),
                    "feature_id": np.full(prepared.profile_count * 2, feature_id),
                    "status": np.where(flattened_available, "available", "insufficient"),
                    "valid_resamples": raw_valid.reshape(-1),
                    "raw_ci_95_low": _nullable(raw_bounds[0].reshape(-1), flattened_available),
                    "raw_ci_95_high": _nullable(raw_bounds[1].reshape(-1), flattened_available),
                    "within_role_percentile_ci_95_low": _nullable(
                        percentile_bounds[0].reshape(-1), flattened_available
                    ),
                    "within_role_percentile_ci_95_high": _nullable(
                        percentile_bounds[1].reshape(-1), flattened_available
                    ),
                }
            )
        )
    return (
        pl.concat(rows).sort("player_id", "competitionId", "period", "feature_id"),
        {
            "raw_null_present_feature_measures": raw_null_present,
            "positive_minutes_zero_event_profile_resamples": zero_event_present,
            "infinite_present_feature_measures": infinite_present,
        },
    )


def _rank_summary_frame(
    samples: np.ndarray,
    *,
    minimum: int,
) -> tuple[
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
]:
    valid = np.sum(np.isfinite(samples), axis=0)
    available = valid >= minimum
    bounds = _nan_quantiles(samples, (0.025, 0.975))
    median = _nan_quantiles(samples, (0.5,))[0]
    recall_1 = np.divide(
        np.sum(np.isfinite(samples) & (samples <= 1), axis=0),
        valid,
        out=np.full(valid.shape, np.nan, dtype=np.float64),
        where=valid > 0,
    )
    recall_5 = np.divide(
        np.sum(np.isfinite(samples) & (samples <= 5), axis=0),
        valid,
        out=np.full(valid.shape, np.nan, dtype=np.float64),
        where=valid > 0,
    )
    recall_10 = np.divide(
        np.sum(np.isfinite(samples) & (samples <= 10), axis=0),
        valid,
        out=np.full(valid.shape, np.nan, dtype=np.float64),
        where=valid > 0,
    )
    return valid, available, bounds, median, recall_1, recall_5, recall_10


def _summarize_retrieval(checkpoint_dir: Path, prepared: PreparedBootstrap) -> pl.DataFrame:
    rows = []
    minimum = prepared.config["minimum_valid_resamples"]
    columns = ["period_order", *(f"rank__{outcome}" for outcome in RETRIEVAL_OUTCOMES)]
    frame = read_all_checkpoints(checkpoint_dir, columns=columns)
    for outcome in RETRIEVAL_OUTCOMES:
        values = frame.filter(pl.col("period_order") == 0)[f"rank__{outcome}"].to_numpy().reshape(
            prepared.draw_plan.requested_resamples,
            prepared.profile_count,
        )
        valid, available, bounds, median, recall_1, recall_5, recall_10 = _rank_summary_frame(
            values,
            minimum=minimum,
        )
        rows.append(
            pl.DataFrame(
                {
                    "player_id": prepared.player_ids,
                    "competitionId": prepared.competition_ids,
                    "outcome": np.full(prepared.profile_count, outcome),
                    "status": np.where(available, "available", "insufficient"),
                    "valid_resamples": valid,
                    "median_rank": _nullable(median, available),
                    "rank_ci_95_low": _nullable(bounds[0], available),
                    "rank_ci_95_high": _nullable(bounds[1], available),
                    "recall_at_1_rate": _nullable(recall_1, available),
                    "recall_at_5_rate": _nullable(recall_5, available),
                    "recall_at_10_rate": _nullable(recall_10, available),
                }
            )
        )
    return pl.concat(rows).sort("player_id", "competitionId", "outcome")


def _summarize_neighbors(checkpoint_dir: Path, prepared: PreparedBootstrap) -> pl.DataFrame:
    rows = []
    minimum = prepared.config["minimum_valid_resamples"]
    frame = read_all_checkpoints(
        checkpoint_dir,
        columns=["period_order", *(f"neighbor_rank__{slot}" for slot in range(1, 6))],
    )
    query_rows = frame.filter(pl.col("period_order") == 0)
    for slot in range(5):
        values = query_rows[f"neighbor_rank__{slot + 1}"].to_numpy().reshape(
            prepared.draw_plan.requested_resamples,
            prepared.profile_count,
        )
        valid, available, bounds, median, _, selection, _ = _rank_summary_frame(values, minimum=minimum)
        targets = prepared.observed_neighbors[:, slot]
        rows.append(
            pl.DataFrame(
                {
                    "player_id": prepared.player_ids,
                    "competitionId": prepared.competition_ids,
                    "neighbor_slot": np.full(prepared.profile_count, slot + 1),
                    "neighbor_player_id": prepared.player_ids[targets],
                    "neighbor_competitionId": prepared.competition_ids[targets],
                    "status": np.where(available, "available", "insufficient"),
                    "valid_resamples": valid,
                    "top_5_selection_rate": _nullable(selection, available),
                    "median_rank": _nullable(median, available),
                    "rank_ci_95_low": _nullable(bounds[0], available),
                    "rank_ci_95_high": _nullable(bounds[1], available),
                }
            )
        )
    return pl.concat(rows).sort("player_id", "competitionId", "neighbor_slot")


def _write_parquet_atomic(frame: pl.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.tmp"
    frame.write_parquet(temporary, compression="zstd", statistics=True)
    temporary.replace(path)


def write_summary_metadata(metadata: dict[str, Any], output_dir: Path) -> Path:
    """Atomically persist run metadata after all timing fields are known."""
    output_dir.mkdir(parents=True, exist_ok=True)
    run_path = output_dir / "run.json"
    temporary = output_dir / ".run.json.tmp"
    persisted = {key: value for key, value in metadata.items() if key != "run_path"}
    temporary.write_text(
        json.dumps(persisted, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(run_path)
    metadata["run_path"] = str(run_path)
    return run_path


def summarize_checkpoints(
    prepared: PreparedBootstrap,
    *,
    checkpoint_dir: Path = DEFAULT_CHECKPOINT_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    execution: dict[str, int | float | str] | None = None,
) -> dict[str, Any]:
    ensure_checkpoint_manifest(checkpoint_dir, checkpoint_manifest(prepared))
    completed = completed_replicates(
        checkpoint_dir,
        requested_resamples=prepared.draw_plan.requested_resamples,
        rows_per_replicate=prepared.profile_count * 2,
    )
    expected = set(range(prepared.draw_plan.requested_resamples))
    if completed != expected:
        missing = sorted(expected - completed)
        raise ValueError(f"cannot summarize incomplete checkpoints; missing replicates: {missing[:10]}")
    presence = read_all_checkpoints(checkpoint_dir, columns=["period_order", "present"])
    present = presence["present"].to_numpy()
    features, feature_invalid_counts = _summarize_features(
        checkpoint_dir,
        prepared,
        present,
    )
    retrieval = _summarize_retrieval(checkpoint_dir, prepared)
    neighbors = _summarize_neighbors(checkpoint_dir, prepared)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "feature_uncertainty": output_dir / "feature-uncertainty.parquet",
        "retrieval_uncertainty": output_dir / "retrieval-uncertainty.parquet",
        "neighbor_stability": output_dir / "neighbor-stability.parquet",
    }
    _write_parquet_atomic(features, paths["feature_uncertainty"])
    _write_parquet_atomic(retrieval, paths["retrieval_uncertainty"])
    _write_parquet_atomic(neighbors, paths["neighbor_stability"])

    query_present = presence.filter(pl.col("period_order") == 0)["present"].to_numpy()
    candidate_present = presence.filter(pl.col("period_order") == 1)["present"].to_numpy()
    metadata: dict[str, Any] = {
        "format": "scoutlens.match-bootstrap-summary/1",
        "manifest": checkpoint_manifest(prepared),
        "status": (
            "available"
            if prepared.draw_plan.requested_resamples >= prepared.config["minimum_valid_resamples"]
            else "insufficient"
        ),
        "requested_resamples": prepared.draw_plan.requested_resamples,
        "completed_resamples": len(completed),
        "valid_resamples": len(completed),
        "invalid_reason_counts": {
            "absent_query_period_profile_resamples": int(np.sum(~query_present)),
            "absent_candidate_period_profile_resamples": int(np.sum(~candidate_present)),
            **feature_invalid_counts,
        },
        "execution": execution or {},
        "outputs": {},
    }
    for key, path in paths.items():
        metadata["outputs"][key] = {
            "path": path.name,
            "rows": {
                "feature_uncertainty": features,
                "retrieval_uncertainty": retrieval,
                "neighbor_stability": neighbors,
            }[key].height,
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    write_summary_metadata(metadata, output_dir)
    return metadata
