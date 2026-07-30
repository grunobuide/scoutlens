"""Frozen percentile, validity and interval summaries."""

from __future__ import annotations

import math

import numpy as np


def quantile_type7(values: np.ndarray, probability: float) -> float:
    finite = np.sort(np.asarray(values, dtype=np.float64)[np.isfinite(values)])
    if finite.size == 0:
        raise ValueError("quantile requires at least one finite value")
    if not 0 <= probability <= 1:
        raise ValueError("probability must be in [0, 1]")
    position = (finite.size - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(finite[lower])
    fraction = position - lower
    return float(finite[lower] + (finite[upper] - finite[lower]) * fraction)


def average_rank_percentiles(values: np.ndarray) -> np.ndarray:
    """Return 0..100 average-rank percentiles, preserving NaN rows."""
    values = np.asarray(values, dtype=np.float64)
    output = np.full(values.shape, np.nan, dtype=np.float64)
    finite_indices = np.flatnonzero(np.isfinite(values))
    count = finite_indices.size
    if count == 0:
        return output
    if count == 1:
        output[finite_indices[0]] = 50.0
        return output
    order = finite_indices[np.argsort(values[finite_indices], kind="stable")]
    sorted_values = values[order]
    start = 0
    while start < count:
        end = start + 1
        while end < count and sorted_values[end] == sorted_values[start]:
            end += 1
        average_zero_based_rank = (start + end - 1) / 2
        output[order[start:end]] = average_zero_based_rank / (count - 1) * 100
        start = end
    return output


def summarize_interval(
    values: np.ndarray,
    *,
    minimum_valid: int,
    point_available: bool = True,
) -> dict[str, object]:
    finite = np.asarray(values, dtype=np.float64)
    finite = finite[np.isfinite(finite)]
    valid = int(finite.size)
    available = point_available and valid >= minimum_valid
    return {
        "status": "available" if available else "insufficient",
        "valid_resamples": valid,
        "ci_95": (
            [quantile_type7(finite, 0.025), quantile_type7(finite, 0.975)]
            if available
            else None
        ),
    }


def summarize_ranks(values: np.ndarray, *, minimum_valid: int) -> dict[str, object]:
    summary = summarize_interval(values, minimum_valid=minimum_valid)
    finite = np.asarray(values, dtype=np.float64)
    finite = finite[np.isfinite(finite)]
    if summary["status"] != "available":
        return {
            "status": "insufficient",
            "valid_resamples": summary["valid_resamples"],
            "median_rank": None,
            "rank_ci_95": None,
            "recall_at_1_rate": None,
            "recall_at_5_rate": None,
            "recall_at_10_rate": None,
        }
    return {
        "status": "available",
        "valid_resamples": summary["valid_resamples"],
        "median_rank": quantile_type7(finite, 0.5),
        "rank_ci_95": summary["ci_95"],
        "recall_at_1_rate": float(np.mean(finite <= 1)),
        "recall_at_5_rate": float(np.mean(finite <= 5)),
        "recall_at_10_rate": float(np.mean(finite <= 10)),
    }


def summarize_neighbor_ranks(values: np.ndarray, *, minimum_valid: int) -> dict[str, object]:
    rank_summary = summarize_ranks(values, minimum_valid=minimum_valid)
    return {
        "status": rank_summary["status"],
        "valid_resamples": rank_summary["valid_resamples"],
        "top_5_selection_rate": rank_summary["recall_at_5_rate"],
        "median_rank": rank_summary["median_rank"],
        "rank_ci_95": rank_summary["rank_ci_95"],
    }
