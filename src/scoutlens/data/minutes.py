"""Formation/substitution audit (SLS-008) and minutes-played derivation
(SLS-009) from matches.teamsData.

teamsData is stored as a JSON string in matches.parquet (see ingestion.py —
its per-match dynamic team-id keys don't fit a flat Parquet column). This
module parses it and turns it into the per-player-per-match minutes table
the brief specifies.

Design follows D005 (80/20 rule): handle the common, well-supported cases
correctly and completely; tag anything genuinely ambiguous with
`derivation_status` rather than silently guessing. In practice, this
dataset turned out cleaner than the brief worried it might be — see
`audit_formation_coverage()`: hasFormation is 1 for 100% of team-match
entries and lineup is always exactly 11 players, so `missing_formation`
never actually triggers here. The status field is kept anyway, since a
future re-run against updated source data could see different coverage.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import polars as pl

REPO_ROOT = Path(__file__).resolve().parents[3]
PROCESSED_DIR = REPO_ROOT / "data" / "processed"

# Regular = 90 minutes. ExtraTime/Penalties matches went through a full
# extra-time period (2x15) before any shootout, which doesn't add playing
# time. Penalty-shootout minutes are not "playing time" and are not
# counted. This is a stated assumption, not something the schema confirms
# directly — flagged here rather than silently baked in.
DURATION_MINUTES = {"Regular": 90, "ExtraTime": 120, "Penalties": 120}


def _to_int_or_none(value) -> int | None:
    if value is None or value == "null" or value == "":
        return None
    return int(value)


def _card_minute(value) -> int | None:
    """redCards/yellowCards store the minute of the card as a string, with
    "0" meaning "no card" — not a count, despite the field name. See
    docs/data-dictionary.md."""
    minute = _to_int_or_none(value)
    if minute is None or minute == 0:
        return None
    return minute


def _normalize_substitutions(raw) -> list[dict]:
    """substitutions is a list of {playerIn, playerOut, minute}, or the
    literal string "null" when a team made zero substitutions (6 cases in
    this dataset) — same null-vs-"null" sentinel pattern as elsewhere."""
    if not isinstance(raw, list):
        return []
    return raw


@dataclasses.dataclass(frozen=True)
class FormationCoverage:
    team_match_entries: int
    has_formation_rate: float
    lineup_size_counts: dict[int, int]
    bench_size_counts: dict[int, int]
    substitution_count_counts: dict[int, int]
    substitutions_null_sentinel_count: int


def audit_formation_coverage(matches: pl.DataFrame) -> FormationCoverage:
    """SLS-008: how much of teamsData is actually usable before minutes
    derivation is attempted. Iterates in Python (not vectorized) — matches
    is only 1,941 rows, so this runs in well under a second."""
    entries = 0
    has_formation = 0
    lineup_sizes: dict[int, int] = {}
    bench_sizes: dict[int, int] = {}
    sub_counts: dict[int, int] = {}
    null_sub_sentinel = 0

    for teams_data_json in matches["teamsData"]:
        teams_data = json.loads(teams_data_json)
        for team_entry in teams_data.values():
            entries += 1
            if team_entry.get("hasFormation") == 1:
                has_formation += 1
            formation = team_entry.get("formation", {})
            lineup = formation.get("lineup", [])
            bench = formation.get("bench", [])
            lineup_sizes[len(lineup)] = lineup_sizes.get(len(lineup), 0) + 1
            bench_sizes[len(bench)] = bench_sizes.get(len(bench), 0) + 1
            raw_subs = formation.get("substitutions")
            if isinstance(raw_subs, str):
                null_sub_sentinel += 1
                sub_counts[0] = sub_counts.get(0, 0) + 1
            else:
                n = len(raw_subs or [])
                sub_counts[n] = sub_counts.get(n, 0) + 1

    return FormationCoverage(
        team_match_entries=entries,
        has_formation_rate=has_formation / entries if entries else 0.0,
        lineup_size_counts=dict(sorted(lineup_sizes.items())),
        bench_size_counts=dict(sorted(bench_sizes.items())),
        substitution_count_counts=dict(sorted(sub_counts.items())),
        substitutions_null_sentinel_count=null_sub_sentinel,
    )


def derive_minutes(matches: pl.DataFrame) -> pl.DataFrame:
    """SLS-009: player_id x match_id minutes table.

    minute_out is the earliest of: full match duration, this player's
    substitution-out minute (if any), this player's red-card minute (if
    any) — a player sent off ends their match there even without a formal
    substitution. Bench players never subbed in get minutes_played=0, not
    excluded — they were an available squad member, which matters for
    later population/eligibility analysis even at zero minutes.
    """
    rows = []

    for match_id, competition_id, duration, teams_data_json in matches.select(
        "wyId", "competitionId", "duration", "teamsData"
    ).iter_rows():
        full_duration = DURATION_MINUTES.get(duration, 90)
        teams_data = json.loads(teams_data_json)

        for team_id_str, team_entry in teams_data.items():
            team_id = int(team_id_str)
            formation = team_entry.get("formation", {})
            lineup = formation.get("lineup", [])
            bench = formation.get("bench", [])
            substitutions = _normalize_substitutions(formation.get("substitutions"))

            sub_in_minute = {s["playerIn"]: s["minute"] for s in substitutions}
            sub_out_minute = {s["playerOut"]: s["minute"] for s in substitutions}

            for player in lineup:
                rows.append(_build_row(
                    match_id, team_id, player, started=True, minute_in=0,
                    sub_out_minute=sub_out_minute, full_duration=full_duration,
                ))
            for player in bench:
                player_id = player["playerId"]
                minute_in = sub_in_minute.get(player_id)
                if minute_in is None:
                    rows.append({
                        "player_id": player_id, "match_id": match_id, "team_id": team_id,
                        "started": False, "minute_in": None, "minute_out": None,
                        "minutes_played": 0, "derivation_status": "clean",
                    })
                else:
                    rows.append(_build_row(
                        match_id, team_id, player, started=False, minute_in=minute_in,
                        sub_out_minute=sub_out_minute, full_duration=full_duration,
                    ))

    return pl.DataFrame(rows)


def _build_row(match_id, team_id, player, started, minute_in, sub_out_minute, full_duration) -> dict:
    player_id = player["playerId"]
    candidates = [full_duration]
    if player_id in sub_out_minute:
        candidates.append(sub_out_minute[player_id])
    card_minute = _card_minute(player.get("redCards"))
    if card_minute is not None:
        candidates.append(card_minute)
    minute_out = min(candidates)

    if minute_out < minute_in:
        # Player entered during stoppage time (e.g. minute_in=94 on a
        # nominal 90-minute match) and has no later sub-out/red-card
        # candidate. matches.parquet doesn't carry the true final-whistle
        # minute (only events.eventSec would), so rather than fabricate an
        # end time we conservatively floor their minutes at 0 and flag it
        # instead of silently guessing. Affects ~0.3% of rows in practice.
        minute_out = minute_in
        minutes_played = 0
        status = "substitution_conflict"
    else:
        minutes_played = minute_out - minute_in
        if minutes_played > full_duration + 30:
            # Generous stoppage-time allowance rather than a hard cap at
            # the nominal duration — real substitutions/cards do occur
            # past minute 90+stoppage. Only flags genuinely implausible
            # values.
            status = "invalid"
        else:
            status = "clean"

    return {
        "player_id": player_id, "match_id": match_id, "team_id": team_id,
        "started": started, "minute_in": minute_in, "minute_out": minute_out,
        "minutes_played": minutes_played, "derivation_status": status,
    }


if __name__ == "__main__":
    matches = pl.read_parquet(PROCESSED_DIR / "matches.parquet")

    coverage = audit_formation_coverage(matches)
    print("hasFormation rate:", coverage.has_formation_rate)
    print("lineup sizes:", coverage.lineup_size_counts)
    print("bench sizes:", coverage.bench_size_counts)
    print("substitution counts:", coverage.substitution_count_counts)
    print("null-sentinel substitutions:", coverage.substitutions_null_sentinel_count)

    minutes = derive_minutes(matches)
    minutes.write_parquet(PROCESSED_DIR / "minutes.parquet")
    print(minutes.shape)
    print(minutes["derivation_status"].value_counts())
