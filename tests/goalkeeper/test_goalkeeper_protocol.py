"""The Gate 2 protocol is frozen, on the record, and the recorded Gate 1
result agrees with the document and the code (`scoutlens-e87`)."""

from __future__ import annotations

import copy
import os
from pathlib import Path

import pytest

from scoutlens.goalkeeper import protocol
from scoutlens.goalkeeper.run_audit import RECORD, main, recorded_result, recorded_table, render_markdown


@pytest.fixture(scope="module")
def recorded() -> dict:
    return recorded_result()


def test_the_protocol_hash_is_stable() -> None:
    assert protocol.protocol_hash() == protocol.protocol_hash()
    assert len(protocol.protocol_hash()) == 64


def test_moving_any_frozen_value_moves_the_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    original = protocol.protocol_hash()
    changed = copy.deepcopy(protocol.PROTOCOL)
    changed["gate1"]["min_coverage"] = 0.85
    monkeypatch.setattr(protocol, "PROTOCOL", changed)
    assert protocol.protocol_hash() != original


def test_the_protocol_is_on_the_ledger() -> None:
    """The evaluation may open only because this exact hash is recorded."""
    assert protocol.is_protocol_registered(), (
        f"protocol {protocol.protocol_hash()} is not in docs/decisions-log.md; a changed "
        "protocol is a new version and needs its own record"
    )
    protocol.assert_gate2_unlocked()


def test_an_unrecorded_protocol_cannot_run(tmp_path: Path) -> None:
    ledger = tmp_path / "decisions-log.md"
    ledger.write_text("# no goalkeeper protocol here\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="not recorded"):
        protocol.assert_gate2_unlocked(ledger)


def test_the_recorded_audit_was_run_against_this_protocol(recorded: dict) -> None:
    assert recorded["gate2_protocol_sha256"] == protocol.protocol_hash()
    assert recorded["gate1"]["decision"] == "GO"


def test_the_table_is_rendered_from_the_recorded_run(recorded: dict) -> None:
    """A hand edit to either block, without the other, fails here."""
    assert recorded_table() == render_markdown(recorded)
    doc = RECORD.read_text(encoding="utf-8")
    assert protocol.protocol_hash() in doc
    assert "Decision: GO" in doc


def test_the_decision_record_states_the_outcome_and_the_hash() -> None:
    ledger = protocol.DECISIONS_LOG.read_text(encoding="utf-8")
    record = ledger.split("## D064", 1)[1].split("\n## D", 1)[0]
    assert "GO" in record and protocol.protocol_hash() in record


@pytest.mark.skipif(
    os.environ.get("SCOUTLENS_DRIFT") != "1",
    reason="re-running the audit needs local provider data: set SCOUTLENS_DRIFT=1",
)
def test_a_fresh_run_reproduces_the_recorded_audit() -> None:
    assert main(["--check"]) == 0
