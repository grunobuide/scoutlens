"""Pre-registered analysis for the recruitment-validation study (h00),
implementing the plan frozen in `recruitment-validation-protocol.md`
(D016). Pure functions — no data dependency — so the whole analysis is
unit-tested on synthetic ratings before any real rating exists.

Nothing here decides the study on its own: `analyze_study` ingests real
rater scores and mechanically applies the pre-registered primary metric,
reliability gate, and three failure criteria to reach GO / REDESIGN /
NO-GO. Implemented without scipy (none in the project) — Wilcoxon
signed-rank via a normal approximation with continuity correction (fine
at n=40), a paired bootstrap CI, and interval-metric Krippendorff alpha.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

ARMS = ("B", "C_role", "R")
ALPHA_GATE = 0.40          # Krippendorff reliability floor (D016 §9)
RATING_MIN, RATING_MAX = 1, 5


def krippendorff_alpha_interval(reliability: list[list[float | None]]) -> float:
    """Interval-metric Krippendorff's alpha over a units×raters matrix
    (`None` = missing). Interval (squared-difference) metric is a standard,
    defensible choice for a 1–5 scale. Perfect agreement → 1.0; chance → ~0.

    Uses the coincidence-matrix definition: each unit with `m ≥ 2` present
    ratings contributes `1/(m−1)` to every ordered pair of its values.
    """
    from collections import defaultdict
    coincidence: dict[tuple[float, float], float] = defaultdict(float)
    for row in reliability:
        vals = [v for v in row if v is not None]
        m = len(vals)
        if m < 2:
            continue
        w = 1.0 / (m - 1)
        for i in range(m):
            for j in range(m):
                if i != j:
                    coincidence[(vals[i], vals[j])] += w
    if not coincidence:
        raise ValueError("no unit has >= 2 ratings; alpha is undefined")

    marginals: dict[float, float] = defaultdict(float)
    for (c, k), o in coincidence.items():
        marginals[c] += o
    n = sum(marginals.values())

    do = sum(o * (c - k) ** 2 for (c, k), o in coincidence.items()) / n
    de = sum(
        nc * nk * (c - k) ** 2
        for c, nc in marginals.items()
        for k, nk in marginals.items()
    ) / (n * (n - 1))
    if de == 0:
        return 1.0
    return 1.0 - do / de


def wilcoxon_signed_rank(differences: list[float]) -> dict:
    """Two-sided Wilcoxon signed-rank test on paired differences, normal
    approximation with continuity + tie correction. Zeros are dropped
    (Wilcoxon convention). Returns statistic W (sum of positive ranks), z,
    and approximate two-sided p."""
    nonzero = [d for d in differences if d != 0]
    n = len(nonzero)
    if n == 0:
        return {"W": 0.0, "z": 0.0, "p_value": 1.0, "n": 0}
    order = sorted(range(n), key=lambda i: abs(nonzero[i]))
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and abs(nonzero[order[j + 1]]) == abs(nonzero[order[i]]):
            j += 1
        avg = (i + j) / 2 + 1  # average rank (1-based) for the tie block
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    w_plus = sum(r for d, r in zip(nonzero, ranks) if d > 0)
    mean = n * (n + 1) / 4
    # tie correction on the variance
    from collections import Counter
    tie_term = sum(t ** 3 - t for t in Counter(abs(d) for d in nonzero).values())
    var = n * (n + 1) * (2 * n + 1) / 24 - tie_term / 48
    if var <= 0:
        return {"W": w_plus, "z": 0.0, "p_value": 1.0, "n": n}
    cc = 0.5 if w_plus != mean else 0.0
    z = (w_plus - mean - math.copysign(cc, w_plus - mean)) / math.sqrt(var)
    p = 2 * (1 - _normal_cdf(abs(z)))
    return {"W": w_plus, "z": z, "p_value": min(1.0, p), "n": n}


def _normal_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def bootstrap_paired_ci(differences: list[float], n_resamples: int = 2000, seed: int = 0) -> dict:
    """Percentile bootstrap CI for the mean paired difference. Sorted input
    + fixed seed → reproducible bounds (same contract as the retrieval
    bootstrap, D013)."""
    diffs = sorted(differences)
    n = len(diffs)
    if n == 0:
        return {"mean": 0.0, "ci_low": 0.0, "ci_high": 0.0, "n": 0}
    rng = random.Random(seed)
    means = []
    for _ in range(n_resamples):
        means.append(sum(diffs[rng.randrange(n)] for _ in range(n)) / n)
    means.sort()
    return {
        "mean": sum(diffs) / n,
        "ci_low": means[int(0.025 * n_resamples)],
        "ci_high": means[int(0.975 * n_resamples) - 1],
        "n": n,
    }


@dataclass
class StudyOutcome:
    primary: dict
    secondary: dict
    reliability: dict
    failures: dict
    decision: str
    notes: list[str] = field(default_factory=list)


def _query_arm_means(ratings: list[dict]) -> dict[tuple, dict[str, float]]:
    """Average each (query, arm)'s candidate ratings, first within rater
    then across raters, so every query contributes one mean per arm."""
    from collections import defaultdict
    by_qar: dict[tuple, list[float]] = defaultdict(list)
    for r in ratings:
        by_qar[(r["query_id"], r["arm"], r["rater_id"])].append(r["rating"])
    rater_means: dict[tuple, list[float]] = defaultdict(list)
    for (q, arm, _rater), vals in by_qar.items():
        rater_means[(q, arm)].append(sum(vals) / len(vals))
    return {key: {"mean": sum(v) / len(v)} for key, v in rater_means.items()}


def analyze_study(ratings: list[dict], reliability: list[list[float | None]], seed: int = 0) -> StudyOutcome:
    """Apply the D016 pre-registered plan to real ratings.

    `ratings`: long-format rows {query_id, arm, rater_id, rating}. `arm` in
    ARMS. `reliability`: items×raters matrix for Krippendorff alpha.

    Primary: paired B − C_role query-level means (Wilcoxon + bootstrap CI).
    Failure criteria (declared before data, D016 §9):
      1. claim fails if primary contrast not positive under the test;
      2. instrument fails if alpha < 0.40 (results unreliable);
      3. floor fails if B does not beat random (B − R ≤ 0).
    """
    qam = _query_arm_means(ratings)
    queries = sorted({q for (q, _arm) in qam})

    def paired(arm_a: str, arm_b: str) -> list[float]:
        out = []
        for q in queries:
            if (q, arm_a) in qam and (q, arm_b) in qam:
                out.append(qam[(q, arm_a)]["mean"] - qam[(q, arm_b)]["mean"])
        return out

    b_minus_crole = paired("B", "C_role")
    b_minus_r = paired("B", "R")

    primary_wilcoxon = wilcoxon_signed_rank(b_minus_crole)
    primary_bootstrap = bootstrap_paired_ci(b_minus_crole, seed=seed)
    primary = {
        "contrast": "B - C_role",
        "n_queries": len(b_minus_crole),
        "wilcoxon": primary_wilcoxon,
        "bootstrap": primary_bootstrap,
    }
    win_rate = (sum(1 for d in b_minus_crole if d > 0) / len(b_minus_crole)) if b_minus_crole else 0.0
    b_minus_random = bootstrap_paired_ci(b_minus_r, seed=seed)
    secondary = {
        "b_minus_random": b_minus_random,
        "win_rate_B_over_Crole": win_rate,
        "mean_rating_by_arm": {
            arm: (sum(v["mean"] for (q, a), v in qam.items() if a == arm)
                  / max(1, sum(1 for (q, a) in qam if a == arm)))
            for arm in ARMS
        },
    }
    alpha = krippendorff_alpha_interval(reliability)
    reliability_out = {"krippendorff_alpha": alpha, "gate": ALPHA_GATE, "passes": alpha >= ALPHA_GATE}

    claim_positive = (primary_bootstrap["ci_low"] > 0) and (primary_wilcoxon["p_value"] < 0.05)
    floor_ok = b_minus_random["ci_low"] > 0
    failures = {
        "claim_fails": not claim_positive,
        "instrument_fails": alpha < ALPHA_GATE,
        "floor_fails": not floor_ok,
    }

    notes: list[str] = []
    if failures["instrument_fails"]:
        decision = "REDESIGN"
        notes.append(f"Krippendorff alpha {alpha:.2f} < {ALPHA_GATE}: raters don't agree enough; "
                     "rubric must be revised before any conclusion (results unreliable, not a pass/fail).")
    elif failures["floor_fails"]:
        decision = "NO-GO"
        notes.append("Baseline B does not beat random same-role candidates — investigate the pipeline "
                     "before interpreting anything.")
    elif claim_positive:
        decision = "GO"
        notes.append("B beats the role+minutes heuristic in expert eyes with a positive, reliable margin.")
    else:
        decision = "NO-GO"
        notes.append("Recruitment usefulness not demonstrated: the primary B - C_role contrast is not "
                     "positive under the pre-registered test.")
    return StudyOutcome(primary, secondary, reliability_out, failures, decision, notes)
