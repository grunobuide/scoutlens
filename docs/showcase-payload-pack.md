# Showcase payload distribution

The Player Fingerprint Lab uses the complete 1,257-profile Gate-2 population,
but those canonical JSON files total 147,054,404 bytes and are deliberately
excluded from Git. A content-addressed release asset makes the static showcase
buildable from a clean clone without downloading or reconstructing provider
data.

## Pinned v1 asset

| Property | Value |
|---|---|
| Dataset | `wyscout-2017-18-v1-0e48066f37cc` |
| Manifest-declared paths | 1,257 |
| Archive format | deterministic `tar+gzip` |
| Archive bytes | 16,686,443 |
| SHA-256 | `4398018f1be1cc9bf2040139fb9ff3a45a55a24f97ae4d93f867354611ad4e7d` |
| Immutable tag | `showcase-wyscout-2017-18-v1-0e48066f37cc` |
| Asset | [`scoutlens-showcase-wyscout-2017-18-v1-0e48066f37cc-4398018f1be1cc9bf2040139fb9ff3a45a55a24f97ae4d93f867354611ad4e7d.tar.gz`](https://github.com/grunobuide/scoutlens/releases/download/showcase-wyscout-2017-18-v1-0e48066f37cc/scoutlens-showcase-wyscout-2017-18-v1-0e48066f37cc-4398018f1be1cc9bf2040139fb9ff3a45a55a24f97ae4d93f867354611ad4e7d.tar.gz) |

The machine-readable authority is
[`config/showcase-payload-pack.json`](../config/showcase-payload-pack.json).
The versioned URL and filename are immutable by project policy; hydration still
trusts only the pinned SHA-256 and byte count, so deletion or replacement of a
remote asset fails closed.

## Clean-clone hydration

From the repository root:

```bash
uv sync --frozen
uv run --frozen python -m scoutlens.showcase.payload hydrate
```

The command downloads the pinned asset to a temporary location, then checks:

1. archive byte count and SHA-256;
2. dataset version and expected path count against the tracked manifest;
3. safe, unique, regular-file archive members;
4. exact equality with all manifest-declared `players/*.json` paths; and
5. every profile byte count and SHA-256 before publication.

Extraction happens in a sibling staging directory. The existing `players/`
directory is retained until all checks pass and is replaced atomically. A local
or air-gapped copy uses the same path:

```bash
uv run --frozen python -m scoutlens.showcase.payload hydrate \
  --archive /path/to/the-pinned-archive.tar.gz
```

## Deterministic offline regeneration

After running the documented Wyscout pipeline and showcase exporter, rebuild
the archive from exporter output only:

```bash
uv run --frozen python -m scoutlens.showcase.payload build \
  --output artifacts/showcase-payload/scoutlens-showcase-wyscout-2017-18-v1-0e48066f37cc-4398018f1be1cc9bf2040139fb9ff3a45a55a24f97ae4d93f867354611ad4e7d.tar.gz
```

The builder validates the source set and all manifest checksums first, sorts
paths, and normalizes timestamps, ownership, permissions, gzip headers, and tar
metadata. Two builds must reproduce the pinned 16,686,443 bytes and SHA-256.

## Licence and redistribution boundary

The asset contains only ScoutLens player-period aggregate profiles already
declared by the public manifest. It contains no event rows, match rows, provider
files, processed Parquet, credentials, or proprietary branding. The underlying
Pappalardo/Wyscout public dataset is attributed and licensed CC BY 4.0 as
recorded in [`data-provenance.md`](data-provenance.md); the repository's MIT
code licence does not relicense the source data. Any future payload must repeat
the provenance audit and receive a new dataset/version pin.
