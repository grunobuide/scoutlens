# ScoutLens — Gate 1 Decision (SLS-012)

**Decision: GO.**

Recorded 2026-07-21, jointly by the user and this session, after reviewing
the evidence below. This is the first formal gate of the charter
([`project-charter.md`](project-charter.md)) — data feasibility is
sufficient to proceed to Week 2 (feature engineering and the temporal
role-stability experiment).

## Evidence against the brief's Gate 1 criteria

| Criterion | GO threshold | Actual | Source |
|---|---|---|---|
| Eligible players | ~≥1,000 | **1,969** (at ≥450 min/season) | [`eligible-population.md`](eligible-population.md) |
| Role coverage | multiple confident roles | all 4 roles, 141–716 players each | [`eligible-population.md`](eligible-population.md) |
| League coverage | ≥3, ideally 5, substantial | **5/5 domestic leagues**, 349–417 players each | [`eligible-population.md`](eligible-population.md) |
| Minutes reconstruction reliability | ≥95% | **99.72%** clean | [`minutes-derivation.md`](minutes-derivation.md) |
| Join integrity | ≥99.5%, or exceptions explained | **99.97%**, one explained exception | [`data-quality-report.md`](data-quality-report.md) |
| No critical feature family blocked by structural missingness | none | none found so far | [`data-dictionary.md`](data-dictionary.md) |

Every quantitative threshold clears with margin, not marginally.

## Explicit scope decision made alongside this gate

**Euro 2016 and World Cup 2018 remain in scope**, despite dropping out of
the eligible population above the 450-minute threshold (see
[`eligible-population.md`](eligible-population.md) — structural: a
tournament squad member can play at most ~630–700 minutes total, so no
international-competition player clears 900+ minutes within that
competition alone). This is a deliberate choice, not an oversight: these
two competitions carry real relevance in football analytics despite their
small population, and the brief's charter doesn't require dropping a
competition just because it's small at higher thresholds.

**Consequence for later work, stated now so it isn't rediscovered as a
surprise in Week 2:**

- SLS-015 (chronological split) will very likely not produce a usable
  within-competition temporal split for Euro/World Cup at anything above
  the lowest minutes threshold — the population is only 50–55 players
  *for the whole tournament*, before even splitting it into two temporal
  halves.
- The final feasibility report (SLS-023) should report international-
  competition results separately from domestic-league results, or
  exclude them from the primary quantitative claim while still including
  them in exploratory/qualitative analysis — not blend a 50-player,
  single-month tournament population into the same statistics as a
  380-player, ten-month league season.
- This is not a reason to reopen Gate 1 — the domestic leagues alone
  already clear every threshold independently.

## What Gate 1 does *not* certify

Per [`project-charter.md`](project-charter.md), Gate 1 is a data-feasibility
gate, not a signal-feasibility gate. It says the population, minutes, and
joins are solid enough to build features and run the temporal-retrieval
experiment — it says nothing yet about whether event-derived profiles
actually carry stable role signal. That is Gate 2 (SLS-022), still fully
open.
