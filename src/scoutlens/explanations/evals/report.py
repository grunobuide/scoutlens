"""Assemble the recorded report, and bind it to the inputs that produced it.

`D057` section 4.6 is the specification this module implements. Three properties,
and each one is a line of code you can point at:

1. **Offline.** Nothing here imports an HTTP client, reads an environment
   variable, or constructs anything but `ScriptedAdapter` and `FaultAdapter`.
   The command generates with no credential present because there is nothing for
   a credential to be used by.
2. **Bound to its inputs.** The report records every bundle digest, the
   prompt-contract version, the output-schema version, the adapter identity and
   a digest over the exact response set that was replayed. Two runs over the
   same artifacts are byte-identical, which is section 4.1's condition 2 and, for
   an artifact whose other possible input is a model, the only thing
   byte-identity can mean.
3. **Not a model result.** `response_source` says `synthesised`, and the live
   gate says `not_run` until a live run is recorded separately. Nothing in this
   file can produce a number about a model, which is the point: a live number
   that reached a document by this path would arrive with the authority of a
   reproducible one.

Nothing time-varying appears in the artifact. No timestamp, no host, no latency,
no path. Those belong in a run manifest for an artifact that has one, and here
they would simply make condition 2 impossible to satisfy.
"""

from __future__ import annotations

from typing import Any

from scoutlens.explanations.evals.corpus import (
    ALIGNMENT_BANDS,
    CORPUS_VERSION,
    ShowcaseArtifacts,
    alignment_matrix,
    build_corpus,
    coverage_matrix,
    materialise,
)
from scoutlens.explanations.evals.metrics import compute_metrics
from scoutlens.explanations.evals.responses import RESPONSE_SET_VERSION
from scoutlens.explanations.evals.runner import SYNTHESISED, CorpusRun, run_corpus
from scoutlens.explanations.evals.thresholds import (
    PREREGISTERED,
    Thresholds,
    evaluate_deterministic_gate,
    evaluate_live_gate,
)
from scoutlens.explanations.policy import CONTRACT, OUTPUT_SCHEMA_VERSION
from scoutlens.explanations.prompt import PROMPT_CONTRACT_VERSION
from scoutlens.showcase.io import canonical_json_bytes, sha256_bytes

REPORT_CONTRACT = f"{CONTRACT}.evals"
REPORT_SCHEMA_VERSION = "1.0.0"

#: The only command permitted to write this artifact (modeling contract section 4.2).
GENERATED_BY = "uv run --frozen python -m scoutlens.explanations.evals.run_report"

#: What the replay is, in one sentence, inside the artifact itself.
#:
#: Written into the file rather than left to the method document because the
#: number most likely to be quoted out of context is the one in the file, and a
#: reader who quotes `as_expected: 1.0` should not be able to do it without
#: seeing what produced it.
RESPONSE_SOURCE_NOTE = (
    "Responses are synthesised deterministically from each bundle by "
    "scoutlens.explanations.evals.responses and mutations. No model produced them. "
    "This report measures the validator, the corpus and the deterministic fallback. "
    "It is not evidence about any model's behaviour; only a live run is that, and a "
    "live run is recorded as telemetry under a separate name."
)


def response_set_digest(artifacts: ShowcaseArtifacts) -> str:
    """SHA-256 over every case's replayed response, keyed by case id.

    This is the "stored-response digest" section 4.6 requires. It changes when a
    case is added, when a mutation changes shape, and when the showcase repins —
    all three of which change what was replayed, and none of which should be
    able to happen invisibly.
    """
    payload = {
        case.case_id: materialise(case, artifacts).response for case in build_corpus()
    }
    return sha256_bytes(canonical_json_bytes(payload))


def bundle_digests(artifacts: ShowcaseArtifacts) -> dict[str, str]:
    """Case id -> the digest of the bundle that case was run against."""
    return {
        case.case_id: materialise(case, artifacts).bundle["bundle_digest"]
        for case in build_corpus()
    }


def build_report(
    run: CorpusRun,
    artifacts: ShowcaseArtifacts,
    *,
    thresholds: Thresholds = PREREGISTERED,
    live_structured_validity: tuple[float, ...] = (),
) -> dict[str, Any]:
    """The full artifact, ready to be written canonically."""
    metrics = compute_metrics(run)
    deterministic = evaluate_deterministic_gate(metrics, thresholds)
    live = evaluate_live_gate(live_structured_validity, thresholds)

    return {
        "contract": REPORT_CONTRACT,
        "schema_version": REPORT_SCHEMA_VERSION,
        "generated_by": GENERATED_BY,
        "corpus_version": CORPUS_VERSION,
        "response_set_version": RESPONSE_SET_VERSION,
        "response_source": run.response_source,
        "response_source_note": RESPONSE_SOURCE_NOTE,
        "inputs": {
            "dataset_version": artifacts.dataset_version(),
            "prompt_contract_version": PROMPT_CONTRACT_VERSION,
            "output_schema_version": OUTPUT_SCHEMA_VERSION,
            "adapter": run.adapter_record(),
            "response_set_digest": response_set_digest(artifacts),
            "bundle_digests": bundle_digests(artifacts),
        },
        "coverage": {
            "dimensions": coverage_matrix(),
            "alignment_bands": {band: list(bounds) for band, bounds in ALIGNMENT_BANDS.items()},
            "alignment_matrix": alignment_matrix(),
        },
        "thresholds": thresholds.as_record(),
        "metrics": metrics.as_record(),
        "gates": {
            "deterministic": deterministic.as_record(),
            "live": live.as_record(),
        },
        "cases": [result.as_record() for result in run.results],
        "failures": [
            result.diagnostic.as_record()
            for result in run.results
            if result.diagnostic is not None
        ],
    }


def replay(artifacts: ShowcaseArtifacts) -> CorpusRun:
    """The offline run the recorded report is built from."""
    return run_corpus(artifacts, response_source=SYNTHESISED)


__all__ = [
    "GENERATED_BY",
    "REPORT_CONTRACT",
    "REPORT_SCHEMA_VERSION",
    "RESPONSE_SOURCE_NOTE",
    "build_report",
    "bundle_digests",
    "replay",
    "response_set_digest",
]
