# artifacts/

Mostly gitignored — generated experiment outputs (plots, exported tables) land
here locally and aren't committed. **Six small exceptions, versioned
because they're the machine-readable numbers backing the docs in
[`../docs/`](../docs)**, not because raw data belongs here:

- `gate2_results.json` — [`run_report.py`](../src/scoutlens/evaluation/run_report.py); backs `feasibility-report.md` / `context-diagnostics.md`.
- `robustness_results.json` — [`run_robustness.py`](../src/scoutlens/evaluation/run_robustness.py); backs `robustness-checks.md`.
- `transfer_analysis_results.json` — [`run_transfer_analysis.py`](../src/scoutlens/evaluation/run_transfer_analysis.py); backs `transfer-analysis.md`.
- `statsbomb_replication_results.json` — [`statsbomb/replication.py`](../src/scoutlens/statsbomb/replication.py); backs `statsbomb-replication.md`.
- `shrinkage_experiment_results.json` — [`run_shrinkage_experiment.py`](../src/scoutlens/evaluation/run_shrinkage_experiment.py); backs `shrinkage-experiment.md`.
- `chance_control_results.json` — [`run_chance_control.py`](../src/scoutlens/evaluation/run_chance_control.py); backs `chance-level-control.md`.

Each is small, always regenerated fresh by its script (never
hand-edited), and small enough that committing them lets a clone inspect
the exact published numbers without re-running the pipeline or having the
raw data locally. This does not extend to raw or processed data itself —
`data/` stays fully gitignored.

## Provenance and drift checking (D015)

Every artifact embeds a `_manifest` recording exactly what produced it:
the resolved experiment parameters (from the versioned
[`config/experiment.json`](../config/experiment.json), plus that file's
own sha256), the git commit, whether tracked files differed from that
commit, a stable sha256 over every Python file in `src/scoutlens/`, the
Python/Polars/platform versions, and a sha256 + byte size for every input
Parquet the run read. The source hash is authoritative for uncommitted
runs: it prevents `HEAD` alone from making a false provenance claim. Two
artifacts whose manifests agree on everything but `generated_at` came
from the same code, config, and data bytes.

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
