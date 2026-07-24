"""Tests for StatsBomb event normalization + roster extraction (8mc.2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import polars as pl

from scoutlens.statsbomb.ingestion import (
    events_frame,
    normalize_events,
    team_ids_from_events,
)
from scoutlens.statsbomb.minutes import derive_match_minutes, minutes_frame
from scoutlens.statsbomb.validation import run_all, summarize

SAMPLE = (
    Path(r"C:\Users\SrGui\AppData\Local\Temp\claude")
    / "C--Users-SrGui-Documents-sandbox-futebol-scoutlens-scoutlens"
    / "0682ec49-87dd-4d01-b993-2e2819db7516" / "scratchpad" / "statsbomb"
)


def _base(idx, type_name, **extra):
    e = {
        "id": f"e{idx}", "index": idx, "period": 1, "minute": 10, "second": 0,
        "type": {"name": type_name},
        "player": {"id": 100, "name": "x"}, "team": {"id": 1, "name": "Home"},
        "position": {"id": 1, "name": "Center Forward"}, "location": [60.0, 40.0],
        "possession": 5, "possession_team": {"id": 1, "name": "Home"},
    }
    e.update(extra)
    return e


def test_normalize_complete_pass_has_null_outcome():
    ev = [_base(1, "Pass", **{"pass": {"length": 12.0, "height": {"name": "Ground Pass"},
                                        "end_location": [72.0, 44.0], "cross": True}})]
    row = normalize_events(ev, match_id=9, competition_id=2)[0]
    assert row["type_name"] == "Pass"
    assert row["pass_outcome_name"] is None      # complete = outcome absent (D020 §6)
    assert row["pass_cross"] is True
    assert row["pass_through_ball"] is False
    assert row["end_location_x"] == 72.0 and row["end_location_y"] == 44.0
    assert row["match_id"] == 9 and row["competitionId"] == 2


def test_normalize_incomplete_pass_keeps_outcome():
    ev = [_base(1, "Pass", **{"pass": {"outcome": {"name": "Incomplete"}, "end_location": [10.0, 5.0]}})]
    row = normalize_events(ev, 9, 2)[0]
    assert row["pass_outcome_name"] == "Incomplete"


def test_normalize_shot_carries_xg_and_outcome():
    ev = [_base(1, "Shot", location=[110.0, 40.0],
                **{"shot": {"statsbomb_xg": 0.23, "outcome": {"name": "Goal"},
                            "type": {"name": "Open Play"}, "body_part": {"name": "Left Foot"},
                            "end_location": [120.0, 40.0]}})]
    row = normalize_events(ev, 9, 2)[0]
    assert row["shot_outcome_name"] == "Goal"
    assert row["shot_statsbomb_xg"] == 0.23
    assert row["shot_type_name"] == "Open Play"
    assert row["end_location_x"] == 120.0


def test_normalize_carry_end_location_resolves():
    ev = [_base(1, "Carry", **{"carry": {"end_location": [65.0, 41.0]}})]
    row = normalize_events(ev, 9, 2)[0]
    assert row["end_location_x"] == 65.0 and row["end_location_y"] == 41.0


def test_normalize_non_action_event_has_null_action_fields():
    ev = [_base(1, "Half Start", player=None, position=None, location=None)]
    row = normalize_events(ev, 9, 2)[0]
    assert row["player_id"] is None
    assert row["location_x"] is None
    assert row["pass_cross"] is None and row["shot_outcome_name"] is None


def test_team_ids_from_events():
    ev = [_base(1, "Pass"), _base(2, "Pass", team={"id": 2, "name": "Away"})]
    assert team_ids_from_events(ev) == {"Home": 1, "Away": 2}


@pytest.mark.skipif(not (SAMPLE / "events_3754217.json").exists(),
                    reason="sample match not present locally")
def test_normalize_real_sample_is_flat_and_complete():
    raw = json.loads((SAMPLE / "events_3754217.json").read_text(encoding="utf-8"))
    rows = normalize_events(raw, 3754217, 2)
    assert len(rows) == len(raw)
    # every row has the full flat schema, same keys
    keys = set(rows[0])
    assert all(set(r) == keys for r in rows)
    # at least one native Carry survived normalization with an end location
    carries = [r for r in rows if r["type_name"] == "Carry"]
    assert carries and all(c["end_location_x"] is not None for c in carries)
    # completed passes (majority) have null outcome
    passes = [r for r in rows if r["type_name"] == "Pass"]
    assert sum(1 for p in passes if p["pass_outcome_name"] is None) > len(passes) / 2


@pytest.mark.skipif(not (SAMPLE / "events_3754217.json").exists(),
                    reason="sample match not present locally")
def test_full_per_match_pipeline_passes_validation():
    """normalize + minutes + validation compose into a clean processed set
    for one real match — the end-to-end wiring `run()` performs per match,
    minus the network fetch."""
    raw = json.loads((SAMPLE / "events_3754217.json").read_text(encoding="utf-8"))
    lineups = json.loads((SAMPLE / "lineups_3754217.json").read_text(encoding="utf-8"))
    team_ids = team_ids_from_events(raw)

    events = events_frame(normalize_events(raw, 3754217, 2))
    minutes = minutes_frame(derive_match_minutes(3754217, 2, team_ids, lineups, raw))
    matches = pl.DataFrame({"match_id": [3754217], "competitionId": [2]})

    summary = summarize(run_all(events, minutes, matches))
    assert summary["passed"] is True, summary
    assert summary["fail"] == 0
    # sanity: a real PL match has ~3.7k events and 22+ minutes rows
    assert events.height > 2000
    assert minutes.height >= 22
