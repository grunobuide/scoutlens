"""Interpretable diagonal metric — the simplest trainable alternative to cosine.

One non-negative weight per feature, and nothing else. The score is

    s(q, c) = sum_i w_i q_i c_i / (sqrt(sum_i w_i q_i^2) sqrt(sum_i w_i c_i^2))

which is exactly cosine similarity in the space scaled by `sqrt(w)`. Two
consequences the rest of this module leans on:

1. **`w = 1` reproduces the frozen Baseline B exactly.** The learned model
   strictly generalizes the incumbent, so "cosine" is a point in the
   hypothesis space rather than a different method. `tests/benchmark`
   asserts the reproduction bit-for-bit.
2. **Ranking needs no new code.** Scaling standardized features by `sqrt(w)`
   and calling the existing `run_baseline_b_retrieval` computes precisely
   this score, so the audited ranking path is reused unchanged.

The score is invariant to a global rescaling of `w` (numerator and
denominator both scale linearly), so weights are normalized to mean 1 after
every step. That makes a weight directly readable as "this feature counts
this many times as much as it would under plain cosine".

Regularization shrinks toward `w = 1`, i.e. toward the incumbent. A large
penalty recovers Baseline B exactly, so the grid interpolates between
"learned" and "the thing we already ship" rather than between "learned" and
an arbitrary origin.
"""

from __future__ import annotations

import hashlib
from typing import Any

import numpy as np
import polars as pl

from scoutlens.showcase.io import canonical_json_bytes

SPEC: dict[str, Any] = {
    "spec_version": 1,
    "bead": "scoutlens-qop.2",
    "model": "diagonal metric over frozen standardized features",
    "score": "cosine in the space scaled by sqrt(w); w=1 is exactly baseline_b_cosine",
    "constraint": "w >= 0, normalized to mean 1 after every step (the score is scale-invariant)",
    "objective": "InfoNCE over (anchor A, positive B, K same-role negatives B)",
    "temperature": 0.05,
    "negatives_per_anchor": 32,
    "negative_sampling": "distinct same-role players, drawn once without replacement, seeded per anchor",
    "negative_seed": 2718,
    "optimizer": "projected full-batch gradient descent, proximal in the penalty",
    "optimizer_note": (
        "the L2 penalty is applied as a proximal step rather than an explicit "
        "gradient step. An explicit step diverges once 2*lr*lambda/n exceeds 1, "
        "which turns a heavy penalty into an oscillation that collapses "
        "weights instead of shrinking them toward the incumbent. The proximal "
        "form is stable for every lambda and has the correct limit w -> 1."
    ),
    "learning_rate": 0.5,
    "iterations": 300,
    "init": "w = 1 (the incumbent)",
    "regularization": "lambda * mean((w - 1)^2), shrinking toward baseline_b_cosine",
    "regularization_grid": [0.0, 0.001, 0.01, 0.1, 1.0, 10.0],
    "selection": "highest within-role MRR on the validation split; ties broken by the larger lambda (simpler model)",
    "selection_note": "test is never consulted for selection",
    "collapse_threshold": 0.05,
    "collapse_threshold_note": "a learned weight below this fraction of mean is reported as collapsed",
    "instability_threshold": 1.0,
    "instability_threshold_note": (
        "a feature whose weight spans more than this across the regularization "
        "grid is reported as not pinned down by the data"
    ),
}
"""Frozen before training. Hashed into every artifact this bead writes.

This is deliberately a *separate* frozen object from
`scoutlens.benchmark.protocol.PROTOCOL`: amending a qop.2 hyperparameter must
not change the qop.1 protocol hash, because that hash is what holds the test
split shut (D041).
"""


def spec_hash() -> str:
    return hashlib.sha256(canonical_json_bytes(SPEC)).hexdigest()


def normalize_weights(weights: np.ndarray) -> np.ndarray:
    """Scale to mean 1. The score is invariant to this, so it is pure
    interpretability: `w_i = 2` reads as "twice the pull of plain cosine"."""
    total = float(weights.sum())
    if total <= 0:
        raise ValueError("weights collapsed to all-zero; cannot normalize")
    return weights * (len(weights) / total)


def sqrt_scaled(frame: pl.DataFrame, feature_columns: list[str], weights: np.ndarray) -> pl.DataFrame:
    """Multiply standardized features by `sqrt(w)`, so plain cosine over the
    result equals the diagonal score. This is what lets the frozen ranking
    path be reused untouched."""
    root = np.sqrt(np.maximum(weights, 0.0))
    return frame.with_columns(
        [(pl.col(column) * float(root[index])).alias(column) for index, column in enumerate(feature_columns)]
    )


def build_training_pairs(
    population_with_split: pl.DataFrame,
    feature_columns: list[str],
    split: str,
    *,
    negatives_per_anchor: int | None = None,
    seed: int | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Anchors (period A), positives (same player, period B) and negatives
    (distinct same-role players, period B).

    Returns `(anchors, positives, negatives)` with shapes `(n, d)`, `(n, d)`
    and `(n, k, d)`. Sampling is drawn once from a seeded generator and never
    resampled, so training is reproducible without depending on iteration
    order.
    """
    negatives_per_anchor = SPEC["negatives_per_anchor"] if negatives_per_anchor is None else negatives_per_anchor
    seed = SPEC["negative_seed"] if seed is None else seed

    rows = population_with_split.filter(pl.col("split") == split)
    queries = rows.filter(pl.col("period") == "A").sort(["player_id", "competitionId"])
    candidates = rows.filter(pl.col("period") == "B").sort(["player_id", "competitionId"])

    candidate_matrix = candidates.select(feature_columns).to_numpy()
    candidate_keys = list(
        zip(candidates["player_id"].to_list(), candidates["competitionId"].to_list())
    )
    key_to_index = {key: index for index, key in enumerate(candidate_keys)}
    candidate_roles = np.asarray(candidates["role"].to_list())

    role_to_indices = {
        role: np.flatnonzero(candidate_roles == role) for role in np.unique(candidate_roles)
    }

    anchors: list[np.ndarray] = []
    positives: list[np.ndarray] = []
    negatives: list[np.ndarray] = []

    anchor_matrix = queries.select(feature_columns).to_numpy()
    generator = np.random.default_rng(seed)

    for row_index, (player_id, competition_id, role) in enumerate(
        zip(queries["player_id"].to_list(), queries["competitionId"].to_list(), queries["role"].to_list())
    ):
        positive_index = key_to_index.get((player_id, competition_id))
        if positive_index is None:
            continue
        pool = role_to_indices[role]
        pool = pool[pool != positive_index]
        if pool.size == 0:
            continue
        take = min(negatives_per_anchor, pool.size)
        chosen = generator.choice(pool, size=take, replace=False)
        if take < negatives_per_anchor:  # pad deterministically by cycling
            chosen = np.resize(chosen, negatives_per_anchor)
        anchors.append(anchor_matrix[row_index])
        positives.append(candidate_matrix[positive_index])
        negatives.append(candidate_matrix[chosen])

    if not anchors:
        raise ValueError(f"no training pairs built for split {split!r}")
    return np.asarray(anchors), np.asarray(positives), np.asarray(negatives)


def _scores_and_grads(
    anchors: np.ndarray, others: np.ndarray, weights: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Diagonal score and d(score)/dw for aligned stacks of vectors.

    `anchors` broadcasts against `others`, so this serves both the positive
    pairs `(n, d)` and the negative stacks `(n, k, d)`.

    d s / d w_i = q_i c_i / sqrt(ab) - (s/2) (q_i^2 / a + c_i^2 / b)
    """
    products = anchors * others
    numerator = np.einsum("...i,i->...", products, weights)
    anchor_sq = anchors**2
    other_sq = others**2
    a = np.einsum("...i,i->...", anchor_sq, weights)
    b = np.einsum("...i,i->...", other_sq, weights)

    denominator = np.sqrt(np.maximum(a * b, 1e-12))
    score = numerator / denominator

    grad = products / denominator[..., None] - 0.5 * score[..., None] * (
        anchor_sq / np.maximum(a, 1e-12)[..., None] + other_sq / np.maximum(b, 1e-12)[..., None]
    )
    return score, grad


def train_diagonal(
    anchors: np.ndarray,
    positives: np.ndarray,
    negatives: np.ndarray,
    *,
    regularization: float,
    iterations: int | None = None,
    learning_rate: float | None = None,
    temperature: float | None = None,
) -> dict[str, Any]:
    """Projected full-batch gradient descent on the InfoNCE objective.

    Deterministic: no shuffling, no dropout, no adaptive state. Same inputs
    and same hyperparameters give bit-identical weights.
    """
    iterations = SPEC["iterations"] if iterations is None else iterations
    learning_rate = SPEC["learning_rate"] if learning_rate is None else learning_rate
    temperature = SPEC["temperature"] if temperature is None else temperature

    n_features = anchors.shape[1]
    weights = np.ones(n_features, dtype=float)
    anchors_expanded = anchors[:, None, :]
    history: list[float] = []

    for _ in range(iterations):
        positive_score, positive_grad = _scores_and_grads(anchors, positives, weights)
        negative_score, negative_grad = _scores_and_grads(anchors_expanded, negatives, weights)

        logits = np.concatenate([positive_score[:, None], negative_score], axis=1) / temperature
        logits -= logits.max(axis=1, keepdims=True)
        exponentiated = np.exp(logits)
        probabilities = exponentiated / exponentiated.sum(axis=1, keepdims=True)

        loss = float(-np.log(np.maximum(probabilities[:, 0], 1e-12)).mean())
        penalty = regularization * float(np.mean((weights - 1.0) ** 2))
        history.append(loss + penalty)

        all_grads = np.concatenate([positive_grad[:, None, :], negative_grad], axis=1)
        weighted = np.einsum("nk,nkd->d", probabilities, all_grads)
        gradient = -(positive_grad.sum(axis=0) - weighted) / (temperature * len(anchors))

        # Data term explicitly, penalty proximally. An explicit penalty step
        # diverges once 2*lr*lambda/n_features > 1; the proximal form is a
        # contraction toward w = 1 for every lambda.
        stepped = weights - learning_rate * gradient
        shrink = 2.0 * learning_rate * regularization / n_features
        stepped = (stepped + shrink) / (1.0 + shrink)

        weights = normalize_weights(np.maximum(stepped, 0.0))

    return {
        "weights": weights,
        "final_objective": history[-1],
        "first_objective": history[0],
        "objective_history": history,
        "regularization": regularization,
        "iterations": iterations,
    }


def weight_stability(
    feature_columns: list[str], weights_by_arm: dict[float, np.ndarray]
) -> list[dict[str, Any]]:
    """How much each feature's weight moves across the regularization grid.

    A feature whose weight swings widely as the penalty changes is not
    pinned down by the data — reporting it as a firm finding would overstate
    what a single fit supports. This is a *stability* statement about the
    fit, not a claim about the feature's meaning.
    """
    arms = sorted(weights_by_arm)
    rows = []
    for index, column in enumerate(feature_columns):
        series = np.array([weights_by_arm[arm][index] for arm in arms], dtype=float)
        spread = float(series.max() - series.min())
        rows.append({
            "feature": column,
            "min_weight": float(series.min()),
            "max_weight": float(series.max()),
            "spread_across_grid": spread,
            "collapsed_in_any_arm": bool((series < SPEC["collapse_threshold"]).any()),
            "collapsed_in_every_arm": bool((series < SPEC["collapse_threshold"]).all()),
            "unstable": bool(spread > SPEC["instability_threshold"]),
        })
    return sorted(rows, key=lambda row: (-row["spread_across_grid"], row["feature"]))


def weight_table(feature_columns: list[str], weights: np.ndarray) -> list[dict[str, Any]]:
    """Per-feature learned weight, ordered by weight descending.

    Deliberately free of quality language: a weight says how much a feature
    moves *this retrieval task* relative to plain cosine. It is not a claim
    about a player, a skill, or how much a feature "matters" in football.
    """
    threshold = SPEC["collapse_threshold"]
    rows = [
        {
            "feature": column,
            "weight": float(weights[index]),
            "relative_to_cosine": float(weights[index]),
            "collapsed": bool(weights[index] < threshold),
        }
        for index, column in enumerate(feature_columns)
    ]
    return sorted(rows, key=lambda row: (-row["weight"], row["feature"]))
