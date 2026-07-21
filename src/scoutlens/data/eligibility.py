"""Eligible-population sizing (SLS-011).

Each `competitionId` is exactly one season (verified empirically — see
docs/eligible-population.md), so "season minutes" is simply minutes_played
summed per player within a competition. A player who appears in more than
one competition (e.g. a domestic league and a World Cup) gets one row per
competition, not a cross-competition total — the brief's population
analysis is framed per league, and mixing club/international minutes into
one number would misrepresent both.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import polars as pl

REPO_ROOT = Path(__file__).resolve().parents[3]
PROCESSED_DIR = REPO_ROOT / "data" / "processed"

DEFAULT_THRESHOLDS = (450, 900, 1350)


def compute_season_minutes(minutes: pl.DataFrame, matches: pl.DataFrame) -> pl.DataFrame:
    """player_id x competitionId -> total minutes_played that season."""
    match_competition = matches.select(
        pl.col("wyId").alias("match_id"), "competitionId"
    )
    return (
        minutes.join(match_competition, on="match_id", how="left")
        .group_by(["player_id", "competitionId"])
        .agg(
            pl.col("minutes_played").sum().alias("season_minutes"),
            pl.col("match_id").n_unique().alias("matches_appeared"),
        )
    )


@dataclasses.dataclass(frozen=True)
class PopulationReport:
    threshold: int
    total_player_competition_rows: int
    eligible_rows: int
    eligible_distinct_players: int
    eligible_by_competition: dict
    eligible_by_role: dict


def population_at_threshold(
    season_minutes: pl.DataFrame, players: pl.DataFrame, competitions: pl.DataFrame, threshold: int
) -> PopulationReport:
    eligible = season_minutes.filter(pl.col("season_minutes") >= threshold)
    eligible_with_meta = eligible.join(
        players.select(pl.col("wyId").alias("player_id"), pl.col("role").struct.field("name").alias("role_name")),
        on="player_id", how="left",
    ).join(
        competitions.select(pl.col("wyId").alias("competitionId"), pl.col("name").alias("competition_name")),
        on="competitionId", how="left",
    )

    by_competition = dict(
        eligible_with_meta.group_by("competition_name").agg(pl.col("player_id").n_unique().alias("n"))
        .sort("competition_name").iter_rows()
    )
    by_role = dict(
        eligible_with_meta.group_by("role_name").agg(pl.col("player_id").n_unique().alias("n"))
        .sort("role_name").iter_rows()
    )

    return PopulationReport(
        threshold=threshold,
        total_player_competition_rows=season_minutes.height,
        eligible_rows=eligible.height,
        eligible_distinct_players=eligible["player_id"].n_unique(),
        eligible_by_competition=by_competition,
        eligible_by_role=by_role,
    )


if __name__ == "__main__":
    minutes = pl.read_parquet(PROCESSED_DIR / "minutes.parquet")
    matches = pl.read_parquet(PROCESSED_DIR / "matches.parquet")
    players = pl.read_parquet(PROCESSED_DIR / "players.parquet")
    competitions = pl.read_parquet(PROCESSED_DIR / "competitions.parquet")

    season_minutes = compute_season_minutes(minutes, matches)
    season_minutes.write_parquet(PROCESSED_DIR / "season_minutes.parquet")

    print(f"player x competition rows: {season_minutes.height}")
    print(f"distinct players with any minutes: {season_minutes['player_id'].n_unique()}")
    print(f"distinct players in roster (players.parquet): {players.height}")
    print()

    for threshold in DEFAULT_THRESHOLDS:
        report = population_at_threshold(season_minutes, players, competitions, threshold)
        print(f"--- threshold >= {threshold} minutes ---")
        print(f"eligible player x competition rows: {report.eligible_rows}")
        print(f"eligible distinct players (any competition): {report.eligible_distinct_players}")
        print(f"by competition: {report.eligible_by_competition}")
        print(f"by role: {report.eligible_by_role}")
        print()
