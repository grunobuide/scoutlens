"""Tests for StatsBomb interval-based minutes derivation (8mc.2)."""

from __future__ import annotations

import pytest

from scoutlens.statsbomb.minutes import (
    derive_match_minutes,
    interval_minutes,
    period_bounds,
    player_minutes,
)


def _half(period, minute, second, kind):
    return {"type": {"name": kind}, "period": period, "minute": minute, "second": second}


def _synthetic_events():
    return [
        _half(1, 0, 0, "Half Start"),
        _half(1, 48, 0, "Half End"),
        _half(2, 45, 0, "Half Start"),
        _half(2, 95, 0, "Half End"),
    ]


def test_period_bounds_reads_half_start_end():
    bounds = period_bounds(_synthetic_events())
    assert bounds == {1: (0.0, 48.0), 2: (45.0, 95.0)}


def test_period_bounds_raises_on_missing_end():
    with pytest.raises(ValueError, match="Half Start or Half End"):
        period_bounds([_half(1, 0, 0, "Half Start")])


def test_interval_minutes_single_period():
    bounds = {1: (0.0, 48.0), 2: (45.0, 95.0)}
    # a player subbed off at 45:00 of period 2 played all of period 1 only
    assert interval_minutes(0.0, 1, 45.0, 2, bounds) == pytest.approx(48.0)


def test_interval_minutes_spans_both_periods_without_double_counting_overlap():
    bounds = {1: (0.0, 48.0), 2: (45.0, 95.0)}
    # full match: 0:00 P1 -> final whistle P2 = 48 (P1) + 50 (P2) = 98, NOT 95
    assert interval_minutes(0.0, 1, 95.0, 2, bounds) == pytest.approx(98.0)


def test_interval_minutes_second_half_only():
    bounds = {1: (0.0, 48.0), 2: (45.0, 95.0)}
    assert interval_minutes(45.0, 2, 95.0, 2, bounds) == pytest.approx(50.0)


def _lineup(player_id, positions):
    return {"player_id": player_id, "player_name": f"p{player_id}", "positions": positions}


def test_derive_match_minutes_synthetic_full_sub_and_unused():
    events = _synthetic_events()
    lineups = [{
        "team_name": "Home",
        "lineup": [
            _lineup(1, [{"from": "00:00", "from_period": 1, "to": None, "to_period": None}]),
            _lineup(2, [{"from": "00:00", "from_period": 1, "to": "45:00", "to_period": 2}]),
            _lineup(3, [{"from": "45:00", "from_period": 2, "to": None, "to_period": None}]),
            _lineup(4, []),
        ],
    }]
    rows = {r.player_id: r for r in derive_match_minutes(1, 99, {"Home": 100}, lineups, events)}
    assert rows[1].minutes_played == pytest.approx(98.0)   # full match
    assert rows[2].minutes_played == pytest.approx(48.0)   # off at half
    assert rows[3].minutes_played == pytest.approx(50.0)   # on at half
    assert rows[4].minutes_played == 0.0                   # unused sub
    assert all(r.derivation_status == "clean" for r in rows.values())
    assert rows[1].team_id == 100 and rows[1].competitionId == 99


def test_player_minutes_unions_overlapping_stints_instead_of_summing():
    bounds = {1: (0.0, 48.0), 2: (45.0, 95.0)}
    # two overlapping period-1 stints: [0,30] and [20,48]. Union = 48, sum
    # would be 58. A tactical-shift record outliving a substitution (real
    # StatsBomb quirk, match 3754217 Coquelin) must not exceed reality.
    positions = [
        {"from": "00:00", "from_period": 1, "to": "30:00", "to_period": 1},
        {"from": "20:00", "from_period": 1, "to": "48:00", "to_period": 1},
    ]
    minutes, overlap = player_minutes(positions, bounds, final_whistle=95.0, last_period=2)
    assert minutes == pytest.approx(48.0)
    assert overlap is True


def test_player_minutes_clips_stint_running_past_the_whistle():
    bounds = {1: (0.0, 48.0), 2: (45.0, 95.0)}
    # a 'to' of 99:00 must clip to the period-2 whistle (95), not credit 99
    positions = [{"from": "45:00", "from_period": 2, "to": "99:00", "to_period": 2}]
    minutes, overlap = player_minutes(positions, bounds, final_whistle=95.0, last_period=2)
    assert minutes == pytest.approx(50.0)
    assert overlap is False


def test_derive_match_minutes_composes_with_portable_sample(synthetic_statsbomb_match):
    events, lineups = synthetic_statsbomb_match
    from scoutlens.statsbomb.ingestion import team_ids_from_events
    team_ids = team_ids_from_events(events)
    rows = {r.player_id: r for r in derive_match_minutes(3754217, 2, team_ids, lineups, events)}
    assert len(rows) == 22
    assert rows[100].minutes_played == pytest.approx(90.0)
    assert rows[100].derivation_status == "clean"
    assert rows[200].minutes_played == pytest.approx(90.0)
