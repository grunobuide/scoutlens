# ScoutLens — Feasibility Spike Charter (operational)

Source: [`00_ScoutLens_Project_Brief_v1.md`](00_ScoutLens_Project_Brief_v1.md)
(frozen). Adjustments made after discussion are in
[`decisions-log.md`](decisions-log.md); this file is the living, operational
summary — update it if a decision changes scope, not the brief.

## Decision question (immutable for the duration of the spike)

> Is there enough signal in the available event data to justify ScoutLens as
> a flagship project?

## Timebox

10 working days. Execution mode: incremental, task-by-task, with review
before proceeding to the next task ([D002](decisions-log.md#d002--2026-07-20--execution-mode-pair-programming-incremental)).
If the timebox is at risk, cut scope in the order defined in
[D003](decisions-log.md#d003--2026-07-20--scope-cut-order-if-the-10-day-timebox-is-at-risk).

## Research question

> Can football event data be used to build stable, interpretable
> player-role representations that support evidence-based recruitment
> searches?

## Outcome

`GO`, `PIVOT`, or `KILL` — recorded explicitly in the final feasibility
report, evaluated against the gates in brief section 8.

## Analytical unit

`player × temporal period` (player × chronological half-season split,
conditional on sufficient minutes in both periods).

## Primary experiment

Temporal Role Stability Experiment: same-player retrieval across two
chronological periods, using event-derived per-90 features + cosine
similarity as Baseline B, compared against a `same role → nearest minutes`
trivial Baseline A.

## Explicitly out of scope for this spike

Deep learning, learned embeddings, clustering, LLM, agent, RAG, user
interface. These must earn their place after the spike, not before.

## Maximum permitted claim after the spike

> Event-derived profiles show sufficient evidence of [stable / unstable]
> player-role signal to justify [continuing / restricting / discontinuing]
> the ScoutLens research program.

Never: "ScoutLens finds the best players to sign."

## Stack decisions

- Data processing: Polars + Parquet ([D001](decisions-log.md#d001--2026-07-20--data-stack-polars--parquet)).
- Raw data lives outside Git (`data/` is gitignored; only a `README.md` and
  the manifest are tracked).

## Gates (full criteria in the brief, section 8)

- **Gate 0 — Provenance:** license verified directly on the Figshare
  artifact page before inventory/manifest work starts
  ([D004](decisions-log.md#d004--2026-07-20--license-must-be-verified-on-the-figshare-artifact-page-directly-before-sls-002sls-003)).
- **Gate 1 — Data:** ~≥1,000 eligible players (GO) / ~500–999 (PIVOT) /
  below that even after defensible relaxation (KILL). Minutes reconstruction
  follows the 80/20 rule — don't over-invest before checking Gate 1 clears
  ([D005](decisions-log.md#d005--2026-07-20--minutes-reconstruction-8020-rule-dont-chase-every-edge-case-in-v1)).
- **Gate 2 — Analytical signal:** Baseline B must beat Baseline A with a
  quantified confidence interval, on at least one primary metric (MRR of
  same-player temporal retrieval), and hold up within-role. No fixed
  magic-number threshold — the criterion is improvement + CI + robustness
  across strata.

## Known risk flagged for the sensitivity analysis

The ≥450 minutes/split starting threshold is noise-prone at that sample
size; low stability scores near the threshold may reflect sample noise, not
genuine role change ([D006](decisions-log.md#d006--2026-07-20--450-minute-threshold-flagged-as-a-known-noise-risk-not-just-a-parameter)).
Must appear explicitly in the final report's limitations section.

## Task backlog

SLS-001 through SLS-023, as listed in the brief section 10. Tracked
incrementally; see session work for current status rather than duplicating
a live checklist here.
