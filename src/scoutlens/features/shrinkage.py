"""Empirical-Bayes shrinkage for the 7 low-sample ratio features (D024,
beads scoutlens-dul; addresses feasibility-report.md Known Limitation
#11). A player with 1 shot and 1 goal gets `shot_conversion_pct = 1.0` —
numerically identical to a striker who converted 20 of 20, with no
attempt-count weighting. Shrinkage pulls each ratio toward the population
mean by an amount that shrinks as the attempt count grows.

Beta-Binomial empirical Bayes: for each ratio, fit a Beta(alpha, beta)
prior to the population of (numerator, denominator) counts by method of
moments, then report `(k + alpha) / (n + alpha + beta)`. High-n players
barely move; a 1-of-1 rate is pulled most of the way to the mean. A
player with zero attempts (previously `null`) gets the prior mean
`alpha/(alpha+beta)` — a defined, defensible value rather than a
missing one.

This is an **experiment variant**, not a change to the v0.1 catalog:
`compute_player_features` still returns the raw ratios by default; this
module rebuilds a shrunk copy from the `with_counts=True` output.
"""

from __future__ import annotations

import polars as pl

# ratio feature -> (numerator column, [denominator columns summed])
RATIO_SPECS: dict[str, tuple[str, list[str]]] = {
    "pass_completion_pct": ("_sum_pass_accurate", ["_sum_pass_accurate", "_sum_pass_not_accurate"]),
    "shot_conversion_pct": ("_sum_shot_goal", ["_sum_is_shot"]),
    "shots_on_target_pct": ("_sum_shot_on_target", ["_sum_is_shot"]),
    "blocked_shot_pct": ("_sum_shot_blocked", ["_sum_is_shot"]),
    "defensive_duel_win_pct": ("_sum_def_duel_won", ["_sum_def_duel_decided"]),
    "duel_win_pct": ("_sum_duel_won", ["_sum_duel_decided"]),
    "take_on_success_pct": ("_sum_take_on_success", ["_sum_take_on_attempt"]),
}


def fit_beta_prior(numerators: list[float], denominators: list[float]) -> tuple[float, float]:
    """Method-of-moments Beta(alpha, beta) prior from per-player counts,
    over players with at least one attempt. Falls back to a weak uniform
    prior (alpha=beta=1) when the observed rates are over-dispersed
    (variance >= m(1-m), where a Beta can't fit) or degenerate."""
    rates = [k / n for k, n in zip(numerators, denominators) if n > 0]
    if len(rates) < 2:
        return 1.0, 1.0
    m = sum(rates) / len(rates)
    v = sum((p - m) ** 2 for p in rates) / (len(rates) - 1)
    if v <= 0 or v >= m * (1 - m) or m <= 0 or m >= 1:
        return 1.0, 1.0
    common = m * (1 - m) / v - 1
    return m * common, (1 - m) * common


def shrink_ratios(profiles_with_counts: pl.DataFrame) -> pl.DataFrame:
    """Return `profiles_with_counts` with each of the 7 ratio columns
    replaced by its shrunk estimate, the `_sum_*` count columns dropped.
    The prior for each ratio is fit on the full input population (the
    eligible A+B set, matching D008's standardization scope)."""
    out = profiles_with_counts
    exprs = []
    for feature, (num_col, den_cols) in RATIO_SPECS.items():
        num = profiles_with_counts[num_col].to_list()
        den = profiles_with_counts.select(pl.sum_horizontal(den_cols).alias("d"))["d"].to_list()
        alpha, beta = fit_beta_prior(num, den)
        den_expr = pl.sum_horizontal(den_cols)
        exprs.append((
            (pl.col(num_col) + alpha) / (den_expr + alpha + beta)
        ).alias(feature))
    out = out.with_columns(exprs)
    count_cols = [c for c in out.columns if c.startswith("_sum_")]
    return out.drop(count_cols)
