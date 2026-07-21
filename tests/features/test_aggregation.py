import polars as pl

from scoutlens.features.aggregation import compute_player_features


def _event(player_id, event_name, sub_event_name="", tags=None, positions=None):
    return {
        "playerId": player_id,
        "eventName": event_name,
        "subEventName": sub_event_name,
        "tags": [{"id": t} for t in (tags or [])],
        "positions": positions or [],
    }


def _events_df(*rows) -> pl.DataFrame:
    return pl.DataFrame(
        list(rows),
        schema={
            "playerId": pl.Int64, "eventName": pl.String, "subEventName": pl.String,
            "tags": pl.List(pl.Struct({"id": pl.Int64})),
            "positions": pl.List(pl.Struct({"x": pl.Int64, "y": pl.Int64})),
        },
    )


def _minutes_df(*rows) -> pl.DataFrame:
    """rows of (player_id, minutes_played)."""
    return pl.DataFrame({"player_id": [r[0] for r in rows], "minutes_played": [r[1] for r in rows]})


def test_passes_and_completion_pct():
    events = _events_df(
        _event(1, "Pass", "Simple pass", tags=[1801]),
        _event(1, "Pass", "Simple pass", tags=[1801]),
        _event(1, "Pass", "Simple pass", tags=[1802]),
    )
    minutes = _minutes_df((1, 90))
    result = compute_player_features(events, minutes)
    row = result.row(0, named=True)
    assert row["passes_p90"] == 3.0
    assert row["pass_completion_pct"] == 2 / 3


def test_progressive_pass_distance_and_count():
    events = _events_df(
        _event(1, "Pass", positions=[{"x": 10, "y": 50}, {"x": 30, "y": 50}]),  # +20, progressive
        _event(1, "Pass", positions=[{"x": 10, "y": 50}, {"x": 15, "y": 50}]),  # +5, not progressive
    )
    minutes = _minutes_df((1, 90))
    result = compute_player_features(events, minutes)
    row = result.row(0, named=True)
    assert row["progressive_pass_distance_p90"] == 25.0
    assert row["progressive_passes_p90"] == 1.0


def test_assist_key_pass_through_ball():
    events = _events_df(
        _event(1, "Pass", tags=[301]),
        _event(1, "Pass", tags=[302]),
        _event(1, "Pass", tags=[901]),
    )
    minutes = _minutes_df((1, 90))
    result = compute_player_features(events, minutes)
    row = result.row(0, named=True)
    assert row["assists_p90"] == 1.0
    assert row["key_passes_p90"] == 1.0
    assert row["through_balls_p90"] == 1.0


def test_box_entry_requires_pass_landing_inside_box_zone():
    events = _events_df(
        _event(1, "Pass", positions=[{"x": 70, "y": 50}, {"x": 90, "y": 50}]),  # inside box
        _event(1, "Pass", positions=[{"x": 70, "y": 50}, {"x": 90, "y": 5}]),  # x ok, y outside box width
    )
    minutes = _minutes_df((1, 90))
    result = compute_player_features(events, minutes)
    row = result.row(0, named=True)
    assert row["box_entries_p90"] == 1.0


def test_shot_features():
    events = _events_df(
        _event(1, "Shot", tags=[101]),  # goal
        _event(1, "Shot", tags=[1201]),  # on target (goal-mouth zone), no goal
        _event(1, "Shot", tags=[2101]),  # blocked
    )
    minutes = _minutes_df((1, 90))
    result = compute_player_features(events, minutes)
    row = result.row(0, named=True)
    assert row["shots_p90"] == 3.0
    assert row["goals_p90"] == 1.0
    assert row["shot_conversion_pct"] == 1 / 3
    assert row["shots_on_target_pct"] == 2 / 3
    assert row["blocked_shot_pct"] == 1 / 3


def test_defensive_features():
    events = _events_df(
        _event(1, "Others on the ball", "Touch", tags=[1401]),  # interception (on a Touch)
        _event(1, "Duel", "Ground defending duel", tags=[703]),  # won
        _event(1, "Duel", "Ground defending duel", tags=[701]),  # lost
        _event(1, "Duel", tags=[1601]),  # sliding tackle
        _event(1, "Others on the ball", "Clearance"),
    )
    minutes = _minutes_df((1, 90))
    result = compute_player_features(events, minutes)
    row = result.row(0, named=True)
    assert row["interceptions_p90"] == 1.0
    assert row["sliding_tackles_p90"] == 1.0
    assert row["clearances_p90"] == 1.0
    assert row["defensive_duel_win_pct"] == 0.5


def test_spatial_features():
    events = _events_df(
        _event(1, "Pass", positions=[{"x": 10, "y": 20}]),  # defensive third
        _event(1, "Pass", positions=[{"x": 90, "y": 20}]),  # attacking third
    )
    minutes = _minutes_df((1, 90))
    result = compute_player_features(events, minutes)
    row = result.row(0, named=True)
    assert row["mean_x"] == 50.0
    assert row["defensive_third_share"] == 0.5
    assert row["attacking_third_share"] == 0.5
    assert row["middle_third_share"] == 0.0


def test_possession_involvement_features():
    events = _events_df(
        _event(1, "Others on the ball", "Touch"),
        _event(1, "Duel", tags=[703]),
        _event(1, "Duel", tags=[701]),
    )
    minutes = _minutes_df((1, 90))
    result = compute_player_features(events, minutes)
    row = result.row(0, named=True)
    assert row["touches_p90"] == 1.0
    assert row["duels_p90"] == 2.0
    assert row["duel_win_pct"] == 0.5


def test_carry_proxy_and_take_on_features():
    events = _events_df(
        _event(1, "Others on the ball", "Acceleration", positions=[{"x": 20, "y": 50}, {"x": 35, "y": 50}]),
        _event(1, "Duel", "Ground attacking duel", tags=[503, 703]),  # take-on attempt, won
        _event(1, "Duel", "Ground attacking duel", tags=[504, 701]),  # take-on attempt, lost
    )
    minutes = _minutes_df((1, 90))
    result = compute_player_features(events, minutes)
    row = result.row(0, named=True)
    assert row["carry_proxy_p90"] == 1.0
    assert row["carry_distance_proxy_p90"] == 15.0
    assert row["take_on_success_pct"] == 0.5


def test_ratios_are_null_not_zero_when_denominator_is_zero():
    events = _events_df(_event(1, "Pass", tags=[1801]))
    minutes = _minutes_df((1, 90))
    result = compute_player_features(events, minutes)
    row = result.row(0, named=True)
    assert row["shots_p90"] == 0.0
    assert row["shot_conversion_pct"] is None
    assert row["take_on_success_pct"] is None


def test_player_with_minutes_but_zero_events_still_appears():
    events = _events_df(_event(2, "Pass", tags=[1801]))
    minutes = _minutes_df((1, 90), (2, 90))
    result = compute_player_features(events, minutes)
    assert result.height == 2
    by_player = {r["player_id"]: r for r in result.to_dicts()}
    assert by_player[1]["passes_p90"] == 0.0
    assert by_player[1]["events_p90"] == 0.0
    assert by_player[1]["pass_completion_pct"] is None


def test_player_id_zero_sentinel_is_excluded():
    events = _events_df(
        _event(0, "Pass", tags=[1801]),  # "no player" sentinel — must not be attributed to anyone
        _event(1, "Pass", tags=[1801]),
    )
    minutes = _minutes_df((1, 90))
    result = compute_player_features(events, minutes)
    assert result.height == 1
    assert result.row(0, named=True)["passes_p90"] == 1.0
