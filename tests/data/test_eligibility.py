import polars as pl

from scoutlens.data.eligibility import compute_season_minutes, population_at_threshold


def _players_df(*rows):
    return pl.DataFrame(
        [{"wyId": pid, "role": {"code2": rc2, "code3": rc3, "name": name}} for pid, rc2, rc3, name in rows]
    )


def _competitions_df(*rows):
    return pl.DataFrame([{"wyId": cid, "name": name} for cid, name in rows])


def test_compute_season_minutes_sums_across_matches_within_a_competition():
    minutes = pl.DataFrame({
        "player_id": [1, 1, 2],
        "match_id": [10, 11, 10],
        "minutes_played": [90, 45, 90],
    })
    matches = pl.DataFrame({"wyId": [10, 11], "competitionId": [100, 100]})

    result = compute_season_minutes(minutes, matches)
    by_player = {r["player_id"]: r for r in result.to_dicts()}
    assert by_player[1]["season_minutes"] == 135
    assert by_player[1]["matches_appeared"] == 2
    assert by_player[2]["season_minutes"] == 90


def test_compute_season_minutes_keeps_competitions_separate():
    """A player appearing in two different competitions gets one row per
    competition, not a combined total — mixing club/international minutes
    into one number would misrepresent both."""
    minutes = pl.DataFrame({
        "player_id": [1, 1],
        "match_id": [10, 20],
        "minutes_played": [90, 90],
    })
    matches = pl.DataFrame({"wyId": [10, 20], "competitionId": [100, 200]})

    result = compute_season_minutes(minutes, matches)
    assert result.height == 2
    assert set(result["competitionId"].to_list()) == {100, 200}


def test_population_at_threshold_filters_and_breaks_down_correctly():
    season_minutes = pl.DataFrame({
        "player_id": [1, 2, 3],
        "competitionId": [100, 100, 200],
        "season_minutes": [1000, 300, 900],
        "matches_appeared": [11, 4, 10],
    })
    players = _players_df((1, "MD", "MID", "Midfielder"), (2, "DF", "DEF", "Defender"), (3, "MD", "MID", "Midfielder"))
    competitions = _competitions_df((100, "League A"), (200, "League B"))

    report = population_at_threshold(season_minutes, players, competitions, threshold=450)

    assert report.eligible_rows == 2
    assert report.eligible_distinct_players == 2
    assert report.eligible_by_competition == {"League A": 1, "League B": 1}
    assert report.eligible_by_role == {"Midfielder": 2}


def test_population_at_threshold_excludes_players_below_threshold():
    season_minutes = pl.DataFrame({
        "player_id": [1],
        "competitionId": [100],
        "season_minutes": [100],
        "matches_appeared": [2],
    })
    players = _players_df((1, "MD", "MID", "Midfielder"))
    competitions = _competitions_df((100, "League A"))

    report = population_at_threshold(season_minutes, players, competitions, threshold=450)
    assert report.eligible_rows == 0
    assert report.eligible_distinct_players == 0
