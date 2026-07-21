import json

import polars as pl

from scoutlens.data.minutes import audit_formation_coverage, derive_minutes


def _player(player_id, red_cards="0", yellow_cards="0", goals="0", own_goals="0"):
    return {
        "playerId": player_id,
        "ownGoals": own_goals,
        "redCards": red_cards,
        "goals": goals,
        "yellowCards": yellow_cards,
    }


def _match(wy_id, teams_data, duration="Regular", competition_id=1):
    return {
        "wyId": wy_id,
        "competitionId": competition_id,
        "duration": duration,
        "teamsData": json.dumps(teams_data),
    }


def _matches_df(*records) -> pl.DataFrame:
    return pl.DataFrame(list(records))


def test_starter_who_plays_full_match():
    matches = _matches_df(_match(1, {
        "10": {
            "hasFormation": 1,
            "formation": {
                "lineup": [_player(100)],
                "bench": [],
                "substitutions": "null",
            },
        }
    }))
    result = derive_minutes(matches)
    row = result.row(0, named=True)
    assert row == {
        "player_id": 100, "match_id": 1, "team_id": 10, "started": True,
        "minute_in": 0, "minute_out": 90, "minutes_played": 90, "derivation_status": "clean",
    }


def test_starter_substituted_off():
    matches = _matches_df(_match(1, {
        "10": {
            "hasFormation": 1,
            "formation": {
                "lineup": [_player(100)],
                "bench": [_player(200)],
                "substitutions": [{"playerIn": 200, "playerOut": 100, "minute": 60}],
            },
        }
    }))
    result = derive_minutes(matches)
    by_player = {r["player_id"]: r for r in result.to_dicts()}
    assert by_player[100]["minutes_played"] == 60
    assert by_player[100]["minute_out"] == 60
    assert by_player[200]["minute_in"] == 60
    assert by_player[200]["minutes_played"] == 30
    assert by_player[200]["derivation_status"] == "clean"


def test_bench_player_never_subbed_in_gets_zero_minutes():
    matches = _matches_df(_match(1, {
        "10": {
            "hasFormation": 1,
            "formation": {
                "lineup": [_player(100)],
                "bench": [_player(200)],
                "substitutions": "null",
            },
        }
    }))
    result = derive_minutes(matches)
    by_player = {r["player_id"]: r for r in result.to_dicts()}
    assert by_player[200]["minutes_played"] == 0
    assert by_player[200]["minute_in"] is None
    assert by_player[200]["started"] is False
    assert by_player[200]["derivation_status"] == "clean"


def test_double_substitution_in_then_out():
    """A substitute who is later substituted out again (see docs/data-dictionary.md
    — confirmed to occur 11 times in the real dataset)."""
    matches = _matches_df(_match(1, {
        "10": {
            "hasFormation": 1,
            "formation": {
                "lineup": [_player(100)],
                "bench": [_player(200), _player(300)],
                "substitutions": [
                    {"playerIn": 200, "playerOut": 100, "minute": 30},
                    {"playerIn": 300, "playerOut": 200, "minute": 70},
                ],
            },
        }
    }))
    result = derive_minutes(matches)
    by_player = {r["player_id"]: r for r in result.to_dicts()}
    assert by_player[200]["minute_in"] == 30
    assert by_player[200]["minute_out"] == 70
    assert by_player[200]["minutes_played"] == 40


def test_red_card_ends_playing_time_without_formal_substitution():
    matches = _matches_df(_match(1, {
        "10": {
            "hasFormation": 1,
            "formation": {
                "lineup": [_player(100, red_cards="75")],
                "bench": [],
                "substitutions": "null",
            },
        }
    }))
    result = derive_minutes(matches)
    row = result.row(0, named=True)
    assert row["minutes_played"] == 75
    assert row["minute_out"] == 75
    assert row["derivation_status"] == "clean"


def test_red_card_after_formal_substitution_out_is_ignored():
    """Player substituted out at minute 60 can't also be sent off at 75 —
    the earlier of the two candidates wins."""
    matches = _matches_df(_match(1, {
        "10": {
            "hasFormation": 1,
            "formation": {
                "lineup": [_player(100, red_cards="75")],
                "bench": [_player(200)],
                "substitutions": [{"playerIn": 200, "playerOut": 100, "minute": 60}],
            },
        }
    }))
    result = derive_minutes(matches)
    by_player = {r["player_id"]: r for r in result.to_dicts()}
    assert by_player[100]["minutes_played"] == 60


def test_stoppage_time_entry_flagged_as_substitution_conflict():
    """Substitute enters at minute 94 (real stoppage-time value) on a
    nominal 90-minute match, with no further sub-out/red-card record.
    matches.parquet has no true final-whistle minute, so this is floored
    at 0 and flagged rather than guessed — see docs/data-dictionary.md."""
    matches = _matches_df(_match(1, {
        "10": {
            "hasFormation": 1,
            "formation": {
                "lineup": [_player(100)],
                "bench": [_player(200)],
                "substitutions": [{"playerIn": 200, "playerOut": 100, "minute": 94}],
            },
        }
    }))
    result = derive_minutes(matches)
    by_player = {r["player_id"]: r for r in result.to_dicts()}
    assert by_player[200]["minutes_played"] == 0
    assert by_player[200]["minute_out"] == 94
    assert by_player[200]["derivation_status"] == "substitution_conflict"


def test_extra_time_match_uses_120_minute_duration():
    matches = _matches_df(_match(1, {
        "10": {
            "hasFormation": 1,
            "formation": {"lineup": [_player(100)], "bench": [], "substitutions": "null"},
        }
    }, duration="ExtraTime"))
    result = derive_minutes(matches)
    row = result.row(0, named=True)
    assert row["minute_out"] == 120
    assert row["minutes_played"] == 120


def test_total_team_minutes_equal_eleven_times_duration_when_no_conflicts():
    """Regardless of how many substitutions happen, 11 outfield-equivalent
    slots are always occupied — total minutes across the roster must equal
    11 x full_duration when nothing is flagged."""
    matches = _matches_df(_match(1, {
        "10": {
            "hasFormation": 1,
            "formation": {
                "lineup": [_player(i) for i in range(100, 111)],
                "bench": [_player(200)],
                "substitutions": [{"playerIn": 200, "playerOut": 100, "minute": 45}],
            },
        }
    }))
    result = derive_minutes(matches)
    assert result["minutes_played"].sum() == 11 * 90


def test_audit_formation_coverage_reports_rates_and_sizes():
    matches = _matches_df(
        _match(1, {"10": {"hasFormation": 1, "formation": {
            "lineup": [_player(i) for i in range(100, 111)],
            "bench": [_player(200)],
            "substitutions": "null",
        }}}),
        _match(2, {"20": {"hasFormation": 1, "formation": {
            "lineup": [_player(i) for i in range(300, 311)],
            "bench": [_player(400), _player(401)],
            "substitutions": [{"playerIn": 400, "playerOut": 300, "minute": 10}],
        }}}),
    )
    coverage = audit_formation_coverage(matches)
    assert coverage.team_match_entries == 2
    assert coverage.has_formation_rate == 1.0
    assert coverage.lineup_size_counts == {11: 2}
    assert coverage.bench_size_counts == {1: 1, 2: 1}
    assert coverage.substitution_count_counts == {0: 1, 1: 1}
    assert coverage.substitutions_null_sentinel_count == 1
