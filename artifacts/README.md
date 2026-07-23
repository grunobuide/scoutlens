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
