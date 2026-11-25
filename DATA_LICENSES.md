# Data Licenses

This file covers licensing for the **data** ScoutLens consumes. It is separate
from the license governing this repository's own source code, which is
[MIT](LICENSE) and covers the code only — never the data described below.

ScoutLens consumes two sources under two very different licences. The
sections from **Source** to **Redistribution stance** cover the primary
evidence, the Wyscout/Pappalardo dataset. **StatsBomb Open Data** covers the
external replication, which is published as aggregate results only.

## Source

**Soccer match event dataset** (Pappalardo, Luca; Massucco, Emanuele),
Figshare collection, DOI `10.6084/m9.figshare.c.4415000` (version 5).

## License

**CC BY 4.0** — verified individually on 2026-07-20 against each of the 7
core artifacts this project consumes, on their own Figshare item pages (not
inferred from the paper text alone). Full verification record, per-artifact
DOIs, and checksums: [`docs/data-provenance.md`](docs/data-provenance.md).

| Artifact | License |
|---|---|
| Events | CC BY 4.0 |
| Matches | CC BY 4.0 |
| Players | CC BY 4.0 |
| Teams | CC BY 4.0 |
| Competitions | CC BY 4.0 |
| Event id → name mapping | CC BY 4.0 |
| Tag id → name mapping | CC BY 4.0 |

CC BY 4.0 permits redistribution with attribution. This repository chooses
**not** to redistribute the raw data anyway (see below) — that is a
project decision, not a license requirement.

## Required attribution

Any use of this data — in code, analysis, or a published report — must
cite:

> Pappalardo, L., Cintia, P., Rossi, A. et al. A public data set of
> spatio-temporal match events in soccer competitions. Sci Data 6, 236
> (2019). https://doi.org/10.1038/s41597-019-0247-7

And, if referencing the PlayeRank methodology specifically:

> Pappalardo, L., Cintia, P., Ferragina, P., Massucco, E., Pedreschi, D.,
> Giannotti, F. (2019). PlayeRank: Data-driven Performance Evaluation and
> Player Ranking in Soccer via a Machine Learning Approach. ACM
> Transactions on Intelligent Systems and Technologies 10(5), Article 59.
> https://doi.org/10.1145/3343172

## Redistribution stance

Raw and processed data files are **gitignored** and never committed to
this repository, even though CC BY 4.0 would legally permit it. This
repository distributes acquisition code
([`src/scoutlens/data/ingestion.py`](src/scoutlens/data/ingestion.py)) and
a manifest ([`docs/data-manifest.csv`](docs/data-manifest.csv)), not the
data itself. Anyone who clones this repo reproduces the dataset by running
the acquisition script against the same pinned Figshare sources.

## StatsBomb Open Data (aggregate replication only)

**Source.** StatsBomb Open Data, from StatsBomb Services Ltd, at
https://github.com/statsbomb/open-data. Acquisition is pinned to repository
commit `b0bc9f22dd77c206ddedc1d742893b3bbe64baec` and scoped to the 2015/16
season (`season_id` 27) of four competitions: Premier League (2), Ligue 1 (7),
La Liga (11) and Serie A (12) (`D014`).

**Licence.** The *StatsBomb Public Data User Agreement* (`LICENSE.pdf` in that
repository, standard terms last updated 8 September 2023), plus the
Terms & Conditions paragraph of its README. This is **not** an open licence,
and it is stricter than CC BY 4.0. The per-clause audit is in
[`docs/statsbomb-provenance.md`](docs/statsbomb-provenance.md).

| What the agreement says | Clause | What ScoutLens does |
|---|---|---|
| Redistributing the data is prohibited | 1.2.1, 7 | Raw and processed StatsBomb files stay under the gitignored `data/`; only the aggregate results (`artifacts/statsbomb_replication_results.json`) are committed. The showcase artifacts carry no per-player StatsBomb data, and no page links or loads any (showcase contract invariant 12; `claims-consistency.spec.ts`). |
| Commercial use of the data **or of any analysis derived from it** is prohibited | 1.2.2 | The replication is non-commercial research. The MIT licence on this repository's code grants nothing over StatsBomb data or the analysis derived from it. |
| Analysis may be published, accredited with the StatsBomb brand logo; the README asks that the source be stated as StatsBomb | 1.4, README | Every route names StatsBomb as the replication's source and shows the StatsBomb logo beside it (`scoutlens-jtt.25`). |

**Attribution.** Any publication of the replication results must state the
data source as StatsBomb and carry the StatsBomb logo from their Media Pack.

## Artifacts explicitly not covered here

Coaches, Referees, PlayeRanks, the data paper, and the software
(replication-code) item in the same Figshare collection have **not** been
individually license-verified, because they are out of scope for this
spike (see [`docs/data-provenance.md`](docs/data-provenance.md#deliberately-out-of-scope-for-this-spike-not-verified-not-ingested)).
If any of them enter scope later, verify their license on their own item
page before use — do not assume they inherit this table.
