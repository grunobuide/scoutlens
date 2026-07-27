"""Tests for StatsBomb canonical feature aggregation + role derivation (8mc.3)."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

from scoutlens.statsbomb.aggregation import (
    CANONICAL_FEATURES,
    CANONICAL_PLUS_CARRY,
    compute_player_features,
)
from scoutlens.statsbomb.ingestion import EVENTS_SCHEMA
from scoutlens.statsbomb.replication import derive_roles

SAMPLE = (
    Path(r"C:\Users\SrGui\AppData\Local\Temp\claude")
    / "C--Users-SrGui-Documents-sandbox-futebol-scoutlens-scoutlens"
    / "0682ec49-87dd-4d01-b993-2e2819db7516" / "scratchpad" / "statsbomb"
)


def _ev(rows):
    full = [{c: r.get(c) for c in EVENTS_SCHEMA} for r in rows]
    return pl.DataFrame(full, schema=EVENTS_SCHEMA)


def _minutes(player_id, minutes):
    return pl.DataFrame({"player_id": [player_id], "minutes_played": [float(minutes)]})


def test_canonical_lists_are_28_and_30_and_exclude_the_right_features():
    assert len(CANONICAL_FEATURES) == 28
    assert "smart_passes_p90" not in CANONICAL_FEATURES
    assert "events_p90" not in CANONICAL_FEATURES
    assert "carry_proxy_p90" not in CANONICAL_FEATURES          # construct-shift held out of primary
    assert CANONICAL_PLUS_CARRY[-2:] == ["carry_proxy_p90", "carry_distance_proxy_p90"]


def test_pass_completion_uses_outcome_by_presence():
    # 3 passes: 2 complete (null outcome), 1 Incomplete -> 2/3
    events = _ev([
        {"id": "1", "player_id": 7, "type_name": "Pass", "location_x": 60.0, "location_y": 40.0},
        {"id": "2", "player_id": 7, "type_name": "Pass", "location_x": 60.0, "location_y": 40.0},
        {"id": "3", "player_id": 7, "type_name": "Pass", "location_x": 60.0, "location_y": 40.0,
         "pass_outcome_name": "Incomplete"},
    ])
    row = compute_player_features(events, _minutes(7, 90)).row(0, named=True)
    assert row["pass_completion_pct"] == pytest.approx(2 / 3)
    assert row["passes_p90"] == pytest.approx(3.0)


def test_native_carry_counted_and_distance_normalized():
    # a carry from x=60 to x=90 in native units -> normalized fwd = (90-60)/120*100 = 25
    events = _ev([
        {"id": "1", "player_id": 7, "type_name": "Carry", "location_x": 60.0, "location_y": 40.0,
         "end_location_x": 90.0, "end_location_y": 40.0},
    ])
    row = compute_player_features(events, _minutes(7, 90)).row(0, named=True)
    assert row["carry_proxy_p90"] == pytest.approx(1.0)
    assert row["carry_distance_proxy_p90"] == pytest.approx(25.0)


def test_shots_are_open_play_only_and_conversion():
    events = _ev([
        {"id": "1", "player_id": 7, "type_name": "Shot", "location_x": 110.0, "location_y": 40.0,
         "shot_type_name": "Open Play", "shot_outcome_name": "Goal"},
        {"id": "2", "player_id": 7, "type_name": "Shot", "location_x": 110.0, "location_y": 40.0,
         "shot_type_name": "Open Play", "shot_outcome_name": "Saved"},
        {"id": "3", "player_id": 7, "type_name": "Shot", "location_x": 110.0, "location_y": 40.0,
         "shot_type_name": "Penalty", "shot_outcome_name": "Goal"},  # excluded from shots_p90
    ])
    row = compute_player_features(events, _minutes(7, 90)).row(0, named=True)
    assert row["shots_p90"] == pytest.approx(2.0)               # penalty not counted
    assert row["shot_conversion_pct"] == pytest.approx(0.5)     # 1 goal of 2 open-play shots
    assert row["shots_on_target_pct"] == pytest.approx(1.0)     # Goal + Saved both on target


def test_box_entry_uses_normalized_coordinates():
    # end at native x=108 -> normalized 90 >= 84, y=40 -> 50 in [19,81]: a box entry
    events = _ev([
        {"id": "1", "player_id": 7, "type_name": "Pass", "location_x": 80.0, "location_y": 40.0,
         "end_location_x": 108.0, "end_location_y": 40.0},
    ])
    row = compute_player_features(events, _minutes(7, 90)).row(0, named=True)
    assert row["box_entries_p90"] == pytest.approx(1.0)


def test_zero_minutes_player_gets_null_rates():
    events = _ev([{"id": "1", "player_id": 7, "type_name": "Pass", "location_x": 60.0, "location_y": 40.0}])
    row = compute_player_features(events, _minutes(7, 0)).row(0, named=True)
    assert row["passes_p90"] is None


def test_derive_roles_buckets_positions():
    events = _ev([
        {"id": "1", "player_id": 1, "type_name": "Pass", "position_name": "Goalkeeper"},
        {"id": "2", "player_id": 2, "type_name": "Pass", "position_name": "Right Wing Back"},
        {"id": "3", "player_id": 3, "type_name": "Pass", "position_name": "Center Defensive Midfield"},
        {"id": "4", "player_id": 4, "type_name": "Pass", "position_name": "Left Wing"},
        {"id": "5", "player_id": 5, "type_name": "Pass", "position_name": "Center Forward"},
    ])
    roles = {r["player_id"]: r["role"] for r in derive_roles(events).to_dicts()}
    assert roles == {1: "Goalkeeper", 2: "Defender", 3: "Midfielder", 4: "Forward", 5: "Forward"}


@pytest.mark.skipif(not (SAMPLE / "events_3754217.json").exists(),
                    reason="sample match not present locally")
def test_aggregation_on_real_sample_produces_all_features():
    from scoutlens.statsbomb.ingestion import events_frame, normalize_events, team_ids_from_events
    from scoutlens.statsbomb.minutes import derive_match_minutes, minutes_frame
    raw = json.loads((SAMPLE / "events_3754217.json").read_text(encoding="utf-8"))
    lu = json.loads((SAMPLE / "lineups_3754217.json").read_text(encoding="utf-8"))
    events = events_frame(normalize_events(raw, 3754217, 2))
    minutes = minutes_frame(derive_match_minutes(3754217, 2, team_ids_from_events(raw), lu, raw))
    feats = compute_player_features(events, minutes.select("player_id", "minutes_played"))
    assert all(c in feats.columns for c in CANONICAL_PLUS_CARRY)
    # a high-minutes outfielder has a plausible pass volume and completion
    outfield = feats.filter(pl.col("minutes_played") > 80).sort("passes_p90", descending=True).row(0, named=True)
    assert 20 < outfield["passes_p90"] < 150
    assert 0.5 < outfield["pass_completion_pct"] <= 1.0
