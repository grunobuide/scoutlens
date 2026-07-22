"""Automated structural and relational validation for the processed
Wyscout Parquet files.

Covers both SLS-006 (intra-table: primary-key uniqueness, required-field
missingness, known sentinel-value patterns from SLS-005 schema profiling —
see docs/data-dictionary.md) and SLS-007 (cross-table foreign-key
integrity: event->match, event->player, event->team, match->competition).

This module reports; it does not silently fix. A CheckResult with status
"warn" documents something real about the data (e.g. a sentinel value) that
a later step may need to handle — it is not swept away here.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Literal

import polars as pl

REPO_ROOT = Path(__file__).resolve().parents[3]
PROCESSED_DIR = REPO_ROOT / "data" / "processed"

Status = Literal["ok", "warn", "fail"]


@dataclasses.dataclass(frozen=True)
class CheckResult:
    check: str
    table: str
    status: Status
    detail: str
    count: int = 0


def check_primary_key_unique(df: pl.DataFrame, table: str, key: str) -> CheckResult:
    n_total = df.height
    n_unique = df[key].n_unique()
    n_dupes = n_total - n_unique
    if n_dupes == 0:
        return CheckResult(f"pk_unique[{key}]", table, "ok", f"{n_unique}/{n_total} unique")
    return CheckResult(
        f"pk_unique[{key}]", table, "fail",
        f"{n_dupes} duplicate values in {key}", count=n_dupes,
    )


def check_required_not_null(df: pl.DataFrame, table: str, columns: list[str]) -> list[CheckResult]:
    results = []
    for col in columns:
        n_null = df[col].null_count()
        if n_null == 0:
            results.append(CheckResult(f"not_null[{col}]", table, "ok", "no nulls"))
        else:
            results.append(CheckResult(
                f"not_null[{col}]", table, "fail",
                f"{n_null} null values in required column {col}", count=n_null,
            ))
    return results


def check_composite_key_unique(df: pl.DataFrame, table: str, key_columns: list[str]) -> CheckResult:
    n_total = df.height
    n_unique = df.select(key_columns).unique().height
    n_dupes = n_total - n_unique
    label = "+".join(key_columns)
    if n_dupes == 0:
        return CheckResult(f"pk_unique[{label}]", table, "ok", f"{n_unique}/{n_total} unique")
    return CheckResult(
        f"pk_unique[{label}]", table, "fail",
        f"{n_dupes} duplicate ({label}) combinations", count=n_dupes,
    )


def check_no_negative(df: pl.DataFrame, table: str, column: str) -> CheckResult:
    n_negative = (df[column] < 0).sum()
    if n_negative == 0:
        return CheckResult(f"no_negative[{column}]", table, "ok", "no negative values")
    return CheckResult(
        f"no_negative[{column}]", table, "fail",
        f"{n_negative} rows have {column} < 0", count=n_negative,
    )


def check_value_range(df: pl.DataFrame, table: str, column: str, lo: float, hi: float) -> CheckResult:
    n_out = ((df[column] < lo) | (df[column] > hi)).sum()
    if n_out == 0:
        return CheckResult(f"value_range[{column}]", table, "ok", f"all values within [{lo},{hi}]")
    return CheckResult(
        f"value_range[{column}]", table, "fail",
        f"{n_out} rows have {column} outside [{lo},{hi}]", count=n_out,
    )


def check_row_count_min(df: pl.DataFrame, table: str, minimum: int) -> CheckResult:
    if df.height >= minimum:
        return CheckResult("row_count_min", table, "ok", f"{df.height} rows (>= {minimum})")
    return CheckResult(
        "row_count_min", table, "fail",
        f"only {df.height} rows, expected at least {minimum}", count=df.height,
    )


def check_sentinel_zero(df: pl.DataFrame, table: str, column: str) -> CheckResult:
    """Flags columns where 0 is a physically implausible value (e.g. weight,
    height) and therefore likely encodes "unknown" rather than a real
    measurement. Warn, not fail — found in SLS-005, not yet used by any
    spike feature, so no normalization is forced here."""
    n_zero = (df[column] == 0).sum()
    if n_zero == 0:
        return CheckResult(f"sentinel_zero[{column}]", table, "ok", "no zero values")
    return CheckResult(
        f"sentinel_zero[{column}]", table, "warn",
        f"{n_zero} rows have {column} == 0 — likely 'unknown' sentinel, not a real "
        "measurement; do not use for physical-attribute features without resolving this",
        count=n_zero,
    )


def check_dual_null_sentinel(df: pl.DataFrame, table: str, column: str) -> CheckResult:
    """Flags columns where both real null and empty-string "" appear to mean
    'unknown' — found in players.foot during SLS-005. Warn, not fail: the
    two are not yet confirmed equivalent, so this isn't auto-normalized."""
    n_null = df[column].null_count()
    n_empty = (df[column] == "").sum()
    if n_null > 0 and n_empty > 0:
        return CheckResult(
            f"dual_null_sentinel[{column}]", table, "warn",
            f"{column} has both {n_null} real nulls and {n_empty} empty strings — "
            "two distinct 'unknown' encodings in the same column, not normalized",
            count=n_null + n_empty,
        )
    return CheckResult(f"dual_null_sentinel[{column}]", table, "ok", "single null encoding")


def check_coordinate_bounds(events: pl.DataFrame, lo: float = 0, hi: float = 100) -> list[CheckResult]:
    results = []
    for axis in ("x", "y"):
        values = (
            events.select(pl.col("positions").list.eval(pl.element().struct.field(axis)).alias("v"))
            .explode("v", empty_as_null=True)
            .drop_nulls()["v"]
        )
        n_out = ((values < lo) | (values > hi)).sum()
        n_total = values.len()
        if n_out == 0:
            results.append(CheckResult(f"coordinate_bounds[{axis}]", "events", "ok", f"all {n_total} within [{lo},{hi}]"))
        else:
            pct = 100 * n_out / n_total
            results.append(CheckResult(
                f"coordinate_bounds[{axis}]", "events", "warn",
                f"{n_out}/{n_total} ({pct:.6f}%) outside [{lo},{hi}]", count=n_out,
            ))
    return results


def check_mapping_coverage(
    events: pl.DataFrame, mapping: pl.DataFrame, event_col: str, mapping_col: str, label: str
) -> CheckResult:
    used = set(events[event_col].drop_nulls().unique().to_list())
    known = set(mapping[mapping_col].drop_nulls().unique().to_list())
    unmapped = used - known
    if not unmapped:
        return CheckResult(f"mapping_coverage[{label}]", "events", "ok", f"all {len(used)} used values are mapped")
    return CheckResult(
        f"mapping_coverage[{label}]", "events", "fail",
        f"{len(unmapped)} values used in events but missing from mapping: {sorted(unmapped)}",
        count=len(unmapped),
    )


def check_foreign_key(
    child: pl.DataFrame,
    child_col: str,
    parent: pl.DataFrame,
    parent_col: str,
    label: str,
    sentinel_values: tuple = (),
) -> CheckResult:
    """Checks that every non-sentinel value in child[child_col] resolves to
    a value in parent[parent_col]. `sentinel_values` (e.g. `(0,)` for
    events.playerId's "no player" marker) are excluded before comparing —
    they are a documented "not applicable" marker, not an orphan."""
    child_values = child[child_col].drop_nulls()
    if sentinel_values:
        child_values = child_values.filter(~child_values.is_in(list(sentinel_values)))
    child_set = set(child_values.unique().to_list())
    parent_set = set(parent[parent_col].drop_nulls().unique().to_list())
    orphans = child_set - parent_set
    if not orphans:
        return CheckResult(f"foreign_key[{label}]", "relational", "ok", f"all {len(child_set)} values resolve")
    return CheckResult(
        f"foreign_key[{label}]", "relational", "fail",
        f"{len(orphans)} distinct orphaned values, e.g. {sorted(orphans)[:10]}",
        count=len(orphans),
    )


def check_tags_coverage(events: pl.DataFrame, tags2name: pl.DataFrame) -> CheckResult:
    used = set(
        events.explode("tags", empty_as_null=True)
        .select(pl.col("tags").struct.field("id"))
        .drop_nulls()
        .to_series()
        .unique()
        .to_list()
    )
    known = set(tags2name["Tag"].unique().to_list())
    unmapped = used - known
    if not unmapped:
        return CheckResult("mapping_coverage[tags]", "events", "ok", f"all {len(used)} used tag ids are mapped")
    return CheckResult(
        "mapping_coverage[tags]", "events", "fail",
        f"{len(unmapped)} tag ids used in events but missing from tags2name: {sorted(unmapped)}",
        count=len(unmapped),
    )


def run_validation_suite() -> list[CheckResult]:
    competitions = pl.read_parquet(PROCESSED_DIR / "competitions.parquet")
    teams = pl.read_parquet(PROCESSED_DIR / "teams.parquet")
    players = pl.read_parquet(PROCESSED_DIR / "players.parquet")
    matches = pl.read_parquet(PROCESSED_DIR / "matches.parquet")
    events = pl.read_parquet(PROCESSED_DIR / "events.parquet")
    eventid2name = pl.read_parquet(PROCESSED_DIR / "eventid2name.parquet")
    tags2name = pl.read_parquet(PROCESSED_DIR / "tags2name.parquet")

    results: list[CheckResult] = []

    results.append(check_row_count_min(competitions, "competitions", 1))
    results.append(check_primary_key_unique(competitions, "competitions", "wyId"))
    results += check_required_not_null(competitions, "competitions", ["wyId", "name", "type"])

    results.append(check_row_count_min(teams, "teams", 1))
    results.append(check_primary_key_unique(teams, "teams", "wyId"))
    results += check_required_not_null(teams, "teams", ["wyId", "name", "type"])

    results.append(check_row_count_min(players, "players", 1))
    results.append(check_primary_key_unique(players, "players", "wyId"))
    results += check_required_not_null(players, "players", ["wyId", "role", "birthDate"])
    results.append(check_sentinel_zero(players, "players", "weight"))
    results.append(check_sentinel_zero(players, "players", "height"))
    results.append(check_dual_null_sentinel(players, "players", "foot"))

    results.append(check_row_count_min(matches, "matches", 1))
    results.append(check_primary_key_unique(matches, "matches", "wyId"))
    results += check_required_not_null(matches, "matches", ["wyId", "competitionId", "dateutc", "status"])

    results.append(check_row_count_min(events, "events", 1))
    results.append(check_primary_key_unique(events, "events", "id"))
    results += check_required_not_null(events, "events", ["id", "matchId", "teamId", "eventId"])
    results += check_coordinate_bounds(events)
    results.append(check_mapping_coverage(events, eventid2name, "eventId", "event", "event_id"))
    results.append(check_tags_coverage(events, tags2name))

    # SLS-007 — cross-table foreign-key integrity
    results.append(check_foreign_key(events, "matchId", matches, "wyId", "events.matchId -> matches.wyId"))
    results.append(check_foreign_key(events, "teamId", teams, "wyId", "events.teamId -> teams.wyId"))
    results.append(check_foreign_key(
        events, "playerId", players, "wyId", "events.playerId -> players.wyId",
        sentinel_values=(0,),
    ))
    results.append(check_foreign_key(
        matches, "competitionId", competitions, "wyId", "matches.competitionId -> competitions.wyId"
    ))

    minutes_path = PROCESSED_DIR / "minutes.parquet"
    if minutes_path.exists():
        minutes = pl.read_parquet(minutes_path)
        results.append(check_row_count_min(minutes, "minutes", 1))
        results.append(check_composite_key_unique(minutes, "minutes", ["player_id", "match_id"]))
        results.append(check_no_negative(minutes, "minutes", "minutes_played"))
        # 130 = generous stoppage allowance above the 120-minute ExtraTime
        # ceiling used in minutes.py's own derivation guard — this is a
        # defense-in-depth check on the output, independent of that
        # module's internal logic, not a duplicate of it.
        results.append(check_value_range(minutes, "minutes", "minutes_played", 0, 130))
        results.append(check_foreign_key(
            minutes, "player_id", players, "wyId", "minutes.player_id -> players.wyId"
        ))
        results.append(check_foreign_key(
            minutes, "match_id", matches, "wyId", "minutes.match_id -> matches.wyId"
        ))
        results.append(check_foreign_key(
            minutes, "team_id", teams, "wyId", "minutes.team_id -> teams.wyId"
        ))

    return results


def format_report(results: list[CheckResult]) -> str:
    lines = ["| Status | Table | Check | Detail |", "|---|---|---|---|"]
    icon = {"ok": "OK", "warn": "WARN", "fail": "FAIL"}
    for r in results:
        lines.append(f"| {icon[r.status]} | {r.table} | {r.check} | {r.detail} |")
    n_fail = sum(1 for r in results if r.status == "fail")
    n_warn = sum(1 for r in results if r.status == "warn")
    n_ok = sum(1 for r in results if r.status == "ok")
    lines.append("")
    lines.append(f"{n_ok} ok, {n_warn} warn, {n_fail} fail (of {len(results)} checks)")
    return "\n".join(lines)


if __name__ == "__main__":
    print(format_report(run_validation_suite()))
