"""Gate 2 of `scoutlens-e87`, proven on synthetic data before it touches the
real data once.

The comparison is one-shot by protocol: a bug found after the real run would
force a new protocol version. So every part of it is pinned here first, on
data whose right answer is known by construction.
"""

from __future__ import annotations

import random
from pathlib import Path

import polars as pl
import pytest

from scoutlens.evaluation.retrieval import RetrievalMetrics, run_within_role_retrieval_experiment
from scoutlens.features.aggregation import FEATURE_COLUMNS
from scoutlens.goalkeeper import evaluate as gate2
from scoutlens.goalkeeper.protocol import protocol_hash

N_GK = 8
N_OUTFIELD = 8
COMPETITION = 10
MATCH = {"A": 100, "B": 200}


def _profiles(seed: int) -> pl.DataFrame:
    """32 features of pure noise, drawn independently per period: the catalog
    carries no identity for these synthetic players."""
    rng = random.Random(seed)
    rows = []
    for player in range(1, N_GK + N_OUTFIELD + 1):
        for period in ("A", "B"):
            row = {"player_id": player, "competitionId": COMPETITION, "period": period, "minutes_played": 900.0}
            row.update({column: rng.gauss(0, 1) for column in FEATURE_COLUMNS})
            rows.append(row)
    return pl.DataFrame(rows)


def _roles() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "player_id": list(range(1, N_GK + N_OUTFIELD + 1)),
            "role": ["Goalkeeper"] * N_GK + ["Midfielder"] * N_OUTFIELD,
        }
    )


def _event(player: int, period: str, event_id: int, sub_event_id: int, tags: tuple[int, ...] = ()) -> dict:
    return {
        "playerId": player,
        "matchId": MATCH[period],
        "eventId": event_id,
        "subEventId": sub_event_id,
        "tags": [{"id": t} for t in tags],
    }


def _events(*, outfield_saves: int = 0) -> pl.DataFrame:
    """Each goalkeeper gets a distinct, period-stable family signature, so the
    family alone identifies every one of them."""
    rows = []
    for gk in range(1, N_GK + 1):
        for period in ("A", "B"):
            rows += [_event(gk, period, 9, 91, (1801,))] * (10 + 2 * gk)
            rows += [_event(gk, period, 9, 90, (101, 1802))] * 20
            rows += [_event(gk, period, 9, 90, (1801,))] * (gk % 3)
            rows += [_event(gk, period, 4, 40)] * (5 + 3 * gk)
            rows += [_event(gk, period, 8, 81, (1801,))] * (4 * gk)
            rows += [_event(gk, period, 8, 85, (1801,))] * 40
    for outfield in range(N_GK + 1, N_GK + 1 + N_OUTFIELD):
        rows += [_event(outfield, "A", 9, 91, (1801,))] * outfield_saves
    return pl.DataFrame(rows, schema_overrides={"tags": pl.List(pl.Struct({"id": pl.Int64}))})


def _minutes() -> pl.DataFrame:
    return pl.DataFrame(
        [
            {"player_id": p, "match_id": m, "minutes_played": 900}
            for p in range(1, N_GK + N_OUTFIELD + 1)
            for m in MATCH.values()
        ]
    )


def _periods() -> pl.DataFrame:
    return pl.DataFrame(
        {"match_id": list(MATCH.values()), "competitionId": [COMPETITION] * 2, "period": list(MATCH)}
    )


def _arms(seed: int = 0, **events: int) -> tuple[pl.DataFrame, pl.DataFrame]:
    return gate2.build_arms(
        _profiles(seed), _roles(), _events(**events), _minutes(), _periods(), 450, [COMPETITION]
    )


@pytest.fixture()
def unlocked_ledger(tmp_path: Path) -> Path:
    ledger = tmp_path / "decisions-log.md"
    ledger.write_text(f"## D999 — test\n\nprotocol {protocol_hash()}\n", encoding="utf-8")
    return ledger


def test_the_baseline_arm_is_the_published_within_role_ranking() -> None:
    """Not a re-implementation: the goalkeeper ranks are the published run's."""
    baseline, _ = _arms()
    ours = gate2.rank_arm(baseline, FEATURE_COLUMNS)
    published = run_within_role_retrieval_experiment(
        _profiles(0), _roles(), 450, [COMPETITION], n_resamples=10
    )["ranks_b"].filter(pl.col("player_id") <= N_GK)
    assert ours.select("player_id", "competitionId", "rank").sort("player_id").to_dicts() == (
        published.select("player_id", "competitionId", "rank").sort("player_id").to_dicts()
    )


def test_only_goalkeepers_are_queried_or_ranked() -> None:
    baseline, candidate = _arms()
    for arm in (baseline, candidate):
        assert set(arm["role"].to_list()) == {"Goalkeeper"}
        assert arm.height == 2 * N_GK


def test_the_family_is_standardised_on_goalkeepers_only() -> None:
    """An outfield player's events cannot move a goalkeeper's family z-score."""
    _, without = _arms()
    _, with_outfield_saves = _arms(outfield_saves=50)
    assert without.select(gate2.FAMILY_COLUMNS).equals(with_outfield_saves.select(gate2.FAMILY_COLUMNS))


def test_a_family_that_identifies_every_goalkeeper_wins(unlocked_ledger: Path) -> None:
    """Known answer: the family is a perfect, period-stable signature and the
    catalog is noise, so the candidate must rank every goalkeeper first."""
    baseline, candidate = _arms()
    result = gate2.compare(baseline, candidate, decisions_log=unlocked_ledger)
    assert result["queries"] == N_GK
    assert result["candidate"]["recall_at_1"] > result["baseline"]["recall_at_1"]
    assert result["mrr_delta"]["point_estimate"] > 0
    assert sum(result["rank_distribution"]["candidate"].values()) == N_GK


def test_the_comparison_refuses_to_run_off_the_record(tmp_path: Path) -> None:
    ledger = tmp_path / "decisions-log.md"
    ledger.write_text("nothing recorded\n", encoding="utf-8")
    baseline, candidate = _arms()
    with pytest.raises(RuntimeError, match="not recorded"):
        gate2.compare(baseline, candidate, decisions_log=ledger)


def _metrics(recall_at_10: float) -> RetrievalMetrics:
    return RetrievalMetrics(n=97, mrr=0.3, median_rank=3, recall_at_1=0.2, recall_at_5=0.5, recall_at_10=recall_at_10)


@pytest.mark.parametrize(
    ("point", "ci_low", "recall_base", "recall_cand", "expected"),
    [
        (0.020, 0.001, 0.70, 0.70, gate2.KEEP),  # exactly the threshold, equal recall
        (0.0199, 0.001, 0.70, 0.80, gate2.DROP),  # just under the effect size
        (0.050, 0.0, 0.70, 0.80, gate2.DROP),  # interval touches zero
        (0.050, 0.010, 0.70, 0.69, gate2.DROP),  # any Recall@10 drop
        (0.050, 0.010, 0.70, 0.75, gate2.KEEP),
    ],
)
def test_the_decision_rule_is_the_protocols(
    point: float, ci_low: float, recall_base: float, recall_cand: float, expected: str
) -> None:
    delta = {"point_estimate": point, "ci_low": ci_low, "ci_high": point + 0.05}
    assert gate2.decide(_metrics(recall_base), _metrics(recall_cand), delta) == expected
