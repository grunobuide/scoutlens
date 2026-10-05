"""Gate 2 of `scoutlens-e87`, frozen before any retrieval outcome is seen.

The bead's acceptance criterion 3: on GO, "formulas, denominators,
null/missingness and minimum support are frozen before outcome evaluation".
They are frozen here, with the comparison and the decision rule, and the hash
of this exact protocol must be on the decision ledger before
`assert_gate2_unlocked` lets an evaluation run. Changing anything below -
a formula, a threshold, the scaler population, the decision rule - changes the
hash, and a run against a different hash is a new protocol version, not a
second look at this one.

Mirrors `scoutlens.benchmark.protocol`, which did the same for the
representation benchmark.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from scoutlens.goalkeeper.observability import (
    FEATURES,
    MIN_COVERAGE,
    MIN_DISTINCT_CONCEPTS,
    MIN_PROPORTION_DENOMINATOR,
    MIN_RATE_NUMERATOR,
)
from scoutlens.release.manifest import REPO_ROOT
from scoutlens.showcase.io import canonical_json_bytes

DECISIONS_LOG = REPO_ROOT / "docs" / "decisions-log.md"

PROTOCOL: dict[str, Any] = {
    "protocol": "scoutlens-e87-goalkeeper-family",
    "version": 1,
    "question": (
        "Does adding a directly observed goalkeeper family to the frozen 32-feature catalog "
        "improve same-goalkeeper temporal identity retrieval within the goalkeeper pool?"
    ),
    "population": {
        "source": "Wyscout 2017/18 public event dataset (Pappalardo et al.), data/processed",
        "competitions": [364, 412, 426, 524, 795],
        "minutes_threshold_per_period": 450,
        "unit": "player_id x competitionId (D007)",
        "periods": "scoutlens.evaluation.temporal.assign_periods: chronological halves by match count",
        "role": "Goalkeeper (players.role.name); outfield players are never evidence for this issue",
    },
    "family": [
        {
            "feature_id": feature.feature_id,
            "concept": feature.concept,
            "kind": feature.kind,
            "numerator": feature.numerator,
            "denominator": feature.denominator,
        }
        for feature in FEATURES
    ],
    "null_rule": {
        "proportion": f"null when the denominator is below {MIN_PROPORTION_DENOMINATOR} events in the goalkeeper-period",
        "rate_p90": "null only without minutes; eligibility guarantees at least 450 per period",
        "imputation": "nulls are mean-imputed before standardisation, so they sit at z = 0 (the catalog's D008 rule)",
    },
    "gate1": {
        "min_proportion_denominator": MIN_PROPORTION_DENOMINATOR,
        "min_rate_numerator": MIN_RATE_NUMERATOR,
        "min_coverage": MIN_COVERAGE,
        "min_distinct_concepts": MIN_DISTINCT_CONCEPTS,
    },
    "comparison": {
        "queries": "every eligible goalkeeper unit's period-A profile",
        "candidates": "every eligible goalkeeper unit's period-B profile (within-role pool)",
        "baseline": (
            "the published within-role Baseline B: the 32 catalog features, scaler fitted on the full "
            "all-roles eligible population over both periods (D008, SLS-019), cosine similarity"
        ),
        "candidate": (
            "the same 32 features scaled the same way, plus the goalkeeper family standardised on the "
            "population it is defined for - eligible goalkeeper unit-periods, both periods combined - "
            "cosine similarity over all 36"
        ),
        "single_candidate_arm": True,
        "ties": "player_id ascending, as Baseline B",
    },
    "metrics": {
        "primary": "MRR of the query unit's own period-B profile",
        "secondary": ["Recall@1", "Recall@5", "Recall@10", "median self-rank"],
        "uncertainty": "paired bootstrap over goalkeeper query units, 1000 resamples, seed 0, 95% percentile interval",
    },
    "decision": {
        "KEEP": "delta MRR >= +0.020 AND 95% CI lower bound of delta MRR > 0 AND delta Recall@10 >= 0",
        "DROP": "anything else",
        "on_keep": "default catalog changes only with atomic docs, config, artifact and drift updates (AC7)",
    },
    "reporting": [
        "sample size: queries and pool",
        "rank distribution for both arms, and per-query rank change",
        "the largest per-query regressions as failure cases",
        "runtime",
        "provider portability: what the StatsBomb event schema would need to compute the family",
    ],
    "non_goals": [
        "proxying positioning, pressure, shot quality or saves the data does not record",
        "evaluating outfield players",
        "quality, recruitment or future-performance interpretation of any goalkeeper feature",
        "changing the published catalog or showcase before a KEEP",
    ],
    "stop_go": {
        "evaluation_opens_only_after": "this protocol's hash is recorded in docs/decisions-log.md",
        "one_shot": "the comparison is run once; another look is a new protocol version",
        "null_result": "a DROP is a result and is published; it is not converted into a redesign without a new protocol",
    },
}


def protocol_bytes() -> bytes:
    """Canonical serialization of `PROTOCOL`, key-sorted and stable."""
    return canonical_json_bytes(PROTOCOL)


def protocol_hash() -> str:
    """sha256 of the canonical protocol bytes - what the decision record cites."""
    return hashlib.sha256(protocol_bytes()).hexdigest()


def is_protocol_registered(decisions_log: Path = DECISIONS_LOG) -> bool:
    if not decisions_log.is_file():
        return False
    return protocol_hash() in decisions_log.read_text(encoding="utf-8")


def assert_gate2_unlocked(decisions_log: Path = DECISIONS_LOG) -> None:
    """Fail closed unless this exact protocol is on the record."""
    if not is_protocol_registered(decisions_log):
        raise RuntimeError(
            f"goalkeeper Gate 2 protocol {protocol_hash()} is not recorded in {decisions_log.name}; "
            "record it before computing any retrieval outcome"
        )
