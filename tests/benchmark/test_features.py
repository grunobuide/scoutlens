"""The canonical shared feature sets are frozen (D021). These tests exist
because the sets lived in prose until `scoutlens-qop.1`, and a silent drift
between the doc and the code would change what the cross-provider
comparison means without changing any published number."""

from __future__ import annotations

from scoutlens.benchmark.features import (
    CANONICAL_28,
    CANONICAL_PLUS_CARRY,
    EXCLUDED_FROM_CANONICAL,
    WEAK_IN_CANONICAL,
)
from scoutlens.features.aggregation import FEATURE_COLUMNS


def test_canonical_set_is_exactly_28_features() -> None:
    assert len(CANONICAL_28) == 28
    assert len(set(CANONICAL_28)) == 28


def test_canonical_excludes_the_four_frozen_exclusions() -> None:
    assert set(EXCLUDED_FROM_CANONICAL) == {
        "smart_passes_p90",
        "events_p90",
        "carry_proxy_p90",
        "carry_distance_proxy_p90",
    }
    for column in EXCLUDED_FROM_CANONICAL:
        assert column not in CANONICAL_28


def test_canonical_is_a_subset_of_the_32_in_source_order() -> None:
    assert set(CANONICAL_28) <= set(FEATURE_COLUMNS)
    expected_order = [c for c in FEATURE_COLUMNS if c in set(CANONICAL_28)]
    assert list(CANONICAL_28) == expected_order


def test_plus_carry_variant_is_30_and_never_mixed_into_the_primary_set() -> None:
    assert len(CANONICAL_PLUS_CARRY) == 30
    assert set(CANONICAL_PLUS_CARRY) - set(CANONICAL_28) == {
        "carry_proxy_p90",
        "carry_distance_proxy_p90",
    }
    # the primary set is unchanged by the existence of the variant
    assert len(CANONICAL_28) == 28


def test_weak_feature_is_retained_rather_than_silently_dropped() -> None:
    for column in WEAK_IN_CANONICAL:
        assert column in CANONICAL_28
