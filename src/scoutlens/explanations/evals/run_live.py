"""Put a real model through the corpus, and record the result as telemetry.

    uv run --frozen python -m scoutlens.explanations.evals.run_live \\
        --adapter mypackage.myadapter:build --runs 3 --output runs/my-model.json

Opt-in by construction: nothing calls this, no test calls this, and the recorded
report never reads its output. `D057` section 4.6 draws the boundary at the
file, and so does this module — it refuses to write anywhere under
`artifacts/ai-evals/`, because that directory holds the offline replay and a
live number landing there would acquire the authority of a reproducible one.

**What a live run measures.** The `ACCEPT` cases only. The rest of the corpus
prescribes an answer, and you cannot ask a model to fabricate a specific
citation on demand without writing the fabrication yourself — at which point you
are measuring your own prose with extra steps. So the headline is structured
validity: how often the model returned something the output schema accepts. The
grounding numbers beside it are real and are *not* the live gate, because the
deterministic gate already holds this repository to them.

**What it never records.** No endpoint URL, no credential, no prompt, no model
prose. An endpoint is often private infrastructure and a URL in a committed file
is a disclosure; the adapter's class is what a reader actually needs to know.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from scoutlens.explanations.adapters.conformance import load_adapter
from scoutlens.explanations.artifacts import ShowcaseArtifacts, ShowcaseUnavailable
from scoutlens.explanations.evals.corpus import CORPUS_VERSION
from scoutlens.explanations.evals.metrics import compute_metrics
from scoutlens.explanations.evals.runner import LIVE, CorpusRun, live_cases, run_corpus
from scoutlens.explanations.evals.thresholds import PREREGISTERED, evaluate_live_gate
from scoutlens.explanations.policy import CONTRACT, OUTPUT_SCHEMA_VERSION
from scoutlens.explanations.prompt import PROMPT_CONTRACT_VERSION
from scoutlens.showcase.io import write_canonical_json

TELEMETRY_CONTRACT = f"{CONTRACT}.evals.live"
TELEMETRY_SCHEMA_VERSION = "1.0.0"

#: The replay report's home. Nothing here may write into it.
FORBIDDEN_OUTPUT_PARENT = "ai-evals"

EXIT_OK = 0
EXIT_DROPPED = 1
EXIT_UNAVAILABLE = 2
EXIT_REFUSED = 4


def endpoint_class(adapter: Any) -> str:
    """A category, never a URL.

    An adapter may name its own; otherwise its class is used. `base_url` is
    deliberately unreachable from here — a private endpoint written into a file
    someone later shares is a disclosure nobody intended.
    """
    declared = getattr(adapter, "endpoint_class", None)
    if isinstance(declared, str) and declared:
        return declared
    return type(adapter).__name__


def _case_telemetry(run: CorpusRun) -> list[dict[str, Any]]:
    """One row per case, with the evidence hash it answered.

    AC4's list, minus the two it asks for "when known": an adapter that does not
    report tokens leaves `None` rather than a guess, which is `AdapterUsage`'s
    rule and not a convention this module is free to relax.
    """
    rows = []
    for result in run.results:
        usage = result.telemetry or {}
        rows.append(
            {
                "case_id": result.case_id,
                "bundle_digest": result.bundle_digest,
                "schema_valid": result.schema_valid,
                "accepted": result.accepted,
                "rules_fired": list(result.rules_fired),
                "used_fallback": result.used_fallback,
                "fallback_reason": result.fallback_reason,
                "input_tokens": usage.get("input_tokens"),
                "output_tokens": usage.get("output_tokens"),
                "latency_ms": usage.get("latency_ms"),
                "cost_usd": usage.get("cost_usd"),
                "attempts": usage.get("attempts"),
                "from_cache": usage.get("from_cache"),
            }
        )
    return rows


def run_once(adapter: Any, artifacts: ShowcaseArtifacts) -> CorpusRun:
    """One pass of the live-eligible cases through ``adapter``."""
    return run_corpus(
        artifacts,
        cases=live_cases(),
        adapter_factory=lambda material: adapter,
        adapter_id=adapter.adapter_id,
        adapter_version=adapter.adapter_version,
        model_id=adapter.model_id,
        response_source=LIVE,
    )


def build_telemetry(adapter: Any, runs: list[CorpusRun]) -> dict[str, Any]:
    """The recordable summary of a live series, with the live gate applied."""
    rates = tuple(compute_metrics(run).structured_validity.value for run in runs)
    gate = evaluate_live_gate(rates, PREREGISTERED)

    return {
        "contract": TELEMETRY_CONTRACT,
        "schema_version": TELEMETRY_SCHEMA_VERSION,
        "corpus_version": CORPUS_VERSION,
        "response_source": LIVE,
        "note": (
            "Live model output. Not reproducible by re-running, and never a substitute "
            "for the offline replay report. A number here reaches a document only after "
            "being recorded as a replay first."
        ),
        "model": {
            "adapter_id": adapter.adapter_id,
            "adapter_version": adapter.adapter_version,
            "model_id": adapter.model_id,
            "endpoint_class": endpoint_class(adapter),
        },
        "versions": {
            "prompt_contract_version": PROMPT_CONTRACT_VERSION,
            "output_schema_version": OUTPUT_SCHEMA_VERSION,
        },
        "thresholds": PREREGISTERED.as_record()["live"],
        "structured_validity_per_run": [round(rate, 6) for rate in rates],
        "gate": gate.as_record(),
        "runs": [
            {"run": index, "metrics": compute_metrics(run).as_record(), "cases": _case_telemetry(run)}
            for index, run in enumerate(runs, start=1)
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--adapter",
        required=True,
        help="module:factory returning an adapter, e.g. mypackage.myadapter:build",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="where to write the telemetry. Must not be under artifacts/ai-evals/.",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=PREREGISTERED.live_runs_required,
        help=f"how many passes to record (default {PREREGISTERED.live_runs_required})",
    )
    args = parser.parse_args(argv)

    if FORBIDDEN_OUTPUT_PARENT in {part.lower() for part in args.output.parts}:
        print(
            f"refusing to write live output under {FORBIDDEN_OUTPUT_PARENT!r}: that is the "
            "offline replay report's directory, and live output never overwrites a recorded "
            "result (D057 section 4.6).",
            file=sys.stderr,
        )
        return EXIT_REFUSED

    adapter = load_adapter(args.adapter)
    artifacts = ShowcaseArtifacts()
    try:
        runs = [run_once(adapter, artifacts) for _ in range(args.runs)]
    except ShowcaseUnavailable as error:
        print(f"cannot run: {error}", file=sys.stderr)
        return EXIT_UNAVAILABLE

    telemetry = build_telemetry(adapter, runs)
    write_canonical_json(args.output, telemetry)

    print(f"model      {telemetry['model']['model_id']} via {telemetry['model']['endpoint_class']}")
    print(f"runs       {telemetry['structured_validity_per_run']}")
    print(f"live gate  {telemetry['gate']['outcome']} - {telemetry['gate']['detail']}")
    print(f"wrote      {args.output}")

    return EXIT_OK if telemetry["gate"]["outcome"] == "pass" else EXIT_DROPPED


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
