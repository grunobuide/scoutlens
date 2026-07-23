"""Pin the player-count reconciliation (D017, beads scoutlens-6w8).

The "3,603 vs 4,299" question stayed open from Gate 1 to the v0.1
release. Resolution, verified against the paper's PDF (Table 1) and the
local data:

- 3,603  = rows in players.json — every player with a profile.
- 3,618  = distinct rostered players (lineup+bench across all matches)
           = 3,603 profiled + 15 unused bench players with 0 minutes
           and 0 events (harmless to every published number).
- 4,362  = SUM of per-competition distinct rostered players — exactly
           reproduces all seven per-competition values in the paper's
           Table 1 (players active in several competitions count once
           per competition).
- 4,299  = the paper's printed total — matches neither its own column
           sum (4,362) nor any distinct count; an arithmetic error in
           the paper's totals row, not a gap in this dataset.

These tests keep that reconciliation true against the local data.
Skipped when data/processed isn't present (e.g. CI).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"

# Paper's Table 1 (#players column), Pappalardo et al. 2019, Sci Data 6:236.
PAPER_TABLE_1_PLAYERS = {
    795: 619,  # Spanish first division
    364: 603,  # English first division
    524: 686,  # Italian first division
    426: 537,  # German first division
    412: 629,  # French first division
    28: 736,   # World Cup 2018
    102: 552,  # European Championship 2016
}


@pytest.fixture(scope="module")
def rostered_by_competition() -> dict[int, set[int]]:
    if not PROCESSED_DIR.exists():
        pytest.skip("data/processed not present — build it first (see README)")
    import polars as pl

    matches = pl.read_parquet(PROCESSED_DIR / "matches.parquet")
    per_comp: dict[int, set[int]] = {}
    for row in matches.select("competitionId", "teamsData").iter_rows(named=True):
        bucket = per_comp.setdefault(row["competitionId"], set())
        for team in json.loads(row["teamsData"]).values():
            formation = team.get("formation") or {}
            for section in ("lineup", "bench"):
                for entry in formation.get(section) or []:
                    if entry["playerId"] != 0:
                        bucket.add(entry["playerId"])
    return per_comp


def test_per_competition_rostered_counts_reproduce_paper_table_1(rostered_by_competition):
    counts = {cid: len(s) for cid, s in rostered_by_competition.items()}
    assert counts == PAPER_TABLE_1_PLAYERS


def test_paper_total_is_the_column_sum_not_a_distinct_count(rostered_by_competition):
    assert sum(len(s) for s in rostered_by_competition.values()) == 4362  # not the paper's 4,299
    union = set().union(*rostered_by_competition.values())
    assert len(union) == 3618


def test_unprofiled_rostered_players_are_exactly_the_harmless_15(rostered_by_competition):
    import polars as pl

    players = pl.read_parquet(PROCESSED_DIR / "players.parquet")
    assert players.height == 3603
    union = set().union(*rostered_by_competition.values())
    missing = union - set(players["wyId"].to_list())
    assert len(missing) == 15

    minutes = pl.read_parquet(PROCESSED_DIR / "minutes.parquet")
    events = pl.read_parquet(PROCESSED_DIR / "events.parquet")
    assert minutes.filter(pl.col("player_id").is_in(missing))["minutes_played"].sum() == 0
    assert events.filter(pl.col("playerId").is_in(missing)).height == 0
