from __future__ import annotations

import numpy as np

from scoutlens.uncertainty.ranking import (
    compute_replicate_ranks,
    normalize_feature_rows,
    observed_neighbor_indices,
)


def test_normalization_keeps_absent_and_zero_norm_rows_at_zero() -> None:
    values = np.array([[3.0, 4.0], [1.0, 1.0], [0.0, 0.0]])
    result = normalize_feature_rows(values, np.array([True, False, True]))
    assert result.tolist() == [[0.6, 0.8], [0.0, 0.0], [0.0, 0.0]]


def test_observed_neighbors_exclude_same_human_and_break_ties_by_identity() -> None:
    similarities = np.array(
        [
            [1.0, 0.9, 0.9, 0.8],
            [0.9, 1.0, 0.7, 0.6],
            [0.9, 0.7, 1.0, 0.6],
            [0.8, 0.6, 0.6, 1.0],
        ]
    )
    roles = np.array(["M", "M", "M", "M"])
    player_ids = np.array([1, 2, 3, 1])
    neighbors = observed_neighbor_indices(similarities, roles=roles, player_ids=player_ids, count=2)
    assert neighbors[0].tolist() == [1, 2]
    assert 3 not in neighbors[0]


def test_replicate_ranking_penalizes_absent_candidates_and_invalidates_absent_queries() -> None:
    query_features = np.array([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0], [0.0, 1.0]])
    candidate_features = query_features.copy()
    query_present = np.array([True, True, False, True])
    candidate_present = np.array([True, True, False, True])
    roles = np.array(["M", "M", "M", "F"])
    player_ids = np.array([1, 2, 3, 4])
    neighbors = np.array([[2], [2], [1], [0]])

    result = compute_replicate_ranks(
        query_features=query_features,
        candidate_features=candidate_features,
        query_minutes=np.array([90.0, 80.0, 70.0, 90.0]),
        candidate_minutes=np.array([90.0, 80.0, 0.0, 90.0]),
        query_present=query_present,
        candidate_present=candidate_present,
        roles=roles,
        player_ids=player_ids,
        neighbor_indices=neighbors,
    )

    assert result.global_self[0] == 1
    assert result.global_self[1] == 2
    assert np.isnan(result.global_self[2])
    assert result.neighbor_ranks[0, 0] == 2
    assert np.isnan(result.neighbor_ranks[2, 0])
    assert np.isnan(result.neighbor_ranks[3, 0])
