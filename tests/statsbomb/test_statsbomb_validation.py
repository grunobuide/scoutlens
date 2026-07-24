"""Tests for StatsBomb processed-table validation (8mc.2), including
malformed / incomplete inputs."""

from __future__ import annotations

import polars as pl

from scoutlens.statsbomb.validation import (
    check_coordinates_in_native_range,
    check_event_id_unique,
    check_events_have_required_columns,
    check_matches_present,
    check_minutes_events_player_referential,
    check_overlap_flag_rate,
    run_all,
    summarize,
)


def _events(rows):
    cols = {"id", "match_id", "competitionId", "type_name", "period", "minute",
            "location_x", "location_y", "possession", "pass_outcome_name", "shot_outcome_name", "player_id"}
    return pl.DataFrame([{c: r.get(c) for c in cols} for r in rows])


def _minutes(rows):
    return pl.DataFrame(rows, schema_overrides={"minutes_played": pl.Float64})


def test_required_columns_fail_when_missing():
    df = pl.DataFrame({"id": ["a"], "match_id": [1]})
    assert check_events_have_required_columns(df).status == "fail"


def test_event_id_duplicate_fails():
    df = _events([{"id": "a", "player_id": 1}, {"id": "a", "player_id": 2}])
    assert check_event_id_unique(df).status == "fail"


def test_coordinates_out_of_range_fail():
    df = _events([{"id": "a", "location_x": 130.0, "location_y": 10.0}])
    assert check_coordinates_in_native_range(df).status == "fail"
    ok = _events([{"id": "b", "location_x": 60.0, "location_y": 40.0},
                  {"id": "c", "location_x": None, "location_y": None}])
    assert check_coordinates_in_native_range(ok).status == "ok"


def test_acting_player_without_minutes_fails():
    events = _events([{"id": "a", "match_id": 1, "player_id": 100}])
    minutes = _minutes([{"player_id": 999, "match_id": 1, "minutes_played": 90.0,
                         "derivation_status": "clean"}])
    assert check_minutes_events_player_referential(events, minutes).status == "fail"


def test_unused_sub_with_no_events_is_fine():
    events = _events([{"id": "a", "match_id": 1, "player_id": 100}])
    minutes = _minutes([
        {"player_id": 100, "match_id": 1, "minutes_played": 90.0, "derivation_status": "clean"},
        {"player_id": 200, "match_id": 1, "minutes_played": 0.0, "derivation_status": "clean"},
    ])
    assert check_minutes_events_player_referential(events, minutes).status == "ok"


def test_overlap_rate_warns_when_high():
    minutes = _minutes([
        {"player_id": i, "match_id": 1, "minutes_played": 90.0,
         "derivation_status": "overlap_merged" if i < 3 else "clean"}
        for i in range(4)
    ])
    assert check_overlap_flag_rate(minutes).status == "warn"  # 3/4 = 75%


def test_matches_present_detects_undeclared():
    events = _events([{"id": "a", "match_id": 7}])
    matches = pl.DataFrame({"match_id": [1], "competitionId": [2]})
    assert check_matches_present(events, matches).status == "fail"


def test_run_all_and_summarize_on_clean_frames():
    events = _events([{"id": "a", "match_id": 1, "competitionId": 2, "type_name": "Pass",
                       "period": 1, "minute": 10, "location_x": 60.0, "location_y": 40.0,
                       "possession": 1, "pass_outcome_name": None, "shot_outcome_name": None,
                       "player_id": 100}])
    minutes = _minutes([{"player_id": 100, "match_id": 1, "minutes_played": 90.0,
                         "derivation_status": "clean"}])
    matches = pl.DataFrame({"match_id": [1], "competitionId": [2]})
    results = run_all(events, minutes, matches)
    summary = summarize(results)
    assert summary["passed"] is True
    assert summary["fail"] == 0
