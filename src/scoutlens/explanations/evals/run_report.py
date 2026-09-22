"""Write `artifacts/ai-evals/grounded-explanations-v1.json`.

    uv run --frozen python -m scoutlens.explanations.evals.run_report

This is the only command permitted to produce that file (modeling contract
section 4.2), and the file is never hand-edited. It makes no network call and
needs no credential; on a clone that has not hydrated the showcase payload it
stops and says so rather than writing a report over an empty corpus.

Exit codes are the gate:

* **0** - every case did what the corpus said it would, and every deterministic
  bar was met.
* **1** - a deterministic bar was missed. That is a defect in a guard, not a
  tuning opportunity: the failing cases are printed, and the report is still
  written so the miss is recorded rather than lost to a red terminal.
* **2** - the artifacts are not available.

``--check`` writes nothing and compares the generated report to the one on disk.
That is the CI form: it proves the committed artifact is exactly what the
command produces, which is what makes "regenerated, never edited" checkable
instead of promised.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scoutlens.explanations.artifacts import REPO_ROOT, ShowcaseArtifacts, ShowcaseUnavailable
from scoutlens.explanations.evals.report import build_report, replay
from scoutlens.showcase.io import canonical_json_bytes, write_canonical_json

ARTIFACT_PATH = REPO_ROOT / "artifacts" / "ai-evals" / "grounded-explanations-v1.json"

EXIT_OK = 0
EXIT_GATE_FAILED = 1
EXIT_UNAVAILABLE = 2
EXIT_DRIFTED = 3


def generate(artifacts: ShowcaseArtifacts | None = None) -> tuple[dict, bytes]:
    """Run the offline replay and render the report. Writes nothing."""
    artifacts = artifacts or ShowcaseArtifacts()
    run = replay(artifacts)
    report = build_report(run, artifacts)
    return report, canonical_json_bytes(report)


def _print_summary(report: dict) -> None:
    metrics = report["metrics"]
    gates = report["gates"]
    print(f"corpus {report['corpus_version']}: {metrics['case_count']} cases")
    print(f"  as expected            {metrics['as_expected']['value']}")
    for name in (
        "supported_entity_rate",
        "supported_number_rate",
        "critical_caveat_retention",
        "forbidden_claim_rejection",
        "degraded_fallback_correctness",
        "expected_rule_precision",
    ):
        entry = metrics[name]
        print(f"  {name:<22} {entry['value']} ({entry['passed']}/{entry['count']})")
    print(f"  deterministic gate     {gates['deterministic']['outcome']}")
    print(f"  live gate              {gates['live']['outcome']} - {gates['live']['detail']}")

    for failure in report["failures"]:
        print(f"\nFAIL {failure['case_id']} [{failure['expectation']}]: {failure['summary']}")
        for detail in failure["details"]:
            print(f"     {detail}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="compare against the committed artifact instead of writing it",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ARTIFACT_PATH,
        help="where to write (or which file to check). Defaults to the published path.",
    )
    args = parser.parse_args(argv)

    try:
        report, payload = generate()
    except ShowcaseUnavailable as error:
        print(f"cannot run: {error}", file=sys.stderr)
        return EXIT_UNAVAILABLE

    _print_summary(report)

    if args.check:
        if not args.output.exists():
            print(f"\n{args.output} does not exist", file=sys.stderr)
            return EXIT_DRIFTED
        if args.output.read_bytes() != payload:
            print(
                f"\n{args.output} differs from what this command produces. "
                "Regenerate it; never edit it by hand.",
                file=sys.stderr,
            )
            return EXIT_DRIFTED
        print(f"\n{args.output} matches this command's output")
    else:
        write_canonical_json(args.output, report)
        print(f"\nwrote {args.output}")

    return EXIT_OK if report["gates"]["deterministic"]["outcome"] == "pass" else EXIT_GATE_FAILED


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
