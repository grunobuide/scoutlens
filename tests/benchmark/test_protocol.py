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
    assert PROTOCOL["subgroups"]["reportable_minimum_queries"] == 100
    gate = PROTOCOL["neural_continuation_gate"]["requires_all"]
    assert any("+0.010" in c for c in gate)
    assert any("-0.005" in c for c in gate)
