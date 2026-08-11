"""The frozen benchmark protocol, its content hash, and the test-set lock.

`PROTOCOL` is the preregistration. It is a literal: no value in it is
computed from data, so the hash is stable before anything is fitted. That
is the whole point — the decision rule is fixed while the answer is still
unknown.

`protocol_hash()` is the identity a decision record cites.
`assert_test_set_unlocked()` refuses to open the test split until that hash
appears in `docs/decisions-log.md`, which makes "preregister first" a
mechanical property rather than a promise.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from scoutlens.showcase.io import canonical_json_bytes

REPO_ROOT = Path(__file__).resolve().parents[3]
DECISIONS_LOG = REPO_ROOT / "docs" / "decisions-log.md"

SPLIT_SEED = 2718
"""Frozen split seed. Distinct from the bootstrap seed (0) and the
match-bootstrap seed (1729) so no two procedures can accidentally share a
draw."""

TRAIN_FRACTION = 0.60
VALIDATION_FRACTION = 0.20
# test takes the remainder; stated as a boundary, not a third fraction, so
# the three can never fail to sum to 1.

PROTOCOL: dict[str, Any] = {
    "protocol_version": 1,
    "bead": "scoutlens-qop.1",
    "question": (
        "Does a learned fingerprint representation retrieve the same player "
        "across a temporal split better than the frozen Baseline B cosine "
        "metric, on players never seen during fitting?"
    ),
    "population": {
        "provider": "wyscout",
        "season": "2017/18",
        "competitions": [364, 412, 426, 524, 795],
        "competitions_note": "England 364, France 412, Germany 426, Italy 524, Spain 795",
        "minutes_threshold_per_period": 450,
        "eligibility": "minutes_played >= threshold in BOTH periods for the same (player_id, competitionId)",
        "profile_key": ["player_id", "competitionId", "period"],
        "profile_key_note": "D007 - player_id alone would collide a league and a tournament",
    },
    "split": {
        "unit": "player_id",
        "unit_note": "the human, not (player_id, competitionId) - every row for one human stays in one split",
        "stratify_by": "role",
        "roles": ["Defender", "Forward", "Goalkeeper", "Midfielder"],
        "fractions": {"train": TRAIN_FRACTION, "validation": VALIDATION_FRACTION, "test": "remainder"},
        "seed": SPLIT_SEED,
        "assignment": (
            "within each role, players are ordered by "
            "sha256(f'{seed}:{player_id}') then player_id, and cut at "
            "floor(n*0.60) and floor(n*0.80)"
        ),
        "assignment_note": (
            "order-independent and stable: the ordering key depends only on "
            "the seed and the player id, never on row order or population size"
        ),
    },
    "candidate_pool": {
        "rule": "within-split",
        "detail": (
            "a query from split S is ranked only against period-B profiles of "
            "players in S"
        ),
        "why": (
            "cross-split pools would let a test query retrieve a training "
            "player, and would make pool size depend on the split sizes"
        ),
        "consequence": (
            "split-level absolute MRR is NOT comparable to the published "
            "full-population numbers - pools are smaller, so retrieval is "
            "easier. Only the within-split paired delta (B - A) is the object "
            "of study."
        ),
    },
    "preprocessing": {
        "scaler": "mean-impute then z-score, per feature",
        "fit_on": "train split only",
        "applied_to": ["train", "validation", "test"],
        "why": (
            "the published experiments fit the scaler on the population being "
            "compared (D008). That is correct for a descriptive experiment and "
            "wrong for a confirmatory one: it lets held-out rows inform the "
            "transform. This benchmark fits on train only."
        ),
        "degenerate_columns": "a feature that is all-null or zero-variance in train contributes exactly 0",
        "fitted_statistic_precision": "12 significant digits",
        "fitted_statistic_precision_why": (
            "Polars sums in parallel, so a mean or std can differ by 1-2 ULPs "
            "between runs on identical input. That never moves an integer "
            "rank, but it does make the published scaler bytes irreproducible. "
            "Quantizing the fitted statistics makes the whole pipeline exactly "
            "reproducible at a cost of ~1e-12 relative on each z-score."
        ),
    },
    "features": {
        "primary": "CANONICAL_28",
        "sensitivity": ["CANONICAL_PLUS_CARRY", "CANONICAL_28 minus touches_p90"],
        "note": "sensitivity arms are reported alongside the primary set, never mixed into it (D021)",
    },
    "baselines": {
        "reference": "baseline_b_cosine",
        "reference_note": "the incumbent this benchmark must beat, over CANONICAL_28",
        "floor": "baseline_a_role_minutes",
        "floor_note": "the trivial method; reported to keep the delta interpretable",
    },
    "metrics": {
        "primary": "within_role_mrr",
        "secondary": ["global_mrr", "median_rank", "recall_at_1", "recall_at_5", "recall_at_10"],
        "paired_interval": {
            "method": "paired bootstrap over the shared query set",
            "n_resamples": 1000,
            "seed": 0,
            "level": 0.95,
            "ordering": "queries sorted by (player_id, competitionId) before resampling (D013)",
        },
    },
    "subgroups": {
        "by": "role",
        "reportable_minimum_queries": 50,
        "rule": "a role subgroup below the minimum is reported but never gates the decision",
        "amended_by": "D044",
        "amendment_note": (
            "D041 froze this at 100, which gated no role at all: the largest "
            "test subgroup is Defender at 95. Amended to 50 by human decision "
            "on 2026-08-11, choosing an option recorded in scoutlens-qop.5 "
            "before any qop.2 or qop.3 outcome existed. At 50, Defender (95) "
            "and Midfielder (90) gate; Forward (48) and Goalkeeper (20) are "
            "reported but do not gate. Nothing else in this protocol changed."
        ),
    },
    "decision": {
        "keep_requires_all": [
            "wyscout test delta MRR >= +0.020 over baseline_b_cosine",
            "paired 95% CI lower bound > 0",
            "no role subgroup with >= 100 queries drops more than 0.020",
            "statsbomb external delta > 0 with 95% CI lower bound > -0.010",
            "operational budgets pass",
        ],
        "otherwise": "DROP - the representation does not earn its place and Baseline B stands",
        "practical_gain_note": (
            "+0.020 is a practical-significance floor, not a statistical one. "
            "A statistically clean but smaller gain is a DROP: it does not "
            "justify the interpretability cost of replacing a transparent "
            "cosine over named features."
        ),
    },
    "neural_continuation_gate": {
        "evaluated_on": "validation",
        "model": "diagonal metric (qop.2)",
        "requires_all": [
            "validation delta MRR >= +0.010 over baseline_b_cosine",
            "paired 95% CI lower bound > -0.005",
        ],
        "otherwise": "do not run the neural contrastive arm (qop.3) - record the null and stop",
    },
    "budgets": {
        "max_wall_clock_seconds_per_arm": 1800,
        "max_peak_rss_bytes": 4 * 1024**3,
        "max_artifact_bytes": 5 * 1024**2,
        "note": "exceeding a budget is a stop condition, not a reason to weaken the protocol",
    },
    "external_test": {
        "provider": "statsbomb",
        "season": "2015/16",
        "competitions": [2, 7, 11, 12],
        "minutes_threshold_per_period": 450,
        "features": "CANONICAL_28, provider-native",
        "weights": "frozen from the Wyscout training split; nothing is refit on StatsBomb",
    },
    "non_goals": [
        "looking at test labels while designing",
        "UMAP or any projection as evidence",
        "recruitment endpoints or transfer-success claims",
        "causal interpretation of similarity",
    ],
    "stop_go": {
        "test_opens_only_after": "protocol_hash recorded in docs/decisions-log.md",
        "one_shot": "the test split is evaluated once per candidate model; a second look is a new protocol version",
        "null_result": "a null is a result and is published (project convention); it is never converted into a redesign without a new preregistration",
    },
}


def protocol_bytes() -> bytes:
    """Canonical serialization of `PROTOCOL`, key-sorted and stable."""
    return canonical_json_bytes(PROTOCOL)


def protocol_hash() -> str:
    """sha256 of the canonical protocol bytes. This is what a decision
    record cites and what `assert_test_set_unlocked` looks for."""
    return hashlib.sha256(protocol_bytes()).hexdigest()


def is_protocol_registered(decisions_log: Path = DECISIONS_LOG) -> bool:
    """Whether the current protocol hash appears in the decision ledger."""
    if not decisions_log.is_file():
        return False
    return protocol_hash() in decisions_log.read_text(encoding="utf-8")


def assert_test_set_unlocked(decisions_log: Path = DECISIONS_LOG) -> None:
    """Fail closed unless the exact current protocol is on the record.

    Any edit to `PROTOCOL` changes the hash and re-locks the test split,
    which is the intended behaviour: a protocol amended after seeing
    validation results is a different protocol and needs its own decision
    record.
    """
    if not is_protocol_registered(decisions_log):
        raise PermissionError(
            f"test split is locked: protocol hash {protocol_hash()} is not "
            f"recorded in {decisions_log}. Preregister it with a decision "
            "record before evaluating on test (scoutlens-qop.1 acceptance "
            "criterion 6)."
        )
