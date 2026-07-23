import polars as pl

from scoutlens.evaluation.diagnostics import compute_primary_team, identify_transferred_players, neighbor_concentration


def test_compute_primary_team_picks_team_with_most_minutes():
    minutes = pl.DataFrame({
        "player_id": [1, 1, 1],
        "match_id": [10, 11, 12],
        "team_id": [100, 100, 200],
        "minutes_played": [90, 60, 30],
    })
    period_assignment = pl.DataFrame({
        "match_id": [10, 11, 12], "competitionId": [1, 1, 1], "period": ["A", "A", "A"],
    })
    result = compute_primary_team(minutes, period_assignment)
    row = result.row(0, named=True)
    assert row["team_id"] == 100  # 150 minutes for team 100 vs 30 for team 200


def test_compute_primary_team_ties_broken_by_lower_team_id():
    minutes = pl.DataFrame({
        "player_id": [1, 1],
        "match_id": [10, 11],
        "team_id": [200, 100],
        "minutes_played": [90, 90],
    })
    period_assignment = pl.DataFrame({"match_id": [10, 11], "competitionId": [1, 1], "period": ["A", "A"]})
    result = compute_primary_team(minutes, period_assignment)
    assert result.row(0, named=True)["team_id"] == 100


def test_compute_primary_team_separates_periods():
    minutes = pl.DataFrame({
        "player_id": [1, 1],
        "match_id": [10, 20],
        "team_id": [100, 200],
        "minutes_played": [90, 90],
    })
    period_assignment = pl.DataFrame({"match_id": [10, 20], "competitionId": [1, 1], "period": ["A", "B"]})
    result = compute_primary_team(minutes, period_assignment).sort("period")
    assert result["team_id"].to_list() == [100, 200]


def test_neighbor_concentration_all_same_team():
    top_k = pl.DataFrame({
        "query_player_id": [1, 1], "competitionId": [100, 100],
        "neighbor_rank": [1, 2], "neighbor_player_id": [2, 3],
    })
    query_team = pl.DataFrame({"player_id": [1], "team_id": [500]})
    neighbor_team = pl.DataFrame({"player_id": [2, 3], "team_id": [500, 500]})
    result = neighbor_concentration(top_k, query_team, neighbor_team, "team_id")
    assert result == 1.0


def test_neighbor_concentration_no_shared_team():
    top_k = pl.DataFrame({
        "query_player_id": [1, 1], "competitionId": [100, 100],
        "neighbor_rank": [1, 2], "neighbor_player_id": [2, 3],
    })
    query_team = pl.DataFrame({"player_id": [1], "team_id": [500]})
    neighbor_team = pl.DataFrame({"player_id": [2, 3], "team_id": [600, 700]})
    result = neighbor_concentration(top_k, query_team, neighbor_team, "team_id")
    assert result == 0.0


def test_neighbor_concentration_partial_match():
    top_k = pl.DataFrame({
        "query_player_id": [1, 1], "competitionId": [100, 100],
        "neighbor_rank": [1, 2], "neighbor_player_id": [2, 3],
    })
    query_team = pl.DataFrame({"player_id": [1], "team_id": [500]})
    neighbor_team = pl.DataFrame({"player_id": [2, 3], "team_id": [500, 700]})
    result = neighbor_concentration(top_k, query_team, neighbor_team, "team_id")
    assert result == 0.5


def test_neighbor_concentration_excludes_true_match_by_default():
    """Regression test for a real bug: a correctly-retrieved true match is
    trivially "same team" (a player's team almost never changes within one
    season split), so counting it inflates the apparent team confound with
    retrieval successes rather than genuine mistakes."""
    top_k = pl.DataFrame({
        "query_player_id": [1, 1],
        "competitionId": [100, 100],
        "neighbor_rank": [1, 2],
        "neighbor_player_id": [1, 3],  # rank 1 is the query's own true match
        "neighbor_competitionId": [100, 100],
        "is_true_match": [True, False],
    })
    query_team = pl.DataFrame({"player_id": [1], "team_id": [500]})
    # true match (player 1) shares team_id 500 with itself; player 3 does not
    neighbor_team = pl.DataFrame({"player_id": [1, 3], "team_id": [500, 700]})

    excluding_true_match = neighbor_concentration(top_k, query_team, neighbor_team, "team_id")
    assert excluding_true_match == 0.0  # only the non-true-match row (player 3) is counted, and it's a mismatch

    including_true_match = neighbor_concentration(
        top_k, query_team, neighbor_team, "team_id", include_true_matches=True
    )
    assert including_true_match == 0.5  # both rows counted, one matches


def test_identify_transferred_players_finds_team_changes():
    eligible = pl.DataFrame({"player_id": [1, 2], "competitionId": [100, 100]})
    primary_team = pl.DataFrame({
        "player_id": [1, 1, 2, 2],
        "competitionId": [100, 100, 100, 100],
        "period": ["A", "B", "A", "B"],
        "team_id": [500, 600, 500, 500],  # player 1 changed teams, player 2 did not
    })
    result = identify_transferred_players(eligible, primary_team)
    assert result.height == 1
    row = result.row(0, named=True)
    assert row["player_id"] == 1
    assert row["team_a"] == 500
    assert row["team_b"] == 600


def test_identify_transferred_players_ignores_players_not_in_eligible():
    eligible = pl.DataFrame({"player_id": [1], "competitionId": [100]})
    primary_team = pl.DataFrame({
        "player_id": [1, 2],
        "competitionId": [100, 100],
        "period": ["A", "A"],
        "team_id": [500, 500],
    })
    primary_team = pl.concat([
        primary_team,
        pl.DataFrame({"player_id": [1, 2], "competitionId": [100, 100], "period": ["B", "B"], "team_id": [600, 999]}),
    ])
    result = identify_transferred_players(eligible, primary_team)
    # player 2 transferred too (500->999) but isn't in `eligible`, so must not appear
    assert result["player_id"].to_list() == [1]


def test_neighbor_concentration_rejects_duplicate_player_id_in_query_attribute():
    """Regression test for a real bug: compute_primary_team runs over every
    competition (including internationals), so a player who also appears
    for their national team gets a second row -- feeding that unfiltered
    into neighbor_concentration silently inflated a published confound
    number instead of failing loudly."""
    top_k = pl.DataFrame({
        "query_player_id": [1], "competitionId": [100],
        "neighbor_rank": [1], "neighbor_player_id": [2],
    })
    duplicated_query_attribute = pl.DataFrame({"player_id": [1, 1], "team_id": [500, 600]})
    neighbor_attribute = pl.DataFrame({"player_id": [2], "team_id": [500]})
    try:
        neighbor_concentration(top_k, duplicated_query_attribute, neighbor_attribute, "team_id")
        assert False, "expected ValueError"
    except ValueError as e:
        assert "duplicate player_id" in str(e)


def test_neighbor_concentration_rejects_duplicate_player_id_in_neighbor_attribute():
    top_k = pl.DataFrame({
        "query_player_id": [1], "competitionId": [100],
        "neighbor_rank": [1], "neighbor_player_id": [2],
    })
    query_attribute = pl.DataFrame({"player_id": [1], "team_id": [500]})
    duplicated_neighbor_attribute = pl.DataFrame({"player_id": [2, 2], "team_id": [500, 600]})
    try:
        neighbor_concentration(top_k, query_attribute, duplicated_neighbor_attribute, "team_id")
        assert False, "expected ValueError"
    except ValueError as e:
        assert "duplicate player_id" in str(e)
