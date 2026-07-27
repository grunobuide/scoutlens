# ScoutLens — StatsBomb Pipeline (schema & reproduction)

Beads issue `scoutlens-8mc.2`. Implements the provider-scoped StatsBomb
ingestion / minutes / validation pipeline whose comparison design was
frozen in [`statsbomb-feature-compatibility.md`](statsbomb-feature-compatibility.md)
(D020) and whose licence + coverage were cleared in
[`statsbomb-provenance.md`](statsbomb-provenance.md) (D014). Logged as
D021. Code: `src/scoutlens/statsbomb/`; tests: `tests/statsbomb/`.

This pipeline is **independent** of `scoutlens.data.*` — it shares no code
path with the Wyscout pipeline, so both providers stay separately
reproducible, and all Wyscout behaviour is unchanged.

## Reproduction

```
uv run python -m scoutlens.statsbomb.ingestion
```

Downloads events + lineups for every 2015/16 match in Premier League (2),
Ligue 1 (7), La Liga (11) and Serie A (12) — ~1,517 matches, ~5 GB of
raw JSON — pinned to open-data commit `b0bc9f22dd`, and writes
`data/processed/statsbomb/{events,matches,minutes,players}.parquet`. Raw
and processed StatsBomb data are **not** committed: the StatsBomb User
Agreement prohibits redistribution (D014), so `data/` stays gitignored,
here as a licence obligation.

The parsing, minutes and validation logic is pure and unit-tested against
a checked real sample match (3754217, Chelsea–Arsenal); only the network
fetch needs the live repository.

## Processed `events` schema

One flat row per StatsBomb event (native coordinates preserved as-is;
the 0–100 normalization happens at feature-aggregation time, D020 §2).
Key columns:

| Column | Notes |
|---|---|
| `id`, `index` | StatsBomb event id (unique) and within-match order |
| `match_id`, `competitionId`, `period`, `minute`, `second` | keys + timing |
| `type_name` | `Pass`, `Shot`, `Carry`, `Dribble`, `Duel`, `Interception`, `Clearance`, … |
| `player_id`, `team_id`, `position_name` | actor (null on non-player events) |
| `location_x/y`, `end_location_x/y` | native 0–120 × 0–80; end from pass/carry/shot |
| `pass_*` | `length`, `height_name`, `cross`, `through_ball`, `shot_assist`, `goal_assist`, `outcome_name` (**null = completed**, D020 §6) |
| `shot_*` | `outcome_name`, `type_name`, `statsbomb_xg` (native xG), `body_part_name` |
| `dribble_outcome_name`, `duel_type_name`, `duel_outcome_name`, `interception_outcome_name` | action outcomes |
| `possession`, `possession_team_id` | native possession sequences (secondary-set use) |

The frame is built with an explicit schema (`EVENTS_SCHEMA`), not
inferred — StatsBomb columns mix ints/floats/bools with heavy nulls, and
first-rows inference overflows or mistypes at scale.

## Minutes derivation

Interval-based from the lineup `positions[]` stints (D020 §4), **not** a
formation+substitution reconstruction. The one real subtlety: StatsBomb's
match clock does not reset between periods and the periods overlap in
absolute numbering (period 1 `[0:00, 48:38]`, period 2 `[45:00, 95:38]`
in the sample), so minutes are summed **per period**, each stint clipped
to its period's `[Half Start, Half End]` bounds, and a player's several
stints are **unioned, not summed** — a lineup occasionally records
overlapping stints for one player (an injury off-and-on plus a
tactical-shift position that outlives the player's own substitution;
match 3754217, Coquelin), and summing them would credit more than a full
match. Such rows are flagged `derivation_status = "overlap_merged"`
rather than silently smoothed; `validation.check_overlap_flag_rate` warns
if the rate is high. Unused substitutes get `minutes_played = 0`, status
`clean` — the same convention as Wyscout, so the ≥450-minute eligibility
filter behaves identically across providers.

Verified against the real sample: Begović (full match) 99.27 min,
Chambers (on at half) 50.63 min — both single clean stints,
hand-checkable against the `Half End` timestamps.

## Validation

`scoutlens.statsbomb.validation.run_all` returns `CheckResult`s
(`ok`/`warn`/`fail`, report-don't-fix): required columns, unique event
ids, native coordinate bounds, minutes bounds `[0, 130]`, the referential
check that every acting player has a minutes row (unused subs with zero
events are allowed), the overlap-flag rate, and that every event's
`match_id` is declared. The full per-match pipeline passes validation on
the real sample (`test_full_per_match_pipeline_passes_validation`).

## Status

Implementation and tests complete and green (25 StatsBomb tests, incl.
malformed-input and real-sample integration). The full ~5 GB
materialization run is the entry step of `8mc.3` (re-run the retrieval
battery) — deferred until that experiment starts, since nothing consumes
the processed parquets until then.
