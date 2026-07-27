"""StatsBomb player-period feature aggregation for the external
replication (8mc.3), realizing the canonical shared feature set frozen in
`statsbomb-feature-compatibility.md` (D020).

Two column lists are exported:

- `CANONICAL_FEATURES` (28) — the like-for-like primary set: the 32
  Wyscout features minus `smart_passes_p90` (no StatsBomb equivalent),
  `events_p90` (event-count density not comparable across providers), and
  the two carry features (`carry_proxy_p90`, `carry_distance_proxy_p90`)
  whose construct shifts from a Wyscout `Acceleration` proxy to a
  StatsBomb *native* `Carry` — kept out of the primary comparison so a
  measurement improvement can't be mistaken for a signal difference.
- `CANONICAL_PLUS_CARRY` (30) — the same set with the two native-carry
  features added back, for the sensitivity run.

Coordinates are normalized from StatsBomb's native 120×80 to the Wyscout
0–100 × 0–100 scale (D020 §2) so every threshold in
`feature-definitions.md` applies unchanged. Completion and outcome use
StatsBomb's outcome-by-presence encoding (D020 §6). The per-90 / ratio
null conventions match the Wyscout aggregation exactly.
"""

from __future__ import annotations

import polars as pl

# --- frozen thresholds (D020 reuses feature-definitions.md's, on the 0-100 scale) ---
PROGRESSIVE_MIN_FWD = 15.0          # normalized forward gain for a "progressive" pass
LONG_BALL_MIN_LENGTH = 30.0         # StatsBomb pass length units; "Launch" has no exact subtype (Approx)
BOX_X_MIN = 84.0                    # normalized penalty-box edge
BOX_Y_LO, BOX_Y_HI = 19.0, 81.0

TACKLE_WON = {"Won", "Success In Play", "Success Out"}
TACKLE_LOST = {"Lost In Play", "Lost Out"}
DUEL_WON = {"Won", "Success In Play", "Success Out"}
DUEL_LOST = {"Lost In Play", "Lost Out"}
PASS_FAIL = {"Incomplete", "Out", "Pass Offside"}     # determinate failures; "Unknown"/"Injury Clearance" excluded
SHOT_ON_TARGET = {"Goal", "Saved", "Saved To Post", "Saved Off Target"}

CANONICAL_FEATURES = [
    "passes_p90", "pass_completion_pct", "crosses_p90", "long_balls_p90",
    "progressive_pass_distance_p90", "progressive_passes_p90",
    "assists_p90", "key_passes_p90", "through_balls_p90", "box_entries_p90",
    "shots_p90", "goals_p90", "shot_conversion_pct", "shots_on_target_pct", "blocked_shot_pct",
    "interceptions_p90", "sliding_tackles_p90", "clearances_p90", "defensive_duel_win_pct",
    "mean_x", "mean_y", "defensive_third_share", "middle_third_share", "attacking_third_share",
    "touches_p90", "duels_p90", "duel_win_pct", "take_on_success_pct",
]
NATIVE_CARRY_FEATURES = ["carry_proxy_p90", "carry_distance_proxy_p90"]
CANONICAL_PLUS_CARRY = CANONICAL_FEATURES + NATIVE_CARRY_FEATURES

assert len(CANONICAL_FEATURES) == 28
assert len(CANONICAL_PLUS_CARRY) == 30


def _per90(count_col: pl.Expr, minutes_col: pl.Expr) -> pl.Expr:
    return pl.when(minutes_col > 0).then(count_col / minutes_col * 90).otherwise(None)


def _safe_ratio(num: pl.Expr, den: pl.Expr) -> pl.Expr:
    return pl.when(den > 0).then(num / den).otherwise(None)


def add_helper_columns(events: pl.DataFrame) -> pl.DataFrame:
    """Row-level derived flags/quantities, mirroring the Wyscout
    aggregation's approach but reading StatsBomb's flat event schema
    (`scoutlens.statsbomb.ingestion.EVENTS_SCHEMA`). Coordinates are
    normalized to 0-100 here so every downstream threshold matches
    feature-definitions.md."""
    x = pl.col("location_x") / 120.0 * 100.0
    y = pl.col("location_y") / 80.0 * 100.0
    ex = pl.col("end_location_x") / 120.0 * 100.0
    ey = pl.col("end_location_y") / 80.0 * 100.0
    is_pass = pl.col("type_name") == "Pass"
    is_shot = (pl.col("type_name") == "Shot") & (pl.col("shot_type_name") == "Open Play")
    is_duel = pl.col("type_name") == "Duel"
    is_tackle = is_duel & (pl.col("duel_type_name") == "Tackle")
    fwd = (ex - x)
    return events.with_columns(
        _x=x, _y=y,
        _is_pass=is_pass.cast(pl.Int64),
        _pass_complete=(is_pass & pl.col("pass_outcome_name").is_null()).cast(pl.Int64),
        _pass_failed=(is_pass & pl.col("pass_outcome_name").is_in(list(PASS_FAIL))).cast(pl.Int64),
        _is_cross=(is_pass & pl.col("pass_cross")).cast(pl.Int64),
        _is_long_ball=(is_pass & (pl.col("pass_height_name") == "High Pass")
                       & (pl.col("pass_length") >= LONG_BALL_MIN_LENGTH)).cast(pl.Int64),
        _pass_fwd=pl.when(is_pass).then(pl.max_horizontal(fwd, pl.lit(0.0))).otherwise(0.0),
        _is_prog_pass=(is_pass & (fwd >= PROGRESSIVE_MIN_FWD)).cast(pl.Int64),
        _is_assist=(is_pass & pl.col("pass_goal_assist")).cast(pl.Int64),
        _is_key_pass=(is_pass & pl.col("pass_shot_assist")).cast(pl.Int64),
        _is_through=(is_pass & pl.col("pass_through_ball")).cast(pl.Int64),
        _is_box_entry=(is_pass & (ex >= BOX_X_MIN) & (ey >= BOX_Y_LO) & (ey <= BOX_Y_HI)).cast(pl.Int64),
        _is_shot=is_shot.cast(pl.Int64),
        _shot_goal=(is_shot & (pl.col("shot_outcome_name") == "Goal")).cast(pl.Int64),
        _shot_on_target=(is_shot & pl.col("shot_outcome_name").is_in(list(SHOT_ON_TARGET))).cast(pl.Int64),
        _shot_blocked=(is_shot & (pl.col("shot_outcome_name") == "Blocked")).cast(pl.Int64),
        _is_interception=(pl.col("type_name") == "Interception").cast(pl.Int64),
        _is_tackle=is_tackle.cast(pl.Int64),
        _tackle_won=(is_tackle & pl.col("duel_outcome_name").is_in(list(TACKLE_WON))).cast(pl.Int64),
        _tackle_decided=(is_tackle & pl.col("duel_outcome_name").is_in(list(TACKLE_WON | TACKLE_LOST))).cast(pl.Int64),
        _is_clearance=(pl.col("type_name") == "Clearance").cast(pl.Int64),
        _in_def_third=pl.when(pl.col("location_x").is_not_null()).then((x < 100 / 3).cast(pl.Int64)).otherwise(None),
        _in_mid_third=pl.when(pl.col("location_x").is_not_null()).then(((x >= 100 / 3) & (x < 200 / 3)).cast(pl.Int64)).otherwise(None),
        _in_att_third=pl.when(pl.col("location_x").is_not_null()).then((x >= 200 / 3).cast(pl.Int64)).otherwise(None),
        _is_touch=(pl.col("type_name") == "Ball Receipt*").cast(pl.Int64),
        _is_duel=is_duel.cast(pl.Int64),
        _duel_won=(is_duel & pl.col("duel_outcome_name").is_in(list(DUEL_WON))).cast(pl.Int64),
        _duel_decided=(is_duel & (pl.col("duel_outcome_name").is_in(list(DUEL_WON | DUEL_LOST))
                                  | (pl.col("duel_type_name") == "Aerial Lost"))).cast(pl.Int64),
        _is_carry=(pl.col("type_name") == "Carry").cast(pl.Int64),
        _carry_dist=pl.when(pl.col("type_name") == "Carry").then(pl.max_horizontal(fwd, pl.lit(0.0))).otherwise(0.0),
        _is_dribble=(pl.col("type_name") == "Dribble").cast(pl.Int64),
        _dribble_complete=((pl.col("type_name") == "Dribble") & (pl.col("dribble_outcome_name") == "Complete")).cast(pl.Int64),
    )


def compute_player_features(events: pl.DataFrame, player_minutes: pl.DataFrame) -> pl.DataFrame:
    """One row per player in `player_minutes` with `minutes_played` plus the
    30 features (`CANONICAL_PLUS_CARRY`). Players with minutes but zero
    events appear with 0 counts / null ratios, exactly like the Wyscout
    aggregation, so the eligibility filter behaves identically."""
    enriched = add_helper_columns(events.filter(pl.col("player_id").is_not_null()))
    sum_cols = [c for c in enriched.columns if c.startswith("_") and c not in ("_x", "_y")
                and not c.startswith("_in_") and not c.startswith("_mean")]
    agg = [pl.len().alias("n_events")]
    agg += [pl.col(c).sum().alias(f"s{c}") for c in sum_cols]
    agg += [pl.col(c).mean().alias(f"m{c}") for c in ("_x", "_y", "_in_def_third", "_in_mid_third", "_in_att_third")]
    per_player = enriched.group_by(pl.col("player_id")).agg(agg)

    result = player_minutes.select("player_id", "minutes_played").join(per_player, on="player_id", how="left")
    count_cols = [f"s{c}" for c in sum_cols]
    result = result.with_columns([pl.col(c).fill_null(0) for c in count_cols])
    m = pl.col("minutes_played")

    return result.with_columns(
        passes_p90=_per90(pl.col("s_is_pass"), m),
        pass_completion_pct=_safe_ratio(pl.col("s_pass_complete"), pl.col("s_pass_complete") + pl.col("s_pass_failed")),
        crosses_p90=_per90(pl.col("s_is_cross"), m),
        long_balls_p90=_per90(pl.col("s_is_long_ball"), m),
        progressive_pass_distance_p90=_per90(pl.col("s_pass_fwd"), m),
        progressive_passes_p90=_per90(pl.col("s_is_prog_pass"), m),
        assists_p90=_per90(pl.col("s_is_assist"), m),
        key_passes_p90=_per90(pl.col("s_is_key_pass"), m),
        through_balls_p90=_per90(pl.col("s_is_through"), m),
        box_entries_p90=_per90(pl.col("s_is_box_entry"), m),
        shots_p90=_per90(pl.col("s_is_shot"), m),
        goals_p90=_per90(pl.col("s_shot_goal"), m),
        shot_conversion_pct=_safe_ratio(pl.col("s_shot_goal"), pl.col("s_is_shot")),
        shots_on_target_pct=_safe_ratio(pl.col("s_shot_on_target"), pl.col("s_is_shot")),
        blocked_shot_pct=_safe_ratio(pl.col("s_shot_blocked"), pl.col("s_is_shot")),
        interceptions_p90=_per90(pl.col("s_is_interception"), m),
        sliding_tackles_p90=_per90(pl.col("s_is_tackle"), m),
        clearances_p90=_per90(pl.col("s_is_clearance"), m),
        defensive_duel_win_pct=_safe_ratio(pl.col("s_tackle_won"), pl.col("s_tackle_decided")),
        mean_x=pl.col("m_x"), mean_y=pl.col("m_y"),
        defensive_third_share=pl.col("m_in_def_third"),
        middle_third_share=pl.col("m_in_mid_third"),
        attacking_third_share=pl.col("m_in_att_third"),
        touches_p90=_per90(pl.col("s_is_touch"), m),
        duels_p90=_per90(pl.col("s_is_duel"), m),
        duel_win_pct=_safe_ratio(pl.col("s_duel_won"), pl.col("s_duel_decided")),
        take_on_success_pct=_safe_ratio(pl.col("s_dribble_complete"), pl.col("s_is_dribble")),
        carry_proxy_p90=_per90(pl.col("s_is_carry"), m),
        carry_distance_proxy_p90=_per90(pl.col("s_carry_dist"), m),
    ).select(["player_id", "minutes_played"] + CANONICAL_PLUS_CARRY)
