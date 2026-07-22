import polars as pl

from scoutlens.evaluation.similarity import baseline_a_rank


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
