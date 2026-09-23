"""Build the claims matrix from the published artifact, and check it holds.

    uv run --frozen python -m scoutlens.release.claims

`scoutlens-jtt.7.1` AC3 asks that every public claim carry evidence and its
mandatory caveats. The obvious way to answer is a table in a document. The
problem with that answer is that a table is a copy: the site renders
`research-summary.json`, the table is written by hand, and the first time
someone edits one without the other the release audit starts describing a
version of the project that no longer exists.

So the matrix is **derived from the artifact the site actually renders**, and
the checks below are what make it an audit rather than a listing:

* every experiment carries at least one caveat code, because a conclusion with
  no caveat is a claim with nothing qualifying it;
* every caveat code resolves to a caveat the artifact publishes, so a claim
  cannot cite a qualification the reader never sees;
* every experiment names its source artifact and report, so a number can be
  traced to the run that produced it;
* every `critical` caveat is reachable from at least one claim, because a
  critical caveat nothing carries is one nobody reads;
* the unsupported claims are non-empty, since the boundary of the work is part
  of the work.

None of this judges whether a conclusion is *true*. It checks that each one is
attributable and qualified, which is the part a release audit can settle.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from scoutlens.console import use_utf8_output
from scoutlens.explanations.artifacts import DEFAULT_SHOWCASE_ROOT

#: Severities that must each be carried by at least one claim.
REQUIRED_SEVERITIES = ("critical",)

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_UNAVAILABLE = 2


@dataclass(frozen=True)
class ClaimRow:
    """One public claim, with what backs it and what qualifies it."""

    experiment_id: str
    title: str
    provider: str
    population: str
    conclusion: str
    caveat_codes: tuple[str, ...]
    source_artifact: str | None
    report_url: str | None
    metric_names: tuple[str, ...]

    def as_record(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "title": self.title,
            "provider": self.provider,
            "population": self.population,
            "conclusion": self.conclusion,
            "caveat_codes": list(self.caveat_codes),
            "source_artifact": self.source_artifact,
            "report_url": self.report_url,
            "metric_names": list(self.metric_names),
        }


@dataclass(frozen=True)
class ClaimsMatrix:
    """The whole matrix, plus whatever did not hold."""

    dataset_version: str
    supported_claim: str
    unsupported_claims: tuple[str, ...]
    caveats: dict[str, dict[str, Any]]
    rows: tuple[ClaimRow, ...]
    findings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return not self.findings

    def as_record(self) -> dict[str, Any]:
        return {
            "dataset_version": self.dataset_version,
            "supported_claim": self.supported_claim,
            "unsupported_claims": list(self.unsupported_claims),
            "caveats": self.caveats,
            "claims": [row.as_record() for row in self.rows],
            "findings": list(self.findings),
        }


def _metric_names(experiment: dict[str, Any]) -> tuple[str, ...]:
    metrics = experiment.get("metrics")
    if isinstance(metrics, dict):
        return tuple(sorted(metrics))
    if isinstance(metrics, list):
        names = [m.get("name") or m.get("metric_id") for m in metrics if isinstance(m, dict)]
        return tuple(sorted(str(n) for n in names if n))
    return ()


def _population(experiment: dict[str, Any]) -> str:
    population = experiment.get("population")
    if isinstance(population, dict):
        parts = [f"{k}={v}" for k, v in sorted(population.items())]
        return ", ".join(parts)
    return str(population or "")


def build_matrix(showcase_root: Path | None = None) -> ClaimsMatrix:
    """Read the published summary and check every claim is attributable."""
    root = showcase_root or DEFAULT_SHOWCASE_ROOT
    path = root / "v2" / "research-summary.json"
    if not path.is_file():
        raise FileNotFoundError(f"{path} is not present")

    summary = json.loads(path.read_text(encoding="utf-8"))
    caveats = {c["code"]: c for c in summary.get("caveats", ())}

    rows: list[ClaimRow] = []
    findings: list[str] = []

    for experiment in summary.get("experiments", ()):
        codes = tuple(experiment.get("caveat_codes", ()) or ())
        row = ClaimRow(
            experiment_id=str(experiment.get("experiment_id", "")),
            title=str(experiment.get("title", "")),
            provider=str(experiment.get("provider", "")),
            population=_population(experiment),
            conclusion=str(experiment.get("conclusion", "")),
            caveat_codes=codes,
            source_artifact=experiment.get("source_artifact"),
            report_url=experiment.get("report_url"),
            metric_names=_metric_names(experiment),
        )
        rows.append(row)

        if not codes:
            findings.append(f"{row.experiment_id}: conclusion carries no caveat code")
        for code in codes:
            if code not in caveats:
                findings.append(f"{row.experiment_id}: cites caveat {code!r} the artifact does not publish")
        if not row.source_artifact:
            findings.append(f"{row.experiment_id}: names no source artifact")
        if not row.report_url:
            findings.append(f"{row.experiment_id}: names no report")
        if not row.metric_names:
            findings.append(f"{row.experiment_id}: publishes no metric")
        if not row.conclusion:
            findings.append(f"{row.experiment_id}: has no conclusion")

    carried = {code for row in rows for code in row.caveat_codes}
    for code, caveat in sorted(caveats.items()):
        if caveat.get("severity") in REQUIRED_SEVERITIES and code not in carried:
            findings.append(f"critical caveat {code!r} is published but carried by no claim")

    if not summary.get("supported_claim"):
        findings.append("the artifact states no supported claim")
    if not summary.get("unsupported_claims"):
        findings.append("the artifact states no unsupported claims; the boundary is part of the work")

    return ClaimsMatrix(
        dataset_version=str(summary.get("dataset_version", "")),
        supported_claim=str(summary.get("supported_claim", "")),
        unsupported_claims=tuple(summary.get("unsupported_claims", ())),
        caveats=caveats,
        rows=tuple(rows),
        findings=tuple(findings),
    )


def render_markdown(matrix: ClaimsMatrix) -> str:
    """The matrix as a table, for a document that should not hand-maintain one."""
    lines = [
        f"Dataset `{matrix.dataset_version}`. "
        f"{len(matrix.rows)} claims, {len(matrix.caveats)} published caveats.",
        "",
        "| Claim | Provider | Evidence | Caveats carried |",
        "|---|---|---|---|",
    ]
    for row in matrix.rows:
        evidence = f"`{row.source_artifact}`" if row.source_artifact else "—"
        codes = ", ".join(f"`{c}`" for c in row.caveat_codes) or "**none**"
        lines.append(
            f"| **{row.experiment_id}** — {row.conclusion} | {row.provider} | {evidence} | {codes} |"
        )
    lines += ["", "**Supported claim.** " + matrix.supported_claim, "", "**Explicitly not claimed.**"]
    lines += [f"- {claim}" for claim in matrix.unsupported_claims]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    use_utf8_output()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    args = parser.parse_args(argv)

    try:
        matrix = build_matrix()
    except FileNotFoundError as error:
        print(f"cannot run: {error}", file=sys.stderr)
        return EXIT_UNAVAILABLE

    if args.format == "json":
        print(json.dumps(matrix.as_record(), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(render_markdown(matrix))

    if matrix.findings:
        print(f"\n{len(matrix.findings)} FINDING(S):", file=sys.stderr)
        for finding in matrix.findings:
            print(f"  {finding}", file=sys.stderr)
        return EXIT_FINDINGS

    print("\nEvery claim names its evidence and carries at least one published caveat.")
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
