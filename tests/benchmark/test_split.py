"""Acceptance criterion 2, first half: the split is player-disjoint and
deterministic. A player who appears in two splits would let a model be
fitted on one half of a person and scored on the other."""

from __future__ import annotations

import polars as pl
import pytest

from scoutlens.benchmark.split import (
    SPLITS,
    TEST,
    TRAIN,
    VALIDATION,
    assign_splits,
    assignment_digest,
    attach_split,
    ordering_key,
    split_counts,
)

ROLES = ["Defender", "Midfielder", "Forward", "Goalkeeper"]


def _players(n: int = 400) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "player_id": list(range(1, n + 1)),
            "role": [ROLES[i % len(ROLES)] for i in range(n)],
        }
    )


def test_every_player_lands_in_exactly_one_split() -> None:
    assignment = assign_splits(_players())
    counts = assignment.group_by("player_id").agg(pl.len().alias("n"))
    assert counts["n"].max() == 1
    assert set(assignment["split"].unique().to_list()) == set(SPLITS)


def test_splits_are_pairwise_disjoint_on_player_id() -> None:
    assignment = assign_splits(_players())
    members = {
        split: set(assignment.filter(pl.col("split") == split)["player_id"].to_list())
        for split in SPLITS
    }
    assert members[TRAIN] & members[VALIDATION] == set()
    assert members[TRAIN] & members[TEST] == set()
    assert members[VALIDATION] & members[TEST] == set()
    assert len(members[TRAIN] | members[VALIDATION] | members[TEST]) == 400


def test_assignment_is_deterministic_and_order_independent() -> None:
    players = _players()
    first = assign_splits(players)
    shuffled = assign_splits(players.sample(fraction=1.0, shuffle=True, seed=11))
    assert assignment_digest(first) == assignment_digest(shuffled)
    assert first.equals(shuffled)


def test_a_different_seed_produces_a_different_assignment() -> None:
    players = _players()
    assert assignment_digest(assign_splits(players, seed=2718)) != assignment_digest(
        assign_splits(players, seed=2719)
    )


def test_proportions_are_60_20_20_within_every_role() -> None:
    # 400 players / 4 roles = 100 per role, so the cuts are exact
    assignment = assign_splits(_players(400))
    per_role = split_counts(assignment)["by_role_split"]
    for role in ROLES:
        assert per_role[f"{role}/{TRAIN}"] == 60
        assert per_role[f"{role}/{VALIDATION}"] == 20
        assert per_role[f"{role}/{TEST}"] == 20


def test_stratification_holds_when_roles_are_imbalanced() -> None:
    players = pl.DataFrame(
        {
            "player_id": list(range(1, 121)),
            "role": ["Defender"] * 100 + ["Goalkeeper"] * 20,
        }
    )
    per_role = split_counts(assign_splits(players))["by_role_split"]
    assert (per_role["Defender/train"], per_role["Defender/validation"], per_role["Defender/test"]) == (60, 20, 20)
    assert (per_role["Goalkeeper/train"], per_role["Goalkeeper/validation"], per_role["Goalkeeper/test"]) == (12, 4, 4)


def test_ordering_key_depends_only_on_seed_and_player_id() -> None:
    assert ordering_key(42, seed=1) == ordering_key(42, seed=1)
    assert ordering_key(42, seed=1) != ordering_key(42, seed=2)
    assert ordering_key(42, seed=1) != ordering_key(43, seed=1)


def test_duplicate_or_null_input_fails_closed() -> None:
    duplicated = pl.DataFrame({"player_id": [1, 1, 2], "role": ["Defender"] * 3})
    with pytest.raises(ValueError, match="duplicate player_id"):
        assign_splits(duplicated)

    with_null = pl.DataFrame({"player_id": [1, 2], "role": ["Defender", None]})
    with pytest.raises(ValueError, match="role for every player"):
        assign_splits(with_null)


def test_every_profile_row_for_one_player_gets_that_players_split() -> None:
    """The bead's requirement in its own words: every competition-period row
    for one human stays in one split."""
    assignment = assign_splits(_players(40))
    profiles = pl.DataFrame(
        {
            "player_id": [pid for pid in range(1, 41) for _ in range(4)],
            "competitionId": [364, 364, 795, 795] * 40,
            "period": ["A", "B", "A", "B"] * 40,
        }
    )
    joined = attach_split(profiles, assignment)
    per_player = joined.group_by("player_id").agg(pl.col("split").n_unique().alias("n"))
    assert per_player["n"].max() == 1


def test_attach_split_fails_on_an_unassigned_player() -> None:
    assignment = assign_splits(_players(10))
    profiles = pl.DataFrame({"player_id": [1, 2, 999], "competitionId": [364] * 3})
    with pytest.raises(ValueError, match="no split assignment"):
        attach_split(profiles, assignment)
