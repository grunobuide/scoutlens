# Data Licenses

This file covers licensing for the **data** ScoutLens consumes. It is
separate from any license governing this repository's own source code
(not yet decided — see [`README.md`](README.md)).

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

## Artifacts explicitly not covered here

Coaches, Referees, PlayeRanks, the data paper, and the software
(replication-code) item in the same Figshare collection have **not** been
individually license-verified, because they are out of scope for this
spike (see [`docs/data-provenance.md`](docs/data-provenance.md#deliberately-out-of-scope-for-this-spike-not-verified-not-ingested)).
If any of them enter scope later, verify their license on their own item
page before use — do not assume they inherit this table.
