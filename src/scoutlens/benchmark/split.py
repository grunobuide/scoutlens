"""Deterministic, role-stratified, player-disjoint train/validation/test split.

The unit is the **human**. Every `(player_id, competitionId, period)` row
for one player lands in exactly one split, so a model can never be fitted
on one half of a person and evaluated on the other.

Determinism does not come from a shuffled RNG. Each player's ordering key
is `sha256(f"{seed}:{player_id}")`, which depends on nothing but the seed
and the id — not on row order, not on how many players are in the
population, not on Polars' sort stability. Re-running on a re-ordered input
gives byte-identical assignments, and adding a player perturbs only its own
position rather than reshuffling everyone.
"""

from __future__ import annotations

import hashlib

import polars as pl

from scoutlens.benchmark.protocol import SPLIT_SEED, TRAIN_FRACTION, VALIDATION_FRACTION

TRAIN = "train"
VALIDATION = "validation"
TEST = "test"
SPLITS = (TRAIN, VALIDATION, TEST)


def ordering_key(player_id: int, seed: int = SPLIT_SEED) -> str:
    """Stable per-player ordering key. Hex digest, compared as a string."""
    return hashlib.sha256(f"{seed}:{player_id}".encode("utf-8")).hexdigest()


def assign_splits(
    players: pl.DataFrame,
    *,
    seed: int = SPLIT_SEED,
    train_fraction: float = TRAIN_FRACTION,
    validation_fraction: float = VALIDATION_FRACTION,
) -> pl.DataFrame:
    """`players` needs `player_id` and `role`, one row per player.

    Returns `player_id`, `role`, `split`. Cuts are taken per role at
    `floor(n * train_fraction)` and `floor(n * (train_fraction +
    validation_fraction))`, so the three splits always partition the role
    exactly and the remainder lands in test.
    """
    duplicated = players.height - players["player_id"].n_unique()
    if duplicated:
        raise ValueError(
            f"assign_splits expects one row per player; found {duplicated} duplicate player_id rows"
        )
    if players["role"].null_count():
        raise ValueError("assign_splits requires a role for every player; found nulls")

    keyed = players.with_columns(
        pl.col("player_id")
        .map_elements(lambda pid: ordering_key(int(pid), seed), return_dtype=pl.String)
        .alias("_order_key")
    )

    frames = []
    for role in sorted(keyed["role"].unique().to_list()):
        role_players = keyed.filter(pl.col("role") == role).sort(["_order_key", "player_id"])
        n = role_players.height
        train_end = int(n * train_fraction)
        validation_end = int(n * (train_fraction + validation_fraction))
        labels = (
            [TRAIN] * train_end
            + [VALIDATION] * (validation_end - train_end)
            + [TEST] * (n - validation_end)
        )
        frames.append(role_players.with_columns(pl.Series("split", labels)))

    return pl.concat(frames).select("player_id", "role", "split").sort("player_id")


def split_counts(assignment: pl.DataFrame) -> dict:
    """Per-split and per-role-per-split player counts, for the manifest."""
    by_split = dict(
        assignment.group_by("split").agg(pl.len().alias("n")).sort("split").iter_rows()
    )
    by_role_split = {
        f"{role}/{split}": n
        for role, split, n in assignment.group_by(["role", "split"])
        .agg(pl.len().alias("n"))
        .sort(["role", "split"])
        .iter_rows()
    }
    return {
        "total_players": assignment.height,
        "by_split": {split: by_split.get(split, 0) for split in SPLITS},
        "by_role_split": by_role_split,
    }


def assignment_digest(assignment: pl.DataFrame) -> str:
    """sha256 over `player_id:split` lines, player-sorted.

    This is the identity of the split itself, independent of how the
    manifest is formatted or which columns it happens to carry.
    """
    digest = hashlib.sha256()
    for player_id, split in (
        assignment.select("player_id", "split").sort("player_id").iter_rows()
    ):
        digest.update(f"{player_id}:{split}\n".encode("utf-8"))
    return digest.hexdigest()


def attach_split(profiles: pl.DataFrame, assignment: pl.DataFrame) -> pl.DataFrame:
    """Join the split label onto profile rows, failing closed if any row
    would come back unlabeled — an unlabeled row is a silent leak, since it
    would otherwise be dropped or default into a pool it does not belong to.
    """
    joined = profiles.join(assignment.select("player_id", "split"), on="player_id", how="left")
    unlabeled = joined.filter(pl.col("split").is_null())
    if unlabeled.height:
        missing = sorted(set(unlabeled["player_id"].to_list()))[:10]
        raise ValueError(
            f"{unlabeled.height} profile rows have no split assignment "
            f"(first player_ids: {missing}); the assignment must cover the "
            "whole evaluated population"
        )
    return joined
