"""Deterministic chronological split (SLS-015) and per-period feature
profiles for the Temporal Role Stability Experiment.

Splits each competition's matches into two chronological halves — never
splitting an individual match's events across periods, per the brief.
Reuses `compute_player_features` (SLS-014) unchanged for each period; this
module's only job is scoping events/minutes to a `(competitionId, period)`
group before calling it.

Per D007 (decisions-log.md), profiles are keyed on
`player_id x competitionId x period`, not just `player_id x period` — a
player who appears in both a domestic league and an international
tournament must not collide into a single retrieval target.
"""

from __future__ import annotations

import polars as pl

from scoutlens.features.aggregation import compute_player_features

PERIOD_A = "A"
PERIOD_B = "B"


def assign_periods(matches: pl.DataFrame) -> pl.DataFrame:
    """One row per match: `match_id`, `competitionId`, `period` ("A"/"B").

    Within each competition, matches are sorted by `dateutc` (lexically
    sortable — confirmed `YYYY-MM-DD hh:mm:ss` format, see
    data-dictionary.md), with `wyId` as an explicit tiebreak, and split by
    match count at the midpoint: the first half chronologically is period
    A, the rest is period B. A competition with an odd match count gives
    the extra match to B.

    The `wyId` tiebreak matters in practice, not just in theory: European
    Championship 2016 has two matches sharing the exact same `dateutc`
    straddling its split boundary. Relying on `dateutc` alone would leave
    which of the two lands in A vs. B dependent on incoming row order /
    sort-stability details rather than a value actually in the data —
    `wyId` makes the split reproducible regardless.
    """
    parts = []
    for competition_id in sorted(matches["competitionId"].unique().to_list()):
        comp_matches = matches.filter(pl.col("competitionId") == competition_id).sort(["dateutc", "wyId"])
        n = comp_matches.height
        split_idx = n // 2
        periods = [PERIOD_A] * split_idx + [PERIOD_B] * (n - split_idx)
        parts.append(
            comp_matches.select(pl.col("wyId").alias("match_id"), "competitionId").with_columns(
                pl.Series("period", periods)
            )
        )
    return pl.concat(parts)


def build_period_profiles(
    events: pl.DataFrame, minutes: pl.DataFrame, period_assignment: pl.DataFrame
) -> pl.DataFrame:
    """One row per `(player_id, competitionId, period)` with `minutes_played`
    plus all 32 features from feature-definitions.md, computed only from
    that period's matches.

    `minutes` is the full player x match minutes table (minutes.parquet
    shape) — this function does the period-scoped
    filter-then-group_by(player_id).sum() itself, so callers don't have to
    pre-aggregate.
    """
    frames = []
    groups = (
        period_assignment.select("competitionId", "period").unique().sort(["competitionId", "period"])
    )
    for competition_id, period in groups.iter_rows():
        match_ids = period_assignment.filter(
            (pl.col("competitionId") == competition_id) & (pl.col("period") == period)
        )["match_id"].to_list()

        period_events = events.filter(pl.col("matchId").is_in(match_ids))
        period_minutes = (
            minutes.filter(pl.col("match_id").is_in(match_ids))
            .group_by("player_id")
            .agg(pl.col("minutes_played").sum())
        )

        features = compute_player_features(period_events, period_minutes)
        features = features.with_columns(
            pl.lit(competition_id).alias("competitionId"), pl.lit(period).alias("period")
        )
        frames.append(features)

    combined = pl.concat(frames)
    id_cols = ["player_id", "competitionId", "period"]
    return combined.select(id_cols + [c for c in combined.columns if c not in id_cols])
