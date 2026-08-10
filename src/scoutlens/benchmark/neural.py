"""Compact neural contrastive projection — the conditional arm (`scoutlens-qop.3`).

Runs only because `scoutlens-qop.2` recorded `CONTINUE_NEURAL` (D042). One
frozen architecture family: a single-hidden-layer MLP projecting the 28
standardized features to a small embedding, scored by cosine.

    z = W2 · tanh(W1 x + b1) + b2
    s(q, c) = <z_q, z_c> / (||z_q|| ||z_c||)

Written in numpy with analytic gradients rather than pulling in a deep
learning framework. The bead asks for "one compact neural contrastive
representation" and names no dependency; the modeling contract (D040) makes
`pyproject.toml` Conditional on the bead justifying one. A ~2 GB dependency
for a two-layer network on 753 training rows would not be justifiable, and
hand-written gradients keep the run bit-for-bit deterministic. The gradient
is checked against a numerical one in the test suite.

Nothing here is adopted. Weights are exported for evaluation only.
"""

from __future__ import annotations

import hashlib
from typing import Any

import numpy as np

from scoutlens.showcase.io import canonical_json_bytes

SPEC: dict[str, Any] = {
    "spec_version": 1,
    "bead": "scoutlens-qop.3",
    "conditional_on": "scoutlens-qop.2 recording CONTINUE_NEURAL (D042)",
    "architecture_family": "single-hidden-layer MLP projection, cosine on the embedding",
    "depth": 1,
    "depth_note": "fixed, not searched",
    "activation": "tanh",
    "hidden_width_grid": [32, 64],
    "embedding_dim_grid": [16, 32],
    "search_limit": (
        "4 configurations, declared before training. No architecture search "
        "beyond this grid, no foundation models, no provider-specific tuning."
    ),
    "objective": "InfoNCE over the same positives and same-role hard negatives as qop.2",
    "temperature": 0.05,
    "negatives_per_anchor": 32,
    "negative_seed": 2718,
    "optimizer": "full-batch gradient descent with momentum",
    "learning_rate": 0.05,
    "momentum": 0.9,
    "max_epochs": 400,
    "init": "scaled uniform, seeded per configuration",
    "init_seed": 2718,
    "early_stopping": {
        "monitor": "validation within-role MRR",
        "evaluate_every_epochs": 25,
        "patience_evaluations": 3,
        "restore": "the checkpoint with the best monitored value",
        "note": "validation only; test is never consulted during training or selection",
    },
    "selection": "highest validation within-role MRR across the 4 configurations",
    "test_policy": "one final evaluation of the selected checkpoint; no retraining afterwards",
}


def spec_hash() -> str:
    return hashlib.sha256(canonical_json_bytes(SPEC)).hexdigest()


Params = dict[str, np.ndarray]


def init_params(n_features: int, hidden: int, embedding: int, seed: int) -> Params:
    """Deterministic scaled-uniform init. Seeded per configuration so two
    runs of the same configuration start from identical weights."""
    generator = np.random.default_rng(seed)
    limit1 = float(np.sqrt(6.0 / (n_features + hidden)))
    limit2 = float(np.sqrt(6.0 / (hidden + embedding)))
    return {
        "W1": generator.uniform(-limit1, limit1, size=(n_features, hidden)),
        "b1": np.zeros(hidden),
        "W2": generator.uniform(-limit2, limit2, size=(hidden, embedding)),
        "b2": np.zeros(embedding),
    }


def forward(x: np.ndarray, params: Params) -> tuple[np.ndarray, np.ndarray]:
    """Returns `(hidden_activations, embedding)`. `x` may carry leading batch
    dimensions; only the last axis is the feature axis."""
    hidden = np.tanh(x @ params["W1"] + params["b1"])
    return hidden, hidden @ params["W2"] + params["b2"]


def embed(x: np.ndarray, params: Params) -> np.ndarray:
    return forward(x, params)[1]


def _mlp_backward(
    x: np.ndarray, hidden: np.ndarray, d_embedding: np.ndarray, params: Params
) -> Params:
    """Backprop one stack of vectors through the shared MLP.

    Flattens leading batch dimensions so anchors `(n, d)` and negative stacks
    `(n, k, d)` take the same path.
    """
    flat_x = x.reshape(-1, x.shape[-1])
    flat_hidden = hidden.reshape(-1, hidden.shape[-1])
    flat_grad = d_embedding.reshape(-1, d_embedding.shape[-1])

    grad_w2 = flat_hidden.T @ flat_grad
    grad_b2 = flat_grad.sum(axis=0)
    d_hidden = flat_grad @ params["W2"].T
    d_pre = d_hidden * (1.0 - flat_hidden**2)
    grad_w1 = flat_x.T @ d_pre
    grad_b1 = d_pre.sum(axis=0)
    return {"W1": grad_w1, "b1": grad_b1, "W2": grad_w2, "b2": grad_b2}


def _normalize(z: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    norm = np.sqrt(np.maximum((z**2).sum(axis=-1, keepdims=True), 1e-12))
    return z / norm, norm


def loss_and_grads(
    anchors: np.ndarray,
    positives: np.ndarray,
    negatives: np.ndarray,
    params: Params,
    temperature: float,
) -> tuple[float, Params]:
    """InfoNCE loss and its gradient with respect to every parameter.

    d/da of <a_hat, c_hat> is (c_hat - s * a_hat) / ||a||, and symmetrically
    for c. The anchor appears in all K+1 pairs, so its embedding gradient
    accumulates across the positive and every negative.
    """
    n_anchors = anchors.shape[0]
    hidden_a, za = forward(anchors, params)
    hidden_p, zp = forward(positives, params)
    hidden_n, zn = forward(negatives, params)

    za_hat, za_norm = _normalize(za)
    zp_hat, zp_norm = _normalize(zp)
    zn_hat, zn_norm = _normalize(zn)

    score_p = (za_hat * zp_hat).sum(axis=-1)
    score_n = np.einsum("nd,nkd->nk", za_hat, zn_hat)

    logits = np.concatenate([score_p[:, None], score_n], axis=1) / temperature
    logits -= logits.max(axis=1, keepdims=True)
    exponentiated = np.exp(logits)
    probabilities = exponentiated / exponentiated.sum(axis=1, keepdims=True)
    loss = float(-np.log(np.maximum(probabilities[:, 0], 1e-12)).mean())

    d_score_p = (probabilities[:, 0] - 1.0) / (n_anchors * temperature)
    d_score_n = probabilities[:, 1:] / (n_anchors * temperature)

    # positive pair
    d_za = d_score_p[:, None] * (zp_hat - score_p[:, None] * za_hat) / za_norm
    d_zp = d_score_p[:, None] * (za_hat - score_p[:, None] * zp_hat) / zp_norm

    # negative pairs: accumulate onto the anchor, one row each onto negatives
    d_za += (
        d_score_n[:, :, None] * (zn_hat - score_n[:, :, None] * za_hat[:, None, :])
    ).sum(axis=1) / za_norm
    d_zn = (
        d_score_n[:, :, None] * (za_hat[:, None, :] - score_n[:, :, None] * zn_hat) / zn_norm
    )

    grads_a = _mlp_backward(anchors, hidden_a, d_za, params)
    grads_p = _mlp_backward(positives, hidden_p, d_zp, params)
    grads_n = _mlp_backward(negatives, hidden_n, d_zn, params)
    grads = {key: grads_a[key] + grads_p[key] + grads_n[key] for key in grads_a}
    return loss, grads


def train_neural(
    anchors: np.ndarray,
    positives: np.ndarray,
    negatives: np.ndarray,
    *,
    hidden: int,
    embedding: int,
    evaluate: Any,
    seed: int | None = None,
    max_epochs: int | None = None,
    learning_rate: float | None = None,
    momentum: float | None = None,
    temperature: float | None = None,
    evaluate_every: int | None = None,
    patience: int | None = None,
) -> dict[str, Any]:
    """Train one configuration with early stopping on a validation callable.

    `evaluate(params) -> float` is the monitored quantity (validation
    within-role MRR). It is called only on validation; the test split is never
    consulted here, which is what keeps acceptance criterion 7 true by
    construction rather than by discipline.
    """
    seed = SPEC["init_seed"] if seed is None else seed
    max_epochs = SPEC["max_epochs"] if max_epochs is None else max_epochs
    learning_rate = SPEC["learning_rate"] if learning_rate is None else learning_rate
    momentum = SPEC["momentum"] if momentum is None else momentum
    temperature = SPEC["temperature"] if temperature is None else temperature
    evaluate_every = (
        SPEC["early_stopping"]["evaluate_every_epochs"] if evaluate_every is None else evaluate_every
    )
    patience = (
        SPEC["early_stopping"]["patience_evaluations"] if patience is None else patience
    )

    params = init_params(anchors.shape[1], hidden, embedding, seed)
    velocity = {key: np.zeros_like(value) for key, value in params.items()}

    curve: list[dict[str, float]] = []
    best_score = -np.inf
    best_params: Params = {key: value.copy() for key, value in params.items()}
    best_epoch = 0
    since_improvement = 0

    for epoch in range(1, max_epochs + 1):
        loss, grads = loss_and_grads(anchors, positives, negatives, params, temperature)
        for key in params:
            velocity[key] = momentum * velocity[key] - learning_rate * grads[key]
            params[key] = params[key] + velocity[key]

        if epoch % evaluate_every == 0 or epoch == max_epochs:
            score = float(evaluate(params))
            curve.append({"epoch": epoch, "loss": loss, "validation_mrr": score})
            if score > best_score:
                best_score = score
                best_params = {key: value.copy() for key, value in params.items()}
                best_epoch = epoch
                since_improvement = 0
            else:
                since_improvement += 1
                if since_improvement >= patience:
                    break

    return {
        "params": best_params,
        "best_validation_mrr": float(best_score),
        "best_epoch": best_epoch,
        "epochs_run": curve[-1]["epoch"] if curve else 0,
        "learning_curve": curve,
        "hidden": hidden,
        "embedding": embedding,
        "stopped_early": since_improvement >= patience,
    }


def checkpoint_digest(params: Params) -> str:
    """Provenance for a trained checkpoint: sha256 over the parameter bytes in
    a fixed key order, so a checkpoint can be tied to the numbers it produced."""
    digest = hashlib.sha256()
    for key in sorted(params):
        array = np.ascontiguousarray(params[key], dtype=np.float64)
        digest.update(key.encode("utf-8"))
        digest.update(str(array.shape).encode("utf-8"))
        digest.update(array.tobytes())
    return digest.hexdigest()


def parameter_count(params: Params) -> int:
    return int(sum(value.size for value in params.values()))
