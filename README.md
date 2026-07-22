# ScoutLens — Feasibility Spike

**Decision question:**

> Is there enough signal in the available event data to justify ScoutLens
> as a flagship project?

**Answer: yes — GO.** The spike is complete; see
[`docs/feasibility-report.md`](docs/feasibility-report.md) for the full
executive summary, results, limitations, and recommended next
experiment. See [`docs/project-charter.md`](docs/project-charter.md) for
the charter, gates, and the maximum claim this spike is allowed to make.

## Status

| Gate | Status |
|---|---|
| Gate 0 — Provenance | **GO** — [`docs/data-provenance.md`](docs/data-provenance.md) |
| Gate 1 — Data | **GO** — [`docs/gate-1-decision.md`](docs/gate-1-decision.md). 1,969 eligible players at ≥450 min/season, 99.72% clean minutes derivation, 99.97% join integrity. |
| Gate 2 — Analytical signal | **GO** — [`docs/gate-2-decision.md`](docs/gate-2-decision.md). Baseline B (standardized features + cosine) beats the trivial baseline ~10x on MRR, holding up within-role, with confounds checked and minor. |

Task-by-task progress against the backlog (SLS-001…023, defined in the
brief) is tracked in-session, not duplicated here as a static checklist —
see recent commit history for what's landed.

## Start here

1. **[`docs/feasibility-report.md`](docs/feasibility-report.md) — the final report. Start here if you only read one document.**
2. [`docs/00_ScoutLens_Project_Brief_v1.md`](docs/00_ScoutLens_Project_Brief_v1.md) — the frozen original brief. Source of truth for scope; never edited.
3. [`docs/project-charter.md`](docs/project-charter.md) — operational charter derived from the brief.
4. [`docs/decisions-log.md`](docs/decisions-log.md) — every adjustment made to the brief during execution, with the reasoning (append-only).
5. [`docs/data-provenance.md`](docs/data-provenance.md) · [`data-dictionary.md`](docs/data-dictionary.md) · [`data-quality-report.md`](docs/data-quality-report.md) — data acquisition, schema, and validation.
6. [`docs/minutes-derivation.md`](docs/minutes-derivation.md) · [`eligible-population.md`](docs/eligible-population.md) · [`gate-1-decision.md`](docs/gate-1-decision.md) — minutes reconstruction and Gate 1.
7. [`docs/feature-definitions.md`](docs/feature-definitions.md) · [`chronological-split.md`](docs/chronological-split.md) · [`baseline-b-standardization.md`](docs/baseline-b-standardization.md) — modeling setup.
8. [`docs/temporal-retrieval-global.md`](docs/temporal-retrieval-global.md) · [`temporal-retrieval-within-role.md`](docs/temporal-retrieval-within-role.md) · [`context-diagnostics.md`](docs/context-diagnostics.md) · [`error-analysis.md`](docs/error-analysis.md) · [`gate-2-decision.md`](docs/gate-2-decision.md) — results and Gate 2.

## Setup

Requires [`uv`](https://docs.astral.sh/uv/) (manages the Python version and
virtualenv — no separate Python install needed).

```
uv sync
```

## Running the pipeline so far

```
# Download the 7 core Wyscout artifacts, verify checksums, convert to Parquet
uv run python -m scoutlens.data.ingestion

# Reconstruct minutes played per player x match (writes minutes.parquet)
uv run python -m scoutlens.data.minutes

# Run structural + relational validation against the processed data
uv run python -m scoutlens.data.validation

# Regenerate every number in feasibility-report.md's results sections
# (retrieval experiments, diagnostics, minutes sensitivity curve) --
# writes artifacts/gate2_results.json
uv run python -m scoutlens.evaluation.run_report

# Run the test suite
uv run pytest
```

Raw and processed data are **not** committed — `data/` is gitignored.
Re-running `ingestion` reproduces `data/raw/` and `data/processed/` from
scratch, and regenerates [`docs/data-manifest.csv`](docs/data-manifest.csv)
with fresh checksums and timestamps.

## Data license and attribution

Source data is [`Pappalardo, L., Cintia, P., Rossi, A. et al.`](docs/data-provenance.md),
*A public data set of spatio-temporal match events in soccer competitions*,
Scientific Data 6:236 (2019), CC BY 4.0. See
[`DATA_LICENSES.md`](DATA_LICENSES.md) for the full attribution requirement
and per-artifact verification. **Not redistributed in this repo** — only
acquisition code and the manifest are tracked; raw files are downloaded
fresh by `ingestion.py`.

The license for ScoutLens's own code (this repository's Python source,
independent of the CC BY 4.0 data license above) has not been decided yet.

## Repository layout

```
docs/          — charter, decisions log, data provenance/dictionary/quality docs
src/scoutlens/ — pipeline code (data/, features/, evaluation/)
tests/         — pytest suite, mirrors src/ structure
configs/       — spike configuration (not yet populated)
notebooks/     — exploratory notebooks (not yet populated); see the brief's
                 "notebooks ask questions, modules produce answers" rule —
                 reusable logic belongs in src/, not notebook cells
data/          — gitignored; raw/processed artifacts live here locally
artifacts/     — gitignored; spike output artifacts (plots, reports) go here
```

Deliberately not created yet: `api/`, `agents/`, `rag/`, `frontend/`,
`services/` — out of scope for a feasibility spike (see the charter's
"explicitly out of scope" section).
