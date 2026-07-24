"""StatsBomb minutes derivation (D020 §4, beads scoutlens-8mc.2).

StatsBomb records each player's on-pitch stints explicitly in the lineup
file: every `positions[]` entry carries `from`/`to` timestamps and
`from_period`/`to_period`. This is cleaner than the Wyscout
formation+substitution reconstruction (`scoutlens.data.minutes`) — but it
has one real subtlety that a naive end-minus-start gets wrong.

The StatsBomb match clock does **not** reset between periods and the
periods overlap in absolute numbering: in the reference match 3754217,
period 1 runs [0:00, 48:38] and period 2 runs [45:00, 95:38] — the
stretch 45:00–48:38 is numbered in both. So a full-match player's real
playing time is `P1_duration + P2_duration` (≈ 48.6 + 50.6 = 99.3 min),
**not** `final_whistle − kickoff` (95.6). Minutes must therefore be summed
**per period**, clipping each on-pitch interval to that period's own
[half_start, half_end] bounds, then added across periods.

`lineup` timestamps use the same absolute clock as `Half Start`/`Half
End` events (a period-2 substitute's `from` is `"45:00"`, not `"00:00"`),
so period bounds are read directly from those events and intervals are
clipped against them.
"""

from __future__ import annotations

import dataclasses

import polars as pl


def _parse_clock(ts: str) -> float:
    """`"MM:SS"` (StatsBomb absolute clock) → minutes as a float."""
    minute, second = ts.split(":")
    return int(minute) + int(second) / 60.0


def period_bounds(events: list[dict]) -> dict[int, tuple[float, float]]:
    """Map period → (start_minute, end_minute) in the absolute clock, read
    from the match's own `Half Start` / `Half End` events. Raises if a
    period has no matching start/end pair — a silently missing bound would
    truncate every interval in that period."""
    starts: dict[int, float] = {}
    ends: dict[int, float] = {}
    for e in events:
        name = e["type"]["name"]
        if name == "Half Start":
            starts.setdefault(e["period"], _parse_clock(f"{e['minute']}:{e['second']}"))
        elif name == "Half End":
            # a period emits one Half End per team; keep the max (true whistle)
            m = _parse_clock(f"{e['minute']}:{e['second']}")
            ends[e["period"]] = max(ends.get(e["period"], m), m)
    bounds = {}
    for p in sorted(set(starts) | set(ends)):
        if p not in starts or p not in ends:
            raise ValueError(f"period {p} is missing a Half Start or Half End event")
        bounds[p] = (starts[p], ends[p])
    return bounds


def interval_minutes(
    from_min: float, from_period: int, to_min: float, to_period: int, bounds: dict[int, tuple[float, float]]
) -> float:
    """Playing minutes for one on-pitch stint, summed per period so the
    cross-period clock overlap is never double-counted (see module
    docstring). `from`/`to` are absolute-clock minutes; the stint may span
    several periods. For a player with *several* stints, use
    `player_minutes`, which unions overlapping stints rather than summing
    them."""
    total = 0.0
    for p in range(from_period, to_period + 1):
        if p not in bounds:
            continue
        start, end = bounds[p]
        seg_start = from_min if p == from_period else start
        seg_end = to_min if p == to_period else end
        total += max(0.0, seg_end - seg_start)
    return total


def player_minutes(
    positions: list[dict], bounds: dict[int, tuple[float, float]], final_whistle: float, last_period: int
) -> tuple[float, bool]:
    """Total on-pitch minutes across all of a player's `positions[]`
    stints, computed as the **union** of clipped per-period intervals, not
    their sum. Real StatsBomb lineups occasionally record overlapping
    stints for one player (e.g. an injury off-and-on plus a tactical-shift
    position that outlives the player's own substitution — match 3754217,
    Coquelin); summing those would credit more than a full match. Union
    counts each moment once and returns an `overlap` flag so the anomaly
    is visible in `derivation_status` rather than silently smoothed.

    Every segment is clipped to its period's [start, end] bounds first, so
    a stint that runs past the whistle (or a `from` before kickoff) cannot
    inflate the total."""
    per_period: dict[int, list[tuple[float, float]]] = {}
    for pos in positions:
        from_period = pos["from_period"]
        from_min = _parse_clock(pos["from"])
        if pos["to"] is None:
            to_min, to_period = final_whistle, last_period
        else:
            to_min, to_period = _parse_clock(pos["to"]), pos["to_period"]
        for p in range(from_period, to_period + 1):
            if p not in bounds:
                continue
            start, end = bounds[p]
            seg_start = max(from_min if p == from_period else start, start)
            seg_end = min(to_min if p == to_period else end, end)
            if seg_end > seg_start:
                per_period.setdefault(p, []).append((seg_start, seg_end))

    total = 0.0
    overlap = False
    for intervals in per_period.values():
        intervals.sort()
        cur_start, cur_end = intervals[0]
        for seg_start, seg_end in intervals[1:]:
            if seg_start < cur_end:
                overlap = True
                cur_end = max(cur_end, seg_end)
            else:
                total += cur_end - cur_start
                cur_start, cur_end = seg_start, seg_end
        total += cur_end - cur_start
    return total, overlap


@dataclasses.dataclass(frozen=True)
class MinutesRow:
    player_id: int
    match_id: int
    team_id: int
    competitionId: int
    minutes_played: float
    derivation_status: str


def derive_match_minutes(
    match_id: int, competition_id: int, team_ids: dict[str, int], lineups: list[dict], events: list[dict]
) -> list[MinutesRow]:
    """One row per squad player. A player with no on-pitch interval (an
    unused substitute) gets `minutes_played == 0`, status `clean` — the
    same convention as the Wyscout pipeline, so the eligibility filter
    downstream behaves identically across providers.

    `team_ids` maps `team_name` → StatsBomb `team.id` (lineup files carry
    the name, events carry the id; joined here so the processed row uses
    the stable id).
    """
    bounds = period_bounds(events)
    last_period = max(bounds) if bounds else 1
    final_whistle = bounds[last_period][1] if bounds else 0.0

    rows: list[MinutesRow] = []
    for team in lineups:
        team_id = team_ids[team["team_name"]]
        for player in team["lineup"]:
            minutes, overlap = player_minutes(player["positions"], bounds, final_whistle, last_period)
            rows.append(MinutesRow(
                player_id=player["player_id"], match_id=match_id, team_id=team_id,
                competitionId=competition_id, minutes_played=round(minutes, 3),
                derivation_status="overlap_merged" if overlap else "clean",
            ))
    return rows


def minutes_frame(rows: list[MinutesRow]) -> pl.DataFrame:
    return pl.DataFrame([dataclasses.asdict(r) for r in rows]) if rows else pl.DataFrame(
        schema={
            "player_id": pl.Int64, "match_id": pl.Int64, "team_id": pl.Int64,
            "competitionId": pl.Int64, "minutes_played": pl.Float64, "derivation_status": pl.Utf8,
        }
    )
