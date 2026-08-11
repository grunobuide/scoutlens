"""Acceptance criterion 6: the test split stays shut until the protocol
hash is on the record, and any amendment to the protocol re-shuts it."""

from __future__ import annotations

import json

import pytest

from scoutlens.benchmark import protocol as protocol_module
from scoutlens.benchmark.protocol import (
    PROTOCOL,
    assert_test_set_unlocked,
    is_protocol_registered,
    protocol_bytes,
    protocol_hash,
)


def test_protocol_hash_is_stable_across_calls() -> None:
    assert protocol_hash() == protocol_hash()
    assert len(protocol_hash()) == 64


def test_protocol_is_a_pure_literal_serializable_before_any_data_exists() -> None:
    """The preregistration must not depend on a measurement. If any value
    were computed from data, the hash could not be fixed in advance."""
    reparsed = json.loads(protocol_bytes())
    assert reparsed == json.loads(json.dumps(PROTOCOL))


def test_amending_the_protocol_changes_the_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    before = protocol_hash()
    amended = {**PROTOCOL, "decision": {**PROTOCOL["decision"], "keep_requires_all": []}}
    monkeypatch.setattr(protocol_module, "PROTOCOL", amended)
    assert protocol_hash() != before


def test_test_split_is_locked_when_the_hash_is_absent(tmp_path) -> None:
    empty_log = tmp_path / "decisions-log.md"
    empty_log.write_text("# no decisions here\n", encoding="utf-8")
    assert is_protocol_registered(empty_log) is False
    with pytest.raises(PermissionError, match="test split is locked"):
        assert_test_set_unlocked(empty_log)


def test_test_split_unlocks_once_the_hash_is_recorded(tmp_path) -> None:
    log = tmp_path / "decisions-log.md"
    log.write_text(f"## D041\n\nprotocol hash `{protocol_hash()}`\n", encoding="utf-8")
    assert is_protocol_registered(log) is True
    assert_test_set_unlocked(log)  # does not raise


def test_a_missing_ledger_locks_rather_than_defaults_open(tmp_path) -> None:
    assert is_protocol_registered(tmp_path / "absent.md") is False


def test_recorded_thresholds_match_the_bead(tmp_path) -> None:
    """The numbers the bead froze, pinned so a later edit is a visible diff
    and a new hash rather than a quiet retune."""
    keep = PROTOCOL["decision"]["keep_requires_all"]
    assert any("+0.020" in c for c in keep)
    assert any("CI lower bound > 0" in c for c in keep)
    assert any("-0.010" in c for c in keep)
    gate = PROTOCOL["neural_continuation_gate"]["requires_all"]
    assert any("+0.010" in c for c in gate)
    assert any("-0.005" in c for c in gate)


# --- the D044 subgroup amendment -------------------------------------------

SUBGROUP_MINIMUM = 50

# Frozen test-split role counts (representation-benchmark-protocol.md §3.1).
FROZEN_TEST_COUNTS = {"Defender": 95, "Midfielder": 90, "Forward": 48, "Goalkeeper": 20}


def _gates(n_queries: int) -> bool:
    """The rule as the runners apply it: `n_queries >= minimum`."""
    return n_queries >= PROTOCOL["subgroups"]["reportable_minimum_queries"]


def test_subgroup_minimum_is_exactly_fifty() -> None:
    assert PROTOCOL["subgroups"]["reportable_minimum_queries"] == SUBGROUP_MINIMUM


def test_the_gating_boundary_is_pinned_at_49_and_50() -> None:
    assert _gates(49) is False
    assert _gates(50) is True


def test_frozen_counts_gate_defender_and_midfielder_only() -> None:
    """The whole point of the amendment: two roles gate, two do not. Forward
    at 48 is below 50 — an earlier revision of the protocol document wrongly
    claimed a minimum of 50 would include it."""
    gating = {role for role, n in FROZEN_TEST_COUNTS.items() if _gates(n)}
    assert gating == {"Defender", "Midfielder"}
    assert _gates(FROZEN_TEST_COUNTS["Forward"]) is False
    assert _gates(FROZEN_TEST_COUNTS["Goalkeeper"]) is False


def test_the_original_hundred_would_have_gated_nothing() -> None:
    """Records why the amendment was needed, so the inertness cannot be
    quietly reintroduced by raising the threshold again."""
    assert all(n < 100 for n in FROZEN_TEST_COUNTS.values())


def test_the_amended_protocol_is_registered_in_the_ledger() -> None:
    """D044 records the amended hash; without it the test split stays shut."""
    assert is_protocol_registered() is True


def test_changing_the_subgroup_minimum_relocks_the_test_split(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    amended = {
        **PROTOCOL,
        "subgroups": {**PROTOCOL["subgroups"], "reportable_minimum_queries": 45},
    }
    monkeypatch.setattr(protocol_module, "PROTOCOL", amended)
    assert is_protocol_registered() is False
    with pytest.raises(PermissionError, match="test split is locked"):
        assert_test_set_unlocked()
