# ScoutLens — Chronological Split & Period Profiles (SLS-015)

Implementation: [`src/scoutlens/evaluation/temporal.py`](../src/scoutlens/evaluation/temporal.py).
Tests: [`tests/evaluation/test_temporal.py`](../tests/evaluation/test_temporal.py).

`assign_periods(matches)` sorts each competition's matches by `dateutc`
and splits by match count at the midpoint — first half chronologically is
period A, the rest is period B. Per the brief: never splits an individual
match's events across periods; an odd match count gives the extra match
to B.

`build_period_profiles(events, minutes, period_assignment)` scopes events
and minutes to each `(competitionId, period)` group and calls
`compute_player_features` (SLS-014) unchanged, returning one row per
**`player_id x competitionId x period`** — per
[D007](decisions-log.md#d007--2026-07-22--sls-015-temporal-split-must-key-on-player--competition--period),
not just `player_id x period`, so a player appearing in both a domestic
league and an international tournament doesn't collide into one row.

## Split sizes (real data)

| Competition | Period A matches | Period B matches |
|---|---|---|
| English/French/German/Italian/Spanish first division | 190 | 190 |
| European Championship | 25 | 26 |
| World Cup | 32 | 32 |

Domestic leagues split evenly (38 match-days → 19/19); the two
international tournaments split close to evenly by match count, which
given their short duration corresponds to "most of the group stage" vs.
"rest of group stage + knockouts," not a comparable calendar-time split to
the leagues.

`build_period_profiles` runs in well under a second (0.4s) across all
3.25M events — no performance concern at this scale.

## Eligible-in-both-periods population, by threshold

A player only supports the same-player temporal retrieval experiment
(SLS-018) if they clear the minutes threshold in **both** periods for a
given competition — the actual, stricter population, not the season-level
figures from [`eligible-population.md`](eligible-population.md).

| Threshold (min/period) | Eligible (player × competition, both periods) | England | France | Germany | Italy | Spain | Euro | World Cup |
|---|---|---|---|---|---|---|---|---|
| ≥225 | 1,538 | 317 | 304 | 274 | 319 | 320 | 4 | 0 |
| ≥450 | 1,257 | 260 | 256 | 225 | 254 | 262 | 0 | 0 |

**This confirms the limitation already flagged in
[`gate-1-decision.md`](gate-1-decision.md) empirically, not just
structurally:** World Cup 2018 has zero eligible players at either
threshold once split into two periods (a group-stage-only squad member
caps out well under 225 minutes in a single period), and Euro 2016
survives only at the loosest threshold with a population of 4 — not
usable for any quantitative claim. The five domestic leagues remain solid
at the brief's suggested ≥450 threshold: 1,257 total, 225–262 per league.

**Consequence for SLS-016 onward:** the primary Temporal Role Stability
Experiment's quantitative results (MRR, Recall@K) should be computed and
reported on the domestic-league population. Euro 2016 and World Cup 2018
stay in the dataset and in any qualitative/exploratory discussion (per the
Gate 1 decision to keep them in scope), but including their near-zero
period-eligible population in the same aggregate statistics as the
leagues would misrepresent both — consistent with what Gate 1 already
anticipated.
