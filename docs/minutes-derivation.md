# ScoutLens — Formation/Substitution Audit & Minutes Derivation (SLS-008/009)

Implementation: [`src/scoutlens/data/minutes.py`](../src/scoutlens/data/minutes.py).
Tests: [`tests/data/test_minutes.py`](../tests/data/test_minutes.py) (10
cases against synthetic match records). Reproduce with:

```
uv run python -m scoutlens.data.minutes
```

This was flagged in the brief (section 11.1) as the single biggest
technical risk of the spike. It turned out considerably cleaner than
expected — see below.

## SLS-008 — Formation/substitution coverage audit

| Check | Result |
|---|---|
| `hasFormation` rate | **100%** (3,882/3,882 team-match entries) — no missing-formation cases at all in this dataset |
| Lineup size | **always exactly 11** players, every entry |
| Bench size | 4–13 players, mode 7 (2,846 entries) |
| Substitutions per team-match | 0 (6 entries, encoded as the literal string `"null"` — same sentinel pattern as elsewhere in this dataset), 1 (49), 2 (443), 3 (3,374, the mode), 4 (10) |

No `missing_formation` derivation-status case exists in the current data.
The status vocabulary in `minutes.py` still supports it, since a future
re-acquisition against updated source data could see different coverage —
but nothing here required inventing a fallback for it.

## SLS-009 — Minutes derivation

`derive_minutes()` produces a `player_id × match_id` table
(`player_id, match_id, team_id, started, minute_in, minute_out,
minutes_played, derivation_status`) — 74,098 rows (one per lineup/bench
squad member per match, including 0-minute bench players).

### Key correctness detail: red cards end playing time

`redCards`/`yellowCards` in the raw schema store the **minute of the
card** as a string (`"0"` = no card), not a count — a genuinely
non-obvious finding from schema profiling (SLS-005). A player who is sent
off without a formal substitution record would otherwise be
(incorrectly) credited with a full 90 minutes under a naive
`90 - substitution_minute` approach. `minute_out` is computed as the
earliest of: full match duration, this player's substitution-out minute
(if any), this player's red-card minute (if any).

### Match duration by type

`Regular` → 90, `ExtraTime` → 120, `Penalties` → 120 (extra time is played
before any shootout; the shootout itself adds no playing time). This is a
stated assumption — the schema doesn't confirm exact added/stoppage time
per match — but it's the standard competition rule and matches.duration
gives no finer-grained signal to improve on.

### Derivation status distribution (real data)

| Status | Count | % |
|---|---|---|
| `clean` | 73,893 | 99.72% |
| `substitution_conflict` | 205 | 0.28% |

`substitution_conflict`: a substitute enters during second-half stoppage
time (e.g. minute 94 on a nominal 90-minute match) with no later
sub-out/red-card record. `matches.parquet` carries no true final-whistle
minute (only `events.eventSec` would), so rather than fabricate an end
time, these are floored at `minutes_played = 0` and flagged — a
conservative, honest lower bound, not a guess. If this population turns
out to matter for eligibility later, cross-referencing `events.eventSec`
per match to recover the real final-whistle minute is the natural
follow-up; not done here per the 80/20 rule
([D005](decisions-log.md#d005--2026-07-20--minutes-reconstruction-8020-rule-dont-chase-every-edge-case-in-v1)) since it's 0.28% of rows.

Zero rows required the `invalid` status after fixing an initial bug in
this same derivation (see git history) where stoppage-time entries
produced `minute_out < minute_in`.

### Sanity check

Median total `minutes_played` summed across a team's full roster for a
single match is exactly 990 = 11 × 90 (11 outfield-equivalent slots are
always occupied, since a substitution is a zero-sum swap of playing time).
75th percentile is also 990; the max is 1,320 = 11 × 120 for ExtraTime
matches. This is strong internal-consistency evidence that the derivation
is behaviorally correct, not just free of hard errors.

### Confirmed-safe edge case: double substitution

11 team-match entries in the real data have a player substituted in and
later substituted out again within the same match (e.g. a tactical
substitute who is themselves replaced). The per-player dict-based
`minute_in`/`minute_out` lookup handles this correctly without special
casing — covered by `test_double_substitution_in_then_out`.

## What this enables next

SLS-011 (eligible population) can now sum `minutes_played` per player
across matches within a competition/season to test the brief's proposed
thresholds (≥450/900/1350 minutes). Given the 99.72% clean rate, minutes
data quality is very unlikely to be the reason Gate 1 fails, if it fails.
