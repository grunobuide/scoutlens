"""Gate 1 of `scoutlens-e87` on synthetic events, so every rule is pinned
without the provider data CI does not have.

AC3 asks for formulas, denominators, null behaviour and minimum support to be
"covered by synthetic tests": each of those is a test below, built from event
rows whose correct answer can be counted by hand.
"""

from __future__ import annotations

import polars as pl
import pytest

from scoutlens.goalkeeper import observability as obs

GK = 1
OTHER = 2


def _event(player: int, match: int, event_id: int, sub_event_id: int, tags: tuple[int, ...] = ()) -> dict:
    return {
        "playerId": player,
        "matchId": match,
        "eventId": event_id,
        "subEventId": sub_event_id,
        "tags": [{"id": tag} for tag in tags],
    }


def _counts(events: list[dict], minutes: list[dict]) -> pl.DataFrame:
    # Competition 10: matches 100 (A) and 200 (B). Competition 20: match 300 (A).
    periods = pl.DataFrame(
        {"match_id": [100, 200, 300], "competitionId": [10, 10, 20], "period": ["A", "B", "A"]}
    )
    units = pl.DataFrame({"player_id": [GK], "competitionId": [10]})
    return obs.unit_period_counts(
        pl.DataFrame(events, schema_overrides={"tags": pl.List(pl.Struct({"id": pl.Int64}))}),
        pl.DataFrame(minutes),
        periods,
        units,
    )


@pytest.fixture()
def counts() -> pl.DataFrame:
    events = [
        # Period A, the goalkeeper's own events.
        _event(GK, 100, 9, 91, (1801,)),  # save, accurate
        _event(GK, 100, 9, 90, (1801, 1203)),  # reflex save, accurate, goal-mouth zone tag
        _event(GK, 100, 9, 90, (101, 1802)),  # reflex, conceded
        _event(GK, 100, 4, 40),  # leaving line
        _event(GK, 100, 4, 40, (1901,)),  # leaving line, counter-attack tag
        _event(GK, 100, 8, 81, (1801,)),  # hand pass
        _event(GK, 100, 8, 84, (1802,)),  # launch
        _event(GK, 100, 8, 85, (1801,)),  # simple pass
        _event(GK, 100, 3, 34),  # goal kick, no accuracy tag
        # Another player in the same match is never counted for the goalkeeper.
        _event(OTHER, 100, 9, 91, (1801,)),
        # The same goalkeeper in another competition's match is out of scope.
        _event(GK, 300, 9, 91, (1801,)),
    ]
    minutes = [
        {"player_id": GK, "match_id": 100, "minutes_played": 90},
        {"player_id": GK, "match_id": 200, "minutes_played": 45},
        {"player_id": GK, "match_id": 300, "minutes_played": 90},
    ]
    return _counts(events, minutes)


def test_counts_are_scoped_to_the_unit_its_competition_and_its_period(counts: pl.DataFrame) -> None:
    a = counts.filter(pl.col("period") == "A").to_dicts()[0]
    assert a["minutes_played"] == 90  # match 300 belongs to competition 20
    assert a["save_attempts"] == 3  # not OTHER's, not match 300's
    assert (a["saves_accurate"], a["saves_not_accurate"], a["saves_tagged"]) == (2, 1, 3)
    assert a["reflex_saves"] == 2
    assert a["leaving_line"] == 2
    assert (a["passes"], a["hand_passes"]) == (3, 1)
    assert (a["goal_kicks"], a["goal_kicks_tagged"]) == (1, 0)


def test_a_period_with_no_events_is_measured_as_zero_not_dropped(counts: pl.DataFrame) -> None:
    b = counts.filter(pl.col("period") == "B").to_dicts()[0]
    assert b["minutes_played"] == 45
    assert all(b[column] == 0 for column in obs.COUNT_COLUMNS)


def test_the_partition_check_counts_what_the_save_formula_assumes() -> None:
    events = [
        _event(GK, 100, 9, 91, ()),  # untagged
        _event(GK, 100, 9, 91, (1801, 1802)),  # both
        _event(GK, 100, 9, 91, (1801,)),
    ]
    counts = _counts(events, [{"player_id": GK, "match_id": 100, "minutes_played": 90}])
    checks = obs.schema_checks(counts)
    assert (checks["save_attempts"], checks["saves_untagged"], checks["saves_double_tagged"]) == (3, 1, 1)


def _row(**values: int) -> dict:
    row = {"player_id": GK, "competitionId": 10, "period": "A", "minutes_played": 900}
    row.update({column: 0 for column in obs.COUNT_COLUMNS})
    row.update(values)
    return row


def test_a_proportion_needs_its_minimum_denominator() -> None:
    below = obs.MIN_PROPORTION_DENOMINATOR - 1
    frame = pl.DataFrame(
        [
            _row(saves_accurate=below, saves_tagged=below, save_attempts=below),
            _row(saves_accurate=15, saves_tagged=20, save_attempts=20, reflex_saves=5),
        ]
    )
    values = obs.feature_values(frame)["gk_save_pct"].to_list()
    assert values[0] is None  # below the minimum: null, never an estimate from 19 events
    assert values[1] == pytest.approx(0.75)
    assert obs.feature_values(frame)["gk_reflex_save_share"].to_list()[1] == pytest.approx(0.25)


def test_a_rate_is_per_90_and_null_only_without_minutes() -> None:
    frame = pl.DataFrame([_row(leaving_line=6, minutes_played=540), _row(leaving_line=6, minutes_played=0)])
    values = obs.feature_values(frame)["gk_leaving_line_p90"].to_list()
    assert values[0] == pytest.approx(1.0)
    assert values[1] is None


def test_hand_pass_share_is_hand_passes_over_all_passes() -> None:
    frame = pl.DataFrame([_row(passes=40, hand_passes=10)])
    assert obs.feature_values(frame)["gk_hand_pass_share"].item() == pytest.approx(0.25)


def _population(n: int, *, supported: int, **values: int) -> pl.DataFrame:
    """n goalkeeper-periods, the first `supported` meeting every minimum."""
    good = _row(save_attempts=30, saves_tagged=30, saves_accurate=20, leaving_line=10, passes=100, hand_passes=30)
    rows = [good if i < supported else _row(**values) for i in range(n)]
    return pl.DataFrame(rows)


def test_coverage_is_judged_against_the_frozen_threshold() -> None:
    n = 100
    at = int(obs.MIN_COVERAGE * n)
    summary = {row["feature_id"]: row for row in obs.support_summary(_population(n, supported=at))}
    assert summary["gk_save_pct"]["coverage"] == obs.MIN_COVERAGE
    assert summary["gk_save_pct"]["supported"]

    summary = {row["feature_id"]: row for row in obs.support_summary(_population(n, supported=at - 1))}
    assert not summary["gk_save_pct"]["supported"]


def test_two_features_of_one_concept_count_once() -> None:
    # Shot-stopping and sweeping supported; distribution never reaches its minimum.
    rows = [
        _row(save_attempts=30, saves_tagged=30, saves_accurate=20, leaving_line=10, passes=5, hand_passes=1)
        for _ in range(10)
    ]
    decision = obs.gate1_decision(obs.support_summary(pl.DataFrame(rows)))
    assert decision["supported_features"] == ["gk_save_pct", "gk_reflex_save_share", "gk_leaving_line_p90"]
    assert decision["supported_concepts"] == ["shot_stopping", "sweeping"]
    assert decision["decision"] == obs.NO_GO


def test_three_distinct_supported_concepts_is_go() -> None:
    decision = obs.gate1_decision(obs.support_summary(_population(10, supported=10)))
    assert decision["supported_concepts"] == ["distribution_mode", "shot_stopping", "sweeping"]
    assert decision["decision"] == obs.GO


def test_no_candidate_re_counts_a_catalog_feature() -> None:
    """A family that re-counted `Launch` would only re-weight long_balls_p90."""
    from scoutlens.features.aggregation import FEATURE_COLUMNS

    family = {feature.feature_id for feature in obs.FEATURES}
    assert not family & set(FEATURE_COLUMNS)
    assert {name for name, _ in obs.ALREADY_IN_CATALOG} <= set(FEATURE_COLUMNS)
