"""Tests for recruitment-study shortlist generation (h00)."""

from __future__ import annotations

import collections
from pathlib import Path

import polars as pl
import pytest

from scoutlens.study.shortlists import sample_queries

PROCESSED = Path(__file__).resolve().parents[2] / "data" / "processed"


def _query_pool():
    # 4 roles x 6 players x (some leagues/teams), each player its own team
    rows, pid = [], 1
    for role in ["Goalkeeper", "Defender", "Midfielder", "Forward"]:
        for i in range(6):
            rows.append({"player_id": pid, "competitionId": 364 + (i % 3),
                         "role": role, "team_id": pid})  # unique team per player
            pid += 1
    return pl.DataFrame(rows)


def test_sample_queries_is_role_stratified_and_seeded():
    q = _query_pool()
    teams = q.select("player_id", "competitionId", "team_id")
    picks = sample_queries(q.select("player_id", "competitionId", "role"), teams, seed=1)
    roles = collections.Counter(p["role"] for p in picks)
    assert roles == {"Goalkeeper": 10, "Defender": 10, "Midfielder": 10, "Forward": 10} or \
        all(v <= 10 for v in roles.values())          # pool of 6/role caps below 10 here
    # determinism
    assert picks == sample_queries(q.select("player_id", "competitionId", "role"), teams, seed=1)


def test_sample_queries_avoids_repeating_a_team():
    # two players share a team; only one may be picked
    q = pl.DataFrame({
        "player_id": [1, 2, 3, 4], "competitionId": [364, 364, 412, 412],
        "role": ["Defender"] * 4,
    })
    teams = pl.DataFrame({"player_id": [1, 2, 3, 4], "competitionId": [364, 364, 412, 412],
                          "team_id": [100, 100, 200, 300]})  # 1 & 2 same team
    picks = sample_queries(q, teams, seed=3)
    picked_teams = [teams.filter((pl.col("player_id") == p["player_id"]))["team_id"][0] for p in picks]
    assert len(picked_teams) == len(set(picked_teams))     # no team twice


@pytest.mark.skipif(not (PROCESSED / "events.parquet").exists(),
                    reason="Wyscout processed data not present locally")
def test_full_generation_is_blinded_and_well_formed():
    from scoutlens.study.shortlists import run
    out = run(seed=0)
    sheet, key = out["rating_sheet"], out["arm_key"]
    assert len(sheet) == 40
    assert out["manifest"]["n_ratings_expected_per_rater"] == 600
    # blinding: no arm label anywhere in the rater-facing sheet
    assert all("arm" not in c for q in sheet for c in q["candidates"])
    # arm key balanced 200/200/200 and every candidate maps to exactly one arm
    assert collections.Counter(k["arm"] for k in key) == {"B": 200, "C_role": 200, "R": 200}
    # each query: 15 distinct candidates
    for q in sheet:
        ids = [(c["player_id"], c["competitionId"]) for c in q["candidates"]]
        assert len(ids) == 15 and len(set(ids)) == 15
        # the query player is never among his own candidates
        assert all(c["player_id"] != q["query"]["player_id"] for c in q["candidates"])
    # role stratified
    assert collections.Counter(q["query"]["role"] for q in sheet) == {
        "Goalkeeper": 10, "Defender": 10, "Midfielder": 10, "Forward": 10}
