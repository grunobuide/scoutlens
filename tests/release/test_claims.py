"""The claims matrix, and the checks that make it an audit rather than a listing.

`jtt.7.1` AC3 wants evidence and mandatory caveats behind every public claim.
The matrix is derived from `research-summary.json` — the artifact the site
actually renders — so it cannot drift from what a reader sees. These tests hold
the derivation to that, and prove each check can fail.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scoutlens.explanations.artifacts import DEFAULT_SHOWCASE_ROOT
from scoutlens.release.claims import EXIT_FINDINGS, EXIT_OK, build_matrix, main, render_markdown

requires_summary = pytest.mark.skipif(
    not (DEFAULT_SHOWCASE_ROOT / "v2" / "research-summary.json").is_file(),
    reason="requires the published showcase v2 research summary",
)

pytestmark = requires_summary


@pytest.fixture(scope="module")
def matrix():
    return build_matrix()


def test_the_published_matrix_has_no_findings(matrix) -> None:
    """The release claim: every public conclusion is attributable and qualified."""
    assert matrix.ok, list(matrix.findings)


def test_every_claim_names_its_evidence_and_a_caveat(matrix) -> None:
    assert matrix.rows
    for row in matrix.rows:
        assert row.conclusion, row.experiment_id
        assert row.source_artifact, row.experiment_id
        assert row.report_url, row.experiment_id
        assert row.caveat_codes, row.experiment_id
        assert row.metric_names, row.experiment_id


def test_every_cited_caveat_is_one_the_artifact_publishes(matrix) -> None:
    """A claim cannot qualify itself with something the reader never sees."""
    for row in matrix.rows:
        for code in row.caveat_codes:
            assert code in matrix.caveats, f"{row.experiment_id} cites unpublished {code}"


def test_every_critical_caveat_is_carried_by_some_claim(matrix) -> None:
    """A critical caveat nothing carries is one nobody reads."""
    carried = {code for row in matrix.rows for code in row.caveat_codes}
    critical = {c for c, v in matrix.caveats.items() if v.get("severity") == "critical"}
    assert critical <= carried, f"published but never carried: {sorted(critical - carried)}"


def test_the_boundary_of_the_work_is_published(matrix) -> None:
    """What the study does not claim is part of what it claims."""
    assert matrix.supported_claim
    assert len(matrix.unsupported_claims) >= 3
    joined = " ".join(matrix.unsupported_claims).lower()
    for forbidden in ("style", "recruitment", "predict"):
        assert forbidden in joined, f"the unsupported list never mentions {forbidden}"


# --- the checks can fail -------------------------------------------------


def _write_summary(tmp_path: Path, summary: dict) -> Path:
    root = tmp_path / "v2"
    root.mkdir(parents=True)
    (root / "research-summary.json").write_text(json.dumps(summary), encoding="utf-8")
    return tmp_path


def _base_summary() -> dict:
    return {
        "dataset_version": "test-dataset",
        "supported_claim": "A supported thing.",
        "unsupported_claims": ["Not style.", "Not recruitment.", "Not prediction."],
        "caveats": [{"code": "a_caveat", "severity": "critical", "message": "m"}],
        "experiments": [
            {
                "experiment_id": "e1",
                "title": "t",
                "provider": "p",
                "population": {"n": 1},
                "conclusion": "c",
                "caveat_codes": ["a_caveat"],
                "source_artifact": "artifacts/x.json",
                "report_url": "docs/x.md",
                "metrics": {"mrr": 0.5},
            }
        ],
    }


def test_a_clean_synthetic_summary_passes(tmp_path: Path) -> None:
    assert build_matrix(_write_summary(tmp_path, _base_summary())).ok


def test_a_conclusion_with_no_caveat_is_a_finding(tmp_path: Path) -> None:
    summary = _base_summary()
    summary["experiments"][0]["caveat_codes"] = []
    findings = build_matrix(_write_summary(tmp_path, summary)).findings
    assert any("carries no caveat code" in f for f in findings)


def test_citing_an_unpublished_caveat_is_a_finding(tmp_path: Path) -> None:
    summary = _base_summary()
    summary["experiments"][0]["caveat_codes"] = ["invented"]
    findings = build_matrix(_write_summary(tmp_path, summary)).findings
    assert any("does not publish" in f for f in findings)


def test_an_untraceable_number_is_a_finding(tmp_path: Path) -> None:
    summary = _base_summary()
    summary["experiments"][0]["source_artifact"] = None
    findings = build_matrix(_write_summary(tmp_path, summary)).findings
    assert any("names no source artifact" in f for f in findings)


def test_an_uncarried_critical_caveat_is_a_finding(tmp_path: Path) -> None:
    summary = _base_summary()
    summary["caveats"].append({"code": "orphan", "severity": "critical", "message": "m"})
    findings = build_matrix(_write_summary(tmp_path, summary)).findings
    assert any("carried by no claim" in f for f in findings)


def test_dropping_the_boundary_is_a_finding(tmp_path: Path) -> None:
    summary = _base_summary()
    summary["unsupported_claims"] = []
    findings = build_matrix(_write_summary(tmp_path, summary)).findings
    assert any("boundary" in f for f in findings)


# --- the command ---------------------------------------------------------


def test_the_command_exits_zero_on_the_published_artifact() -> None:
    assert main([]) == EXIT_OK


def test_the_command_reports_findings_non_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    summary = _base_summary()
    summary["experiments"][0]["caveat_codes"] = []
    root = _write_summary(tmp_path, summary)
    import scoutlens.release.claims as module

    monkeypatch.setattr(module, "DEFAULT_SHOWCASE_ROOT", root)
    assert main([]) == EXIT_FINDINGS


def test_the_rendered_table_names_every_claim(matrix) -> None:
    rendered = render_markdown(matrix)
    for row in matrix.rows:
        assert row.experiment_id in rendered
    assert matrix.supported_claim in rendered
    for claim in matrix.unsupported_claims:
        assert claim in rendered
