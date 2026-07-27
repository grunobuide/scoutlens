"""Reproducible acquisition of StatsBomb open data for the ScoutLens
external replication (D014 / D020, beads scoutlens-8mc.2).

Scoped to the four leagues the Gate 0 audit cleared — Premier League (2),
Ligue 1 (7), La Liga (11), Serie A (12) — season 2015/16 (`season_id`
27), pinned to open-data commit `b0bc9f22dd`. This is a **separate,
provider-scoped pipeline**; it does not touch `scoutlens.data.*`, and the
Wyscout pipeline stays independently reproducible.

Raw StatsBomb JSON is downloaded fresh, never committed — the StatsBomb
User Agreement prohibits redistributing the data (D014), so `data/` stays
gitignored exactly as for Wyscout, here as a licence obligation rather
than only hygiene.

Run with:

    uv run python -m scoutlens.statsbomb.ingestion

Downloads ~1,517 events files (~5 GB) plus lineups, normalizes to
`data/processed/statsbomb/{events,matches,minutes,players}.parquet`. The
`normalize_events` / player+team extraction functions are pure and unit-
tested on a checked sample match; only the network fetch needs the live
repository.
"""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import requests

from scoutlens.statsbomb.minutes import derive_match_minutes, minutes_frame

REPO_ROOT = Path(__file__).resolve().parents[3]
PROCESSED_DIR = REPO_ROOT / "data" / "processed" / "statsbomb"

PINNED_COMMIT = "b0bc9f22dd77c206ddedc1d742893b3bbe64baec"
BASE = f"https://raw.githubusercontent.com/statsbomb/open-data/{PINNED_COMMIT}/data"
SEASON_ID = 27
COMPETITIONS = {2: "Premier League", 7: "Ligue 1", 11: "La Liga", 12: "Serie A"}

CITATION = (
    "StatsBomb Open Data (https://github.com/statsbomb/open-data), "
    "non-commercial use under the StatsBomb Public Data User Agreement; "
    "attribution with the StatsBomb logo required on any published analysis."
)


_F = pl.Float64
_I = pl.Int64
_S = pl.Utf8
_B = pl.Boolean
EVENTS_SCHEMA: dict[str, pl.DataType] = {
    "id": _S, "match_id": _I, "competitionId": _I, "index": _I, "period": _I,
    "minute": _I, "second": _I, "type_name": _S, "player_id": _I, "team_id": _I,
    "position_name": _S, "location_x": _F, "location_y": _F,
    "end_location_x": _F, "end_location_y": _F, "pass_length": _F,
    "pass_height_name": _S, "pass_cross": _B, "pass_through_ball": _B,
    "pass_shot_assist": _B, "pass_goal_assist": _B, "pass_outcome_name": _S,
    "shot_outcome_name": _S, "shot_type_name": _S, "shot_statsbomb_xg": _F,
    "shot_body_part_name": _S, "dribble_outcome_name": _S, "duel_type_name": _S,
    "duel_outcome_name": _S, "interception_outcome_name": _S,
    "possession": _I, "possession_team_id": _I,
}


def events_frame(rows: list[dict]) -> pl.DataFrame:
    """Build the events frame with an explicit schema. StatsBomb events
    mix ints, floats, bools and many nulls per column; letting Polars
    infer from the first rows overflows or mistypes at scale (e.g. a
    whole-number coordinate read as Int, then a fractional one), so the
    schema is pinned to match `normalize_events`' output exactly."""
    return pl.DataFrame(rows, schema=EVENTS_SCHEMA)


def _end_location(e: dict) -> tuple[float | None, float | None]:
    for field in ("pass", "carry", "shot"):
        loc = e.get(field, {}).get("end_location")
        if loc:
            return float(loc[0]), float(loc[1])
    return None, None


def normalize_events(raw_events: list[dict], match_id: int, competition_id: int) -> list[dict]:
    """Flatten StatsBomb's nested event JSON into the one-row-per-event
    schema the StatsBomb feature aggregation consumes (8mc.3). Native
    coordinates (0–120 × 0–80) are preserved as-is; the 0–100
    normalization (D020 §2) happens at aggregation time so the processed
    layer stays a faithful copy of the source. Every field maps to a
    concept frozen in `statsbomb-feature-compatibility.md`; outcome fields
    are null when absent (StatsBomb's outcome-by-presence encoding, D020
    §6 — a `pass` with null `pass_outcome_name` is a completed pass)."""
    rows = []
    for e in raw_events:
        loc = e.get("location") or [None, None]
        end_x, end_y = _end_location(e)
        pas = e.get("pass", {})
        shot = e.get("shot", {})
        duel = e.get("duel", {})
        rows.append({
            "id": e["id"],
            "match_id": match_id,
            "competitionId": competition_id,
            "index": e["index"],
            "period": e["period"],
            "minute": e["minute"],
            "second": e["second"],
            "type_name": e["type"]["name"],
            "player_id": (e.get("player") or {}).get("id"),
            "team_id": (e.get("team") or {}).get("id"),
            "position_name": (e.get("position") or {}).get("name"),
            "location_x": loc[0],
            "location_y": loc[1],
            "end_location_x": end_x,
            "end_location_y": end_y,
            "pass_length": pas.get("length"),
            "pass_height_name": (pas.get("height") or {}).get("name"),
            "pass_cross": bool(pas.get("cross", False)) if pas else None,
            "pass_through_ball": bool(pas.get("through_ball", False)) if pas else None,
            "pass_shot_assist": bool(pas.get("shot_assist", False)) if pas else None,
            "pass_goal_assist": bool(pas.get("goal_assist", False)) if pas else None,
            "pass_outcome_name": (pas.get("outcome") or {}).get("name") if pas else None,
            "shot_outcome_name": (shot.get("outcome") or {}).get("name") if shot else None,
            "shot_type_name": (shot.get("type") or {}).get("name") if shot else None,
            "shot_statsbomb_xg": shot.get("statsbomb_xg"),
            "shot_body_part_name": (shot.get("body_part") or {}).get("name") if shot else None,
            "dribble_outcome_name": (e.get("dribble", {}).get("outcome") or {}).get("name"),
            "duel_type_name": (duel.get("type") or {}).get("name") if duel else None,
            "duel_outcome_name": (duel.get("outcome") or {}).get("name") if duel else None,
            "interception_outcome_name": (e.get("interception", {}).get("outcome") or {}).get("name"),
            "possession": e.get("possession"),
            "possession_team_id": (e.get("possession_team") or {}).get("id"),
        })
    return rows


def extract_players(lineups: list[dict], competition_id: int) -> list[dict]:
    """Player roster rows from a match's lineup file. `position` (nominal
    role) is filled downstream from the modal event position; here we keep
    identity + the country, which is all the lineup carries."""
    out = []
    for team in lineups:
        for p in team["lineup"]:
            out.append({
                "player_id": p["player_id"],
                "player_name": p["player_name"],
                "nickname": p.get("player_nickname"),
                "country": (p.get("country") or {}).get("name"),
                "team_id": None,  # filled by caller from team_ids
                "competitionId": competition_id,
            })
    return out


def team_ids_from_events(raw_events: list[dict]) -> dict[str, int]:
    """team_name → team.id, needed because lineup files carry the name and
    minutes rows should key on the stable id."""
    ids: dict[str, int] = {}
    for e in raw_events:
        team = e.get("team")
        if team:
            ids[team["name"]] = team["id"]
    return ids


def _get_json(url: str) -> list[dict]:
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return resp.json()


def _match_ids(competition_id: int) -> list[tuple[int, int]]:
    matches = _get_json(f"{BASE}/matches/{competition_id}/{SEASON_ID}.json")
    return [(m["match_id"], competition_id) for m in matches]


def run() -> dict:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    all_events, all_minutes, all_players = [], [], []
    match_rows = []
    n_matches = 0
    for competition_id, comp_name in COMPETITIONS.items():
        for match_id, cid in _match_ids(competition_id):
            raw_events = _get_json(f"{BASE}/events/{match_id}.json")
            lineups = _get_json(f"{BASE}/lineups/{match_id}.json")
            team_ids = team_ids_from_events(raw_events)

            all_events.extend(normalize_events(raw_events, match_id, cid))
            all_minutes.extend(derive_match_minutes(match_id, cid, team_ids, lineups, raw_events))
            for p in extract_players(lineups, cid):
                # resolve team_id via the lineup team name
                team_name = next(t["team_name"] for t in lineups
                                 if any(x["player_id"] == p["player_id"] for x in t["lineup"]))
                p["team_id"] = team_ids[team_name]
                all_players.append(p)
            match_rows.append({"match_id": match_id, "competitionId": cid, "competition_name": comp_name})
            n_matches += 1

    events_df = events_frame(all_events)
    events_df.write_parquet(PROCESSED_DIR / "events.parquet")
    minutes_frame(all_minutes).write_parquet(PROCESSED_DIR / "minutes.parquet")
    pl.DataFrame(all_players).unique(subset=["player_id", "competitionId"]).write_parquet(PROCESSED_DIR / "players.parquet")
    pl.DataFrame(match_rows).write_parquet(PROCESSED_DIR / "matches.parquet")
    return {"n_matches": n_matches, "n_events": events_df.height, "n_minutes_rows": len(all_minutes)}


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2))
