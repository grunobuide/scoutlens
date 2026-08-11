"""The final KEEP / DROP decision (`scoutlens-qop.4`).

Applies every preregistered clause conjunctively. There is no discretionary
override in either direction: the clauses were fixed in `D041`, the subgroup
minimum was amended in `D044`, and this module only evaluates them.

Three things it deliberately does **not** do:

- retrain or retune anything. The Wyscout evidence is read from the artifacts
  `scoutlens-qop.2` and `scoutlens-qop.3` recorded, which are immutable;
- rescue the neural arm. `D043` recorded it as a final DROP and it is not a
  candidate here;
- fit anything on StatsBomb. The diagonal weights come frozen from the Wyscout
  training split.
"""

from __future__ import annotations

import hashlib
from typing import Any

import numpy as np

from scoutlens.benchmark.protocol import PROTOCOL
from scoutlens.showcase.io import canonical_json_bytes

D041_PROTOCOL_HASH = "886ba315b587a91d0fa9ab5c7387f172f8957cf2cfde8a39a65216cb4ff31f1d"
"""The hash under which the qop.2 and qop.3 artifacts were recorded."""

D041_SUBGROUPS = {
    "by": "role",
    "reportable_minimum_queries": 100,
    "rule": "a role subgroup below the minimum is reported but never gates the decision",
}
"""The subgroup block exactly as `D041` froze it, kept so the lineage claim
can be *proved* rather than asserted — see `reconcile_lineage`."""

KEEP = "KEEP"
DROP = "DROP"


def reconcile_lineage() -> dict[str, Any]:
    """Prove mechanically that `D044` changed the subgroup clause and nothing else.

    Substituting `D041`'s subgroup block back into the current protocol must
    reproduce the D041 hash exactly. If it does, then every other field is
    byte-identical to what qop.2 and qop.3 were measured under, and their
    recorded results remain valid evidence for clauses this module evaluates.
    """
    reconstructed = {**PROTOCOL, "subgroups": D041_SUBGROUPS}
    reconstructed_hash = hashlib.sha256(canonical_json_bytes(reconstructed)).hexdigest()
    matches = reconstructed_hash == D041_PROTOCOL_HASH
    return {
        "d041_protocol_hash": D041_PROTOCOL_HASH,
        "reconstructed_d041_hash": reconstructed_hash,
        "only_the_subgroup_clause_changed": matches,
        "detail": (
            "Substituting D041's subgroup block back into the amended protocol "
            "reproduces the D041 hash, so every other clause is unchanged and "
            "the qop.2/qop.3 artifacts recorded under that hash remain valid "
            "evidence."
            if matches
            else "RECONSTRUCTION FAILED: the amendment touched more than the "
            "subgroup clause, so recorded evidence cannot be reused."
        ),
    }


def evaluate_clauses(
    wyscout_test_delta: float,
    wyscout_test_ci_low: float,
    by_role: dict[str, dict[str, Any]],
    statsbomb_delta: float,
    statsbomb_ci_low: float,
    budgets: dict[str, Any],
) -> list[dict[str, Any]]:
    """One row per preregistered KEEP clause, each marked pass/fail with the
    evidence that decided it. Applied conjunctively by `decide`."""
    minimum = PROTOCOL["subgroups"]["reportable_minimum_queries"]
    gating = {role: row for role, row in by_role.items() if row["n_queries"] >= minimum}
    worst_drop = min(
        (row["delta"] for row in gating.values()), default=0.0
    )

    clauses = [
        {
            "clause": "wyscout test delta MRR >= +0.020 over baseline_b_cosine",
            "observed": wyscout_test_delta,
            "threshold": 0.020,
            "passed": wyscout_test_delta >= 0.020,
            "evidence": "artifacts/benchmark/diagonal-results.json test.delta_vs_cosine.point_estimate",
        },
        {
            "clause": "paired 95% CI lower bound > 0",
            "observed": wyscout_test_ci_low,
            "threshold": 0.0,
            "passed": wyscout_test_ci_low > 0.0,
            "evidence": "artifacts/benchmark/diagonal-results.json test.delta_vs_cosine.ci_low",
        },
        {
            "clause": f"no role subgroup with >= {minimum} queries drops more than 0.020",
            "observed": worst_drop,
            "threshold": -0.020,
            "passed": worst_drop >= -0.020,
            "gating_roles": sorted(gating),
            "non_gating_roles": sorted(set(by_role) - set(gating)),
            "evidence": "recorded per-role table, D044 minimum applied without retraining",
        },
        {
            "clause": "statsbomb external delta > 0",
            "observed": statsbomb_delta,
            "threshold": 0.0,
            "passed": statsbomb_delta > 0.0,
            "evidence": "cross-provider evaluation in this run, weights frozen from Wyscout",
        },
        {
            "clause": "statsbomb paired 95% CI lower bound > -0.010",
            "observed": statsbomb_ci_low,
            "threshold": -0.010,
            "passed": statsbomb_ci_low > -0.010,
            "evidence": "cross-provider evaluation in this run",
        },
        {
            "clause": "operational budgets pass",
            "observed": budgets,
            "threshold": PROTOCOL["budgets"],
            "passed": bool(budgets["within_budget"]),
            "evidence": "recorded costs from qop.2/qop.3 and this run",
        },
    ]
    return clauses


def decide(clauses: list[dict[str, Any]]) -> dict[str, Any]:
    """Conjunctive, no override. Every clause must pass for KEEP."""
    failed = [clause["clause"] for clause in clauses if not clause["passed"]]
    return {
        "outcome": KEEP if not failed else DROP,
        "all_clauses_passed": not failed,
        "failed_clauses": failed,
        "rule": (
            "KEEP the diagonal representation if and only if every Wyscout, "
            "StatsBomb, subgroup and operational clause passes; otherwise DROP. "
            "No discretionary override in either direction."
        ),
        "neural_arm": "DROP, final under D043; not a candidate for rescue, retuning or promotion",
    }


def diagonal_weight_vector(recorded_weights: list[dict[str, Any]], columns: list[str]) -> np.ndarray:
    """The frozen Wyscout weights, ordered to the given feature columns.

    Fails closed on any missing feature: applying a weight vector positionally
    to a differently-ordered feature set would silently score the wrong thing.
    """
    by_feature = {row["feature"]: float(row["weight"]) for row in recorded_weights}
    missing = [column for column in columns if column not in by_feature]
    if missing:
        raise ValueError(f"recorded weights are missing features: {missing}")
    return np.array([by_feature[column] for column in columns], dtype=float)
