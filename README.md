# ScoutLens — Feasibility Spike

**Decision question (fixed for the duration of the spike):**

> Is there enough signal in the available event data to justify ScoutLens
> as a flagship project?

10-working-day timebox. Outcome is `GO`, `PIVOT`, or `KILL` — see
[`docs/project-charter.md`](docs/project-charter.md) for the full charter,
gates, and the maximum claim this spike is allowed to make.

## Status

| Gate | Status |
|---|---|
| Gate 0 — Provenance | **GO** — license verified per-artifact, see [`docs/data-provenance.md`](docs/data-provenance.md) |
| Gate 1 — Data | In progress. Structural + relational validation clean (33 ok, 5 warn, 0 fail — see [`docs/data-quality-report.md`](docs/data-quality-report.md)). Minutes reconstruction and eligible-population sizing not done yet. |
| Gate 2 — Analytical signal | Not started. |

Task-by-task progress against the backlog (SLS-001…023, defined in the
brief) is tracked in-session, not duplicated here as a static checklist —
see recent commit history for what's landed.

## Start here

1. [`docs/00_ScoutLens_Project_Brief_v1.md`](docs/00_ScoutLens_Project_Brief_v1.md) — the frozen original brief. Source of truth for scope; never edited.
2. [`docs/project-charter.md`](docs/project-charter.md) — operational charter derived from the brief.
3. [`docs/decisions-log.md`](docs/decisions-log.md) — every adjustment made to the brief during execution, with the reasoning (append-only).
4. [`docs/data-provenance.md`](docs/data-provenance.md) — where the data comes from, license verification, redistribution stance.
5. [`docs/data-dictionary.md`](docs/data-dictionary.md) — what's actually in each processed table, empirically profiled (not just the source's documented schema).
6. [`docs/data-quality-report.md`](docs/data-quality-report.md) — automated validation results, regenerable.

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

# Run structural + relational validation against the processed data
uv run python -m scoutlens.data.validation

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
