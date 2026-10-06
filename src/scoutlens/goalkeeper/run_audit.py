"""Run Gate 1 of `scoutlens-e87` on the processed Wyscout data.

    uv run --frozen python -m scoutlens.goalkeeper.run_audit           # print
    uv run --frozen python -m scoutlens.goalkeeper.run_audit --write   # record
    uv run --frozen python -m scoutlens.goalkeeper.run_audit --check   # compare

The recorded result lives in the evidence document,
`docs/goalkeeper-observability.md`, between two pairs of markers: the canonical
JSON of the run, and the support table rendered from it. Not in `artifacts/`:
that directory is ignored by allowlist, and widening the allowlist is outside
what a modeling bead may change (`docs/modeling-agent-contract.md`), so a file
written there would never reach a reviewer or CI. A new evidence document is
allowed, and here it is the record.

`--write` replaces the two marked blocks; `--check` fails unless a fresh run
reproduces them exactly. The JSON carries no timestamp, so a re-run on the same
data is identical. Reads only `data/processed`; computes no retrieval outcome.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import polars as pl

from scoutlens.evaluation.retrieval import select_eligible_both_periods
from scoutlens.evaluation.run_manifest import load_experiment_config
from scoutlens.evaluation.temporal import assign_periods
from scoutlens.goalkeeper import observability as obs
from scoutlens.goalkeeper import record
from scoutlens.goalkeeper.protocol import protocol_hash
from scoutlens.release.manifest import REPO_ROOT

PROCESSED_DIR = REPO_ROOT / "data" / "processed"
RECORD = REPO_ROOT / "docs" / "goalkeeper-observability.md"

RESULT_BLOCK = record.markers("audit-result")
TABLE_BLOCK = record.markers("audit-table")


def eligible_goalkeepers(
    period_profiles: pl.DataFrame, players: pl.DataFrame, minutes_threshold: int, leagues: list[int]
) -> pl.DataFrame:
    """The units Gate 2 would query: eligible in both periods, role Goalkeeper."""
    roles = players.select(pl.col("wyId").alias("player_id"), pl.col("role").struct.field("name").alias("role"))
    eligible = select_eligible_both_periods(period_profiles, minutes_threshold, leagues)
    return (
        eligible.select("player_id", "competitionId")
        .unique()
        .join(roles, on="player_id", how="inner")
        .filter(pl.col("role") == "Goalkeeper")
        .select("player_id", "competitionId")
        .sort("player_id", "competitionId")
    )


def run(processed: Path = PROCESSED_DIR) -> dict:
    config = load_experiment_config()
    leagues = list(config["domestic_leagues"])
    threshold = int(config["primary_minutes_threshold"])

    def read(name: str, columns: list[str] | None = None) -> pl.DataFrame:
        return pl.read_parquet(processed / f"{name}.parquet", columns=columns)

    matches = read("matches").filter(pl.col("competitionId").is_in(leagues))
    period_assignment = assign_periods(matches)
    units = eligible_goalkeepers(read("period_profiles"), read("players"), threshold, leagues)
    events = read("events", ["eventId", "subEventId", "tags", "playerId", "matchId"])
    counts = obs.unit_period_counts(events, read("minutes"), period_assignment, units)
    summary = obs.support_summary(counts)
    return {
        "bead": "scoutlens-e87",
        "gate": 1,
        "population": {
            "competitions": leagues,
            "minutes_threshold_per_period": threshold,
            "eligible_goalkeeper_units": units.height,
            "goalkeeper_unit_periods": counts.height,
        },
        "features": summary,
        "already_in_catalog": [{"feature_id": f, "measures": m} for f, m in obs.ALREADY_IN_CATALOG],
        "unavailable": [{"concept": c, "why": w} for c, w in obs.UNAVAILABLE],
        "schema_checks": obs.schema_checks(counts),
        "gate1": obs.gate1_decision(summary),
        "gate2_protocol_sha256": protocol_hash(),
    }


def render_json(result: dict) -> str:
    return json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def render_markdown(result: dict) -> str:
    """The support table the evidence document shows."""
    lines = [
        "| Feature | Concept | Support basis | Minimum | Supported goalkeeper-periods | Coverage | Support p10 / median | Supported |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in result["features"]:
        lines.append(
            f"| `{row['feature_id']}` | {row['concept']} | `{row['support_basis']}` | {row['minimum']} "
            f"| {row['unit_periods_supported']} of {row['unit_periods']} | {row['coverage']:.1%} "
            f"| {row['support_p10']:g} / {row['support_median']:g} | {'yes' if row['supported'] else 'no'} |"
        )
    return "\n".join(lines) + "\n"


def recorded_result(path: Path = RECORD) -> dict:
    """The run recorded in the evidence document."""
    return record.read_json(path, RESULT_BLOCK)


def recorded_table(path: Path = RECORD) -> str:
    return record.read(path, TABLE_BLOCK)


def write_record(result: dict, path: Path = RECORD) -> None:
    record.replace(path, {RESULT_BLOCK: record.json_body(result), TABLE_BLOCK: render_markdown(result)})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help=f"record the run in {RECORD.name}")
    mode.add_argument("--check", action="store_true", help=f"fail unless a fresh run reproduces {RECORD.name}")
    args = parser.parse_args(argv)

    result = run()
    if args.write:
        write_record(result)
        print(f"recorded in {RECORD.relative_to(REPO_ROOT).as_posix()}")
    elif args.check:
        if recorded_result() != result or recorded_table() != render_markdown(result):
            print(f"{RECORD.name} does not match a fresh run", file=sys.stderr)
            return 1
        print(f"{RECORD.name} reproduces")
    else:
        sys.stdout.write(render_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
