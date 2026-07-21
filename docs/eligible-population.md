# ScoutLens — Eligible Population (SLS-011)

Implementation: [`src/scoutlens/data/eligibility.py`](../src/scoutlens/data/eligibility.py).
Tests: [`tests/data/test_eligibility.py`](../tests/data/test_eligibility.py).
Reproduce with:

```
uv run python -m scoutlens.data.eligibility
```

`season_minutes` is `minutes_played` summed per player within a
`competitionId` — verified empirically (not assumed) that each
competition is exactly one season, so this is a clean "season minutes"
figure per league/tournament. A player appearing in more than one
competition (e.g. a domestic league and a World Cup) gets one row per
competition rather than a combined total, since club and international
minutes shouldn't be pooled into a single number.

## Population cascade

| Step | Count |
|---|---|
| Players in `players.json` roster | 3,603 |
| Distinct players appearing in `minutes.parquet` (any squad membership, incl. 0-minute bench) | 3,618 |
| — of which not in `players.json` (see [`data-quality-report.md`](data-quality-report.md)) | 15, all 0-minute bench-only |
| Distinct players with `season_minutes > 0` in at least one competition | **3,020** |
| Player × competition rows with `season_minutes > 0` | 3,654 |

`season_minutes` sanity bound: max observed is exactly **3,420 = 38 × 90**,
the theoretical ceiling for a full domestic league season (38 match-days)
with zero missed minutes — confirms no derivation error inflates a
player's total beyond what's physically possible.

## Distribution (player × competition rows with `season_minutes > 0`)

| Percentile | Minutes |
|---|---|
| 25th | 201 |
| 50th (median) | 638 |
| 75th | 1,841 |
| max | 3,420 |

## Eligibility at the brief's candidate thresholds

| Threshold | Eligible player×competition rows | Eligible distinct players | By competition | By role |
|---|---|---|---|---|
| ≥450 min | 2,056 | **1,969** | England 385, France 396, Germany 349, Italy 404, Spain 417, Euro 50, World Cup 55 | Defender 716, Midfielder 710, Forward 402, Goalkeeper 141 |
| ≥900 min | 1,628 | 1,626 | England 333, France 330, Germany 290, Italy 330, Spain 345 (no Euro/WC — see below) | Defender 601, Midfielder 588, Forward 316, Goalkeeper 121 |
| ≥1350 min | 1,278 | 1,278 | England 271, France 271, Germany 218, Italy 256, Spain 262 (no Euro/WC) | Defender 489, Midfielder 449, Forward 235, Goalkeeper 105 |

**Euro 2016 and World Cup 2018 drop out entirely above the 450-minute
threshold.** This is structural, not a data problem: a World Cup squad
member plays at most ~7 matches (630 minutes) and Euro 2016 fewer still,
so no international-tournament player can reach 900 minutes within that
tournament alone. This matters directly for
[`decisions-log.md`](decisions-log.md) D006 and for SLS-015 — the
international competitions are not going to support a meaningful
within-competition temporal split at any threshold above ~450 minutes;
they're only usable, if at all, at the lowest threshold, and even then
provide a small population (50–55 players).

## Reading against Gate 1

The brief's Gate 1 GO criterion is **~≥1,000 eligible players**, spread
across multiple roles and at least 3 (ideally 5) leagues with substantial
population. At the ≥450-minute threshold — the brief's suggested starting
point for the primary temporal-retrieval experiment — **1,969 eligible
players** clears that bar by a wide margin, with all four roles
represented in the hundreds and all five domestic leagues each
contributing 349–417 players.

This is a population-size result only. Gate 1 also requires minutes
reconstruction reliability (≥95% — actual: 99.72% clean, see
[`minutes-derivation.md`](minutes-derivation.md)) and join integrity
(≥99.5% — actual: 99.97%, see [`data-quality-report.md`](data-quality-report.md)).
Both are already comfortably cleared. SLS-012 makes the formal gate call
using all three together.

Note: this counts **season** minutes, not minutes within each half of a
chronological split. SLS-015's temporal split will need its own,
separately-computed eligibility (minutes ≥ some threshold in *each* half),
which will be a stricter and smaller population than the season-level
numbers here — expect the temporal-retrieval experiment's actual eligible
count to be lower than 1,969.
