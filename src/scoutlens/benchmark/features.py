"""Frozen canonical feature sets for the cross-provider benchmark.

`statsbomb-feature-compatibility.md` froze these sets in prose and `D021`
corrected them, but until now they existed only as text — every consumer
re-derived "the 28" by hand. This module is the single executable
definition, and it fails at import time if the derivation stops matching
the frozen counts.

The primary set is the **like-for-like** set: features whose construct is
measured comparably by Wyscout and StatsBomb. Four of the 32 are excluded:

- `smart_passes_p90` — Unavailable on StatsBomb (no equivalent construct).
- `events_p90` — Non-comparable; total event count is a function of each
  provider's taxonomy density, not of the player.
- `carry_proxy_p90`, `carry_distance_proxy_p90` — Construct-shift. Wyscout
  measures this family through an `Acceleration` proxy while StatsBomb has
  a native `Carry`. An improvement there would confound "the signal
  replicates" with "the measurement got better", so the pair is reported as
  a +2 sensitivity variant and never mixed into the primary set (D021).
"""

from __future__ import annotations

from scoutlens.features.aggregation import FEATURE_COLUMNS

EXCLUDED_UNAVAILABLE = ("smart_passes_p90",)
"""No comparable StatsBomb construct."""

EXCLUDED_NON_COMPARABLE = ("events_p90",)
"""Provider taxonomy density, not player signal."""

EXCLUDED_CONSTRUCT_SHIFT = ("carry_proxy_p90", "carry_distance_proxy_p90")
"""Wyscout `Acceleration` proxy vs. StatsBomb native `Carry` (D021)."""

EXCLUDED_FROM_CANONICAL = (
    *EXCLUDED_UNAVAILABLE,
    *EXCLUDED_NON_COMPARABLE,
    *EXCLUDED_CONSTRUCT_SHIFT,
)

CANONICAL_28: tuple[str, ...] = tuple(
    column for column in FEATURE_COLUMNS if column not in EXCLUDED_FROM_CANONICAL
)
"""The primary like-for-like set. Source order from `FEATURE_COLUMNS`."""

CANONICAL_PLUS_CARRY: tuple[str, ...] = (*CANONICAL_28, *EXCLUDED_CONSTRUCT_SHIFT)
"""+2 sensitivity variant. Reported alongside the primary set, never mixed
into it."""

WEAK_IN_CANONICAL = ("touches_p90",)
"""Retained in the primary set but labeled weak by
`statsbomb-feature-compatibility.md`; a drop-it sensitivity run is a
separate arm, not a redefinition of the primary set."""


def _check() -> None:
    """Fail at import rather than let a feature-set drift reach a published
    number. `FEATURE_COLUMNS` growing is the realistic way this breaks: a
    new Wyscout feature would silently enter the 'canonical shared' set and
    quietly change what the cross-provider comparison means."""
    if len(FEATURE_COLUMNS) != 32:
        raise AssertionError(
            f"expected 32 Wyscout features, found {len(FEATURE_COLUMNS)}; "
            "the canonical shared set is frozen against 32 "
            "(statsbomb-feature-compatibility.md) and must be re-frozen "
            "with a decision record before this benchmark can use it"
        )
    missing = [column for column in EXCLUDED_FROM_CANONICAL if column not in FEATURE_COLUMNS]
    if missing:
        raise AssertionError(f"excluded features absent from FEATURE_COLUMNS: {missing}")
    if len(CANONICAL_28) != 28:
        raise AssertionError(f"canonical set must be 28 features, got {len(CANONICAL_28)}")
    if len(CANONICAL_PLUS_CARRY) != 30:
        raise AssertionError(f"plus-carry variant must be 30 features, got {len(CANONICAL_PLUS_CARRY)}")


_check()
