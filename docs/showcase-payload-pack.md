# Showcase payload distribution

The Player Fingerprint Lab uses the complete 1,257-profile Gate-2 population,
but those canonical JSON files total 147,054,404 bytes and are deliberately
excluded from Git. A content-addressed release asset makes the static showcase
buildable from a clean clone without downloading or reconstructing provider
data.

## Pinned asset

| Property | Value |
|---|---|
| Dataset | `wyscout-2017-18-v2-dc398ff5661c` |
| Representation | `rep-f018e6041ccbad10` |
| Manifest-declared paths | 1,257 |
| Archive format | deterministic `tar+gzip` |
| Archive bytes | 23,453,297 |
| SHA-256 | `4a5c092d8d6fcee2a5f7a226fe79e7e89079ffb668c43f863da6259df5d29635` |
| Immutable tag | `showcase-wyscout-2017-18-v2-dc398ff5661c-rep-f018e6041ccbad10` |
| Asset | [`scoutlens-showcase-wyscout-2017-18-v2-dc398ff5661c-4a5c092d8d6fcee2a5f7a226fe79e7e89079ffb668c43f863da6259df5d29635.tar.gz`](https://github.com/grunobuide/scoutlens/releases/download/showcase-wyscout-2017-18-v2-dc398ff5661c-rep-f018e6041ccbad10/scoutlens-showcase-wyscout-2017-18-v2-dc398ff5661c-4a5c092d8d6fcee2a5f7a226fe79e7e89079ffb668c43f863da6259df5d29635.tar.gz) |

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
  --output artifacts/showcase-payload/scoutlens-showcase-wyscout-2017-18-v1-31d2ccc6af37-9a57719458cc6666169f5e38c169e1dafbe8a9a5aabce79db3a1e76e9ac3dc32.tar.gz
```

The builder validates the source set and all manifest checksums first, sorts
paths, and normalizes timestamps, ownership, permissions, gzip headers, and tar
metadata. Two builds must reproduce the pinned 23,453,297 bytes and SHA-256.

## Scientific evidence asset

Published alongside the payload under the same immutable tag, as a **separate
asset**. It is offline audit evidence for the intervals the Lab shows, not a
runtime input: the site never fetches it and hydration does not need it. Only
the payload URL enters `config/showcase-payload-pack.json`.

| Property | Value |
|---|---|
| Archive bytes | 1,660,853 |
| SHA-256 | `99c273f50ac7c31507ed83dd8ad6b8350a60324f216ce41116760af0d7c5cea2` |
| Members | `CHECKSUMS.json`, `README.md`, `run.json`, and the three `match_bootstrap_diagonal_v1` parquet summaries |
| Asset | [`scoutlens-showcase-evidence-wyscout-2017-18-v2-dc398ff5661c-99c273f50ac7c31507ed83dd8ad6b8350a60324f216ce41116760af0d7c5cea2.tar.gz`](https://github.com/grunobuide/scoutlens/releases/download/showcase-wyscout-2017-18-v2-dc398ff5661c-rep-f018e6041ccbad10/scoutlens-showcase-evidence-wyscout-2017-18-v2-dc398ff5661c-99c273f50ac7c31507ed83dd8ad6b8350a60324f216ce41116760af0d7c5cea2.tar.gz) |

Verify it before use:

```bash
uv run --frozen python -m scoutlens.showcase.evidence_bundle verify   --archive <downloaded>.tar.gz
```

That refuses the archive unless its members are exactly the allowlist in
canonical order and every source matches `CHECKSUMS.json`.

## Two versions, and why they are not the same number

Frozen by `D050`. The pin document carries both, and conflating them is how a
pin ends up promising a dataset it does not describe:

| Field | Versions |
|---|---|
| `schema_version` | the **pin document** itself |
| `showcase_schema_version` | the **artifact contract** being hydrated |

They move independently. A `2.0.0` pin hydrates a showcase `2.0.0` dataset
today, but a later pin revision would raise the first without touching the
second.

### Key sets are exact per schema

`1.0.0` accepts only the frozen legacy shape. `2.0.0` additionally requires
`showcase_schema_version`, `manifest_sha256` and `representation`
(`id` and `sha256`). Neither accepts the other's fields, so a document mixing
the two is rejected rather than validated on the union, and the dataset-version
prefix must match the schema's major.

The manifest and representation digests are pinned because the archive carries
players only: both of those files are tracked in Git and could be at any
revision. Without pinning them a v2 player set could hydrate against a manifest
that never produced it, and every per-file check would still pass, because each
extracted profile would match a manifest that is simply the wrong one.

### Hydration derives its own target

With no explicit paths, `hydrate` resolves `public/showcase/v{major}/manifest.json`
and `players/` from the validated pin, and only after validation. There is no
fallback to v1. Explicit `--manifest` and `--output-dir` remain available for
tests and recovery and must still agree with every pinned identity.

### Building a candidate pin

```bash
uv run --frozen python -m scoutlens.showcase.payload pin   --sidecar artifacts/showcase-payload/<candidate>.tar.gz.metadata.json   --verified-archive artifacts/showcase-payload/<candidate>.tar.gz   --manifest public/showcase/v2/manifest.json   --representation public/showcase/v2/representation.json   --url https://.../<content-addressed-name>.tar.gz   --output artifacts/showcase-payload/candidate-pin.json
```

Every field is recomputed from the artefacts and then required to agree with the
sidecar; the sidecar is an operator convenience, never the authority. The
document is round-tripped through the loader before it is written, and replacing
an existing pin requires `--replace` because it retargets every clean clone.

### Rolling back to v1

The frozen `1.0.0` shape stays accepted for exactly the v1 dataset, so restoring
the previous `config/showcase-payload-pack.json` is the whole rollback. The
web consumer follows the same way: `DEPLOYED_SHOWCASE_MAJOR` in
`web/src/contracts/showcase-repository.ts` goes back to `1`.

## Licence and redistribution boundary

The asset contains only ScoutLens player-period aggregate profiles already
declared by the public manifest. It contains no event rows, match rows, provider
files, processed Parquet, credentials, or proprietary branding. The underlying
Pappalardo/Wyscout public dataset is attributed and licensed CC BY 4.0 as
recorded in [`data-provenance.md`](data-provenance.md); the repository's MIT
code licence does not relicense the source data. Any future payload must repeat
the provenance audit and receive a new dataset/version pin.
