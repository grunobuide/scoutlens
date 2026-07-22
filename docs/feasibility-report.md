# ScoutLens Data & Modeling Feasibility Report

**Spike duration:** 2026-07-20 to 2026-07-22 (accelerated from the
charter's 10-working-day estimate — see note on pacing in the closing
section). **Status: complete. Both gates GO.**

---

## Executive Summary

The decision question this spike was commissioned to answer:

> Is there enough signal in the available event data to justify
> ScoutLens as a flagship project?

**Answer: yes.** Event-derived, standardized player statistics, compared
by cosine similarity, recover a player's own second-half-of-season
statistical profile from their first-half-of-season profile far better
than a trivial role-and-minutes baseline — a ~10x improvement in Mean
Reciprocal Rank, holding up (if anything strengthening) when the
comparison is restricted to players who already share a nominal
position, and not substantially explained by shared team or league. Both
formal gates in the charter were cleared with margin, not marginally.

**Maximum permitted claim, per the charter, now supported by evidence:**

> Event-derived profiles show sufficient evidence of **stable**
> player-role signal to justify **continuing** the ScoutLens research
> program.

**Not supported, and not claimed:** that ScoutLens finds good players to
sign, that this generalizes beyond the five domestic leagues studied, or
that the specific feature catalog used here is final.

## Research Question

> Can football event data be used to build stable, interpretable
> player-role representations that support evidence-based recruitment
> searches?

This spike tested the *stability* half of that question directly (same
statistical fingerprint, two points in time) and deliberately did not
test the *recruitment search* half — see Limitations.

## Data Provenance & License Assessment

Source: Pappalardo, Cintia, Rossi et al., *A public data set of
spatio-temporal match events in soccer competitions*, Scientific Data 6:236
(2019), via Figshare (DOI `10.6084/m9.figshare.c.4415000`, v5). **CC BY
4.0, verified individually on each of the 7 consumed artifacts' own
Figshare item pages** (not inferred from the paper text) — see
[`data-provenance.md`](data-provenance.md) and
[`DATA_LICENSES.md`](../DATA_LICENSES.md). No redistribution blocker;
this repository does not redistribute the raw data regardless (only
acquisition code + manifest are tracked). **Gate 0: GO.**

## Dataset Audit

7 core artifacts acquired reproducibly (checksums pinned against
Figshare's own reported hashes) and profiled empirically — see
[`data-dictionary.md`](data-dictionary.md). Highlights:

- 1,941 matches (exact match to the paper), 3,251,294 events (matches the
  paper's ~3.25M), 142 teams, 7 competitions (5 domestic leagues + Euro
  2016 + World Cup 2018).
- 3,603 players in `players.json` — **below the paper's stated 4,299**,
  unexplained, flagged rather than silently resolved.
- Match-level position confirmed genuinely absent (only a single
  `players.role` per player) — the brief's section 3.2 concern, closed
  out empirically.
- `redCards`/`yellowCards` were found to encode the **minute of the
  card**, not a count — a non-obvious schema property essential to
  getting minutes-played and any card-related feature right.
- `interception` tag was verified (via co-occurrence analysis) to mark
  the *acting* player's own action, not "this event was intercepted."
- Automated validation: [`data-quality-report.md`](data-quality-report.md)
  — 39 ok / 5 warn / 1 fail (of 45 checks); the one fail (15 bench-only
  player ids absent from `players.json`) is fully explained and
  inconsequential (all involved rows are 0-minute).

## Minutes Reconstruction

Flagged in the brief as the single biggest technical risk. Turned out
much cleaner than feared: `hasFormation` present in 100% of team-match
entries, lineup always exactly 11 players — no `missing_formation` case
exists in this dataset. **99.72% of the 74,098 player-match rows derived
`clean`**; the remaining 0.28% are stoppage-time substitute entries with
no recoverable true final-whistle minute, conservatively floored at 0
minutes and flagged (`substitution_conflict`), not guessed. Full writeup:
[`minutes-derivation.md`](minutes-derivation.md).

## Eligible Population

Season-level: **1,969 distinct eligible players** at ≥450 min/season,
well past the charter's ~1,000-player Gate 1 bar, across all 4 roles and
all 5 domestic leagues ([`eligible-population.md`](eligible-population.md)).

The stricter population actually used for retrieval — eligible at ≥450
min in **each** chronological half separately, keyed on
`player × competition × period` per
[D007](decisions-log.md#d007--2026-07-22--sls-015-temporal-split-must-key-on-player--competition--period)
— is **1,257 player×competition combinations** across the five domestic
leagues. World Cup 2018 and Euro 2016 drop to **zero and near-zero**
eligible players respectively once split into two periods (a tournament
squad member cannot accumulate enough minutes within one period alone) —
confirmed empirically in [`chronological-split.md`](chronological-split.md),
not just anticipated. Both competitions remain in the dataset for
qualitative purposes by deliberate decision
([`gate-1-decision.md`](gate-1-decision.md)), excluded only from the
quantitative headline numbers.

**Gate 1: GO** — recorded in full at [`gate-1-decision.md`](gate-1-decision.md).

## Feature Definitions

**32 event-derived features** across 8 families (passing, progression,
chance creation, shooting, defensive actions, spatial tendencies,
possession involvement, carrying-as-proxy) — every definition grounded in
verified tag/subevent co-occurrence evidence, not assumed from field
names. `assist`/`keyPass` tags gave a direct chance-creation signal with
no need for a modeled xA proxy. Carrying is explicitly and consistently
labeled a proxy throughout (no native carry event exists in this
dataset). "Sequence involvement" was cut from v0 entirely — buildable in
principle but needing a possession-break-detection rule with no
obviously-correct definition, exactly the kind of complexity to drop
first under the charter's scope-priority rule
([D003](decisions-log.md#d003--2026-07-20--scope-cut-order-if-the-10-day-timebox-is-at-risk)).
Full catalog: [`feature-definitions.md`](feature-definitions.md).

## Temporal Split

Deterministic, per competition: matches sorted by `dateutc`, split by
match count at the midpoint (never splitting an individual match's
events). Domestic leagues split evenly (19/19 match-days); the two short
international tournaments split close to evenly by count, which given
their duration means "most of the group stage" vs. "rest of group stage
plus knockouts," not a comparable calendar-time split to the leagues.
Full writeup: [`chronological-split.md`](chronological-split.md).

## Baselines

- **Baseline A** (trivial): same nominal role → nearest minutes played.
  Full ranking, not a same-role filter, so it plugs into the same
  rank-based metrics as Baseline B.
- **Baseline B**: z-score standardized features + cosine similarity.
  Standardization fit once on the full combined query+candidate
  population per comparison; null ratio features (e.g. a center-back's
  `shot_conversion_pct`) mean-imputed *before* standardizing, landing at
  exactly z=0 ("uninformative"), not a fabricated extreme — resolves
  [D008](decisions-log.md#d008--2026-07-22--feature-normalizationnull-handling-strategy).
  Full writeup: [`baseline-b-standardization.md`](baseline-b-standardization.md).

## Temporal Stability Results

**Global condition** (five domestic leagues, 1,257 queries, candidate
pool pooled across all five leagues):

| Metric | Baseline A | Baseline B |
|---|---|---|
| MRR | 0.0256 | **0.2539** |
| Median rank (of 1,257) | 128 | **16** |
| Recall@1 | 0.32% | **16.2%** |
| Recall@10 | 4.85% | **43.3%** |

MRR delta (B−A): **+0.228, 95% bootstrap CI [0.208, 0.248]** — excludes 0
by a wide margin. Full writeup: [`temporal-retrieval-global.md`](temporal-retrieval-global.md).

**Within-role condition** (candidate pool restricted to the query's
nominal role, ~391 candidates on average):

| Metric | Baseline A | Baseline B |
|---|---|---|
| MRR | 0.0256 (identical to global — explained below) | **0.2787** |
| Median rank | 128 | **12** |
| Recall@10 | 4.85% | **47.7%** |

MRR delta: **+0.253, 95% CI [0.232, 0.274]** — at least as large as the
global delta. Baseline A's numbers are *structurally* unchanged by the
role restriction (it already sorts same-role candidates first, so a
different-role candidate could never have out-ranked the true match in
the global pool either) — this makes it a *stronger*, not weaker,
comparison here, not a redundant repeat of the global result. Full
writeup: [`temporal-retrieval-within-role.md`](temporal-retrieval-within-role.md).

**This is the spike's central finding for H4:** Baseline B's advantage
over a method that gets role-matching for free does not shrink, and if
anything grows slightly, once role stops being able to explain any of
it. The signal is not merely "finding another player in the same
position."

## Position / Minutes / League Diagnostics

- **Team confound:** 4.79% of top-10 neighbors share the query's primary
  team, vs. 1.05% expected under squad-size-weighted random selection
  (~4.6x enrichment) — real, but still a small minority: 95.2% of
  neighbors play for a different team.
- **League confound:** 25.0% observed vs. 20.1% expected
  (league-size-weighted) — close to negligible.
- **Minutes sensitivity** (resolves [D006](decisions-log.md#d006--2026-07-20--450-minute-threshold-flagged-as-a-known-noise-risk-not-just-a-parameter)):
  ran the full experiment at six thresholds from 225 to 1,350 min/period.
  The B−A delta's CI stays clear of 0 at **every** threshold and
  strengthens (not weakens) with more data — the ≥450-minute primary
  threshold is not sitting on a fragile edge case.
- **By-role signal:** Goalkeeper is the weakest stratum (MRR 0.129),
  plausibly because the feature catalog is built almost entirely around
  outfield actions; Midfielder and Forward are strongest (0.36, 0.33).

Full writeup: [`context-diagnostics.md`](context-diagnostics.md).

## Qualitative Error Analysis

Individual-level `corr(minutes, reciprocal rank) = 0.18` — real but
modest; minutes alone don't explain most retrieval-quality variance.
Investigating the 4 worst-ranked cases directly: only 1 of 4 fit the
"small sample" pattern cleanly (a player right at the eligibility floor
in one period); the other 3 had ample minutes in both periods and stayed
at the same club — their profile shifts are plausibly real (tactical
role change, squad rotation), not data artifacts. Close-miss cases (rank
2) were football-coherent: Kyle Walker's top rival was fellow
attacking-fullback Elseid Hysaj; Morgan Schneiderlin's was fellow
defensive midfielder Julian Weigl-type profiles — evidence of
finer-grained sub-role signal, not arbitrary confusion. Full writeup:
[`error-analysis.md`](error-analysis.md).

## Known Limitations

1. **Quantitative results cover the five domestic leagues only.** Euro
   2016 / World Cup 2018 stay in the dataset for qualitative use but
   their period-eligible population is near-zero.
2. **Same-player retrieval tests representation *stability*, not
   recruitment quality.** A stable fingerprint is a prerequisite for a
   recruitment-oriented similarity search to make sense — it is not
   evidence that such a search would produce good recruitment decisions.
   This is the single most important boundary on the claim above.
3. **Carrying features are explicit proxies** (`carry_proxy_p90`,
   `carry_distance_proxy_p90`, `take_on_success_pct`) — no native carry
   event exists in this dataset.
4. **Sequence involvement was never built** — cut from the v0 catalog
   entirely under the scope-priority rule.
5. **Two sentinel-encoding ambiguities remain unresolved by design**:
   `players.foot`'s `""` vs. `null`, and `weight`/`height`'s `0`-as-sentinel.
   Currently inconsequential (no anthropometric feature is used) but
   flagged, not silently fixed.
6. **The 3,603 vs. 4,299 players discrepancy** against the paper's
   stated count is still unexplained.
7. **Goalkeepers are the weakest-signal role**, consistent with an
   outfield-action-heavy feature catalog — a goalkeeper-specific feature
   family is the most obvious near-term extension.
8. **Nominal role is broad** (4 categories) — the error analysis suggests
   real, finer sub-role structure exists (attacking vs. defensive
   fullback, for example) that this spike didn't attempt to model
   directly, only observed as a byproduct.
9. **Code license for this repository is still undecided** (independent
   of the CC BY 4.0 data license), deferred by the user pending public
   positioning of the project.

## GO / PIVOT / KILL Decision

**GO.**

Both gates cleared, several criteria with considerable margin rather than
marginally:

- **Gate 0 (Provenance):** GO — [`gate-1-decision.md`](gate-1-decision.md) §Evidence table.
- **Gate 1 (Data):** GO — 1,969 eligible players (season-level), 99.72%
  clean minutes, 99.97% join integrity, all comfortably past threshold.
- **Gate 2 (Analytical signal):** GO — Baseline B beats the trivial
  baseline by ~10x on MRR, with a confidently non-zero CI, in both the
  global and (critically) the within-role condition, with confounds
  checked and found minor, and with errors that have identifiable,
  heterogeneous causes rather than being unexplained.

This supports: **continuing the ScoutLens research program**, scoped
initially to the five domestic leagues studied, with the stability claim
established but the recruitment-search claim explicitly not yet tested.

## Recommended Next Experiment

In priority order:

1. **Test whether added model complexity earns its place**, per the
   charter's own gating principle. Baseline B (standardized features +
   cosine) is now the standard to beat — the next legitimate question is
   whether a learned representation (e.g. a simple learned embedding,
   metric learning, or feature reweighting) meaningfully outperforms it,
   not whether it's more sophisticated-sounding. Given how strong the
   simple baseline already is, the burden of proof is real.
2. **Goalkeeper-specific features.** The weakest-signal role by a clear
   margin, and the most obvious gap in the current feature catalog
   (positioning, distribution under pressure, claim/punch tendencies —
   none currently captured).
3. **A genuinely different validation methodology for the recruitment
   claim**, since same-player retrieval cannot speak to it: expert
   scout review of shortlists, or a downstream-task validation, before
   any product surface is built on top of the similarity search.
4. **Extend to more seasons and leagues** before generalizing beyond this
   single 2017/18 snapshot — particularly before drawing conclusions
   about the two international competitions, whose population was too
   small here to support any quantitative claim at all.
5. **Resolve the players-count discrepancy** against the source paper —
   low cost, closes a standing question rather than carrying it forward
   indefinitely.

## Note on Pacing

The charter allotted 10 working days; this spike's tasks (SLS-001–023)
were completed across 3 calendar days via continuous iterative
development with the user reviewing and merging each stage. This does
not change the substance of any gate decision — every criterion in the
charter was evaluated on its own terms — but is noted here because the
charter's checkpoints (e.g. "Friday's Data Feasibility Report v0.1") were
time-based assumptions that didn't end up governing the actual pace of
work.
