"""Tag/subevent constants and per-event helper expressions backing the
feature catalog in docs/feature-definitions.md. Every constant here is
grounded in tag/subevent co-occurrence counts verified against the real
events data during SLS-013 — see that document for the evidence.
"""

from __future__ import annotations

import polars as pl

# Tag ids (see docs/data-dictionary.md / tags2name.parquet)
TAG_GOAL = 101
TAG_ASSIST = 301
TAG_KEY_PASS = 302
TAG_TAKE_ON_L = 503
TAG_TAKE_ON_R = 504
TAG_LOST = 701
TAG_WON = 703
TAG_THROUGH = 901
TAG_GOAL_ZONES = {1201, 1202, 1203, 1204, 1205, 1206, 1207, 1208, 1209}
TAG_INTERCEPTION = 1401
TAG_SLIDING_TACKLE = 1601
TAG_ACCURATE = 1801
TAG_NOT_ACCURATE = 1802
TAG_BLOCKED = 2101

# Stated parameters (not schema-derived — see feature-definitions.md)
PROGRESSIVE_PASS_MIN_DELTA_X = 15
BOX_MIN_X = 84
BOX_MIN_Y = 19
BOX_MAX_Y = 81
THIRD_BOUNDARY_LOW = 33.3
THIRD_BOUNDARY_HIGH = 66.7

# subEventNames (within eventName == "Free Kick") a player can actually
# score from — excludes "Free Kick" itself (indirect, can't score direct),
# "Goal kick" and "Throw in" (can't score direct under the laws of the
# game). "Corner" is included because a direct corner goal, while rare,
# is legal and does occur in this data (3 occurrences — verified).
GOAL_SCORING_SET_PIECES = {"Free kick shot", "Penalty", "Corner"}


def tag_ids(tags_col: pl.Expr = pl.col("tags")) -> pl.Expr:
    return tags_col.list.eval(pl.element().struct.field("id"))


def has_any_tag(tag_id_set: set[int], tags_col: pl.Expr = pl.col("tags")) -> pl.Expr:
    """True if any of the event's tags is in tag_id_set. A single-id set
    checks for one specific tag; a larger set checks membership in a
    group (e.g. TAG_GOAL_ZONES)."""
    return tag_ids(tags_col).list.eval(pl.element().is_in(list(tag_id_set))).list.any()


def origin_x(pos_col: pl.Expr = pl.col("positions")) -> pl.Expr:
    return pos_col.list.get(0, null_on_oob=True).struct.field("x")


def origin_y(pos_col: pl.Expr = pl.col("positions")) -> pl.Expr:
    return pos_col.list.get(0, null_on_oob=True).struct.field("y")


def dest_x(pos_col: pl.Expr = pl.col("positions")) -> pl.Expr:
    return pos_col.list.get(1, null_on_oob=True).struct.field("x")


def dest_y(pos_col: pl.Expr = pl.col("positions")) -> pl.Expr:
    return pos_col.list.get(1, null_on_oob=True).struct.field("y")


def add_event_helper_columns(events: pl.DataFrame) -> pl.DataFrame:
    """Adds the boolean/numeric per-event columns the aggregation groups
    and sums. Kept as a separate, inspectable step rather than inlined
    into one giant group_by().agg() expression."""
    ox, oy, dx, dy = origin_x(), origin_y(), dest_x(), dest_y()
    fwd_delta = (dx - ox).fill_null(0)

    is_pass = pl.col("eventName") == "Pass"
    is_shot = pl.col("eventName") == "Shot"
    is_duel = pl.col("eventName") == "Duel"
    is_att_duel = pl.col("subEventName") == "Ground attacking duel"
    is_def_duel = pl.col("subEventName") == "Ground defending duel"
    has_take_on = has_any_tag({TAG_TAKE_ON_L, TAG_TAKE_ON_R})
    has_won = has_any_tag({TAG_WON})
    has_lost = has_any_tag({TAG_LOST})
    has_goal = has_any_tag({TAG_GOAL})
    # The Goal tag [101] also appears on the *conceding* goalkeeper's
    # "Save attempt" event (5,279 occurrences, 5,274 of them on players
    # with role Goalkeeper — verified) — it marks "a goal happened during
    # this action," not "this player scored." A scorer's own goal is only
    # ever recorded on their Shot event or one of these Free Kick subtypes.
    is_scoring_event = is_shot | pl.col("subEventName").is_in(list(GOAL_SCORING_SET_PIECES))
    scorer_goal = has_goal & is_scoring_event

    return events.with_columns(
        origin_x=ox, origin_y=oy,
        fwd_delta=fwd_delta,
        is_pass=is_pass,
        pass_accurate=is_pass & has_any_tag({TAG_ACCURATE}),
        pass_not_accurate=is_pass & has_any_tag({TAG_NOT_ACCURATE}),
        is_cross=pl.col("subEventName") == "Cross",
        is_long_ball=pl.col("subEventName") == "Launch",
        is_smart_pass=pl.col("subEventName") == "Smart pass",
        is_progressive_pass=is_pass & (fwd_delta >= PROGRESSIVE_PASS_MIN_DELTA_X),
        # Progressive distance is a Pass-only metric, floored at 0 per the
        # spec (a backward pass contributes 0, not a negative number, and
        # non-Pass events with a position delta — e.g. a Duel or
        # Acceleration — must not contribute at all).
        pass_progress_distance=pl.when(is_pass).then(fwd_delta.clip(lower_bound=0)).otherwise(0.0),
        has_assist=has_any_tag({TAG_ASSIST}),
        has_key_pass=has_any_tag({TAG_KEY_PASS}),
        is_through_ball=is_pass & has_any_tag({TAG_THROUGH}),
        is_box_entry=is_pass & (dx >= BOX_MIN_X) & (dy >= BOX_MIN_Y) & (dy <= BOX_MAX_Y),
        is_shot=is_shot,
        shot_goal=is_shot & has_goal,
        scorer_goal=scorer_goal,
        shot_on_target=is_shot & (has_any_tag(TAG_GOAL_ZONES) | has_goal),
        shot_blocked=is_shot & has_any_tag({TAG_BLOCKED}),
        has_interception=has_any_tag({TAG_INTERCEPTION}),
        has_sliding_tackle=has_any_tag({TAG_SLIDING_TACKLE}),
        is_clearance=pl.col("subEventName") == "Clearance",
        is_def_duel=is_def_duel,
        def_duel_won=is_def_duel & has_won,
        def_duel_decided=is_def_duel & (has_won | has_lost),
        is_touch=pl.col("subEventName") == "Touch",
        is_duel=is_duel,
        duel_won=is_duel & has_won,
        duel_decided=is_duel & (has_won | has_lost),
        is_acceleration=pl.col("subEventName") == "Acceleration",
        is_att_duel=is_att_duel,
        take_on_attempt=is_att_duel & has_take_on,
        take_on_success=is_att_duel & has_take_on & has_won,
        in_defensive_third=ox < THIRD_BOUNDARY_LOW,
        in_middle_third=(ox >= THIRD_BOUNDARY_LOW) & (ox < THIRD_BOUNDARY_HIGH),
        in_attacking_third=ox >= THIRD_BOUNDARY_HIGH,
    )
