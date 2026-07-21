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
    "is_smart_pass", "fwd_delta", "is_progressive_pass", "has_assist", "has_key_pass",
    "is_through_ball", "is_box_entry", "is_shot", "shot_goal", "any_goal",
    "shot_on_target", "shot_blocked", "has_interception", "has_sliding_tackle",
    "is_clearance", "def_duel_won", "def_duel_decided", "is_touch", "is_duel",
    "duel_won", "duel_decided", "is_acceleration", "take_on_attempt", "take_on_success",
]
_MEAN_COLUMNS = ["origin_x", "origin_y", "in_defensive_third", "in_middle_third", "in_attacking_third"]


def _safe_ratio(numerator: pl.Expr, denominator: pl.Expr) -> pl.Expr:
    """Null (not 0) when the denominator is 0 — a player with zero
    attempts has no rate, not a 0% one. See feature-definitions.md."""
    return pl.when(denominator > 0).then(numerator / denominator).otherwise(None)


def compute_player_features(events: pl.DataFrame, player_minutes: pl.DataFrame) -> pl.DataFrame:
    """events: rows already scoped to the period of interest, with the
    usual events.parquet schema (playerId, eventName, subEventName, tags,
    positions, ...).
    player_minutes: one row per player with columns `player_id`,
    `minutes_played`, already summed for the same period — e.g. filter
    minutes.parquet to the period's match ids and group_by(player_id).

    Returns one row per player in player_minutes (players with minutes but
    zero events still appear, with all counts at 0 and ratios at null),
    with `minutes_played` plus all 32 features from feature-definitions.md.
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

    minutes = pl.col("minutes_played")

    result = result.with_columns(
        events_p90=(pl.col("n_events") / minutes * 90),
        passes_p90=(pl.col("_sum_is_pass") / minutes * 90),
        pass_completion_pct=_safe_ratio(
            pl.col("_sum_pass_accurate"), pl.col("_sum_pass_accurate") + pl.col("_sum_pass_not_accurate")
        ),
        crosses_p90=(pl.col("_sum_is_cross") / minutes * 90),
        long_balls_p90=(pl.col("_sum_is_long_ball") / minutes * 90),
        smart_passes_p90=(pl.col("_sum_is_smart_pass") / minutes * 90),
        progressive_pass_distance_p90=(pl.col("_sum_fwd_delta") / minutes * 90),
        progressive_passes_p90=(pl.col("_sum_is_progressive_pass") / minutes * 90),
        assists_p90=(pl.col("_sum_has_assist") / minutes * 90),
        key_passes_p90=(pl.col("_sum_has_key_pass") / minutes * 90),
        through_balls_p90=(pl.col("_sum_is_through_ball") / minutes * 90),
        box_entries_p90=(pl.col("_sum_is_box_entry") / minutes * 90),
        shots_p90=(pl.col("_sum_is_shot") / minutes * 90),
        goals_p90=(pl.col("_sum_any_goal") / minutes * 90),
        shot_conversion_pct=_safe_ratio(pl.col("_sum_shot_goal"), pl.col("_sum_is_shot")),
        shots_on_target_pct=_safe_ratio(pl.col("_sum_shot_on_target"), pl.col("_sum_is_shot")),
        blocked_shot_pct=_safe_ratio(pl.col("_sum_shot_blocked"), pl.col("_sum_is_shot")),
        interceptions_p90=(pl.col("_sum_has_interception") / minutes * 90),
        sliding_tackles_p90=(pl.col("_sum_has_sliding_tackle") / minutes * 90),
        clearances_p90=(pl.col("_sum_is_clearance") / minutes * 90),
        defensive_duel_win_pct=_safe_ratio(pl.col("_sum_def_duel_won"), pl.col("_sum_def_duel_decided")),
        mean_x=pl.col("_mean_origin_x"),
        mean_y=pl.col("_mean_origin_y"),
        defensive_third_share=pl.col("_mean_in_defensive_third"),
        middle_third_share=pl.col("_mean_in_middle_third"),
        attacking_third_share=pl.col("_mean_in_attacking_third"),
        touches_p90=(pl.col("_sum_is_touch") / minutes * 90),
        duels_p90=(pl.col("_sum_is_duel") / minutes * 90),
        duel_win_pct=_safe_ratio(pl.col("_sum_duel_won"), pl.col("_sum_duel_decided")),
        carry_proxy_p90=(pl.col("_sum_is_acceleration") / minutes * 90),
        carry_distance_proxy_p90=(pl.col("_sum_carry_distance") / minutes * 90),
        take_on_success_pct=_safe_ratio(pl.col("_sum_take_on_success"), pl.col("_sum_take_on_attempt")),
    )

    feature_columns = [
        "player_id", "minutes_played",
        "events_p90", "passes_p90", "pass_completion_pct", "crosses_p90", "long_balls_p90",
        "smart_passes_p90", "progressive_pass_distance_p90", "progressive_passes_p90",
        "assists_p90", "key_passes_p90", "through_balls_p90", "box_entries_p90",
        "shots_p90", "goals_p90", "shot_conversion_pct", "shots_on_target_pct", "blocked_shot_pct",
        "interceptions_p90", "sliding_tackles_p90", "clearances_p90", "defensive_duel_win_pct",
        "mean_x", "mean_y", "defensive_third_share", "middle_third_share", "attacking_third_share",
        "touches_p90", "duels_p90", "duel_win_pct",
        "carry_proxy_p90", "carry_distance_proxy_p90", "take_on_success_pct",
    ]
    return result.select(feature_columns)
