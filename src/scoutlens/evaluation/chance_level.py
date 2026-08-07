"""Chance-level control for retrieval results (SLS-024).

Every published ScoutLens MRR is produced by a ranker that emits a total
ordering of a candidate pool of size N. That ordering is a bijection
between candidates and ranks 1..N, so if the same-player link carried no
signal at all — target drawn uniformly from the exact pool the query was
ranked against — the expected reciprocal rank is

    E[1/rank] = (1/N) * sum_{k=1..N} 1/k = H_N / N

independent of which method produced the ranking. That number is the
*chance level* of the experiment design: the MRR any method would get by
lucking into correct answers only through pool composition. Lifts of 41x
vs. 1.6x mean very different things, so every absolute MRR should be
reported next to its chance level and the lift over it.

Two consumers:

1. `chance_level_mrr` / `lift` — the exact design floor for a per-query
   pool-size list (global pools are constant-N, within-role pools vary by
   query), used to normalize every published MRR.
2. `random_target_null` — an empirical permutation null. For each
   permutation it draws a uniform target per query (from 1..pool_size),
   computes the resulting MRR, and returns the null distribution's mean,
   95% central interval, and an empirical p-value against an observed MRR.
   Seed-fixed and order-independent (queries are sorted, mirrors
   `bootstrap_mrr_delta`'s determinism contract, D013).

The chance level is the same regardless of which baseline is being
anonymous-normalized (with equal per-query pool sizes); what differs per
baseline is the *observed* MRR it is compared against. The control does
not replace Baseline A/B/C — those compare methods against each other;
this one pins each method against the design's own floor.
"""

from __future__ import annotations

import random
from functools import lru_cache


@lru_cache(maxsize=None)
def _harmonic(n: int) -> float:
    """Precise H_n for the N values actually seen as pool sizes."""
    return sum(1.0 / k for k in range(1, n + 1))


def chance_level_mrr(pool_sizes: list[int]) -> float:
    """Mean of H_{n_q}/n_q over queries — the exact expected MRR under a
    uniform-random target in each query's own effective pool.

    Requires the *per-query* pool size: a global condition is constant-N
    for every query, but the within-role condition ranks each query only
    against that query's nominal-role candidates, so pool sizes differ
    across queries and must be supplied individually (the `pool_size`
    column that `run_baseline_*_retrieval` already records).
    """
    if not pool_sizes:
        raise ValueError("chance_level_mrr called with an empty pool-size list")
    if any(n < 1 for n in pool_sizes):
        raise ValueError("pool sizes must be >= 1")
    return sum(_harmonic(n) / n for n in pool_sizes) / len(pool_sizes)


def lift(observed_mrr: float, chance_level: float) -> float:
    """observed / chance-level. 1.0 = nothing above the design floor."""
    if chance_level <= 0:
        raise ValueError("chance level must be > 0")
    return observed_mrr / chance_level


def _null_mrr_per_permutation(pool_sizes: list[int], rng: random.Random) -> float:
    """One permutation: a uniform target rank in 1..n per query, mean 1/k."""
    return sum(1.0 / rng.randint(1, n) for n in pool_sizes) / len(pool_sizes)


def random_target_null(
    pool_sizes: list[int],
    observed_mrr: float,
    n_resamples: int = 1000,
    seed: int = 0,
) -> dict:
    """Empirical permutation null for the uniform-random-target hypothesis.

    `observed_mrr` is the method's real MRR on the same query/pool layout;
    the null distribution answers "what would MRR look like if the target
    were random within each query's pool?" Returns mean, 95% central
    interval of the null, and the empirical p-value (fraction of
    permutations at or above the observed MRR, +1 smoothing so it is
    never exactly 0). Deterministic for a fixed seed regardless of input
    order, matching D013's reproducibility contract.
    """
    if not pool_sizes:
        raise ValueError("random_target_null requires at least one query")
    if any(n < 1 for n in pool_sizes):
        raise ValueError("pool sizes must be >= 1")

    sorted_sizes = sorted(pool_sizes)
    rng = random.Random(seed)
    null_mrrs = [_null_mrr_per_permutation(sorted_sizes, rng) for _ in range(n_resamples)]
    null_mrrs.sort()

    mean = sum(null_mrrs) / n_resamples
    ci_low = null_mrrs[int(0.025 * n_resamples)]
    ci_high = null_mrrs[int(0.975 * n_resamples) - 1]
    p_value = (sum(1 for x in null_mrrs if x >= observed_mrr) + 1) / (n_resamples + 1)

    return {
        "expected_mrr": chance_level_mrr(pool_sizes),
        "observed_mrr": observed_mrr,
        "null_mean": mean,
        "ci_low": ci_low,
        "ci_high": ci_high,
        "p_value": p_value,
        "n_resamples": n_resamples,
        "n_queries": len(pool_sizes),
    }
