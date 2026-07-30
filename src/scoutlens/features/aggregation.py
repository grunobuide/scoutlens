"""Player x period feature aggregation (SLS-014).

`compute_player_features` is agnostic to what "period" means — the caller
passes in events and minutes already scoped to whichever boundary they
want (a full season, a chronological half, a single competition). SLS-015
supplies the actual chronological split; this module doesn't know about
time at all, only about a set of events and each player's minutes within
whatever set was passed in.
"""

from __future__ import annotations

import polars as pl

from scoutlens.features.definitions import add_event_helper_columns

# Columns produced by add_event_helper_columns() that get summed (counts)
# per player. carry_distance is handled separately below since it's a sum
# of fwd_delta filtered to is_acceleration, not a plain column sum.
_SUM_COLUMNS = [
    "is_pass", "pass_accurate", "pass_not_accurate", "is_cross", "is_long_ball",
    "is_smart_pass", "pass_progress_distance", "is_progressive_pass", "has_assist", "has_key_pass",
    "is_through_ball", "is_box_entry", "is_shot", "shot_goal", "scorer_goal",
    "shot_on_target", "shot_blocked", "has_interception", "has_sliding_tackle",
    "is_clearance", "def_duel_won", "def_duel_decided", "is_touch", "is_duel",
    "duel_won", "duel_decided", "is_acceleration", "take_on_attempt", "take_on_success",
]
_MEAN_COLUMNS = ["origin_x", "origin_y", "in_defensive_third", "in_middle_third", "in_attacking_third"]

# The 32 feature names from feature-definitions.md, in the order
# compute_player_features() returns them. Exposed so downstream modules
# (e.g. evaluation/similarity.py) don't have to duplicate this list.
FEATURE_COLUMNS = [
    "events_p90", "passes_p90", "pass_completion_pct", "crosses_p90", "long_balls_p90",
    "smart_passes_p90", "progressive_pass_distance_p90", "progressive_passes_p90",
    "assists_p90", "key_passes_p90", "through_balls_p90", "box_entries_p90",
    "shots_p90", "goals_p90", "shot_conversion_pct", "shots_on_target_pct", "blocked_shot_pct",
    "interceptions_p90", "sliding_tackles_p90", "clearances_p90", "defensive_duel_win_pct",
    "mean_x", "mean_y", "defensive_third_share", "middle_third_share", "attacking_third_share",
    "touches_p90", "duels_p90", "duel_win_pct",
    "carry_proxy_p90", "carry_distance_proxy_p90", "take_on_success_pct",
]

# The same 32 features grouped into the 8 families from
# feature-definitions.md — used for the per-family ablation robustness
# check (robustness-checks.md), not by compute_player_features() itself.
FEATURE_FAMILIES: dict[str, list[str]] = {
    "passing": ["passes_p90", "pass_completion_pct", "crosses_p90", "long_balls_p90", "smart_passes_p90"],
    "progression": ["progressive_pass_distance_p90", "progressive_passes_p90"],
    "chance_creation": ["assists_p90", "key_passes_p90", "through_balls_p90", "box_entries_p90"],
    "shooting": ["shots_p90", "goals_p90", "shot_conversion_pct", "shots_on_target_pct", "blocked_shot_pct"],
    "defensive": ["interceptions_p90", "sliding_tackles_p90", "clearances_p90", "defensive_duel_win_pct"],
    "spatial": ["mean_x", "mean_y", "defensive_third_share", "middle_third_share", "attacking_third_share"],
    "possession": ["events_p90", "touches_p90", "duels_p90", "duel_win_pct"],
    "carrying_proxy": ["carry_proxy_p90", "carry_distance_proxy_p90", "take_on_success_pct"],
}

assert sorted(sum(FEATURE_FAMILIES.values(), [])) == sorted(FEATURE_COLUMNS), (
    "FEATURE_FAMILIES must partition FEATURE_COLUMNS exactly"
)


def _safe_ratio(numerator: pl.Expr, denominator: pl.Expr) -> pl.Expr:
    """Null (not 0) when the denominator is 0 — a player with zero
    attempts has no rate, not a 0% one. See feature-definitions.md."""
    return pl.when(denominator > 0).then(numerator / denominator).otherwise(None)


def _per90(count_col: pl.Expr, minutes_col: pl.Expr) -> pl.Expr:
    """Null (not NaN/inf) when minutes_played is 0. A per-90 rate is
    undefined, not zero, for a player who didn't play — and dividing by 0
    would otherwise silently produce NaN that propagates into any
    downstream similarity computation (SLS-017)."""
    return pl.when(minutes_col > 0).then(count_col / minutes_col * 90).otherwise(None)


def _select_feature_output(result: pl.DataFrame, *, with_counts: bool) -> pl.DataFrame:
    """Derive the frozen 32-feature catalog from additive aggregates.

    Both the ordinary period aggregation and the match-bootstrap path call
    this function. Keeping the formulas in one place prevents the optimized
    weighted path from becoming a second scientific implementation.
    """
    minutes = pl.col("minutes_played")
    result = result.with_columns(
        events_p90=_per90(pl.col("n_events"), minutes),
        passes_p90=_per90(pl.col("_sum_is_pass"), minutes),
        pass_completion_pct=_safe_ratio(
            pl.col("_sum_pass_accurate"), pl.col("_sum_pass_accurate") + pl.col("_sum_pass_not_accurate")
        ),
        crosses_p90=_per90(pl.col("_sum_is_cross"), minutes),
        long_balls_p90=_per90(pl.col("_sum_is_long_ball"), minutes),
        smart_passes_p90=_per90(pl.col("_sum_is_smart_pass"), minutes),
        progressive_pass_distance_p90=_per90(pl.col("_sum_pass_progress_distance"), minutes),
        progressive_passes_p90=_per90(pl.col("_sum_is_progressive_pass"), minutes),
        assists_p90=_per90(pl.col("_sum_has_assist"), minutes),
        key_passes_p90=_per90(pl.col("_sum_has_key_pass"), minutes),
        through_balls_p90=_per90(pl.col("_sum_is_through_ball"), minutes),
        box_entries_p90=_per90(pl.col("_sum_is_box_entry"), minutes),
        shots_p90=_per90(pl.col("_sum_is_shot"), minutes),
        goals_p90=_per90(pl.col("_sum_scorer_goal"), minutes),
        shot_conversion_pct=_safe_ratio(pl.col("_sum_shot_goal"), pl.col("_sum_is_shot")),
        shots_on_target_pct=_safe_ratio(pl.col("_sum_shot_on_target"), pl.col("_sum_is_shot")),
        blocked_shot_pct=_safe_ratio(pl.col("_sum_shot_blocked"), pl.col("_sum_is_shot")),
        interceptions_p90=_per90(pl.col("_sum_has_interception"), minutes),
        sliding_tackles_p90=_per90(pl.col("_sum_has_sliding_tackle"), minutes),
        clearances_p90=_per90(pl.col("_sum_is_clearance"), minutes),
        defensive_duel_win_pct=_safe_ratio(pl.col("_sum_def_duel_won"), pl.col("_sum_def_duel_decided")),
        mean_x=pl.col("_mean_origin_x"),
        mean_y=pl.col("_mean_origin_y"),
        defensive_third_share=pl.col("_mean_in_defensive_third"),
        middle_third_share=pl.col("_mean_in_middle_third"),
        attacking_third_share=pl.col("_mean_in_attacking_third"),
        touches_p90=_per90(pl.col("_sum_is_touch"), minutes),
        duels_p90=_per90(pl.col("_sum_is_duel"), minutes),
        duel_win_pct=_safe_ratio(pl.col("_sum_duel_won"), pl.col("_sum_duel_decided")),
        carry_proxy_p90=_per90(pl.col("_sum_is_acceleration"), minutes),
        carry_distance_proxy_p90=_per90(pl.col("_sum_carry_distance"), minutes),
        take_on_success_pct=_safe_ratio(pl.col("_sum_take_on_success"), pl.col("_sum_take_on_attempt")),
    )
    identity_columns = [
        column
        for column in ("player_id", "competitionId", "period")
        if column in result.columns
    ]
    columns = identity_columns + ["minutes_played"] + FEATURE_COLUMNS
    if with_counts:
        columns += RATIO_COUNT_COLUMNS
    return result.select(columns)


def build_player_match_statistics(events: pl.DataFrame, player_match_minutes: pl.DataFrame) -> pl.DataFrame:
    """Precompute additive feature inputs for each player-match pair.

    The returned rows are sufficient to reproduce every frozen feature under
    integer match multiplicities. Spatial means carry explicit numerators and
    non-null counts so weighted recombination is exactly equivalent to
    duplicating the underlying event rows.
    """
    real_events = events.lazy().filter(pl.col("playerId") != 0)
    enriched = add_event_helper_columns(real_events)
    aggregations = [
        pl.len().alias("n_events"),
        pl.col("fwd_delta").filter(pl.col("is_acceleration")).sum().alias("_sum_carry_distance"),
    ]
    aggregations += [pl.col(column).sum().alias(f"_sum_{column}") for column in _SUM_COLUMNS]
    for column in _MEAN_COLUMNS:
        aggregations.extend(
            [
                pl.col(column).sum().alias(f"_mean_sum_{column}"),
                pl.col(column).count().alias(f"_mean_count_{column}"),
            ]
        )
    per_match = (
        enriched.group_by("matchId", pl.col("playerId").alias("player_id"))
        .agg(aggregations)
        .rename({"matchId": "match_id"})
        .collect(engine="streaming")
    )
    result = player_match_minutes.select("player_id", "match_id", "minutes_played").join(
        per_match, on=["player_id", "match_id"], how="left"
    )
    additive_columns = [
        "n_events",
        "_sum_carry_distance",
        *(f"_sum_{column}" for column in _SUM_COLUMNS),
        *(name for column in _MEAN_COLUMNS for name in (f"_mean_sum_{column}", f"_mean_count_{column}")),
    ]
    return result.with_columns([pl.col(column).fill_null(0) for column in additive_columns])


def compute_weighted_player_features(
    player_match_statistics: pl.DataFrame,
    match_weights: pl.DataFrame,
    *,
    group_columns: list[str] | None = None,
    with_counts: bool = False,
) -> pl.DataFrame:
    """Aggregate player-match statistics under positive integer weights."""
    group_columns = group_columns or []
    if match_weights.select(pl.col("multiplicity").is_null().any()).item():
        raise ValueError("match multiplicities must not be null")
    if match_weights.filter(pl.col("multiplicity") <= 0).height:
        raise ValueError("match multiplicities must be positive")
    if match_weights.select("match_id").n_unique() != match_weights.height:
        raise ValueError("match weights must contain one row per match_id")

    keys = ["player_id", *group_columns]
    weighted = player_match_statistics.join(match_weights, on="match_id", how="inner").sort(
        [*keys, "match_id"]
    )
    aggregations = [
        (pl.col("minutes_played") * pl.col("multiplicity")).sum().alias("minutes_played"),
        (pl.col("n_events") * pl.col("multiplicity")).sum().alias("n_events"),
        (pl.col("_sum_carry_distance") * pl.col("multiplicity")).sum().alias("_sum_carry_distance"),
    ]
    aggregations += [
        (pl.col(f"_sum_{column}") * pl.col("multiplicity")).sum().alias(f"_sum_{column}")
        for column in _SUM_COLUMNS
    ]
    for column in _MEAN_COLUMNS:
        aggregations.extend(
            [
                (pl.col(f"_mean_sum_{column}") * pl.col("multiplicity")).sum().alias(
                    f"_mean_sum_{column}"
                ),
                (pl.col(f"_mean_count_{column}") * pl.col("multiplicity")).sum().alias(
                    f"_mean_count_{column}"
                ),
            ]
        )
    result = weighted.group_by(keys, maintain_order=True).agg(aggregations)
    result = result.with_columns(
        [
            _safe_ratio(pl.col(f"_mean_sum_{column}"), pl.col(f"_mean_count_{column}")).alias(
                f"_mean_{column}"
            )
            for column in _MEAN_COLUMNS
        ]
    )
    return _select_feature_output(result, with_counts=with_counts)


# Numerator/denominator count columns backing each of the 7 ratio
# features — exposed via `with_counts=True` for the shrinkage experiment
# (D024). Names are the `_sum_<col>` aliases produced during aggregation.
RATIO_COUNT_COLUMNS = [
    "_sum_pass_accurate", "_sum_pass_not_accurate",
    "_sum_is_shot", "_sum_shot_goal", "_sum_shot_on_target", "_sum_shot_blocked",
    "_sum_def_duel_won", "_sum_def_duel_decided",
    "_sum_duel_won", "_sum_duel_decided",
    "_sum_take_on_success", "_sum_take_on_attempt",
]


def compute_player_features(
    events: pl.DataFrame, player_minutes: pl.DataFrame, with_counts: bool = False
) -> pl.DataFrame:
    """events: rows already scoped to the period of interest, with the
    usual events.parquet schema (playerId, eventName, subEventName, tags,
    positions, ...).
    player_minutes: one row per player with columns `player_id`,
    `minutes_played`, already summed for the same period — e.g. filter
    minutes.parquet to the period's match ids and group_by(player_id).

    Returns one row per player in player_minutes (players with minutes but
    zero events still appear, with all counts at 0 and ratios at null),
    with `minutes_played` plus all 32 features from feature-definitions.md.
    `with_counts=True` additionally returns `RATIO_COUNT_COLUMNS` (the
    numerator/denominator behind each ratio feature) — used by the ratio-
    shrinkage experiment; the default (False) is byte-for-byte the v0.1
    behavior.
    """
    real_events = events.filter(pl.col("playerId") != 0)
    enriched = add_event_helper_columns(real_events)

    agg_exprs = [
        pl.len().alias("n_events"),
        pl.col("fwd_delta").filter(pl.col("is_acceleration")).sum().alias("_sum_carry_distance"),
    ]
    agg_exprs += [pl.col(c).sum().alias(f"_sum_{c}") for c in _SUM_COLUMNS]
    agg_exprs += [pl.col(c).mean().alias(f"_mean_{c}") for c in _MEAN_COLUMNS]

    per_player = enriched.group_by(pl.col("playerId").alias("player_id")).agg(agg_exprs)

    result = player_minutes.select("player_id", "minutes_played").join(
        per_player, on="player_id", how="left"
    )

    # players with minutes but literally zero events (possible, if rare)
    # get nulls from the left join for every count column — fill with 0
    # so per-90 rates come out as 0, not null.
    count_cols = ["n_events", "_sum_carry_distance"] + [f"_sum_{c}" for c in _SUM_COLUMNS]
    result = result.with_columns([pl.col(c).fill_null(0) for c in count_cols])

    return _select_feature_output(result, with_counts=with_counts)
