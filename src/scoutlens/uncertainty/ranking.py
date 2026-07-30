"""Vectorized deterministic ranking over a fixed profile universe."""

from __future__ import annotations

import dataclasses

import numpy as np


@dataclasses.dataclass(frozen=True)
class ReplicateRanks:
    global_self: np.ndarray
    within_role_self: np.ndarray
    baseline_role_minutes_self: np.ndarray
    neighbor_ranks: np.ndarray


def normalize_feature_rows(values: np.ndarray, present: np.ndarray) -> np.ndarray:
    output = np.zeros_like(values, dtype=np.float64)
    if not np.any(present):
        return output
    selected = values[present]
    norms = np.linalg.norm(selected, axis=1)
    nonzero = norms > 0
    selected_output = np.zeros_like(selected)
    selected_output[nonzero] = selected[nonzero] / norms[nonzero, None]
    output[present] = selected_output
    return output


def observed_neighbor_indices(
    similarities: np.ndarray,
    *,
    roles: np.ndarray,
    player_ids: np.ndarray,
    count: int = 5,
) -> np.ndarray:
    size = similarities.shape[0]
    output = np.empty((size, count), dtype=np.int64)
    identity_order = np.arange(size)
    for query in range(size):
        pool = (roles == roles[query]) & (player_ids != player_ids[query])
        candidates = identity_order[pool]
        order = np.lexsort((candidates, -similarities[query, candidates]))
        if order.size < count:
            raise ValueError(f"query {query} has fewer than {count} observed non-self neighbors")
        output[query] = candidates[order[:count]]
    return output


def compute_replicate_ranks(
    *,
    query_features: np.ndarray,
    candidate_features: np.ndarray,
    query_minutes: np.ndarray,
    candidate_minutes: np.ndarray,
    query_present: np.ndarray,
    candidate_present: np.ndarray,
    roles: np.ndarray,
    player_ids: np.ndarray,
    neighbor_indices: np.ndarray,
) -> ReplicateRanks:
    """Rank self and observed neighbors with missing candidates at the bottom."""
    size = query_features.shape[0]
    if candidate_features.shape[0] != size:
        raise ValueError("query and candidate fixed cohorts must have equal size")
    identity_before = np.arange(size)[None, :] < np.arange(size)[:, None]
    same_role = roles[None, :] == roles[:, None]

    normalized_queries = normalize_feature_rows(query_features, query_present)
    normalized_candidates = normalize_feature_rows(candidate_features, candidate_present)
    similarities = normalized_queries @ normalized_candidates.T
    effective = similarities.copy()
    effective[:, ~candidate_present] = -np.inf

    self_scores = effective[np.arange(size), np.arange(size)]
    global_ranks = 1 + np.sum(effective > self_scores[:, None], axis=1) + np.sum(
        (effective == self_scores[:, None]) & identity_before,
        axis=1,
    )
    global_valid = query_present & np.any(candidate_present)

    within_ranks = 1 + np.sum((effective > self_scores[:, None]) & same_role, axis=1) + np.sum(
        (effective == self_scores[:, None]) & same_role & identity_before,
        axis=1,
    )
    within_valid = query_present & np.any(same_role & candidate_present[None, :], axis=1)

    distances = np.abs(query_minutes[:, None] - candidate_minutes[None, :])
    distances[:, ~candidate_present] = np.inf
    self_distances = distances[np.arange(size), np.arange(size)]
    baseline_ranks = 1 + np.sum((distances < self_distances[:, None]) & same_role, axis=1) + np.sum(
        (distances == self_distances[:, None]) & same_role & identity_before,
        axis=1,
    )

    nonself_role_pool = same_role & (player_ids[None, :] != player_ids[:, None])
    neighbor_valid = query_present & np.any(nonself_role_pool & candidate_present[None, :], axis=1)
    neighbor_ranks = np.empty(neighbor_indices.shape, dtype=np.float64)
    for slot in range(neighbor_indices.shape[1]):
        targets = neighbor_indices[:, slot]
        target_scores = effective[np.arange(size), targets]
        before_target = np.arange(size)[None, :] < targets[:, None]
        neighbor_ranks[:, slot] = 1 + np.sum(
            (effective > target_scores[:, None]) & nonself_role_pool,
            axis=1,
        ) + np.sum(
            (effective == target_scores[:, None]) & nonself_role_pool & before_target,
            axis=1,
        )
    neighbor_ranks[~neighbor_valid] = np.nan

    outputs = [global_ranks.astype(np.float64), within_ranks.astype(np.float64), baseline_ranks.astype(np.float64)]
    for values, valid in zip(outputs, (global_valid, within_valid, within_valid), strict=True):
        values[~valid] = np.nan
    return ReplicateRanks(
        global_self=outputs[0],
        within_role_self=outputs[1],
        baseline_role_minutes_self=outputs[2],
        neighbor_ranks=neighbor_ranks,
    )
