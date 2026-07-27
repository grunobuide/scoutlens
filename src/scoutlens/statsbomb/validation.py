"""Structural + relational validation for the processed StatsBomb tables
(8mc.2). Mirrors `scoutlens.data.validation`'s report-don't-fix contract:
every check returns a `CheckResult`; a `fail` blocks the pipeline, a
`warn` is a documented data-quality signal (e.g. the lineup/substitution
overlap discrepancy from D020 §4), an `ok` passes.

Provider-scoped — it validates the StatsBomb processed frames only and
shares no code path with the Wyscout validator, so the two providers stay
independently reproducible.
"""

from __future__ import annotations

import dataclasses
from typing import Literal

import polars as pl

Status = Literal["ok", "warn", "fail"]


@dataclasses.dataclass(frozen=True)
class CheckResult:
    check: str
    table: str
    status: Status
    detail: str
    count: int = 0


def check_events_have_required_columns(events: pl.DataFrame) -> CheckResult:
    required = {
        "id", "match_id", "competitionId", "type_name", "period", "minute",
        "location_x", "location_y", "possession", "pass_outcome_name", "shot_outcome_name",
    }
    missing = required - set(events.columns)
    if missing:
        return CheckResult("required_columns", "events", "fail", f"missing: {sorted(missing)}", len(missing))
    return CheckResult("required_columns", "events", "ok", f"all {len(required)} present")


def check_event_id_unique(events: pl.DataFrame) -> CheckResult:
    n_total, n_unique = events.height, events["id"].n_unique()
    if n_total == n_unique:
        return CheckResult("event_id_unique", "events", "ok", f"{n_unique}/{n_total} unique")
    return CheckResult("event_id_unique", "events", "fail",
                       f"{n_total - n_unique} duplicate event ids", n_total - n_unique)


def check_coordinates_in_native_range(events: pl.DataFrame) -> CheckResult:
    """StatsBomb pitch is 120 x 80; anything outside is corrupt, not a
    normalization choice. Nulls (non-spatial events) are allowed."""
    bad = events.filter(
        (pl.col("location_x") < 0) | (pl.col("location_x") > 120)
        | (pl.col("location_y") < 0) | (pl.col("location_y") > 80)
    ).height
    if bad == 0:
        return CheckResult("coord_range", "events", "ok", "all within 120x80")
    return CheckResult("coord_range", "events", "fail", f"{bad} events out of pitch bounds", bad)


def check_minutes_non_negative_and_bounded(minutes: pl.DataFrame) -> CheckResult:
    bad = minutes.filter((pl.col("minutes_played") < 0) | (pl.col("minutes_played") > 130)).height
    if bad == 0:
        return CheckResult("minutes_bounds", "minutes", "ok", "all in [0, 130]")
    return CheckResult("minutes_bounds", "minutes", "fail", f"{bad} rows out of [0,130]", bad)


def check_minutes_events_player_referential(events: pl.DataFrame, minutes: pl.DataFrame) -> CheckResult:
    """Every player who logged an event in a match must have a minutes row
    for that match — otherwise the per-90 denominator is missing. The
    reverse (a squad player with 0 events) is fine: unused subs exist."""
    ev_keys = events.filter(pl.col("player_id").is_not_null()).select("player_id", "match_id").unique()
    min_keys = minutes.select("player_id", "match_id").unique()
    orphaned = ev_keys.join(min_keys, on=["player_id", "match_id"], how="anti").height
    if orphaned == 0:
        return CheckResult("events_have_minutes", "minutes", "ok", "every acting player has minutes")
    return CheckResult("events_have_minutes", "minutes", "fail",
                       f"{orphaned} (player, match) pairs act but have no minutes row", orphaned)


def check_overlap_flag_rate(minutes: pl.DataFrame) -> CheckResult:
    """Report, not block: how many players hit the overlapping-stint path
    (D020 §4). A high rate would mean the lineup data is systematically
    inconsistent and the minutes need a closer look."""
    n = minutes.height
    flagged = minutes.filter(pl.col("derivation_status") == "overlap_merged").height
    if n == 0:
        return CheckResult("overlap_rate", "minutes", "warn", "no minutes rows", 0)
    pct = 100.0 * flagged / n
    status: Status = "ok" if pct < 5 else "warn"
    return CheckResult("overlap_rate", "minutes", status, f"{flagged}/{n} ({pct:.2f}%) overlap-merged", flagged)


def check_matches_present(events: pl.DataFrame, matches: pl.DataFrame) -> CheckResult:
    ev_matches = set(events["match_id"].unique().to_list())
    declared = set(matches["match_id"].unique().to_list())
    missing = ev_matches - declared
    if not missing:
        return CheckResult("events_match_declared", "matches", "ok", f"{len(ev_matches)} match ids all declared")
    return CheckResult("events_match_declared", "matches", "fail",
                       f"{len(missing)} match ids in events but not in matches table", len(missing))


def run_all(events: pl.DataFrame, minutes: pl.DataFrame, matches: pl.DataFrame) -> list[CheckResult]:
    return [
        check_events_have_required_columns(events),
        check_event_id_unique(events),
        check_coordinates_in_native_range(events),
        check_minutes_non_negative_and_bounded(minutes),
        check_minutes_events_player_referential(events, minutes),
        check_overlap_flag_rate(minutes),
        check_matches_present(events, matches),
    ]


def summarize(results: list[CheckResult]) -> dict:
    counts = {"ok": 0, "warn": 0, "fail": 0}
    for r in results:
        counts[r.status] += 1
    return {"total": len(results), **counts, "passed": counts["fail"] == 0}
