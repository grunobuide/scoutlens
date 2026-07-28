"""Frozen public vocabulary for ``scoutlens.showcase/1.0.0``.

Scientific feature order and family ownership come from the research layer.
This module adds presentation metadata once, so neither the exporter nor the
web application has to infer labels or semantics from column names.
"""

from __future__ import annotations

from scoutlens.features.aggregation import FEATURE_COLUMNS, FEATURE_FAMILIES

CONTRACT = "scoutlens.showcase"
SCHEMA_VERSION = "1.0.0"
EXPECTED_PROFILE_COUNT = 1257
FEATURED_PROFILE_KEY = "wy-8287-c-795"
FEATURED_PROFILE_REASON = (
    "Editorially selected recognizable midfielder whose activity spans several feature families; "
    "the choice is not based on retrieval rank or player quality."
)

FEATURE_LABELS: dict[str, tuple[str, str]] = {
    "events_p90": ("Events per 90", "Events"),
    "passes_p90": ("Passes per 90", "Passes"),
    "pass_completion_pct": ("Pass completion", "Pass completion"),
    "crosses_p90": ("Crosses per 90", "Crosses"),
    "long_balls_p90": ("Long balls per 90", "Long balls"),
    "smart_passes_p90": ("Smart passes per 90", "Smart passes"),
    "progressive_pass_distance_p90": ("Progressive pass distance per 90", "Prog. distance"),
    "progressive_passes_p90": ("Progressive passes per 90", "Prog. passes"),
    "assists_p90": ("Assists per 90", "Assists"),
    "key_passes_p90": ("Key passes per 90", "Key passes"),
    "through_balls_p90": ("Through balls per 90", "Through balls"),
    "box_entries_p90": ("Passes into the penalty box per 90", "Box entries"),
    "shots_p90": ("Open-play shots per 90", "Shots"),
    "goals_p90": ("Goals per 90", "Goals"),
    "shot_conversion_pct": ("Shot conversion", "Conversion"),
    "shots_on_target_pct": ("Shots on target share", "On target"),
    "blocked_shot_pct": ("Blocked shot share", "Blocked shots"),
    "interceptions_p90": ("Interceptions per 90", "Interceptions"),
    "sliding_tackles_p90": ("Sliding tackles per 90", "Sliding tackles"),
    "clearances_p90": ("Clearances per 90", "Clearances"),
    "defensive_duel_win_pct": ("Defensive duel win rate", "Def. duel win"),
    "mean_x": ("Mean event x-coordinate", "Mean x"),
    "mean_y": ("Mean event y-coordinate", "Mean y"),
    "defensive_third_share": ("Defensive-third event share", "Def. third"),
    "middle_third_share": ("Middle-third event share", "Middle third"),
    "attacking_third_share": ("Attacking-third event share", "Att. third"),
    "touches_p90": ("Touches per 90", "Touches"),
    "duels_p90": ("Duels per 90", "Duels"),
    "duel_win_pct": ("Duel win rate", "Duel win"),
    "carry_proxy_p90": ("Acceleration carry proxy per 90", "Carry proxy"),
    "carry_distance_proxy_p90": ("Carry-distance proxy per 90", "Carry distance"),
    "take_on_success_pct": ("Take-on success rate", "Take-on success"),
}

RATIO_FEATURES = {
    "pass_completion_pct",
    "shot_conversion_pct",
    "shots_on_target_pct",
    "blocked_shot_pct",
    "defensive_duel_win_pct",
    "duel_win_pct",
    "take_on_success_pct",
}
PITCH_PERCENT_FEATURES = {"mean_x", "mean_y"}
SHARE_FEATURES = {"defensive_third_share", "middle_third_share", "attacking_third_share"}
DISTANCE_FEATURES = {"progressive_pass_distance_p90", "carry_distance_proxy_p90"}
METHOD_REFS = {
    "passing": "docs/feature-definitions.md#1-passing-5-features",
    "progression": "docs/feature-definitions.md#2-progression-2-features",
    "chance_creation": "docs/feature-definitions.md#3-chance-creation-4-features",
    "shooting": "docs/feature-definitions.md#4-shooting-5-features",
    "defensive": "docs/feature-definitions.md#5-defensive-actions-4-features",
    "spatial": "docs/feature-definitions.md#6-spatial-tendencies-5-features",
    "possession": "docs/feature-definitions.md#7-possession--on-ball-involvement-4-features",
    "carrying_proxy": "docs/feature-definitions.md#8-carrying--explicit-proxy-family-3-features",
}

RATIO_SUPPORT_COLUMNS: dict[str, tuple[str, tuple[str, ...]]] = {
    "pass_completion_pct": ("_sum_pass_accurate", ("_sum_pass_accurate", "_sum_pass_not_accurate")),
    "shot_conversion_pct": ("_sum_shot_goal", ("_sum_is_shot",)),
    "shots_on_target_pct": ("_sum_shot_on_target", ("_sum_is_shot",)),
    "blocked_shot_pct": ("_sum_shot_blocked", ("_sum_is_shot",)),
    "defensive_duel_win_pct": ("_sum_def_duel_won", ("_sum_def_duel_decided",)),
    "duel_win_pct": ("_sum_duel_won", ("_sum_duel_decided",)),
    "take_on_success_pct": ("_sum_take_on_success", ("_sum_take_on_attempt",)),
}


def _family_by_feature() -> dict[str, str]:
    result: dict[str, str] = {}
    for family, features in FEATURE_FAMILIES.items():
        for feature_id in features:
            if feature_id in result:
                raise AssertionError(f"feature assigned to multiple families: {feature_id}")
            result[feature_id] = family
    if set(result) != set(FEATURE_COLUMNS):
        raise AssertionError("feature families do not partition the frozen feature catalog")
    return result


def build_feature_catalog() -> list[dict]:
    """Return the 32 public feature definitions in scientific order."""
    family_by_feature = _family_by_feature()
    features: list[dict] = []
    for order, feature_id in enumerate(FEATURE_COLUMNS):
        label, short_label = FEATURE_LABELS[feature_id]
        if feature_id in RATIO_FEATURES or feature_id in SHARE_FEATURES:
            unit = "ratio"
            precision = 3
        elif feature_id in PITCH_PERCENT_FEATURES:
            unit = "pitch_percent"
            precision = 1
        elif feature_id in DISTANCE_FEATURES:
            unit = "distance_per_90"
            precision = 1
        else:
            unit = "per_90"
            precision = 2
        raw_null_meaning = "no_attempts" if feature_id in RATIO_FEATURES else (
            "not_observed" if feature_id in PITCH_PERCENT_FEATURES or feature_id in SHARE_FEATURES else None
        )
        features.append(
            {
                "feature_id": feature_id,
                "label": label,
                "short_label": short_label,
                "family": family_by_feature[feature_id],
                "order": order,
                "description": (
                    f"Descriptive {label.lower()} from the frozen Wyscout event-derived feature definition. "
                    "Higher values are not interpreted as better player quality."
                ),
                "unit": unit,
                "display_precision": precision,
                "raw_null_meaning": raw_null_meaning,
                "model_null_handling": "population_mean_then_z_zero",
                "direction_semantics": "descriptive_not_quality",
                "support_kind": "attempts" if feature_id in RATIO_FEATURES else "minutes",
                "method_ref": METHOD_REFS[family_by_feature[feature_id]],
            }
        )
    return features


FEATURE_CATALOG = build_feature_catalog()
FEATURE_ORDER = {item["feature_id"]: item["order"] for item in FEATURE_CATALOG}
FAMILY_ORDER = {family: index for index, family in enumerate(FEATURE_FAMILIES)}
