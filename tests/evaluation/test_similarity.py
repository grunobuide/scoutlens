import math

import polars as pl

from scoutlens.evaluation.similarity import baseline_a_rank, baseline_b_rank, impute_and_standardize


def _candidates(*rows):
    """rows of (player_id, role, minutes_played)."""
    return pl.DataFrame({
        "player_id": [r[0] for r in rows],
        "role": [r[1] for r in rows],
        "minutes_played": [r[2] for r in rows],
    })


def test_same_role_candidates_always_rank_before_different_role():
    """Even a same-role candidate with a huge minutes gap must outrank a
    different-role candidate with an identical minutes total."""
    candidates = _candidates(
        (1, "Forward", 500),  # same role, far in minutes
        (2, "Defender", 1000),  # different role, exact minutes match
    )
    result = baseline_a_rank(query_role="Forward", query_minutes=1000, candidates=candidates)
    assert result.sort("rank")["player_id"].to_list() == [1, 2]


def test_within_same_role_nearest_minutes_ranks_first():
    candidates = _candidates(
        (1, "Midfielder", 200),
        (2, "Midfielder", 950),
        (3, "Midfielder", 1000),
    )
    result = baseline_a_rank(query_role="Midfielder", query_minutes=1000, candidates=candidates)
    assert result.sort("rank")["player_id"].to_list() == [3, 2, 1]


def test_rank_column_is_one_indexed_and_covers_every_candidate():
    candidates = _candidates((1, "Goalkeeper", 100), (2, "Goalkeeper", 200), (3, "Forward", 300))
    result = baseline_a_rank(query_role="Goalkeeper", query_minutes=150, candidates=candidates)
    assert sorted(result["rank"].to_list()) == [1, 2, 3]


def test_ties_broken_deterministically_by_player_id():
    """Two same-role candidates equidistant in minutes must not have
    arbitrary/unstable ordering across runs."""
    candidates = _candidates((5, "Defender", 900), (2, "Defender", 1100))
    result = baseline_a_rank(query_role="Defender", query_minutes=1000, candidates=candidates)
    # both are 100 minutes away -- lower player_id wins the tiebreak
    assert result.sort("rank")["player_id"].to_list() == [2, 5]


def test_query_own_player_id_can_appear_in_candidates_and_rank_first_if_identical():
    """The temporal retrieval use case (SLS-018) ranks a period-B pool that
    includes the same player's own period-B row -- that's the target being
    searched for, not something to exclude here."""
    candidates = _candidates((1, "Forward", 1000), (2, "Forward", 500))
    result = baseline_a_rank(query_role="Forward", query_minutes=1000, candidates=candidates)
    assert result.sort("rank")["player_id"].to_list()[0] == 1


def test_impute_and_standardize_produces_zero_mean_unit_std():
    profiles = pl.DataFrame({"f": [10.0, 20.0, 30.0]})
    result = impute_and_standardize(profiles, ["f"])
    assert abs(result["f"].mean()) < 1e-9
    assert abs(result["f"].std() - 1.0) < 1e-9


def test_impute_and_standardize_null_becomes_exactly_zero():
    """Mean-imputation preserves the population mean, so a null's z-score
    must come out to exactly 0 -- "average, uninformative," not a
    fabricated extreme."""
    profiles = pl.DataFrame({"f": [10.0, 20.0, None]})
    result = impute_and_standardize(profiles, ["f"])
    null_row_value = result["f"][2]
    assert null_row_value == 0.0


def test_impute_and_standardize_constant_column_becomes_zero_not_nan():
    profiles = pl.DataFrame({"f": [5.0, 5.0, 5.0]})
    result = impute_and_standardize(profiles, ["f"])
    assert result["f"].to_list() == [0.0, 0.0, 0.0]


def test_impute_and_standardize_all_null_column_becomes_zero():
    profiles = pl.DataFrame({"f": [None, None, None]}, schema={"f": pl.Float64})
    result = impute_and_standardize(profiles, ["f"])
    assert result["f"].to_list() == [0.0, 0.0, 0.0]


def _b_candidates(*rows):
    """rows of (player_id, f1, f2)."""
    return pl.DataFrame({
        "player_id": [r[0] for r in rows],
        "f1": [r[1] for r in rows],
        "f2": [r[2] for r in rows],
    })


def test_baseline_b_identical_vector_ranks_first_with_similarity_one():
    candidates = _b_candidates((1, 1.0, 0.0), (2, 0.0, 1.0))
    result = baseline_b_rank({"f1": 1.0, "f2": 0.0}, candidates, ["f1", "f2"])
    top = result.sort("rank").row(0, named=True)
    assert top["player_id"] == 1
    assert abs(top["cosine_similarity"] - 1.0) < 1e-9


def test_baseline_b_orthogonal_vector_has_zero_similarity():
    candidates = _b_candidates((1, 0.0, 1.0))
    result = baseline_b_rank({"f1": 1.0, "f2": 0.0}, candidates, ["f1", "f2"])
    assert abs(result.row(0, named=True)["cosine_similarity"]) < 1e-9


def test_baseline_b_opposite_vector_has_negative_similarity():
    candidates = _b_candidates((1, -1.0, 0.0))
    result = baseline_b_rank({"f1": 1.0, "f2": 0.0}, candidates, ["f1", "f2"])
    assert abs(result.row(0, named=True)["cosine_similarity"] - (-1.0)) < 1e-9


def test_baseline_b_zero_norm_candidate_does_not_crash_and_scores_zero():
    candidates = _b_candidates((1, 0.0, 0.0), (2, 1.0, 0.0))
    result = baseline_b_rank({"f1": 1.0, "f2": 0.0}, candidates, ["f1", "f2"])
    by_player = {r["player_id"]: r for r in result.to_dicts()}
    assert by_player[1]["cosine_similarity"] == 0.0
    assert not math.isnan(by_player[1]["cosine_similarity"])
    assert by_player[2]["rank"] == 1


def test_baseline_b_ties_broken_deterministically_by_player_id():
    candidates = _b_candidates((5, 1.0, 0.0), (2, 1.0, 0.0))
    result = baseline_b_rank({"f1": 1.0, "f2": 0.0}, candidates, ["f1", "f2"])
    assert result.sort("rank")["player_id"].to_list() == [2, 5]


def test_baseline_b_ranks_more_similar_candidate_first():
    candidates = _b_candidates((1, 0.9, 0.1), (2, 0.1, 0.9))
    result = baseline_b_rank({"f1": 1.0, "f2": 0.0}, candidates, ["f1", "f2"])
    assert result.sort("rank")["player_id"].to_list() == [1, 2]
