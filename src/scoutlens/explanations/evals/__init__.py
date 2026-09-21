"""Measure whether a grounded explanation stays inside the contract.

`jtt.6.1` said what an explanation may claim and `jtt.6.2` said how a model is
reached. Neither says how often the rules actually hold, and "the validator
looks strict" is not a result. This package answers that mechanically.

The pieces:

* `corpus` - the versioned case set and its coverage matrix. Cases are derived
  from published showcase artifacts, never hand-authored, so the corpus cannot
  drift away from the data it claims to describe.
* `degrade` - named single-property degradations of a validated profile, for the
  conditions the published artifacts do not contain (an absent measurement,
  insufficient uncertainty, a stripped evidence set, a mismatched
  representation).
* `responses` - the deterministic reference explanation for a bundle.
* `mutations` - one named break per way an explanation can lie, each naming the
  validator rule that must fire.
* `fallback` - the typed deterministic explanation used when a model fails or
  its answer is refused. Built only from the bundle, so it is always available.
* `runner` - drives one adapter over the corpus and records what happened.
* `metrics` / `thresholds` - the numbers, and the preregistered bars they are
  judged against. The bars are mechanical: a miss is a `DROP` for that exact
  model, prompt and schema version, not a prompt to retune.
* `report` / `run_report` - the recorded artifact,
  `artifacts/ai-evals/grounded-explanations-v1.json`.

**What the recorded report is evidence of.** The offline replay drives the real
adapter path with deterministic responses this package synthesises from each
bundle. It measures the validator, the corpus and the fallback - the parts this
repository controls - and it is byte-identical between runs, which is the only
thing byte-equality can mean for an artifact whose other possible input is a
model. It is not evidence about any model. Only a live run is that, and a live
run is telemetry under a different name (`D057` section 4.6).
"""

from __future__ import annotations

from scoutlens.explanations.evals.corpus import (
    CORPUS_VERSION,
    Dimension,
    EvalCase,
    Expectation,
    build_corpus,
    coverage_matrix,
)
from scoutlens.explanations.evals.fallback import FallbackReason, deterministic_fallback
from scoutlens.explanations.evals.metrics import CorpusMetrics, compute_metrics
from scoutlens.explanations.evals.runner import CaseResult, CorpusRun, run_case, run_corpus
from scoutlens.explanations.evals.thresholds import (
    PREREGISTERED,
    GateOutcome,
    Thresholds,
    evaluate_deterministic_gate,
    evaluate_live_gate,
)

__all__ = [
    "CORPUS_VERSION",
    "PREREGISTERED",
    "CaseResult",
    "CorpusMetrics",
    "CorpusRun",
    "Dimension",
    "EvalCase",
    "Expectation",
    "FallbackReason",
    "GateOutcome",
    "Thresholds",
    "build_corpus",
    "compute_metrics",
    "coverage_matrix",
    "deterministic_fallback",
    "evaluate_deterministic_gate",
    "evaluate_live_gate",
    "run_case",
    "run_corpus",
]
