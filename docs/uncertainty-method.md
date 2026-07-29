# Match-bootstrap uncertainty method

**Status:** preregistered and frozen before production execution, 2026-07-29

**Design:** `match_bootstrap_v1`

**Authority:** [`config/uncertainty.json`](../config/uncertainty.json) and
[D031](decisions-log.md#d031--2026-07-29--match-bootstrap-v1-is-frozen-before-execution)

This document turns the uncertainty fields already reserved by
`scoutlens.showcase/1.0.0` into an executable analytical contract. The method
must be implemented and tested against the synthetic truth fixture before any
production result is inspected. A result may reveal that the method is
uninformative; it may not be used to revise the estimand after the fact.

## Question and estimands

The bootstrap asks: **how much do the displayed fingerprints, identity ranks,
and observed neighbors change when the observed matches are resampled?** It
estimates sampling stability inside the frozen Wyscout 2017/18 dataset.

The observed point estimates remain exactly those in the current showcase.
Replicates produce distributions for:

1. each profile-period-feature raw value and within-role percentile;
2. each profile's global, within-role, and role-plus-minutes self rank;
3. recall-at-1, recall-at-5, and recall-at-10 indicators for those ranks; and
4. each of the five observed non-self neighbors' within-role rank and top-five
   selection indicator.

The design does not create intervals for cosine similarity, feature evidence
contributions, player quality, future performance, tactical fit, or causal
ability. Evidence contributions remain deterministic explanations of the
observed point estimate.

## Frozen population and strata

The cohort is the observed 1,257 `(player_id, competitionId)` profiles that
clear 450 minutes in both chronological periods in the unresampled data. Its
membership, role, competition, identity, periods, and point-estimate candidate
counts are frozen before resampling. A replicate cannot admit a new player or
reapply the 450-minute eligibility threshold.

The original chronological assignment is also frozen. Each stratum is one
`(competitionId, period)` pair. Matches never move between competitions or
periods, and the chronological split is never recomputed inside a replicate.

## Exact draw algorithm

The public build uses 500 replicates and seed `1729`.

1. Sort strata by numeric `competitionId`, then period A before B.
2. Sort source match IDs numerically inside each stratum.
3. Before any computation, generate the complete draw plan in replicate order
   `0..499`. For each of the `n` draws in a stratum, encode
   `match_bootstrap_v1|1729|replicate|competitionId|period|draw_index|attempt`
   as UTF-8 and compute SHA-256.
4. Interpret the first eight digest bytes as an unsigned big-endian integer
   `u`. Let `limit = 2^64 - (2^64 mod n)`. Accept `u` when `u < limit` and
   select sorted source index `u mod n`; otherwise increment `attempt` and hash
   again. This rejection step avoids modulo bias.
5. Persist or hash the complete draw plan in the production run artifact. A
   subject failure cannot consume or shift another draw because every draw is
   counter-addressed. The machine-readable test vector in the config freezes
   byte encoding, endianness, and index selection across Python versions.

The sampling unit is a whole match. If a match is drawn `w` times, every event
and every player-minute contribution from that match receives integer weight
`w`. An implementation may duplicate rows or aggregate by multiplicity, but
the results must be identical. It must not deduplicate repeated match IDs and
must not resample events, players, or already-aggregated profile rows.

## Replicate computation

For each precomputed draw plan:

1. apply match multiplicities to raw events and reconstructed player minutes;
2. rebuild all 32 features separately for every competition-period stratum;
3. retain only identities in the fixed observed cohort, without reapplying the
   eligibility threshold;
4. mark a player-period as present when sampled minutes are strictly positive;
5. fit the existing combined-period scaler on all present fixed-cohort A and B
   rows in that replicate, using the existing non-null mean imputation and
   zero-variance handling;
6. recompute global and within-role percentiles over present rows, using
   average rank for ties;
7. rebuild global cosine, within-role cosine, and role-plus-minutes rankings;
8. record subject-level feature, rank, recall, and neighbor observations.

Positive sampled minutes with zero events are observed data: per-90 counts are
zero and ratios with zero attempts are null, exactly as in the existing feature
engine. Zero sampled minutes are absence, not a zero-valued fingerprint.

### Fixed candidate universe with absent candidates

The candidate universe remains the observed fixed cohort. Present period-B
candidates are ranked normally. A candidate with zero sampled period-B minutes
has no invented vector or workload and is placed after every present candidate,
then ordered by numeric `(player_id, competitionId)`. This rule keeps candidate
counts comparable and makes absence reduce stability instead of disappearing
from the denominator.

If the period-A query is absent, all retrieval and neighbor measures for that
profile-replicate are invalid. If it is present but no candidate in the
required scope is present, the affected measure is invalid. Otherwise absent
self or neighbor candidates receive the fixed-universe bottom ordering above.
Neighbor rankings exclude every candidate with the query's `player_id`, even
when that human has another competition-scoped profile, matching the observed
showcase neighbor contract.

Ranking ties among present candidates use descending cosine followed by
numeric `(player_id, competitionId)`. The role-plus-minutes baseline uses role
match, ascending absolute minutes difference, then the same identity order.
These rules are exact; assertion tolerances never create fuzzy ranking ties.

## Missingness and validity

Missingness is local to the smallest affected measure:

| Condition | Feature measure | Retrieval rank | Neighbor stability |
|---|---|---|---|
| Query period absent | affected period invalid | invalid | invalid |
| Positive minutes, zero events | per-90 zero; zero-attempt ratio invalid | valid after normal imputation | valid after normal imputation |
| Raw feature is null | that raw/percentile pair invalid | model uses existing mean imputation | model uses existing mean imputation |
| Period-B self/neighbor absent | period-B feature invalid | fixed-universe bottom rank | fixed-universe bottom rank and not top five |
| Other period-B candidate absent | no feature observation | fixed-universe bottom rank | fixed-universe bottom rank |
| Non-finite value or computation error | affected measure invalid and counted | affected measure invalid and counted | affected measure invalid and counted |

An implementation must record invalid-reason counts. It must never replace an
absent feature observation with zero merely to reach the validity threshold.

The top-level `valid_resamples` counts replicates whose draw and shared rebuild
pipeline completed. Nested counts are measure-specific. A measure is
`available` only with at least 450 valid observations (90% of 500). Below that
it is `insufficient`: the valid count remains visible, while interval, median,
and rate fields are null. A feature whose observed point value is null is also
`insufficient`, even if some bootstrap draws produce a non-null value.

## Summaries and numeric rules

For an available measure, sort its finite replicate values ascending. The 95%
interval is the 0.025 and 0.975 quantiles using Hyndman-Fan type 7 linear
interpolation: for probability `p`, `h = (n - 1) * p`; interpolate between
indices `floor(h)` and `ceil(h)`. Median rank uses the same rule at `p = 0.5`.

Recall and selection rates are arithmetic means of their Boolean indicators
over valid replicates. Ranks and output order are exact. Tests use absolute
tolerances from `config/uncertainty.json`: `1e-12` for raw features,
similarities, interval bounds, and rates; `1e-9` for percentiles and additive
cosine reconstruction. No relative tolerance is used.

## Synthetic truth cases

[`tests/uncertainty/fixtures/match_bootstrap_v1.json`](../tests/uncertainty/fixtures/match_bootstrap_v1.json)
is the mandatory pre-production fixture. It has two matches per period in two
competitions and freezes forced draw plans for review.

| Case | Required qualitative result |
|---|---|
| Invariant player | Identical per-match rates yield zero-width feature intervals |
| High-variance, low-support player | Feature intervals are wider than the invariant case |
| Missing-in-resample player | Absence is not zero-imputed; feature validity falls and candidate rank is penalized |
| Tied candidates | The lower numeric player ID ranks first, then competition ID |
| Multiple competitions | Every draw remains inside its competition-period stratum |
| Duplicate match | Drawing one match twice doubles both its events and minutes |

The production engine must pass these cases, deterministic reruns, reversed
input-order tests, and one deliberately insufficient subject before it may read
the real processed dataset.

## Supported and unsupported interpretations

Supported: an available narrow interval or high selection rate means the
displayed statistic is stable to resampling the matches observed in this
dataset under this design. An insufficient result means the data do not support
a stable summary for that measure; the player remains visible.

Unsupported: these intervals do not represent causal uncertainty, data-provider
annotation error, measurement validity, unobserved tactics, injury or transfer
effects, opponent quality, future seasons, player quality, recruitment value,
or style proof. Bootstrap stability cannot repair a biased feature definition
or a contextual confound.

## Contract-field review checklist

Every reserved showcase field has exactly one owner:

| Contract field | Computation / source |
|---|---|
| `uncertainty.status` | `available` when shared valid replicates >=450, else `insufficient` |
| `uncertainty.design_version` | literal `match_bootstrap_v1` |
| `uncertainty.seed` | literal `1729` |
| `uncertainty.requested_resamples` | literal `500` |
| `uncertainty.valid_resamples` | completed shared replicate pipelines |
| `uncertainty.interval` | literal `percentile_95` |
| `uncertainty.resampling_unit` | literal `whole_match_stratified_by_competition_and_period` |
| `uncertainty.cohort_policy` | literal `fixed_observed_eligible_cohort` |
| `uncertainty.warning` | exact sampling-only warning from `config/uncertainty.json` |
| `feature.uncertainty.status` | feature-specific validity threshold and observed-point availability |
| `feature.uncertainty.valid_resamples` | finite raw and percentile observations for that profile-period-feature |
| `feature.uncertainty.raw_ci_95` | type-7 interval over raw feature observations |
| `feature.uncertainty.within_role_percentile_ci_95` | type-7 interval over replicate within-role percentiles |
| `retrieval.uncertainty.status` | outcome-specific rank validity threshold |
| `retrieval.uncertainty.valid_resamples` | valid ranks for that profile and retrieval scope |
| `retrieval.uncertainty.median_rank` | type-7 median of valid ranks |
| `retrieval.uncertainty.rank_ci_95` | type-7 interval over valid ranks |
| `retrieval.uncertainty.recall_at_1_rate` | mean of `rank <= 1` indicators |
| `retrieval.uncertainty.recall_at_5_rate` | mean of `rank <= 5` indicators |
| `retrieval.uncertainty.recall_at_10_rate` | mean of `rank <= 10` indicators |
| `neighbor.stability.status` | neighbor-specific rank validity threshold |
| `neighbor.stability.valid_resamples` | valid query/scope replicates for the observed neighbor |
| `neighbor.stability.top_5_selection_rate` | mean of `rank <= 5`; absent neighbor is false |
| `neighbor.stability.median_rank` | type-7 median including fixed-universe bottom ranks |
| `neighbor.stability.rank_ci_95` | type-7 interval including fixed-universe bottom ranks |
| `players.index.uncertainty_status` | mirrors the profile top-level uncertainty status |

Review must also verify the SHA-256 draw test vector, draw-plan hash,
invalid-reason totals, fixed cohort
identity, exact candidate counts, and config hash in provenance. Any field
without one deterministic owner fails closed.

## Change control and implementation gate

`config/uncertainty.json` is separate from `config/experiment.json` because the
published v0.1 experiments must retain their existing manifest hash while this
new experiment is preregistered. The uncertainty publication must record both
config hashes where applicable.

Before production execution, run:

```bash
uv run --frozen pytest tests/uncertainty -q
uv run --frozen ruff check .
uv run --frozen mypy src/scoutlens
```

Changing an estimand, draw rule, validity rule, threshold, ordering rule, or
quantile method requires a new decision entry and `design_version`. Corrections
that affect the public artifact shape also require the appropriate showcase
schema version change. Performance optimization may not change draw plans or
numeric outputs beyond the frozen assertion tolerances.
