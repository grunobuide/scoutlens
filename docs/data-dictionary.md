# ScoutLens — Data Dictionary (SLS-005)

Schema profiling of the 7 Parquet files produced by
[`src/scoutlens/data/ingestion.py`](../src/scoutlens/data/ingestion.py)
(SLS-004), run against the 2026-07-21 acquisition. This is a description of
what the data actually contains, empirically observed — not a restatement
of the Figshare item descriptions. Where this disagrees with those
descriptions, the disagreement is called out explicitly.

Full referential-integrity testing (SLS-007) and automated validation
(SLS-006) come later; the checks here are the ones needed to write an
accurate dictionary, not a complete audit.

---

## competitions.parquet — 7 rows × 5 cols

| Column | Type | Notes |
|---|---|---|
| `wyId` | Int64 | PK. 7 distinct values, no nulls. |
| `name` | String | e.g. "Italian first division". |
| `type` | String | `club` (5) or `international` (2). |
| `format` | String | `Domestic league` or `International cup`. |
| `area` | Struct(name, id, alpha3code, alpha2code) | ISO 3166-1 country info. |

No missing values in any column. The 7 rows are exactly the five domestic
leagues + World Cup 2018 + European Championship 2016, as documented.

## teams.parquet — 142 rows × 6 cols

| Column | Type | Notes |
|---|---|---|
| `wyId` | Int64 | PK, 142/142 unique. |
| `name`, `officialName`, `city` | String | No missing values. |
| `type` | String | `club` (98) / `national` (44). |
| `area` | Struct | Same shape as competitions.area. |

No missing values in any column.

## players.parquet — 3,603 rows × 14 cols

| Column | Type | Notes |
|---|---|---|
| `wyId` | Int64 | PK, 3603/3603 unique. |
| `role` | Struct(code2, code3, name) | **Only** position field present — no match-level position. Confirms the brief's section 3.2 concern empirically. |
| `role.name` distribution | — | Goalkeeper 426, Defender 1200, Midfielder 1257, Forward 720. |
| `currentTeamId` | Int64, nullable | 135 nulls (3.7%) — free agents / no current club on record. |
| `currentNationalTeamId` | Int64, nullable | 2,246 nulls (62.3%) — most players have no national-team record. Do not treat this as "player never played internationally"; likely means "not currently in a national-team squad." |
| `foot` | String, nullable | `right` 2708, `left` 838, `both` 5, empty string `""` 48, actual null 4. **`""` and `null` are two different sentinels for the same "unknown" concept here** — not normalized in ingestion because it wasn't confirmed whether they're truly equivalent; flagged for SLS-006 to decide and treat consistently. |
| `weight`, `height` | Int64 | 93 players have `weight == 0`; 77 have `height == 0`. These are almost certainly "unknown," not real zero values — a physically impossible measurement is being used as a sentinel. Needs explicit handling before any feature uses these fields. |
| `birthDate` | String, `YYYY-MM-DD` | No missing/empty values. |
| `birthArea`, `passportArea` | Struct | Same shape as competitions.area. |

**Discrepancy vs. the paper:** 3,603 players here vs. ~4,299 stated in
Pappalardo et al. Not yet explained — see
[`data-provenance.md`](data-provenance.md) for the standing question.

**Normalized during ingestion:** `currentTeamId`/`currentNationalTeamId`
literal string `"null"` folded to real `null` (see ingestion.py). `foot`'s
`""` vs `null` split was left as-is, deliberately, pending a decision.

## matches.parquet — 1,941 rows × 16 cols

| Column | Type | Notes |
|---|---|---|
| `wyId` | Int64 | PK, 1941/1941 unique. |
| `competitionId` | Int64 | All 7 values are exactly `competitions.wyId` — clean FK, verified. |
| `status` | String | **100% `"Played"`** — the public dataset only includes completed matches; no Cancelled/Postponed/Suspended rows exist despite the schema documenting those states. |
| `duration` | String | `Regular` 1931, `ExtraTime` 3, `Penalties` 7. Sums to 1941. |
| `groupName` | String, nullable | Only populated for World Cup/Euro group stage (Groups A–H); null for domestic-league matches (1826 nulls) and empty string for knockout-stage international matches (16). Undocumented in the Figshare item description — found empirically. |
| `teamsData` | String (JSON) | **Not flattened.** Dict keyed by per-match team id (`{"1646": {...}, "1659": {...}}`), so its struct shape varies row to row — can't be a flat Parquet column. Serialized to a JSON string at ingestion; see below for what's inside. |
| `referees` | List(Struct(refereeId, role)) | Structurally consistent list-of-struct, converts cleanly. Not decomposed further — Referees dataset itself is out of scope per the brief. |
| `dateutc` | String | `YYYY-MM-DD hh:mm:ss`, no missing values — this is the field to sort on for the chronological split (SLS-015), not `date`. |
| `date` | String | Human-readable duplicate of `dateutc`, e.g. `"May 13, 2018 at 4:00:00 PM GMT+2"`. Redundant; not needed downstream. |
| `roundId`, `seasonId`, `gameweek`, `winner`, `venue`, `label` | — | No missing values observed. |

### Inside `teamsData` (parsed from the JSON string, not yet a Parquet column)

Each team entry has: `scoreET`, `coachId`, `side`, `teamId`, `score`,
`scoreP`, `hasFormation`, `scoreHT`, and `formation.lineup` /
`formation.bench` (each a list of `{playerId, ownGoals, redCards, goals,
yellowCards}`), plus `substitutions` when present.

**Important:** every per-player stat inside `lineup`/`bench`
(`ownGoals`, `redCards`, `goals`, `yellowCards`) is stored as a **string**,
including the literal string `"null"` for "no goals" — not a JSON number
or JSON null. This needs explicit casting/sentinel-handling in SLS-008/009,
the same pattern already seen in `players.currentTeamId`. **No per-player,
per-match position field exists anywhere in this structure** — only
lineup/bench membership and basic stats. This closes out the brief's
section 3.2 question empirically: match-level position is not available
in this public artifact.

## events.parquet — 3,251,294 rows × 13 cols

| Column | Type | Notes |
|---|---|---|
| `id` | Int64 | PK, 3,251,294/3,251,294 unique — no duplicate event ids. |
| `matchId` | Int64 | FK to matches.wyId. **0 orphans** — every event resolves to a known match, and all 1,941 matches are represented. |
| `teamId` | Int64 | FK to teams.wyId. **0 orphans.** |
| `playerId` | Int64 | FK to players.wyId, with `0` as an explicit "no player" sentinel (226,038 events, 7.0% — mostly ball-out-of-play / interruption-type events). **0 orphans** among non-zero values — every non-zero playerId resolves to a known player. |
| `eventId` / `eventName` | Int64 / String | 10 distinct values, not the 7 documented in the Figshare item text ("pass, foul, shot, duel, free kick, offside and touch"). Actual values: Pass, Duel, Others on the ball, Free Kick, Foul, Shot, Save attempt, Offside, Goalkeeper leaving line, Interruption. The item description's "touch" category appears to have been split into several of these in the actual data. |
| `subEventId` / `subEventName` | Int64 (nullable) / String | Null **exactly** for `eventName == "Offside"` (8,182 rows) — Offside has no subtype. This is a genuine schema property, normalized from the raw `""` sentinel at ingestion (see ingestion.py docstring), not an error to filter out. |
| `tags` | List(Struct(id)) | 0–6 tags per event; 311,485 events (9.6%) have an empty tag list. All 57 distinct tag ids used are covered by `tags2name`; 2 mapping codes (802, 1501) are simply unused in this dataset slice. |
| `positions` | List(Struct(x, y)) | Almost always length 2 (origin + destination): 3,250,553 events. 741 events have length 1 (origin only). Coordinates are documented as `[0,100]`; **empirically confirmed to 99.9999% accuracy** — out of 6,501,847 individual coordinate values, exactly 1 `x < 0` (`x = -1`) and 4 `y > 100` (`y = 101`) were found. Rare enough to treat as data-entry noise, but real — SLS-007 should clip or flag rather than assume the domain claim is absolute. |
| `eventSec` | Float64 | Range `[0.0, 3537.36]` seconds within a half — plausible given stoppage time. Normalized from mixed int/float JSON encoding at ingestion. |
| `matchPeriod` | String | `1H` (1,628,459), `2H` (1,617,928), `E1` (2,421), `E2` (2,339), `P` (147, penalty shootouts). `E1`/`E2`/`P` counts are internally consistent with `matches.duration`'s 3 ExtraTime + 7 Penalties matches. |
| `_source_file` | String | Ingestion provenance tag (which per-competition JSON the row came from), not part of the original schema. |

Events per match range from 1,270 to 2,216 (mean 1,675) — no match has
zero events.

## eventid2name.parquet — 36 rows × 4 cols

`event`, `subevent` (nullable), `event_label`, `subevent_label`. Every
`subEventId` actually used in `events.parquet` is covered; one mapping
code (`60`) is unused in this dataset slice.

## tags2name.parquet — 59 rows × 3 cols

`Tag`, `Label`, `Description`. Every tag id actually used in
`events.parquet` is covered; two mapping codes (802, 1501) are unused in
this dataset slice.

---

## Summary of open items carried to later tasks

- **SLS-006 (raw-data validation):** decide how to treat `players.foot`'s
  `""` vs `null` split; decide how to treat `weight == 0` / `height == 0`
  as sentinels; sweep other files for the same `null`-vs-`"null"`-string
  pattern found in `players`.
- **SLS-007 (relational integrity):** already substantially clean based on
  this profiling (0 orphaned matchId/teamId/playerId in events;
  competitionId fully resolves) — formal automated checks should still be
  written, but no major integrity problem is expected.
- **SLS-008 (formation/substitution audit):** `teamsData` is unparsed JSON
  today; decomposing `lineup`/`bench`/`substitutions` into real rows, and
  handling the string-typed stat fields (including `"null"` sentinels), is
  the next real task.
- **players count discrepancy (3,603 vs. paper's 4,299):** still
  unexplained; not blocking, but should not be silently resolved without
  a stated reason in the final report.
