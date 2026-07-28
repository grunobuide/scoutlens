"""Portable, schema-faithful StatsBomb fixtures.

The real open-data JSON cannot be redistributed under StatsBomb's licence.
These deliberately small synthetic records exercise the same normalization,
minutes, aggregation, and validation boundaries on every machine and in CI.
"""

from __future__ import annotations

import pytest


def _event(
    idx: int,
    type_name: str,
    *,
    period: int,
    minute: int,
    player_id: int | None = None,
    team_id: int | None = None,
    team_name: str | None = None,
    **extra,
) -> dict:
    event = {
        "id": f"synthetic-{idx}",
        "index": idx,
        "period": period,
        "minute": minute,
        "second": 0,
        "type": {"name": type_name},
        "player": {"id": player_id, "name": f"Player {player_id}"} if player_id is not None else None,
        "team": {"id": team_id, "name": team_name} if team_id is not None else None,
        "position": {"id": 1, "name": "Center Midfield"} if player_id is not None else None,
        "location": [60.0, 40.0] if player_id is not None else None,
        "possession": idx if player_id is not None else None,
        "possession_team": {"id": team_id, "name": team_name} if team_id is not None else None,
    }
    event.update(extra)
    return event


def _team_lineup(team_name: str, first_player_id: int) -> dict:
    return {
        "team_name": team_name,
        "lineup": [
            {
                "player_id": player_id,
                "player_name": f"Player {player_id}",
                "positions": [
                    {"from": "00:00", "from_period": 1, "to": None, "to_period": None}
                ],
            }
            for player_id in range(first_player_id, first_player_id + 11)
        ],
    }


@pytest.fixture
def synthetic_statsbomb_match() -> tuple[list[dict], list[dict]]:
    events = [
        _event(1, "Half Start", period=1, minute=0),
        _event(
            2, "Pass", period=1, minute=10, player_id=100, team_id=1, team_name="Home",
            **{"pass": {"length": 15.0, "height": {"name": "Ground Pass"}, "end_location": [75.0, 42.0]}},
        ),
        _event(
            3, "Carry", period=1, minute=20, player_id=100, team_id=1, team_name="Home",
            carry={"end_location": [70.0, 40.0]},
        ),
        _event(
            4, "Pass", period=1, minute=30, player_id=200, team_id=2, team_name="Away",
            **{"pass": {"length": 10.0, "height": {"name": "Ground Pass"}, "end_location": [70.0, 38.0]}},
        ),
        _event(5, "Half End", period=1, minute=45),
        _event(6, "Half Start", period=2, minute=45),
        _event(
            7, "Shot", period=2, minute=70, player_id=100, team_id=1, team_name="Home",
            location=[108.0, 40.0],
            shot={
                "statsbomb_xg": 0.2,
                "outcome": {"name": "Saved"},
                "type": {"name": "Open Play"},
                "body_part": {"name": "Right Foot"},
                "end_location": [120.0, 40.0],
            },
        ),
        _event(8, "Half End", period=2, minute=90),
    ]
    return events, [_team_lineup("Home", 100), _team_lineup("Away", 200)]
