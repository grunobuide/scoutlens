# artifacts/

Mostly gitignored — generated experiment outputs (plots, exported tables) land
here locally and aren't committed. **A short list of small exceptions, versioned
because they're the machine-readable numbers backing the docs in
[`../docs/`](../docs)**, not because raw data belongs here:

- `gate2_results.json` — [`run_report.py`](../src/scoutlens/evaluation/run_report.py); backs `feasibility-report.md` / `context-diagnostics.md`.
- `robustness_results.json` — [`run_robustness.py`](../src/scoutlens/evaluation/run_robustness.py); backs `robustness-checks.md`.
- `transfer_analysis_results.json` — [`run_transfer_analysis.py`](../src/scoutlens/evaluation/run_transfer_analysis.py); backs `transfer-analysis.md`.
- `statsbomb_replication_results.json` — [`statsbomb/replication.py`](../src/scoutlens/statsbomb/replication.py); backs `statsbomb-replication.md`.
- `shrinkage_experiment_results.json` — [`run_shrinkage_experiment.py`](../src/scoutlens/evaluation/run_shrinkage_experiment.py); backs `shrinkage-experiment.md`.
- `chance_control_results.json` — [`run_chance_control.py`](../src/scoutlens/evaluation/run_chance_control.py); backs `chance-level-control.md`.
- `benchmark/split-manifest.json` and `benchmark/frozen-baselines.json` — [`run_preregistration.py`](../src/scoutlens/benchmark/run_preregistration.py); back `representation-benchmark-protocol.md` (D041). The split manifest carries the protocol hash, split seed and assignment digest; the baselines file carries the frozen Baseline A/B reference values that `scoutlens-qop.2`/`.3`/`.4` measure their delta against, so a clone can check a claimed improvement without local Wyscout data.
- `benchmark/diagonal-results.json` — [`run_diagonal.py`](../src/scoutlens/benchmark/run_diagonal.py); backs `diagonal-metric-benchmark.md` (D042). Carries every regularization arm, the 28 learned weights, their stability across the grid, role subgroups, costs and the `CONTINUE_NEURAL` / `STOP_NEURAL` decision. Its `cost` timings and `artifact_bytes` are observations of the run, not results, and are excluded from the byte-identity check.
- `benchmark/neural-results.json` — [`run_neural.py`](../src/scoutlens/benchmark/run_neural.py); backs `neural-contrastive-benchmark.md` (D043). Carries the gate evidence read from qop.2, all four architecture arms with learning curves and checkpoint digests, the three-way cosine/diagonal/neural comparison on shared pools, calibration, subgroups, failure cases and costs. Same exclusions as above, plus `peak_rss_bytes`.
- `benchmark/decision-results.json` — [`run_decision.py`](../src/scoutlens/benchmark/run_decision.py); backs `keep-drop-decision.md` (D045). Carries the protocol-lineage proof, the untouched StatsBomb cross-provider evaluation, every KEEP clause with its evidence and pass/fail, and the final outcome. Its `budgets.decision_harness_observation` block is an observation of the run and is explicitly not a decision input.

- `ai-evals/grounded-explanations-v1.json` — [`explanations/evals/run_report.py`](../src/scoutlens/explanations/evals/run_report.py); backs `ai-eval-method.md` (D057). The grounded-explanation eval corpus, its coverage matrix, the preregistered thresholds and the gate outcome. **Read its `response_source_note` before quoting any number from it:** the replay drives the real adapter path with responses the package synthesises from each bundle, so the file measures the validator, the corpus and the deterministic fallback — not any model. A live model produces separate, differently named telemetry that never overwrites this file. D057 permits this one path; other paths under `ai-evals/` stay gitignored, so a second report needs a second amendment rather than arriving by precedent.

Each is small, always regenerated fresh by its script (never
hand-edited), and small enough that committing them lets a clone inspect
the exact published numbers without re-running the pipeline or having the
raw data locally. This does not extend to raw or processed data itself —
`data/` stays fully gitignored.

## Provenance and drift checking (D015)

Every artifact **except the AI eval report** embeds a `_manifest` recording
exactly what produced it:
the resolved experiment parameters (from the versioned
[`config/experiment.json`](../config/experiment.json), plus that file's
own sha256), the git commit, whether tracked files differed from that
commit, a stable sha256 over every Python file in `src/scoutlens/`, the
Python/Polars/platform versions, and a sha256 + byte size for every input
Parquet the run read. The source hash is authoritative for uncommitted
runs: it prevents `HEAD` alone from making a false provenance claim. Two
artifacts whose manifests agree on everything but `generated_at` came
from the same code, config, and data bytes.

`ai-evals/grounded-explanations-v1.json` is the one exception, and deliberately
so. A `_manifest` carries `generated_at` and the git commit, which would make
the file differ between two runs of the same command — and for that artifact
byte-identity is the *only* available meaning of determinism, because its other
possible input is a model (D057 §4.6). It binds itself to its inputs instead:
every bundle digest, the prompt-contract and output-schema versions, the adapter
identity, and a digest over the exact response set replayed. Two runs over the
same payload produce the same bytes, and `run_report --check` is what proves the
committed copy is one of them.

Two test layers keep artifacts, docs, and code in agreement:

- [`tests/evaluation/test_artifacts.py`](../tests/evaluation/test_artifacts.py)
  (runs in the default suite) pins the checked-in artifacts to the
  headline numbers quoted in `docs/*.md`.
- [`tests/evaluation/test_artifact_drift.py`](../tests/evaluation/test_artifact_drift.py)
  (opt-in — needs both local datasets, takes a few minutes) regenerates all
  six result sets from scratch and compares them against the checked-in
  artifact number-by-number, CI bounds included:

  ```
  SCOUTLENS_DRIFT=1 uv run pytest tests/evaluation/test_artifact_drift.py
  ```

If either layer fails after an intentional change (to the config, the
data, or the evaluation code), regenerate the artifacts with the three
Wyscout `scoutlens.evaluation.run_*` commands plus
`scoutlens.statsbomb.replication` and
`scoutlens.evaluation.run_shrinkage_experiment`, update the doc prose that
quotes them, and commit all of it together.
