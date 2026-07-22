"""Context/minutes diagnostics (SLS-020).

Checks whether Baseline B's retrieval signal is genuinely about playing
style, or is substantially explained by confounds it would be easy to
mistake for role signal: same-team continuity (a player's teammates tend
to share tactical patterns) or same-league conventions (a league's
overall style could make any two players from it look more alike than
they are). Also builds the minimum-minutes -> population -> stability
curve flagged as a required sensitivity check in D006.
"""

from __future__ import annotations

import polars as pl


def compute_primary_team(minutes: pl.DataFrame, period_assignment: pl.DataFrame) -> pl.DataFrame:
    """player_id x competitionId x period -> the team_id the player
    accumulated the most minutes for in that period (ties broken by the
    lower team_id). A player transferred mid-period will have minutes
    split across teams; this picks the dominant one rather than modeling
    multi-team periods, consistent with the spike's 80/20 scope."""
    with_period = minutes.join(period_assignment, on="match_id", how="inner")
    team_minutes = with_period.group_by(["player_id", "competitionId", "period", "team_id"]).agg(
        pl.col("minutes_played").sum().alias("team_minutes")
    )
    return (
        team_minutes.sort(["team_minutes", "team_id"], descending=[True, False])
        .group_by(["player_id", "competitionId", "period"])
        .agg(pl.col("team_id").first())
    )


def neighbor_concentration(
    top_k_neighbors: pl.DataFrame,
    query_attribute: pl.DataFrame,
    neighbor_attribute: pl.DataFrame,
    attribute_name: str,
) -> float:
    """Fraction of (query, neighbor) pairs in `top_k_neighbors` where the
    neighbor shares the query's value of `attribute_name` (e.g. team_id).

    `query_attribute`/`neighbor_attribute`: `player_id` -> `attribute_name`,
    each pre-filtered by the caller to the relevant period (queries are
    always period A, neighbors always period B — see
    `compute_primary_team`). Keyed by `player_id` alone: the eligible
    domestic-league population essentially never has one player active in
    two different domestic leagues in the same season, so this doesn't
    need `competitionId` disambiguation in practice.
    """
    joined = top_k_neighbors.join(
        query_attribute.rename({"player_id": "query_player_id", attribute_name: "query_attr"}),
        on="query_player_id", how="left",
    ).join(
        neighbor_attribute.rename({"player_id": "neighbor_player_id", attribute_name: "neighbor_attr"}),
        on="neighbor_player_id", how="left",
    )
    matches = joined.filter(pl.col("query_attr") == pl.col("neighbor_attr")).height
    return matches / joined.height if joined.height else 0.0
