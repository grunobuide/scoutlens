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


def identify_transferred_players(eligible: pl.DataFrame, primary_team: pl.DataFrame) -> pl.DataFrame:
    """Of the `(player_id, competitionId)` pairs present in `eligible`
    (typically `select_eligible_both_periods`'s output), returns the ones
    whose primary team (see `compute_primary_team`) differs between period
    A and period B — the population D010/robustness-checks.md's
    team-continuity finding says the retrieval experiment should be
    re-run on directly, since Baseline C's team-based advantage
    structurally cannot apply to them.

    Returns `player_id`, `competitionId`, `team_a`, `team_b`, sorted by
    `(player_id, competitionId)` — join output row order isn't
    deterministic in Polars, and this table is exported verbatim into a
    versioned artifact (`transferred_pairs`), where a run-to-run order
    shuffle would read as spurious drift."""
    pairs = eligible.select("player_id", "competitionId").unique()
    team_a = primary_team.filter(pl.col("period") == "A").select(
        "player_id", "competitionId", pl.col("team_id").alias("team_a")
    )
    team_b = primary_team.filter(pl.col("period") == "B").select(
        "player_id", "competitionId", pl.col("team_id").alias("team_b")
    )
    merged = pairs.join(team_a, on=["player_id", "competitionId"], how="left").join(
        team_b, on=["player_id", "competitionId"], how="left"
    )
    return merged.filter(pl.col("team_a") != pl.col("team_b")).sort(["player_id", "competitionId"])


def neighbor_concentration(
    top_k_neighbors: pl.DataFrame,
    query_attribute: pl.DataFrame,
    neighbor_attribute: pl.DataFrame,
    attribute_name: str,
    include_true_matches: bool = False,
) -> float:
    """Fraction of (query, neighbor) pairs in `top_k_neighbors` where the
    neighbor shares the query's value of `attribute_name` (e.g. team_id).

    By default (`include_true_matches=False`), rows where the "neighbor"
    is actually the query's own correctly-retrieved period-B profile
    (`top_k_neighbors.is_true_match`, from `get_top_k_neighbors`) are
    excluded first. A player's team essentially never changes within a
    single season split, so a correct retrieval trivially "shares the
    query's team" — counting it would measure retrieval *success*, not a
    confound, and inflate the apparent team/league effect. Pass
    `include_true_matches=True` only if `top_k_neighbors` has no
    `is_true_match` column (older data) or the inflated figure is wanted
    deliberately for comparison.

    `query_attribute`/`neighbor_attribute`: `player_id` -> `attribute_name`,
    each pre-filtered by the caller to the relevant period (queries are
    always period A, neighbors always period B). **Must have at most one
    row per `player_id`** — raises `ValueError` otherwise, rather than
    silently joining into a duplicate-row explosion. This bites in
    practice, not just in theory: `compute_primary_team` runs over every
    competition including Euro/World Cup, so a player who also appears
    for their national team gets a second row there (28.7% of this
    project's eligible population, in fact) unless the caller filters to
    the relevant competition set first — found by exactly this failure
    mode inflating a published number, see decisions-log.md.
    """
    for label, attribute_df in (("query_attribute", query_attribute), ("neighbor_attribute", neighbor_attribute)):
        n_dupes = attribute_df.height - attribute_df["player_id"].n_unique()
        if n_dupes:
            raise ValueError(
                f"{label} has {n_dupes} duplicate player_id rows — did you forget to filter "
                "to a single competition set (e.g. domestic leagues only) before selecting "
                "player_id + attribute? A duplicated player_id silently inflates this join."
            )

    if not include_true_matches and "is_true_match" in top_k_neighbors.columns:
        top_k_neighbors = top_k_neighbors.filter(~pl.col("is_true_match"))

    joined = top_k_neighbors.join(
        query_attribute.rename({"player_id": "query_player_id", attribute_name: "query_attr"}),
        on="query_player_id", how="left",
    ).join(
        neighbor_attribute.rename({"player_id": "neighbor_player_id", attribute_name: "neighbor_attr"}),
        on="neighbor_player_id", how="left",
    )
    matches = joined.filter(pl.col("query_attr") == pl.col("neighbor_attr")).height
    return matches / joined.height if joined.height else 0.0
