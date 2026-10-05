"""Gate 1 of `scoutlens-e87`: can the event schema observe goalkeeping?

The gate is fixed before anything is measured, so it cannot be fitted to what
the data happens to show:

- a goalkeeper behaviour counts only if a field of the provider's event schema
  records it **directly** - an event type, a subtype or a tag - with an
  auditable denominator. Inferring it from coordinates, timing or a fitted
  model is proxying, and the bead's non-goals exclude it;
- a candidate feature counts only if enough eligible goalkeeper-periods have
  the support to estimate it (`MIN_COVERAGE` of them at the minimum below);
- GO needs supported features in at least `MIN_DISTINCT_CONCEPTS` distinct
  concepts. Two features of one concept are one concept.

Two otherwise-qualifying measurements are deliberately not candidates because
the frozen catalog already has them (`ALREADY_IN_CATALOG`): a goalkeeper
family that re-counted `Launch` would only re-weight an existing feature.

Everything here is a count or a ratio of counts. Nothing is fitted.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast

import polars as pl

# Event and tag identifiers, from data/raw/eventid2name.csv and tags2name.csv.
EVENT_LEAVING_LINE = 4
EVENT_PASS = 8
EVENT_SAVE_ATTEMPT = 9
SUBEVENT_GOAL_KICK = 34
SUBEVENT_HAND_PASS = 81
SUBEVENT_REFLEXES = 90
TAG_ACCURATE = 1801
TAG_NOT_ACCURATE = 1802

#: A proportion is estimated for a goalkeeper-period only from at least this
#: many denominator events; below it the value is null (and is mean-imputed to
#: z = 0 downstream, the catalog's rule for "never came up").
MIN_PROPORTION_DENOMINATOR = 20
#: A per-90 rate's denominator is minutes, which eligibility already holds at
#: 450 or more per period. What can be missing is the behaviour itself, so a
#: rate counts as supported for a goalkeeper-period with at least this many
#: numerator events.
MIN_RATE_NUMERATOR = 5
#: Share of eligible goalkeeper-periods that must meet the minimum above.
MIN_COVERAGE = 0.90
#: Distinct supported concepts needed for GO.
MIN_DISTINCT_CONCEPTS = 3

GO = "GO"
NO_GO = "NO_GO_OBSERVABILITY"


@dataclass(frozen=True)
class Feature:
    feature_id: str
    concept: str
    kind: Literal["proportion", "rate_p90"]
    numerator: str
    denominator: str
    numerator_column: str
    denominator_column: str


FEATURES: tuple[Feature, ...] = (
    Feature(
        "gk_save_pct",
        "shot_stopping",
        "proportion",
        "Save attempt (eventId 9) tagged accurate [1801]",
        "Save attempt (eventId 9) tagged accurate [1801] or not accurate [1802]",
        "saves_accurate",
        "saves_tagged",
    ),
    Feature(
        "gk_reflex_save_share",
        "shot_stopping",
        "proportion",
        "Save attempt of subtype Reflexes (subEventId 90)",
        "Save attempt (eventId 9)",
        "reflex_saves",
        "save_attempts",
    ),
    Feature(
        "gk_leaving_line_p90",
        "sweeping",
        "rate_p90",
        "Goalkeeper leaving line (eventId 4)",
        "minutes played, per 90",
        "leaving_line",
        "minutes_played",
    ),
    Feature(
        "gk_hand_pass_share",
        "distribution_mode",
        "proportion",
        "Pass of subtype Hand pass (subEventId 81)",
        "Pass (eventId 8)",
        "hand_passes",
        "passes",
    ),
)

#: Directly observed, and already in the frozen 32-feature catalog.
ALREADY_IN_CATALOG: tuple[tuple[str, str], ...] = (
    ("long_balls_p90", "Pass subtype Launch (subEventId 84) per 90 - long distribution"),
    ("pass_completion_pct", "Pass tagged accurate / accurate or not accurate - distribution accuracy"),
)

#: Goalkeeping concepts the schema does not record directly, and why.
UNAVAILABLE: tuple[tuple[str, str], ...] = (
    (
        "positioning at the moment of a shot",
        "event positions locate the acting player's event only; nothing records where the "
        "goalkeeper stood when the shot was struck",
    ),
    (
        "shot quality faced, post-shot xG, goals prevented",
        "the schema has no expected-goals or shot-quality field; building one is a model, "
        "which the bead's non-goals exclude as proxying",
    ),
    (
        "claiming and punching crosses, aerial command",
        "there is no claim or punch event; 'Goalkeeper leaving line' does not distinguish a "
        "claim, a punch, a smother or a sweep",
    ),
    (
        "one-on-one outcomes",
        "no field marks a one-on-one; deriving one from attacker and goalkeeper coordinates "
        "and timing would be inference",
    ),
    (
        "goal-kick accuracy",
        "Goal kick (subEventId 34) carries no accurate / not-accurate tag - counted by the "
        "audit as goal_kicks_tagged",
    ),
    (
        "penalty saving",
        "no field links a save attempt to the penalty it faced; pairing by time would be "
        "inference, and the support per goalkeeper-period would be a handful of events",
    ),
    (
        "distribution under pressure, communication, organisation",
        "the schema records no pressure, no off-ball organisation and no communication",
    ),
)

COUNT_COLUMNS: tuple[str, ...] = (
    "save_attempts",
    "saves_accurate",
    "saves_not_accurate",
    "saves_tagged",
    "saves_untagged",
    "saves_double_tagged",
    "reflex_saves",
    "leaving_line",
    "passes",
    "hand_passes",
    "goal_kicks",
    "goal_kicks_tagged",
)


def unit_period_counts(
    events: pl.DataFrame,
    minutes: pl.DataFrame,
    period_assignment: pl.DataFrame,
    units: pl.DataFrame,
) -> pl.DataFrame:
    """One row per `(player_id, competitionId, period)` for every unit in
    `units` and both periods, with minutes and every count the gate reads.

    `events` has the events.parquet shape, `minutes` the minutes.parquet shape,
    `period_assignment` the `temporal.assign_periods` shape and `units` one row
    per eligible `(player_id, competitionId)`. Events are scoped exactly as the
    catalog scopes them: the unit's own events, in that competition's matches
    of that period. A goalkeeper-period with no events still appears, with
    zero counts, so absence is measured rather than dropped.
    """
    periods = period_assignment.select(
        pl.col("match_id").alias("matchId"), "competitionId", "period"
    )
    scoped = events.join(periods, on="matchId", how="inner").join(
        units.select(pl.col("player_id").alias("playerId"), "competitionId"),
        on=["playerId", "competitionId"],
        how="inner",
    )
    tags = pl.col("tags").list.eval(pl.element().struct.field("id")).fill_null([])
    scoped = scoped.with_columns(
        tags.list.contains(TAG_ACCURATE).alias("_acc"),
        tags.list.contains(TAG_NOT_ACCURATE).alias("_not_acc"),
    )
    save = pl.col("eventId") == EVENT_SAVE_ATTEMPT
    goal_kick = pl.col("subEventId") == SUBEVENT_GOAL_KICK
    counted = scoped.group_by(
        pl.col("playerId").alias("player_id"), "competitionId", "period"
    ).agg(
        save.sum().alias("save_attempts"),
        (save & pl.col("_acc")).sum().alias("saves_accurate"),
        (save & pl.col("_not_acc")).sum().alias("saves_not_accurate"),
        (save & (pl.col("_acc") | pl.col("_not_acc"))).sum().alias("saves_tagged"),
        (save & ~pl.col("_acc") & ~pl.col("_not_acc")).sum().alias("saves_untagged"),
        (save & pl.col("_acc") & pl.col("_not_acc")).sum().alias("saves_double_tagged"),
        (pl.col("subEventId") == SUBEVENT_REFLEXES).sum().alias("reflex_saves"),
        (pl.col("eventId") == EVENT_LEAVING_LINE).sum().alias("leaving_line"),
        (pl.col("eventId") == EVENT_PASS).sum().alias("passes"),
        (pl.col("subEventId") == SUBEVENT_HAND_PASS).sum().alias("hand_passes"),
        goal_kick.sum().alias("goal_kicks"),
        (goal_kick & (pl.col("_acc") | pl.col("_not_acc"))).sum().alias("goal_kicks_tagged"),
    )
    played = (
        minutes.join(period_assignment, on="match_id", how="inner")
        .group_by("player_id", "competitionId", "period")
        .agg(pl.col("minutes_played").sum())
    )
    grid = units.select("player_id", "competitionId").join(
        pl.DataFrame({"period": ["A", "B"]}), how="cross"
    )
    keys = ["player_id", "competitionId", "period"]
    out = (
        grid.join(played, on=keys, how="left")
        .join(counted, on=keys, how="left")
        .with_columns(
            pl.col("minutes_played").fill_null(0),
            *[pl.col(c).fill_null(0).cast(pl.Int64) for c in COUNT_COLUMNS],
        )
    )
    return out.select(keys + ["minutes_played", *COUNT_COLUMNS]).sort(keys)


def feature_values(counts: pl.DataFrame) -> pl.DataFrame:
    """The family's values per goalkeeper-period, under the frozen null rule.

    A proportion is null below `MIN_PROPORTION_DENOMINATOR` denominator
    events; a per-90 rate is null only without minutes.
    """
    exprs = []
    for feature in FEATURES:
        num = pl.col(feature.numerator_column).cast(pl.Float64)
        den = pl.col(feature.denominator_column).cast(pl.Float64)
        if feature.kind == "proportion":
            value = pl.when(den >= MIN_PROPORTION_DENOMINATOR).then(num / den)
        else:
            value = pl.when(den > 0).then(num * 90.0 / den)
        exprs.append(value.otherwise(None).alias(feature.feature_id))
    return counts.select("player_id", "competitionId", "period", *exprs)


def _supported(feature: Feature) -> pl.Expr:
    if feature.kind == "proportion":
        return pl.col(feature.denominator_column) >= MIN_PROPORTION_DENOMINATOR
    return pl.col(feature.numerator_column) >= MIN_RATE_NUMERATOR


def support_summary(counts: pl.DataFrame) -> list[dict]:
    """Per feature: how many goalkeeper-periods can estimate it, and the
    support distribution behind that, in the units the minimum is stated in."""
    rows = []
    for feature in FEATURES:
        basis = feature.denominator_column if feature.kind == "proportion" else feature.numerator_column
        support = counts[basis].cast(pl.Float64)
        covered = int(counts.select(_supported(feature).sum()).item())
        rows.append(
            {
                "feature_id": feature.feature_id,
                "concept": feature.concept,
                "kind": feature.kind,
                "support_basis": basis,
                "minimum": MIN_PROPORTION_DENOMINATOR if feature.kind == "proportion" else MIN_RATE_NUMERATOR,
                "unit_periods": counts.height,
                "unit_periods_supported": covered,
                "coverage": round(covered / counts.height, 4) if counts.height else 0.0,
                "support_min": int(cast(float, support.min() or 0)),
                "support_p10": float(cast(float, support.quantile(0.10, "nearest") or 0)),
                "support_median": float(cast(float, support.median() or 0)),
                "numerator_total": int(cast(float, counts[feature.numerator_column].sum())),
                "denominator_total": float(cast(float, counts[feature.denominator_column].sum())),
                "supported": counts.height > 0 and covered / counts.height >= MIN_COVERAGE,
            }
        )
    return rows


def schema_checks(counts: pl.DataFrame) -> dict[str, int]:
    """What the gate assumes about the schema, counted rather than assumed.

    `saves_untagged` and `saves_double_tagged` must be zero for `gk_save_pct`
    to be a partition of save attempts. `goal_kicks_tagged` documents why
    goal-kick accuracy is listed as unavailable.
    """
    return {
        column: int(counts[column].sum())
        for column in ("save_attempts", "saves_untagged", "saves_double_tagged", "goal_kicks", "goal_kicks_tagged")
    }


def gate1_decision(summary: list[dict]) -> dict:
    """GO when supported features span `MIN_DISTINCT_CONCEPTS` concepts."""
    concepts = sorted({row["concept"] for row in summary if row["supported"]})
    return {
        "decision": GO if len(concepts) >= MIN_DISTINCT_CONCEPTS else NO_GO,
        "supported_concepts": concepts,
        "supported_features": [row["feature_id"] for row in summary if row["supported"]],
        "min_distinct_concepts": MIN_DISTINCT_CONCEPTS,
    }
