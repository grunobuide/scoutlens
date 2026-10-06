"""Run Gate 2 of `scoutlens-e87` - once.

    uv run --frozen python -m scoutlens.goalkeeper.run_gate2           # print
    uv run --frozen python -m scoutlens.goalkeeper.run_gate2 --write   # record
    uv run --frozen python -m scoutlens.goalkeeper.run_gate2 --check   # reproduce

The comparison is one-shot by protocol, so `--write` refuses when a result is
already recorded: replacing a recorded outcome is a new protocol version, not a
re-run. `--check` recomputes the same frozen comparison and fails unless it
reproduces the record exactly - reproducibility, not a second look.

The record lives in `docs/goalkeeper-retrieval.md`, between markers, for the
reason `run_audit` gives: `artifacts/` is closed to a modeling bead.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import polars as pl

from scoutlens.evaluation.run_manifest import load_experiment_config
from scoutlens.evaluation.temporal import assign_periods
from scoutlens.goalkeeper import record
from scoutlens.goalkeeper.evaluate import build_arms, compare
from scoutlens.goalkeeper.protocol import protocol_hash
from scoutlens.release.manifest import REPO_ROOT
from scoutlens.showcase.builder import normalize_identity_text

PROCESSED_DIR = REPO_ROOT / "data" / "processed"
RECORD = REPO_ROOT / "docs" / "goalkeeper-retrieval.md"
RESULT_BLOCK = record.markers("gate2-result")
TABLE_BLOCK = record.markers("gate2-table")


def run(processed: Path = PROCESSED_DIR) -> dict:
    config = load_experiment_config()
    leagues = list(config["domestic_leagues"])
    threshold = int(config["primary_minutes_threshold"])

    def read(name: str, columns: list[str] | None = None) -> pl.DataFrame:
        return pl.read_parquet(processed / f"{name}.parquet", columns=columns)

    players = read("players")
    roles = players.select(pl.col("wyId").alias("player_id"), pl.col("role").struct.field("name").alias("role"))
    baseline, candidate = build_arms(
        read("period_profiles"),
        roles,
        read("events", ["eventId", "subEventId", "tags", "playerId", "matchId"]),
        read("minutes"),
        assign_periods(read("matches").filter(pl.col("competitionId").is_in(leagues))),
        threshold,
        leagues,
    )
    result = compare(baseline, candidate)
    names = dict(zip(players["wyId"].to_list(), players["shortName"].to_list(), strict=True))
    for row in result["largest_regressions"]:
        row["name"] = normalize_identity_text(names.get(row["player_id"], str(row["player_id"])))
    result["protocol_sha256"] = protocol_hash()
    result["bead"] = "scoutlens-e87"
    result["gate"] = 2
    return result


def render_markdown(result: dict) -> str:
    """The headline table the evidence document shows."""
    rows = [
        "| Arm | Queries | MRR | Recall@1 | Recall@5 | Recall@10 | Median rank |",
        "|---|---|---|---|---|---|---|",
    ]
    for arm, label in (("baseline", "Baseline B, 32 features"), ("candidate", "32 + goalkeeper family")):
        m = result[arm]
        rows.append(
            f"| {label} | {m['n']} | {m['mrr']:.4f} | {m['recall_at_1']:.3f} | {m['recall_at_5']:.3f} "
            f"| {m['recall_at_10']:.3f} | {m['median_rank']:g} |"
        )
    delta = result["mrr_delta"]
    rows += [
        "",
        f"ΔMRR {delta['point_estimate']:+.4f}, 95% paired-bootstrap interval "
        f"{delta['ci_low']:+.4f} to {delta['ci_high']:+.4f} ({delta['n_resamples']} resamples); "
        f"ΔRecall@10 {result['recall_at_10_delta']:+.3f}. **Decision: {result['decision']}.**",
    ]
    return "\n".join(rows) + "\n"


def recorded_result(path: Path = RECORD) -> dict:
    return record.read_json(path, RESULT_BLOCK)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help=f"record the one run in {RECORD.name}")
    mode.add_argument("--check", action="store_true", help=f"fail unless a fresh run reproduces {RECORD.name}")
    args = parser.parse_args(argv)

    if args.write and recorded_result():
        print(
            f"{RECORD.name} already records a Gate 2 result. The comparison is one-shot: "
            "replacing it is a new protocol version, not a re-run.",
            file=sys.stderr,
        )
        return 1

    started = time.perf_counter()
    result = run()
    elapsed = time.perf_counter() - started
    if args.write:
        record.replace(RECORD, {RESULT_BLOCK: record.json_body(result), TABLE_BLOCK: render_markdown(result)})
        print(f"recorded in {RECORD.relative_to(REPO_ROOT).as_posix()} ({elapsed:.1f}s)")
    elif args.check:
        if recorded_result() != json.loads(json.dumps(result)) or record.read(RECORD, TABLE_BLOCK) != render_markdown(
            result
        ):
            print(f"{RECORD.name} does not match a fresh run", file=sys.stderr)
            return 1
        print(f"{RECORD.name} reproduces ({elapsed:.1f}s)")
    else:
        sys.stdout.write(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
        print(f"({elapsed:.1f}s)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
