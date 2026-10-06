"""The recorded Gate 2 run, held to the protocol, the decision rule and the
prose that reports it (`scoutlens-e87`).

The run itself happens once. What CI can check without the provider data is
that the record is internally consistent - the decision follows from its own
numbers under the frozen rule - and that every number the document repeats in
prose is the recorded one.
"""

from __future__ import annotations

import os
import re

import pytest

from scoutlens.evaluation.retrieval import RetrievalMetrics
from scoutlens.goalkeeper import evaluate as gate2
from scoutlens.goalkeeper import record
from scoutlens.goalkeeper.protocol import DECISIONS_LOG, protocol_hash
from scoutlens.goalkeeper.run_gate2 import RECORD, TABLE_BLOCK, main, recorded_result, render_markdown

COMPETITIONS = {
    364: "English first division",
    412: "French first division",
    426: "German first division",
    524: "Italian first division",
    795: "Spanish first division",
}


@pytest.fixture(scope="module")
def recorded() -> dict:
    return recorded_result()


@pytest.fixture(scope="module")
def doc() -> str:
    return " ".join(RECORD.read_text(encoding="utf-8").split())


def test_the_run_was_against_the_frozen_protocol(recorded: dict) -> None:
    assert recorded["protocol_sha256"] == protocol_hash()
    assert recorded["queries"] == recorded["baseline"]["n"] == recorded["candidate"]["n"]


def test_the_decision_follows_from_the_recorded_numbers(recorded: dict) -> None:
    decided = gate2.decide(
        RetrievalMetrics(**recorded["baseline"]), RetrievalMetrics(**recorded["candidate"]), recorded["mrr_delta"]
    )
    assert decided == recorded["decision"] == "DROP"


def test_the_headline_table_is_rendered_from_the_record(recorded: dict) -> None:
    assert record.read(RECORD, TABLE_BLOCK) == render_markdown(recorded)


def test_the_prose_repeats_the_recorded_numbers(recorded: dict, doc: str) -> None:
    change = recorded["rank_change"]
    assert f"{change['improved']} improved, {change['unchanged']} unchanged, {change['worsened']} worsened" in doc
    assert f"{change['improved']} of {recorded['queries']} goalkeepers rank better and {change['worsened']} worse" in doc
    base, cand = recorded["baseline"], recorded["candidate"]
    assert f"MRR {base['mrr']:.4f} → {cand['mrr']:.4f}" in doc
    assert f"Recall@10 {base['recall_at_10']:.3f} → {cand['recall_at_10']:.3f}" in doc
    assert f"{recorded['mrr_delta']['point_estimate']:+.4f}" in doc
    assert f"{recorded['mrr_delta']['ci_low']:+.4f}".replace("-", "−") in doc


def test_the_rank_table_is_the_recorded_distribution(recorded: dict, doc: str) -> None:
    labels = {"1": "1", "2-5": "2–5", "6-10": "6–10", "11-20": "11–20", ">20": "over 20"}
    for bucket, label in labels.items():
        row = f"| {label} | {recorded['rank_distribution']['baseline'][bucket]} | {recorded['rank_distribution']['candidate'][bucket]} |"
        assert row in doc, f"rank table row for {label} does not match the record"


def test_the_failure_cases_are_the_recorded_regressions(recorded: dict, doc: str) -> None:
    for row in recorded["largest_regressions"]:
        line = (
            f"| {row['name']} | {COMPETITIONS[row['competitionId']]} | {row['rank_baseline']} | {row['rank_candidate']} |"
        )
        assert line in doc, f"failure case {row['name']} does not match the record"


def test_the_chance_level_stated_is_the_pool_s(recorded: dict, doc: str) -> None:
    pool = recorded["pool_size"][0]
    chance = sum(1 / k for k in range(1, pool + 1)) / pool
    assert round(chance, 2) == 0.05 and "chance-level MRR is about 0.05" in doc


def test_the_decision_record_names_drop_and_the_hash() -> None:
    ledger = DECISIONS_LOG.read_text(encoding="utf-8")
    record_text = ledger.split("## D065", 1)[1].split("\n## D", 1)[0]
    assert "DROP" in record_text and protocol_hash() in record_text


def test_writing_again_is_refused(capsys: pytest.CaptureFixture) -> None:
    """One-shot: --write refuses before computing anything while a result is recorded."""
    assert main(["--write"]) == 1
    assert "one-shot" in capsys.readouterr().err
    assert re.search(r"Decision: DROP", RECORD.read_text(encoding="utf-8"))


@pytest.mark.skipif(
    os.environ.get("SCOUTLENS_DRIFT") != "1",
    reason="re-running the comparison needs local provider data: set SCOUTLENS_DRIFT=1",
)
def test_a_fresh_run_reproduces_the_record() -> None:
    assert main(["--check"]) == 0
