# ScoutLens — Data Provenance (SLS-002)

## Canonical source

**Collection:** Soccer match event dataset
**Authors:** Luca Pappalardo, Emanuele Massucco
**Host:** Figshare
**Collection DOI:** `10.6084/m9.figshare.c.4415000` (version 5, resolved at
`https://figshare.com/collections/Soccer_match_event_dataset/4415000/5`)
**Collection posted:** 2020-01-28
**Required citations** (per the collection page, verbatim):

1. Pappalardo et al. (2019). *A public data set of spatio-temporal match
   events in soccer competitions.* Nature Scientific Data 6:236.
   https://www.nature.com/articles/s41597-019-0247-7
2. Pappalardo et al. (2019). *PlayeRank: Data-driven Performance Evaluation
   and Player Ranking in Soccer via a Machine Learning Approach.* ACM
   Transactions on Intelligent Systems and Technologies (TIST) 10, 5,
   Article 59.
3. Data collection itself: Pappalardo, Luca; Massucco, Emanuele (2019).
   *Soccer match event dataset.* figshare. Collection.
   https://doi.org/10.6084/m9.figshare.c.4415000

## Gate 0 — license verification (D004)

Checked directly on each individual Figshare item page — not inferred from
the paper text — on 2026-07-20. Every artifact this spike consumes declares
`LICENCE: CC BY 4.0` independently on its own item page. No divergence
found between the paper's stated license and the artifact pages.

**Verdict: GO.** Attribution (the three citations above) must ship with
any derived report or publication.

## Artifact inventory

| Artifact | Item DOI | File | Size | Item version | Declared license | Verified |
|---|---|---|---|---|---|---|
| Events | `10.6084/m9.figshare.7770599` | `events.zip` | 73.74 MB | — | CC BY 4.0 | 2026-07-20 |
| Matches | `10.6084/m9.figshare.7770422` | `matches.zip` | 629.98 kB | — | CC BY 4.0 | 2026-07-20 |
| Players | `10.6084/m9.figshare.7765196` | `players.json` | 1.66 MB | v3 | CC BY 4.0 | 2026-07-20 |
| Teams | `10.6084/m9.figshare.7765310` | `teams.json` | 26.76 kB | v3 | CC BY 4.0 | 2026-07-20 |
| Competitions | `10.6084/m9.figshare.7765316` | `competitions.json` | 1.18 kB | v4 | CC BY 4.0 | 2026-07-20 |
| Event id → name mapping | `10.6084/m9.figshare.11743836` | `eventid2name.csv` | 0.98 kB | — | CC BY 4.0 | 2026-07-20 |
| Tag id → name mapping | `10.6084/m9.figshare.11743818` | `tags2name.csv` | 1.71 kB | — | CC BY 4.0 | 2026-07-20 |

`retrieved_at` and `checksum` columns are intentionally omitted here — they
belong to the machine-readable manifest produced during acquisition
(SLS-003/SLS-004): see [`data-manifest.csv`](data-manifest.csv), generated
by [`src/scoutlens/data/ingestion.py`](../src/scoutlens/data/ingestion.py).
Every downloaded file's md5 was verified against the checksum Figshare's
own API reports (`supplied_md5`) before conversion; the manifest records an
independently computed sha256 for our own reproducibility checks.

## Acquisition results (SLS-004, run 2026-07-21)

- **Matches:** 1,941 rows in the processed Parquet — matches the paper's
  stated count exactly.
- **Events:** 3,251,294 rows — matches the paper's stated "~3.25 million"
  events.
- **Players:** 3,603 rows in `players.json`. This is meaningfully below the
  paper's stated 4,299 players. Not yet explained — candidate causes to
  check in SLS-005 schema profiling: the paper's count may include players
  who only appear in `events.playerId` without a corresponding entry in
  `players.json` (e.g., red-carded/early-substituted players from smaller
  federations), or may come from a different dataset version. Flagged here
  rather than silently assumed benign.
- **Teams:** 142 rows. **Competitions:** 7 rows (five domestic leagues +
  World Cup 2018 + Euro 2016, as documented).

## Data-quality findings during ingestion (relevant to SLS-005/SLS-006)

Two inconsistent-encoding issues were found and normalized during
conversion (see `ingestion.py` docstrings for the exact handling):

1. **`events.subEventId`** is the empty string `""` (not JSON `null`)
   specifically for `Offside` events, which have no subtype. Normalized to
   `None`. This is a genuine semantic property of the schema (Offside truly
   has no subEventId), not corrupt data — worth documenting in
   `data-dictionary.md` as expected, not filtering it out as an error.
2. **`players.currentTeamId` / `players.currentNationalTeamId`** encode
   "missing" two different ways in the same file: JSON `null` in some
   records, the literal string `"null"` in others. Both normalized to
   `None`. This inconsistency itself is worth flagging in SLS-006's raw
   validation as a real data-quality signal, not assumed to be isolated to
   these two fields — other files should be swept for the same pattern.
3. **`matches.teamsData`** is a dict keyed by a per-match, dynamic team id
   (e.g. `{"1646": {...}, "1659": {...}}`), so its shape differs row to
   row and cannot be a flat Parquet column. Serialized to a JSON string at
   ingestion to stay lossless; decomposing `lineup`/`bench`/`substitutions`
   into proper rows is SLS-008/SLS-009's job, not ingestion's. Note also
   that per-player fields inside `lineup`/`bench` (`goals`, `ownGoals`,
   `redCards`, `yellowCards`) are themselves stored as strings, including
   the literal string `"null"` for no goals — another sentinel to handle
   downstream.

## Deliberately out of scope for this spike (not verified, not ingested)

Per the brief (section 2, "Não ingeriria coaches ou referees inicialmente"):

- **Coaches** — dataset posted 2019-05-06
- **Referees** — dataset posted 2019-05-06
- **PlayeRanks** — derived/scored dataset, posted 2019-08-08
- **Data paper on soccer-logs** — journal contribution, not raw data
- **Plots replication code** — software item, likely carries its own
  (possibly different) license; not something we redistribute or depend on

If any of these enter scope later, their license must be verified
individually before use, following the same process as above — do not
assume they inherit the collection's CC BY 4.0 without checking.

## Schema note relevant to brief section 3.2 (position granularity)

The **Matches** item description confirms `teamsData` contains `lineup`,
`bench`, `substitutions`, and a `hasFormation` flag, but the *only*
per-player fields documented inside `lineup`/`bench` are basic match
statistics (goals, own goals, cards) — no match-level position field is
mentioned. This is consistent with the brief's caution: detailed
position-per-match likely is **not** available in this public artifact;
`players.role` (a single main-role subdocument) may be the only position
signal we have. To be confirmed empirically against the actual JSON in
SLS-005 (schema profiling) — this is a description-page reading, not a
verification against real records yet.

## Redistribution stance

Raw data is not committed to Git (`data/` is gitignored). This repository
distributes acquisition code and this manifest, not the ~76 MB of source
files, even though CC BY 4.0 would legally permit redistribution — per the
brief's own guidance (section 5, "Não adicionar raw data ao Git por
padrão").
