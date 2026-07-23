# ScoutLens Data & Modeling Feasibility Report

**Spike duration:** 2026-07-20 to 2026-07-22 (accelerated from the
charter's 10-working-day estimate — see note on pacing in the closing
section). **Status: complete. Both gates GO.** Updated 2026-07-22 twice
with post-spike follow-ups — a robustness battery
([`robustness-checks.md`](robustness-checks.md)) that found and then a
transferred-players analysis ([`transfer-analysis.md`](transfer-analysis.md))
that directly addressed a team-continuity caveat it raised; the gate
decision is unchanged throughout, now with a more precisely qualified and
better-supported account of what it showed. **Follow-up work paused here**
(D012): the natural next step, extending to another season, requires a
new external dataset (this collection has exactly one season per
competition) — scoped in Recommended Next Experiment #1 but not started,
pending feedback and a deliberately separate next project.

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
**One important qualifier, found in follow-up robustness testing:** an
even more trivial baseline that also knows a player's *team* (role + team
+ minutes, no event data) outperforms the full feature-based method by
more than 2x — because eligible players essentially never change clubs
within one season, so team continuity is a very strong prior for "same
player" in this experimental design specifically. This doesn't change the
gate decision (the charter's actual criterion, Baseline B vs. Baseline A,
is unaffected), but it sharpens what "10x better than trivial" should be
understood to mean. **That next validation step was run the same day:**
restricting the retrieval experiment to the 26 eligible players who did
change clubs between the two periods — where the team-based baseline's
advantage cannot structurally apply — shows the team-based baseline
collapsing to chance-level performance, unambiguously. The feature-based
method's advantage over the trivial baseline (Baseline B − A) also
survives, though a closer look at rank distribution and Recall@5/10 (not
just MRR) shows real, moderate degradation for this subset — a smaller,
more mixed win than "unchanged" would suggest. Small sample (n=26); see
the full discussion below.

**Maximum permitted claim, per the charter** (quoted verbatim from
`project-charter.md` — this is the ceiling the charter allows, not
edited here even though the wording is now known to be looser than what
was actually demonstrated):

> Event-derived profiles show sufficient evidence of **stable**
> player-role signal to justify **continuing** the ScoutLens research
> program.

**What this spike actually demonstrated, more precisely — flagged in a
second review round as still worth tightening:** a stable *individual
statistical fingerprint*, not proven role/style representation
specifically. Prefer this framing over the charter's own wording above
when describing results:

> Event-derived profiles show a temporally stable individual statistical
> fingerprint, consistent with — but not sufficient on its own to prove —
> a stable player-role or playing-style representation.

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
nominal position." **A caution on wording, though:** this shows the
extra signal isn't explained by the 4 nominal role categories — it does
not by itself prove the extra signal *is specifically a finer-grained
role/sub-position representation*, as opposed to individual quality,
set-piece duties, team style, or some other idiosyncratic but stable
statistical trait. "Stable player statistical fingerprint" is the claim
this experiment actually supports; "stable player-*role* representation"
is a plausible but not yet proven interpretation of it — see Limitations.

### Follow-up (2026-07-22): a cheap team-based baseline beats Baseline B by 2x+

Per the revised Recommended Next Experiment's robustness battery (full
writeup: [`robustness-checks.md`](robustness-checks.md)), a Baseline C —
same role **and** same primary team first, then role only, then team
only, minutes as the tiebreak — was tested. Result:

| | MRR | Median rank | Recall@5 |
|---|---|---|---|
| Baseline A (role + minutes) | 0.0256 | 128 | 2.7% |
| Baseline B (32 features + cosine) | 0.2539 | 16 | 34.5% |
| **Baseline C (role + team + minutes)** | **0.5893** | **2** | **94.7%** |

**Baseline C — using nothing but role, team, and minutes, no event data
at all — outperforms the full 32-feature Baseline B by more than 2x.**
Why: the eligible population requires ≥450 minutes in both halves of the
*same season*, and players essentially never change clubs mid-season —
so a club's specific-role sub-roster (often just 2–4 eligible players)
already narrows the field to almost nothing before any statistics are
consulted. **Team continuity within one season is a far stronger prior
for "same player" in this experimental design than event-derived playing
style turned out to be.**

This does not overturn Gate 2 — Baseline B still clearly, confidently
beats Baseline A (the charter's actual gating question), and a
teammates-excluded sensitivity check confirms Baseline B's own result
doesn't depend on team-clustering (robustness-checks.md, Check 4). But it
means the "10x better than a trivial baseline" framing needs a sharper
caveat: an even more trivial baseline, using information Baseline B never
sees, does much better. It also elevates **testing transferred
players** — where Baseline C's team-continuity advantage structurally
disappears — from a nice-to-have to the single most important remaining
validation of what event-derived features are worth on their own. See
Limitations and Recommended Next Experiment, both updated accordingly.

### Direct follow-up: transferred players confirm the signal isn't team continuity

The obvious next check was run the same day: of the 1,257 eligible
players, 26 (2.1%) have a different primary team in period B than period
A. Re-running all three baselines with queries restricted to just this
subset (same global candidate pool otherwise) — full writeup:
[`transfer-analysis.md`](transfer-analysis.md):

| | Full population (n=1,257) | Transferred only (n=26) |
|---|---|---|
| Baseline B MRR | 0.2539 | 0.2387 |
| Baseline B median rank | 16 | **38.5** |
| Baseline B Recall@10 | 43.3% | **34.6%** |
| Baseline C MRR | 0.5893 | **0.0101** |
| Baseline B − A delta | +0.228, CI [0.210, 0.250] | +0.228, CI [0.089, 0.393] |

**Baseline C's team-based advantage completely collapses for transferred
players** (0.589 → 0.010, statistically indistinguishable from Baseline
A) — direct confirmation, not just inference, that its strength was
entirely about team continuity; this part of the finding is clean and
doesn't depend on which metric is read.

**Baseline B's picture is more mixed than "holds up" alone conveys** —
flagged in a second review round. MRR stays close to the full-population
value and the B−A delta remains positive with a CI clearing 0, but median
rank roughly doubles and Recall@10 drops by nearly 9 points. At n=26,
MRR's near-parity is consistent with a handful of perfect (rank-1) hits
(Recall@1 was actually slightly *higher* for transferred players, 19.2%
vs 16.2%) propping up the average while the rest of the subset ranks
meaningfully worse — plausibly real degradation from a new club changing
a transferred player's actual role/usage, not only noise. Read with the
sample-size caveat in `transfer-analysis.md`: this is genuine, direct
evidence that Baseline B's advantage over the trivial baseline is not
solely a team-continuity artifact, but n=26 cannot yet distinguish "the
individual signal is fully intact" from "there's a real, moderate cost to
changing clubs on top of it." A larger sample from another season is the
natural way to resolve that, not just to tighten the confidence interval.

## Position / Minutes / League Diagnostics

**Correction to the original analysis:** the first pass measured
team/league concentration over every top-10 neighbor, including cases
where the "neighbor" was simply the query's own correctly-retrieved true
match — which trivially shares the query's team (players rarely change
clubs mid-split) and therefore measured retrieval *success*, not a
confound. Fixed and re-run excluding true matches; see
[`context-diagnostics.md`](context-diagnostics.md) for the full
before/after. The correction **strengthens** the diagnostic conclusion.

- **Team confound:** 1.20% of genuinely-other-player top-10 neighbors
  share the query's primary team, vs. 1.05% expected under squad-size-
  weighted random selection (~1.14x enrichment) — small. (A second
  correction, made the same day as the first: the original 1.30% figure
  came from a `player_id`-keyed join vulnerable to silent duplication —
  28.7% of the eligible population has minutes recorded under more than
  one competitionId, mostly via Euro/World Cup appearances. Fixed with a
  hard failure on duplicate keys, not just a recomputation — see D013.)
- **League confound:** 21.64% observed vs. 20.06% expected
  (league-size-weighted) — close to negligible (~1.08x), unaffected by
  the above.
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
2b. **"Stable statistical fingerprint" is proven; "stable role
   representation" is an interpretation, not yet a separately-tested
   claim.** Within-role retrieval (H4) shows the signal isn't explained
   by the 4 nominal role categories, but doesn't establish that the extra
   signal specifically encodes finer sub-role/positional information as
   opposed to individual quality, set-piece duties, team system, or other
   stable-but-not-role traits. Distinguishing these needs sub-role labels,
   expert evaluation, or a downstream task — none attempted here.
2c. **The eligible population (≥450 min in *both* periods) has a real
   survivorship bias.** It selects for players who were continuously
   good enough to keep playing throughout the season — by construction it
   excludes breakout youngsters, players returning from injury, and
   players losing their starting spot. Transferred players are a partial
   exception: [`transfer-analysis.md`](transfer-analysis.md) found and
   tested 26 of them within the existing eligible population, with
   encouraging results — but 26 is small, and the youngster/injury/
   lost-starting-spot cases remain completely untested. The
   minutes-threshold sensitivity curve (D006) does not address this
   either: every threshold tested still required both-periods
   eligibility, so it varies the bar for "established," not whether the
   established-player restriction itself holds. The result here is a
   statement about established players specifically, not players in
   general.
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
10. **Resolved by the robustness battery:** the default standardization
    is fit on the combined A+B population (D008), but
    [`robustness-checks.md` Check 1](robustness-checks.md#check-1--standardization-fit-a-only-vs-ab-combined)
    directly compared it with fitting on period A alone. MRR was 0.2539
    with the combined fit and 0.2543 with the A-only fit (median rank 16
    in both), so the transductive choice is not meaningfully inflating
    this result. A genuinely unseen production period should still use a
    scaler fit only on historical data.
11. **Ratio features computed from very few attempts can be extreme and
    over-trusted** — a player with 1 shot and 1 goal gets
    `shot_conversion_pct = 1.0`, the same numeric value as a striker who
    converted 20 of 20, with no attempt-count-based confidence weighting.
    No shrinkage or minimum-attempts floor was applied in this catalog.
12. **The bootstrap treats queries as independent draws**, though they
    share teams, leagues, and the same period-B candidate pool — some
    correlation between queries is plausible (e.g. two teammates'
    retrieval difficulty could move together). The reported effect size
    is large enough to likely survive a more conservative
    cluster-aware interval, but the exact CI bounds should be read as
    approximate, not exact, for that reason.
13. **The specific causal explanations offered in the qualitative error
    analysis** (e.g. "tactical role shift," "squad rotation" for the
    non-sample-noise misses) **are plausible hypotheses, not verified
    facts** — [`error-analysis.md`](error-analysis.md) establishes that 3
    of the 4 worst cases are *not* explained by low minutes or a club
    change; it does not establish *what* did change.
14. **Partially resolved (2026-07-22):** `uv run python -m
    scoutlens.evaluation.run_report` now regenerates every number in this
    report's Temporal Stability Results and Diagnostics sections in one
    command, writing `artifacts/gate2_results.json`
    ([`run_report.py`](../src/scoutlens/evaluation/run_report.py)); `uv
    run python -m scoutlens.evaluation.run_robustness` does the same for
    [`robustness-checks.md`](robustness-checks.md), writing
    `artifacts/robustness_results.json`; `uv run python -m
    scoutlens.evaluation.run_transfer_analysis` does the same for
    [`transfer-analysis.md`](transfer-analysis.md). Still missing, and
    still real future work: an externally versioned
    config (today's threshold/competition-set/seed are inlined constants,
    not a separate file), a run-manifest recording the git commit and
    data checksums the numbers were produced from, and an automated test
    that diffs the report's published numbers against a freshly-generated
    artifact so drift is caught automatically rather than by manual
    review. `data/processed/period_profiles.parquet` and the raw data it's
    built from remain local and gitignored, as intended — only the results
    artifact is meant to be inspectable without re-running anything.

## GO / PIVOT / KILL Decision

**GO.**

Both gates cleared, several criteria with considerable margin rather than
marginally:

- **Gate 0 (Provenance):** GO — license verified individually on each of
  the 7 consumed artifacts' own Figshare pages, see
  [`data-provenance.md`](data-provenance.md) (corrected citation — this
  previously pointed to `gate-1-decision.md`, which covers Gate 1, not
  Gate 0; found in a second review round).
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

**Revised three times.** Originally: test learned representations first.
Reordered (2026-07-22) to harden the baseline and build reproducibility
tooling first, per the charter's "complexity must earn its place"
principle — done, and it surfaced the team-continuity finding. Reordered
again the same day once the direct transferred-players follow-up
confirmed the signal survives that confound.

**Done:**
- ~~Make the current baseline unimpeachable~~ — 5 robustness checks
  ([`robustness-checks.md`](robustness-checks.md)): 3 of 5 confirm
  robustness (standardization fit, distance metric, teammates-excluded
  sensitivity); 1 (role+team+minutes baseline) is the team-continuity
  finding; family ablation confirmed the signal is genuinely distributed.
- ~~Build the reproducible runner~~ — `run_report.py`,
  `run_robustness.py`, and `run_transfer_analysis.py` now regenerate
  every number in this report and its two follow-up docs in one command
  each.
- ~~Test transferred players~~ — [`transfer-analysis.md`](transfer-analysis.md):
  the 26 eligible players who changed clubs between periods show
  Baseline C collapsing to chance-level (MRR 0.010) while Baseline B's
  advantage over Baseline A holds essentially unchanged (delta identical
  to three decimal places, though the CI is wide at this sample size).
  Direct, encouraging confirmation — not proof at n=26.

**Remaining, in priority order:**

1. **Extend to another season** — now the clearest highest-value next
   step. Two purposes: get a larger transferred-player sample (n=26 is
   suggestive, not conclusive — a few hundred would make the CI in
   `transfer-analysis.md` genuinely tight), and check the domestic-league
   results generalize beyond this single 2017/18 snapshot at all.

   **Scoping check (2026-07-22):** the current Pappalardo/Wyscout
   collection has exactly one season per competition — confirmed
   empirically (every `competitionId` maps to a single `seasonId`), not
   assumed. There is no second season available within this same
   collection; "extend to another season" requires a *new* external data
   source, not a parameter change to the existing pipeline, which reopens
   Gate-0-style work (source discovery, per-artifact license
   verification, schema audit) before any acquisition code can be
   written.

   Researched one candidate: **StatsBomb Open Data**
   (github.com/statsbomb/open-data), free, custom attribution license
   (not yet verified in the same per-artifact detail as
   `data-provenance.md` did for Wyscout — only a surface-level check was
   done here). Two real obstacles found:
   - **Uneven per-league coverage, and per-season match completeness
     varies a lot.** La Liga has many seasons listed (18, including
     2018/19), but **the 2018/19 file is not a full season** — verified
     directly by fetching it: it's the Messi/Barcelona-career release (a
     few dozen matches, not 380). The originally-recorded recommendation
     to use it was wrong and has been removed (see D013).
     **2015/16 is a better candidate**: Premier League, La Liga, Serie A,
     and Ligue 1 each appear to carry a full season's worth of matches —
     corroborated by file size scaling (PL's 2015/16 match file is ~11x
     the line count of Bundesliga's same-season file for a competition
     with a similar number of teams) rather than an exhaustive per-match
     count, so treat this as *strong, not exhaustive* verification.
     **Bundesliga's 2015/16 release is itself a small subset** (~34
     matches, confirmed directly — appears focused on Bayer Leverkusen)
     and should be excluded. **No single StatsBomb season has all five of
     this spike's leagues at full depth** — a StatsBomb-based extension
     would cover four leagues (dropping Bundesliga) or mix seasons.
   - **A structurally different schema.** StatsBomb's event taxonomy,
     coordinate system, and file structure are not compatible with
     `scoutlens.data.ingestion`/`validation`/`minutes` as built — this
     would mean re-doing the equivalent of SLS-005 through SLS-014's work
     for a new source, not reusing the existing pipeline with new input
     files. A multi-day undertaking, not a rerun.

   **Recommendation, if/when this is picked back up:** StatsBomb 2015/16
   across Premier League, La Liga, Serie A, and Ligue 1 (Bundesliga
   excluded) is the best-supported StatsBomb option found — not La Liga
   2018/19 alone, which was this document's earlier (wrong) suggestion.
   Before any acquisition code is written: a full per-artifact license
   audit matching `data-provenance.md`'s rigor, and an exact match-count
   check per competition (this section's verification was corroborating,
   not exhaustive — confirm the true per-league match count directly
   against the downloaded files, not inferred from file sizes), the same
   discipline Gate 0 applied to the original source.
2. **A genuinely different validation methodology for the recruitment
   claim itself**, since same-player retrieval cannot speak to it: blind
   expert scout review of shortlists, or a downstream-task validation —
   only after (1), not before.
3. **Only then, test whether added model complexity earns its place** —
   a learned representation, metric learning, or feature reweighting,
   compared against Baseline B *and* Baseline C, not today's version of
   either.
4. **Goalkeeper-specific features** (positioning, distribution under
   pressure, claim/punch tendencies — none currently captured) — the
   clearest specific gap in the feature catalog, addressable in parallel
   with the above.
5. **Resolve the players-count discrepancy** against the source paper —
   low cost, closes a standing question rather than carrying it forward
   indefinitely.
6. **Still open from the robustness pass itself:** a versioned config
   file and a run-manifest (git commit + data checksums) for
   `run_report.py`, `run_robustness.py`, and `run_transfer_analysis.py`,
   and an automated test that diffs published report numbers against a
   freshly-generated artifact.

## Note on Pacing

The charter allotted 10 working days; this spike's tasks (SLS-001–023)
were completed across 3 calendar days via continuous iterative
development with the user reviewing and merging each stage. This does
not change the substance of any gate decision — every criterion in the
charter was evaluated on its own terms — but is noted here because the
charter's checkpoints (e.g. "Friday's Data Feasibility Report v0.1") were
time-based assumptions that didn't end up governing the actual pace of
work.
