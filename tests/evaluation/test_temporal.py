import polars as pl

from scoutlens.evaluation.temporal import assign_periods, build_period_profiles


def _matches_df(*rows):
    """rows of (wyId, competitionId, dateutc)."""
    return pl.DataFrame(
        {
            "wyId": [r[0] for r in rows],
            "competitionId": [r[1] for r in rows],
            "dateutc": [r[2] for r in rows],
        }
    )


def test_assign_periods_splits_by_chronological_order_within_competition():
    matches = _matches_df(
        (1, 100, "2020-01-04"),
        (2, 100, "2020-01-01"),
        (3, 100, "2020-01-03"),
        (4, 100, "2020-01-02"),
    )
    result = assign_periods(matches).sort("match_id")
    by_match = dict(result.select("match_id", "period").iter_rows())
    # chronological order is 2 (01-01), 4 (01-02), 3 (01-03), 1 (01-04)
    # first half (2 matches) -> A, second half -> B
    assert by_match[2] == "A"
    assert by_match[4] == "A"
    assert by_match[3] == "B"
    assert by_match[1] == "B"


def test_assign_periods_keeps_competitions_independent():
    matches = _matches_df(
        (1, 100, "2020-01-01"),
        (2, 100, "2020-01-02"),
        (3, 200, "2020-06-01"),
        (4, 200, "2020-06-02"),
    )
    result = assign_periods(matches)
    assert set(result.filter(pl.col("competitionId") == 100)["match_id"].to_list()) == {1, 2}
    assert set(result.filter(pl.col("competitionId") == 200)["match_id"].to_list()) == {3, 4}
    # each competition split independently: 1 match each side within each comp
    counts = result.group_by(["competitionId", "period"]).agg(pl.len().alias("n")).sort(["competitionId", "period"])
    assert counts["n"].to_list() == [1, 1, 1, 1]


def test_assign_periods_odd_match_count_gives_extra_to_b():
    matches = _matches_df((1, 100, "2020-01-01"), (2, 100, "2020-01-02"), (3, 100, "2020-01-03"))
    result = assign_periods(matches)
    counts = result["period"].value_counts().sort("period")
    by_period = dict(counts.iter_rows())
    assert by_period["A"] == 1
    assert by_period["B"] == 2


def test_assign_periods_ties_broken_deterministically_by_match_id():
    """Regression test: European Championship 2016 has two real matches
    sharing an identical dateutc straddling the split boundary. Without an
    explicit tiebreak, which one lands in A vs B depends on incoming row
    order rather than a value in the data. wyId as a secondary sort key
    makes the result independent of input row order."""
    # two matches tied on dateutc, in each of two different input orders
    forward_order = _matches_df(
        (10, 100, "2020-01-01"), (20, 100, "2020-01-02"), (30, 100, "2020-01-02"), (40, 100, "2020-01-03"),
    )
    reversed_order = _matches_df(
        (40, 100, "2020-01-03"), (30, 100, "2020-01-02"), (20, 100, "2020-01-02"), (10, 100, "2020-01-01"),
    )
    result_forward = assign_periods(forward_order).sort("match_id")
    result_reversed = assign_periods(reversed_order).sort("match_id")
    assert result_forward["period"].to_list() == result_reversed["period"].to_list()
    # deterministic outcome: lower wyId (20) wins the tie and lands in A
    by_match = dict(result_forward.select("match_id", "period").iter_rows())
    assert by_match[20] == "A"
    assert by_match[30] == "B"


def _event(player_id, match_id, event_name="Pass", tags=None):
    return {
        "playerId": player_id, "matchId": match_id, "eventName": event_name, "subEventName": "",
        "tags": [{"id": t} for t in (tags or [])], "positions": [],
    }


def test_build_period_profiles_scopes_events_and_minutes_per_period():
    period_assignment = pl.DataFrame({
        "match_id": [1, 2],
        "competitionId": [100, 100],
        "period": ["A", "B"],
    })
    events = pl.DataFrame(
        [_event(1, 1, tags=[1801]), _event(1, 1, tags=[1801]), _event(1, 2, tags=[1801])],
        schema={
            "playerId": pl.Int64, "matchId": pl.Int64, "eventName": pl.String, "subEventName": pl.String,
            "tags": pl.List(pl.Struct({"id": pl.Int64})), "positions": pl.List(pl.Struct({"x": pl.Int64, "y": pl.Int64})),
        },
    )
    minutes = pl.DataFrame({"player_id": [1, 1], "match_id": [1, 2], "minutes_played": [90, 90]})

    result = build_period_profiles(events, minutes, period_assignment)

    by_period = {r["period"]: r for r in result.to_dicts()}
    assert by_period["A"]["passes_p90"] == 2.0  # 2 passes in match 1 over 90 minutes
    assert by_period["B"]["passes_p90"] == 1.0  # 1 pass in match 2 over 90 minutes
    assert by_period["A"]["competitionId"] == 100
    assert by_period["A"]["minutes_played"] == 90


def test_build_period_profiles_keeps_same_player_separate_across_competitions():
    """Regression case for D007: a player appearing in two competitions in
    the same period label must produce two distinct rows, not collide."""
    period_assignment = pl.DataFrame({
        "match_id": [1, 2],
        "competitionId": [100, 200],
        "period": ["A", "A"],
    })
    events = pl.DataFrame(
        [_event(1, 1, tags=[1801]), _event(1, 2, tags=[1801]), _event(1, 2, tags=[1801])],
        schema={
            "playerId": pl.Int64, "matchId": pl.Int64, "eventName": pl.String, "subEventName": pl.String,
            "tags": pl.List(pl.Struct({"id": pl.Int64})), "positions": pl.List(pl.Struct({"x": pl.Int64, "y": pl.Int64})),
        },
    )
    minutes = pl.DataFrame({"player_id": [1, 1], "match_id": [1, 2], "minutes_played": [90, 90]})

    result = build_period_profiles(events, minutes, period_assignment)

    assert result.height == 2
    rows = {(r["competitionId"], r["period"]): r for r in result.to_dicts()}
    assert rows[(100, "A")]["passes_p90"] == 1.0
    assert rows[(200, "A")]["passes_p90"] == 2.0
