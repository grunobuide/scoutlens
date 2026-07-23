# artifacts/

Mostly gitignored — generated spike outputs (plots, exported tables) land
here locally and aren't committed. **Three small exceptions, versioned
because they're the machine-readable numbers backing the docs in
[`../docs/`](../docs)**, not because raw data belongs here:

- `gate2_results.json` — [`run_report.py`](../src/scoutlens/evaluation/run_report.py); backs `feasibility-report.md` / `context-diagnostics.md`.
- `robustness_results.json` — [`run_robustness.py`](../src/scoutlens/evaluation/run_robustness.py); backs `robustness-checks.md`.
- `transfer_analysis_results.json` — [`run_transfer_analysis.py`](../src/scoutlens/evaluation/run_transfer_analysis.py); backs `transfer-analysis.md`.

Each is a few KB, always regenerated fresh by its script (never
hand-edited), and small enough that committing them lets a clone inspect
the exact published numbers without re-running the pipeline or having the
raw data locally. This does not extend to raw or processed data itself —
`data/` stays fully gitignored.

## Provenance and drift checking (D015)

Every artifact embeds a `_manifest` recording exactly what produced it:
the resolved experiment parameters (from the versioned
[`config/experiment.json`](../config/experiment.json), plus that file's
own sha256), the git commit, the Python/Polars/platform versions, and a
sha256 + byte size for every input Parquet the run read. Two artifacts
whose manifests agree on everything but `generated_at` came from the
same code, config, and data bytes.

Two test layers keep artifacts, docs, and code in agreement:

- [`tests/evaluation/test_artifacts.py`](../tests/evaluation/test_artifacts.py)
  (runs in the default suite) pins the checked-in artifacts to the
  headline numbers quoted in `docs/*.md`.
- [`tests/evaluation/test_artifact_drift.py`](../tests/evaluation/test_artifact_drift.py)
  (opt-in — needs the local dataset, takes ~2 minutes) regenerates each
  result set from scratch and compares it against the checked-in
  artifact number-by-number, CI bounds included:

  ```
  SCOUTLENS_DRIFT=1 uv run pytest tests/evaluation/test_artifact_drift.py
  ```

If either layer fails after an intentional change (to the config, the
data, or the evaluation code), regenerate the artifacts with the three
`uv run python -m scoutlens.evaluation.run_*` commands above, update the
doc prose that quotes them, and commit all of it together.
