# ScoutLens — Gate 2 Decision (SLS-022)

**Decision: GO.**

Recorded 2026-07-22, jointly by the user and this session, after
reviewing the evidence below. This is the second and final formal gate of
the charter ([`project-charter.md`](project-charter.md)) — analytical
signal is sufficient to conclude the primary experiment supports
continuing the ScoutLens research program, subject to the stated scope
and limitations.

## Evidence against the brief's Gate 2 criteria

| Criterion | GO requirement | Actual | Source |
|---|---|---|---|
| Baseline B beats Baseline A materially | yes | MRR 0.0256 → 0.2539 (global, ~10x); 0.0256 → 0.2787 (within-role) | [`temporal-retrieval-global.md`](temporal-retrieval-global.md), [`temporal-retrieval-within-role.md`](temporal-retrieval-within-role.md) |
| Gain has a consistent confidence interval | yes | CI excludes 0 at every minutes threshold tested, 225–1,350 min | [`context-diagnostics.md`](context-diagnostics.md) |
| Signal holds up within-role | yes | Within-role delta (+0.253, CI [0.232, 0.274]) is at least as large as the global delta (+0.228, CI [0.208, 0.248]) — structurally can't be explained by Baseline A's free role-matching, since Baseline A's own numbers didn't move | [`temporal-retrieval-within-role.md`](temporal-retrieval-within-role.md) |
| No collapse in the main strata | yes, with a noted exception | Team confound ~4.6x enriched but still a small minority (95.2% of neighbors are a different team); league confound ~1.25x, close to negligible. Goalkeeper is the weakest role stratum (MRR 0.129) but still clearly positive, plausibly because the feature catalog (SLS-013) is built almost entirely around outfield actions | [`context-diagnostics.md`](context-diagnostics.md) |
| Errors are investigable and explicable | yes | Worst cases have identifiable, heterogeneous causes (genuine profile change at 3 of 4 top misses; sample-size noise at 1 of 4) rather than being unexplained; close misses are football-coherent (attacking-fullback and defensive-midfielder sub-clusters), not arbitrary | [`error-analysis.md`](error-analysis.md) |

Every criterion clears, several with considerable margin. This is a
notably cleaner Gate 2 outcome than the charter's own framing anticipated
as the default case — the brief treated "Baseline B beats Baseline A" as
a real open question, not a foregone conclusion.

## What Gate 2 does — and does not — license

Per [`project-charter.md`](project-charter.md), the **maximum permitted
claim** from this spike is:

> Event-derived profiles show sufficient evidence of **stable**
> player-role signal to justify **continuing** the ScoutLens research
> program.

Not, and never: *"ScoutLens finds the best players to sign."* Same-player
temporal retrieval is a test of representation stability, not a
validation of recruitment quality — a stable role fingerprint is a
prerequisite for a recruitment-oriented similarity search to be
meaningful, not proof that such a search produces good recruitment
outcomes. This distinction must appear in the final report's limitations
section (SLS-023), not just here.

## Standing limitations carried into the final report

- **Population scope:** quantitative results are reported on the five
  domestic leagues only. Euro 2016 and World Cup 2018 remain in the
  dataset and in qualitative discussion (Gate 1 decision), but their
  eligible population is near-zero once split into two periods
  ([`chronological-split.md`](chronological-split.md)) — not part of the
  headline numbers.
- **Carrying features are proxies**, not ground truth (no native carry
  event in this dataset — [`feature-definitions.md`](feature-definitions.md)).
- **Sequence involvement** was cut from the feature catalog v0 entirely
  (D003 scope-priority order).
- **Two unresolved sentinel-encoding ambiguities** in `players.foot` and
  `weight`/`height` were flagged, not silently resolved — currently
  inconsequential since no anthropometric feature is in the catalog
  ([`data-quality-report.md`](data-quality-report.md)).
- **players count discrepancy** (3,603 vs. the paper's stated 4,299) is
  still unexplained ([`data-provenance.md`](data-provenance.md)).
- **Code license** for this repository (independent of the CC BY 4.0 data
  license) remains an open decision, deferred by the user.

## Next step

SLS-023: write the final ScoutLens Data & Modeling Feasibility Report,
synthesizing every SLS-00X document into the charter's required
structure, with the GO/PIVOT/KILL decision and recommended next
experiment recorded explicitly.
