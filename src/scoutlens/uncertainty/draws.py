"""Counter-addressed, stratified whole-match bootstrap draw plans."""

from __future__ import annotations

import dataclasses
import hashlib
import json

import numpy as np
import polars as pl


@dataclasses.dataclass(frozen=True)
class DrawPlan:
    match_ids: np.ndarray
    competition_ids: np.ndarray
    periods: tuple[str, ...]
    multiplicities: np.ndarray
    sha256: str

    @property
    def requested_resamples(self) -> int:
        return int(self.multiplicities.shape[0])

    def weights(self, replicate: int) -> pl.DataFrame:
        if not 0 <= replicate < self.requested_resamples:
            raise IndexError(f"replicate out of range: {replicate}")
        values = self.multiplicities[replicate]
        selected = values > 0
        return pl.DataFrame(
            {
                "match_id": self.match_ids[selected],
                "multiplicity": values[selected].astype(np.int64, copy=False),
            }
        )


def counter_source_index(
    *,
    design_version: str,
    seed: int,
    replicate: int,
    competition_id: int,
    period: str,
    draw_index: int,
    source_size: int,
) -> int:
    """Map one counter-addressed SHA-256 draw to an unbiased source index."""
    if source_size <= 0:
        raise ValueError("source_size must be positive")
    limit = 2**64 - (2**64 % source_size)
    attempt = 0
    while True:
        payload = (
            f"{design_version}|{seed}|{replicate}|{competition_id}|{period}|{draw_index}|{attempt}"
        ).encode("utf-8")
        value = int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")
        if value < limit:
            return value % source_size
        attempt += 1


def _plan_digest(
    *,
    match_ids: np.ndarray,
    competition_ids: np.ndarray,
    periods: tuple[str, ...],
    multiplicities: np.ndarray,
) -> str:
    header = json.dumps(
        {
            "format": "scoutlens.match-bootstrap-draw-plan/1",
            "match_ids": [int(value) for value in match_ids],
            "competition_ids": [int(value) for value in competition_ids],
            "periods": list(periods),
            "shape": list(multiplicities.shape),
            "dtype": "uint16-big-endian",
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    digest = hashlib.sha256()
    digest.update(len(header).to_bytes(8, "big"))
    digest.update(header)
    digest.update(multiplicities.astype(">u2", copy=False).tobytes(order="C"))
    return digest.hexdigest()


def build_draw_plan(
    matches: pl.DataFrame,
    *,
    requested_resamples: int,
    seed: int,
    design_version: str,
) -> DrawPlan:
    """Build the complete match-multiplicity matrix before computation."""
    required = {"match_id", "competitionId", "period"}
    missing = required - set(matches.columns)
    if missing:
        raise ValueError(f"matches missing draw-plan columns: {sorted(missing)}")
    if requested_resamples <= 0:
        raise ValueError("requested_resamples must be positive")
    if matches.select("match_id").n_unique() != matches.height:
        raise ValueError("draw-plan match_id values must be unique")
    if matches.filter(~pl.col("period").is_in(["A", "B"])).height:
        raise ValueError("draw-plan periods must be A or B")

    ordered = (
        matches.select("match_id", "competitionId", "period")
        .with_columns(pl.when(pl.col("period") == "A").then(0).otherwise(1).alias("_period_order"))
        .sort("competitionId", "_period_order", "match_id")
        .drop("_period_order")
    )
    match_ids = ordered["match_id"].to_numpy().astype(np.int64, copy=False)
    competition_ids = ordered["competitionId"].to_numpy().astype(np.int64, copy=False)
    periods = tuple(str(value) for value in ordered["period"].to_list())
    multiplicities = np.zeros((requested_resamples, ordered.height), dtype=np.uint16)

    rows = ordered.with_row_index("_index")
    for stratum in rows.partition_by("competitionId", "period", maintain_order=True):
        competition_id = int(stratum["competitionId"][0])
        period = str(stratum["period"][0])
        indices = stratum["_index"].to_numpy().astype(np.int64, copy=False)
        size = len(indices)
        for replicate in range(requested_resamples):
            for draw_index in range(size):
                source_index = counter_source_index(
                    design_version=design_version,
                    seed=seed,
                    replicate=replicate,
                    competition_id=competition_id,
                    period=period,
                    draw_index=draw_index,
                    source_size=size,
                )
                multiplicities[replicate, indices[source_index]] += 1

    digest = _plan_digest(
        match_ids=match_ids,
        competition_ids=competition_ids,
        periods=periods,
        multiplicities=multiplicities,
    )
    return DrawPlan(
        match_ids=match_ids,
        competition_ids=competition_ids,
        periods=periods,
        multiplicities=multiplicities,
        sha256=digest,
    )
