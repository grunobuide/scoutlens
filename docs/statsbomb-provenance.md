# ScoutLens — StatsBomb Open Data Provenance (mini Gate 0 for the external replication)

Audit performed 2026-07-23 for beads issue `scoutlens-8mc.1`, the entry
gate of the external-replication epic (`scoutlens-8mc`). Scope and rigor
follow [`data-provenance.md`](data-provenance.md), the Gate 0 document
for the original Wyscout source. **Nothing here authorizes acquisition
by itself** — it establishes whether acquisition work (`scoutlens-8mc.2`)
may begin, and under what constraints.

## Canonical source

**Collection:** StatsBomb Open Data
**Provider:** StatsBomb Services Ltd (registered in England and Wales,
company no. 10377735)
**Host:** GitHub — https://github.com/statsbomb/open-data
**Verified at repository commit:** `b0bc9f22dd77c206ddedc1d742893b3bbe64baec`
(master as of 2026-07-23; commit dated 2026-05-26). All file fetches and
counts below were made against `master`, which resolved to this commit —
pin acquisition code to this SHA, not to `master`, so the numbers in this
document stay reproducible if StatsBomb updates the repository.
**License document:** `LICENSE.pdf` in the repository root ("StatsBomb
Public Data User Agreement", standard terms last updated 8 September
2023), plus a Terms & Conditions paragraph in the repository `README.md`.

## License audit (per-clause, from the actual LICENSE.pdf text)

This is **not** an open license, and it is materially more restrictive
than the CC BY 4.0 covering the Wyscout/Pappalardo data. Clause numbers
refer to the User Agreement.

| Dimension | What the agreement says | Clause |
|---|---|---|
| **Access** | Provided via the GitHub repository, fully controlled by StatsBomb; they may withhold the service at any time without warning. | 2.1, 1.3 |
| **Permitted use** | Analysis, research, and sharing of ideas & understanding of the data. Analyses/conclusions built on the data **may be shared publicly**. | 1.1, preamble |
| **Redistribution of the data** | **Prohibited.** The user may not "edit, distort, distribute, reproduce, sell or in any way provide the data to any external or third party." The data remains StatsBomb's property; no redistribution without express prior written consent. | 1.2.1, 7 |
| **Commercial use** | **Prohibited** — the user may not "commercially exploit the data **or any analysis derived from** the use of the Service." | 1.2.2 |
| **Publication of analysis** | Permitted, but any publication of analysis formed from StatsBomb data **must be accredited with the StatsBomb brand logo** (README adds: state the data source as StatsBomb; logo available in their Media Pack at statsbomb.com/media-pack). | 1.4, README |
| **Registration** | StatsBomb *asks* (request, not a stated condition of the grant) that users register name + email at statsbomb.com/resource-centre before accessing. | 2.2 |
| **Warranty / liability** | Provided "as is"; no warranty of accuracy, reliability, or completeness; no liability. | 3.2–3.4, 5 |
| **Governing law** | England and Wales. | 9 |

### What this means for ScoutLens, concretely

1. **Raw StatsBomb data must never be committed to this repository or
   otherwise redistributed** — same operational practice as today
   (`data/` is gitignored), but here it is a license obligation, not
   just a hygiene choice as it is with CC BY 4.0.
2. **Derived per-player/per-event tables should also stay out of Git.**
   The agreement permits sharing "analysis or conclusions"; it prohibits
   providing "the data" in any form. Small aggregate *results* artifacts
   (metrics JSONs like `artifacts/*.json`) are clearly analysis outputs;
   feature tables reconstructable into substantial portions of the
   source data are not clearly so — keep them local, as the Wyscout
   pipeline already does with `data/processed/`.
3. **The non-commercial restriction covers analyses, not just the raw
   data.** If ScoutLens ever moves toward a commercial scouting product,
   results derived from StatsBomb Open Data cannot go with it. The
   Wyscout CC BY 4.0 results carry no such restriction. Any published
   comparison of the two must keep this asymmetry in mind.
4. **Publishing replication results requires StatsBomb attribution with
   their logo** — a heavier obligation than Wyscout's three-citation
   requirement. This applies to the eventual replication report, not to
   code.
5. **Registration at statsbomb.com/resource-centre is a user action**,
   recommended before the acquisition step even though the agreement
   phrases it as a request rather than a precondition.

## Match-count verification (exact, from the official matches files)

Season 2015/16 is `season_id 27` for all five leagues in
`data/competitions.json`. Each `data/matches/{competition_id}/27.json`
was downloaded and counted directly — no file-size inference (which is
what D012's first pass used, and what D013 flagged as non-exhaustive).

| League | comp_id | Matches | Unique match_ids | Teams | Per-team count | Date span | match_status |
|---|---|---|---|---|---|---|---|
| Premier League | 2 | **380** | 380 | 20 | all 38 | 2015-08-08 → 2016-05-17 | 380 available |
| La Liga | 11 | **380** | 380 | 20 | all 38 | 2015-08-21 → 2016-05-15 | 380 available |
| Serie A | 12 | **380** | 380 | 20 | all 38 | 2015-08-22 → 2016-05-15 | 380 available |
| Ligue 1 | 7 | **377** | 377 | 20 | 14 teams at 38, 6 at 37 | 2015-08-07 → 2016-05-14 | 377 available |
| 1. Bundesliga | 9 | **34** | 34 | 18 | Leverkusen 34, every other team ≤2 | 2015-08-15 → 2016-05-14 | 34 available |

### Why Ligue 1 has 377, not 380

A 20-team double round-robin schedules 380 fixtures; the release omits
exactly three, each from a different match week, identified by
enumerating all home/away pairings against the file:

| Missing fixture (home vs away) | Match week |
|---|---|
| Bastia vs Gazélec Ajaccio | 14 |
| Saint-Étienne vs Paris Saint-Germain | 23 |
| Troyes vs Bordeaux | 36 |

Those weeks carry 9 matches in the file instead of 10. The repository
does not document a reason; treat it as three missing data files, not
three matches that didn't happen. Impact on ScoutLens: six clubs lose
one match of minutes/events each — negligible for period-level
aggregates, but the minutes-derivation validation for Ligue 1 must
expect 377, and per-team completeness checks must allow 37 for these
six clubs.

### Bundesliga 2015/16: excluded

Confirmed directly: the file contains Bayer Leverkusen's full 34-match
season and nothing else (all 17 other teams appear at most twice — i.e.,
only as Leverkusen's opponents). This is a club-focused release, not a
league season. **Excluded from the replication scope**, as D013 already
recorded.

### La Liga 2018/19: re-verified as unusable (D013 confirmation)

The `data/matches/11/4.json` file contains 34 matches; Barcelona appears
in **all 34** while no other club appears more than twice. It is the
Messi/Barcelona release — and not even Barcelona-complete (they played
38 league matches that season). D013's withdrawal of the earlier "La
Liga 2018/19" recommendation stands confirmed against the file itself.

## Events and lineups coverage

Full file listings of `data/events/` and `data/lineups/` were obtained
via the GitHub git-trees API (4,235 files each, listing not truncated)
and checked against every candidate match id:

- **1,517 candidate matches** (380 + 380 + 380 + 377, all match_ids
  unique across the four leagues).
- **1,517 / 1,517 have an events file. 1,517 / 1,517 have a lineups
  file.** No gaps.

StatsBomb 360 data (`data/three-sixty/`) was not audited — it covers
selected matches only and is out of scope for the replication.

## Gate 0 verdict for the replication epic

**GO — for non-commercial research replication, under the constraints
above.** Specifically:

- Coverage is sufficient and now exhaustively verified: four of the five
  original leagues at full-season depth in a single season (2015/16),
  1,517 matches with complete events + lineups files.
- The license permits exactly what the replication epic needs (research
  analysis, publicly shared conclusions) and prohibits things the
  project already doesn't do (redistributing raw data) — plus one new
  real constraint (non-commercial, including derived analyses) and one
  new obligation (logo attribution on published analysis) that must
  travel with every future StatsBomb-derived result.
- Remaining pre-acquisition user action: register at
  statsbomb.com/resource-centre (recommended), and decide where the
  StatsBomb logo obligation will be satisfied when replication results
  are published.

Acquisition (`scoutlens-8mc.2`) may proceed against repository commit
`b0bc9f22dd77c206ddedc1d742893b3bbe64baec`, scoped to competitions
{2, 7, 11, 12}, season 27, with Bundesliga (9) and every other
competition excluded.
