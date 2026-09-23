# ScoutLens v1.0.0 — release-candidate audit

What is being frozen, what was checked, what was found, and what is explicitly
not claimed.

Bead `scoutlens-jtt.7.1`. This document is evidence, not a summary: every number
below came from a command run against this tree, and §9 says how to re-run each
one. Where something could not be verified, it says so rather than omitting it.

---

## 1. What is being frozen

The identity of a candidate is computed rather than remembered:

```bash
uv run --frozen python -m scoutlens.release.manifest
```

It prints canonical JSON and **exits non-zero on a dirty tree**, because a
manifest taken from a dirty working copy does not describe a reproducible
commit. Run it on the candidate commit to obtain the commit-bound record; the
content identities below are stable and do not depend on which commit carries
them.

### Version

| | |
|---|---|
| Project version | `1.0.0` (was `0.2.0.dev0`) |
| Python floor | `>=3.11`; CI runs 3.11 and 3.14 |
| Node | `24.14.0` (`web/.node-version`) |

### Contracts

| Contract | Version |
|---|---|
| `scoutlens.showcase` (published artifact) | `2.0.0` |
| Explanation bundle schema | `1.0.0` |
| Explanation output schema | `1.0.0` |
| Prompt contract | `1.0.0` |
| Adapter protocol | `1.0.0` |
| Evaluation corpus | `1.0.0` |

### Dataset

| | |
|---|---|
| Dataset version | `wyscout-2017-18-v2-332766e3a822` |
| Representation | `rep-f018e6041ccbad10` |
| Payload archive | `d357540984e054748a06181620ba591af6a1190e5da4adce5800d49628d5ffec` (23,451,200 bytes, 1,257 paths) |

The dataset is content-addressed and pinned in
`config/showcase-payload-pack.json`. A clean clone reproduces it exactly by
hydrating that pin; `public/showcase/*/players/` is deliberately not tracked.

### Versioned inputs

| File | sha256 |
|---|---|
| `config/experiment.json` | `6b04c4ebb2d36eb1a93e7856008823207dca7b8e5ce384c3dafd8e8cbd4d7cd1` |
| `config/uncertainty.json` | `e23d7afb565ce757a41d4c944f7c0cd1e9d76d7af7c4ce50cd0999ac460c9d3d` |
| `config/uncertainty-diagonal.json` | `138abf784d8f5a0bc5a8bcca3d0e51306389da974206d089f1a6895d53f281bb` |
| `config/showcase-payload-pack.json` | `18a46fd349dc921f32422864c59affdd5ea92c39f8a5f4b33fad226a6bf68603` |

### Published artifacts

| File | sha256 |
|---|---|
| `public/showcase/v2/manifest.json` | `ed01ff11b716d0cc1991251440e06c56e6c1b7ab3a79ecf3d07e47bd981f7c74` |
| `public/showcase/v2/representation.json` | `30439e647a31c4fd63f8502647801c47882b248714c58a98b41e7986df2cd4a3` |
| `public/showcase/v2/players.index.json` | `322f21a4c98c6db3b83fe001b0b6e11c8d10fca92a4c50640b6c1d9405c4192b` |
| `public/showcase/v2/feature-catalog.json` | `b1d71bf9d1f86d488207136797ac65e303b26f284f0a16a4707659a57872e629` |
| `public/showcase/v2/research-summary.json` | `9efbc6b052a1a57c334853c125ff9019f1e58572a653436155755391756c2600` |
| `artifacts/ai-evals/grounded-explanations-v1.json` | `28035380609c964366b93970d28e8058ee73a63952f3eae4384dcc5e1a4b3713` |

The representation digest in the payload pin and the digest of the published
`representation.json` are the same value, and a test asserts it. A pin that
claimed a representation the repository does not ship would otherwise be
invisible.

## 2. Gate results

Every gate, run against this tree.

| Gate | Result |
|---|---|
| `ruff check .` | All checks passed |
| `mypy src/scoutlens` | no issues in 101 source files |
| `pytest -q` (with `SCOUTLENS_REQUIRE_SHOWCASE=1`) | **1076 passed, 40 skipped** |
| `uv build` | `scoutlens-1.0.0` sdist + wheel |
| `pnpm quality` | passed — contracts, lint, typecheck, unit tests, static export |
| `pnpm budget:check` | passed, every budget with headroom |
| `pnpm test:e2e` | **210 passed, 68 skipped** |
| `pnpm lighthouse` | passed, 3 runs, all assertions |
| `run_report --check` (AI eval replay) | exit 0, matches the committed artifact |
| `claims` matrix | exit 0, 8 claims, no findings |
| `SCOUTLENS_DRIFT=1 pytest tests/evaluation/test_artifact_drift.py` | **6 passed** in 233s |

The 40 skipped Python tests are the deliberate opt-in integration suites
(`SCOUTLENS_*_INTEGRATION`) plus the v1 audit-baseline tests, which no clean
clone can run — see §6.

The drift gate recomputed all six result sets from local processed data and
found no drift, which is the check that the committed `artifacts/*_results.json`
still match what the pipeline produces. It needs `data/processed/*.parquet` and
so cannot run in CI; it was run here, for this candidate, and that is the point
of running it at freeze time rather than relying on CI.

### 2.1 Clean-clone verification

Run during `scoutlens-jtt.6` closure and repeated here, because "works on a
clean clone" is the claim most often asserted and least often tested. A fresh
`git clone --depth 1`, `uv sync --frozen --all-groups`, hydrate, then:

```
hydrate                 1257 profiles, wyscout-2017-18-v2-332766e3a822
cli explain             exit 0, status validated, no credential, no network
run_report --check      exit 0, byte-identical to the committed artifact
pytest (CI mode)        1035 passed, 57 skipped, 0 failures
```

That run also confirmed the committed eval artifact arrives with **0 CRLF
bytes** on a Windows clone, so the `eol=lf` rule is doing what it claims.

It found one real defect — a test that read a v1 payload no clean clone can
obtain — fixed before this candidate. That is the return on actually running
the check instead of reasoning about it.

### Budget headroom

| Budget | Used | Limit |
|---|---|---|
| Initial `/lab` JavaScript | 161,454 | 204,800 gzip bytes |
| Initial `/lab` transfer (excl. fonts) | 285,827 | 768,000 gzip bytes |
| Feature catalog | 1,567 | 409,600 gzip bytes |
| Largest player profile | 19,163 | 30,720 gzip bytes |

## 3. Claims matrix

Derived from `public/showcase/v2/research-summary.json` — the artifact the site
actually renders — rather than hand-maintained, so it cannot drift from what a
reader sees:

```bash
uv run --frozen python -m scoutlens.release.claims
```

It exits non-zero if any conclusion lacks a caveat, cites a caveat the artifact
does not publish, names no source artifact or report, publishes no metric, or if
a `critical` caveat is published but carried by no claim. **It exits 0 on this
candidate.**

8 claims, 4 published caveats, all attributable:

| Claim | Provider | Evidence | Caveats carried |
|---|---|---|---|
| `wyscout_global_gate2` | Wyscout/Pappalardo | `artifacts/gate2_results.json` | `fingerprint_not_style_proof`, `same_season_team_confound` |
| `wyscout_within_role_gate2` | Wyscout/Pappalardo | `artifacts/gate2_results.json` | `fingerprint_not_style_proof`, `same_season_team_confound` |
| `wyscout_role_team_minutes` | Wyscout/Pappalardo | `artifacts/robustness_results.json` | `same_season_team_confound` |
| `wyscout_transferred_players` | Wyscout/Pappalardo | `artifacts/transfer_analysis_results.json` | `small_transfer_sample`, `fingerprint_not_style_proof` |
| `statsbomb_global_replication` | StatsBomb open data | `artifacts/statsbomb_replication_results.json` | `provider_replication_lower_magnitude`, `same_season_team_confound` |
| `statsbomb_within_role_replication` | StatsBomb open data | `artifacts/statsbomb_replication_results.json` | `provider_replication_lower_magnitude`, `same_season_team_confound` |
| `statsbomb_transferred_players` | StatsBomb open data | `artifacts/statsbomb_replication_results.json` | `small_transfer_sample`, `provider_replication_lower_magnitude` |
| `wyscout_ratio_shrinkage` | Wyscout/Pappalardo | `artifacts/shrinkage_experiment_results.json` | `fingerprint_not_style_proof` |

**The supported claim.** Event-derived profiles contain a reproducible
individual fingerprint that supports same-player temporal retrieval across two
chronological halves.

**Explicitly not claimed**, in the artifact and on the site:

- statistical similarity proves playing style;
- a statistical neighbour is a recruitment recommendation or replacement;
- the experiment predicts future performance, tactical fit, value or transfer
  success.

Two of the four caveats are `critical` and both are carried:
`fingerprint_not_style_proof` and `same_season_team_confound`. The latter is the
uncomfortable one and is published anyway — team continuity is a *stronger*
shortcut than the fingerprint in this same-season design, and the project says
so in its own claims matrix.

## 4. Licences and attribution

### Code

MIT, and now stated consistently. `LICENSE`, `pyproject.toml` (`license =
"MIT"`), `README.md` and `DATA_LICENSES.md` agree.

**Finding, fixed in this candidate.** `DATA_LICENSES.md` opened by saying the
code licence was *"not yet decided"* and pointed the reader at `README.md`,
which said MIT. Three files said MIT and the fourth said undecided. Corrected
here; shipping a 1.0.0 whose licensing file contradicts its own `LICENSE` is not
a defensible release.

### Data

| Source | Licence | Redistributed? |
|---|---|---|
| Soccer match event dataset (Pappalardo & Massucco), DOI `10.6084/m9.figshare.c.4415000` v5 | CC BY 4.0, verified per artifact on 2026-07-20 | No raw data. Attributed player-period aggregates only, published under CC BY 4.0. |
| StatsBomb open data | Per StatsBomb terms | Aggregate results only. No per-player StatsBomb data is published. |

`docs/data-provenance.md` carries the per-artifact DOIs and checksums;
`docs/statsbomb-provenance.md` carries the aggregate-only boundary. The site
states the attribution on the page a reader reaches it from, not only in a file
they would have to go looking for.

### Dependencies

**Python — 5 declared runtime dependencies**, 29 installed distributions, all
permissive:

| Licence | Count |
|---|---|
| MIT | 15 |
| BSD (2/3-clause, generic) | 5 |
| Apache-2.0 | 4 |
| MPL-2.0 | 2 |
| PSF-2.0 | 1 |
| Apache-2.0 OR BSD-2-Clause | 1 |

Zero distributions with no declared licence. No provider-specific AI SDK:
`fireworks-ai` was removed in `scoutlens-jtt.6.2`, which is what keeps the base
runtime provider-neutral.

**Web — 66 production packages**: 48 MIT, 7 Apache-2.0, 5 ISC, 2 BSD-3-Clause,
1 OFL-1.1 (the Inter font), 1 CC-BY-4.0, 1 0BSD.

One package needed a closer look: **`@img/sharp-win32-x64`, `Apache-2.0 AND
LGPL-3.0-or-later`**. It is a transitive, platform-specific binary of `sharp`,
pulled in by `next`, and it bundles libvips under LGPL.

It is **not distributed and never executed**: `next.config.ts` sets `images: {
unoptimized: true }`, which is required for `output: "export"` and means Next's
image optimizer never runs. Nothing derived from libvips reaches `out/`. The
OFL-1.1 font *is* distributed, self-hosted, which OFL permits.

## 5. Security and privacy

### Secret scan

A pattern scan over **375 tracked files** — AWS keys, private-key blocks,
GitHub/Slack/OpenAI tokens, bearer tokens and assigned-secret literals, with
environment reads and placeholders excluded. **No secrets found.**

Nothing in this repository requires a credential to build, test or deploy. The
only credential the project knows about is `SCOUTLENS_MODEL_API_KEY`, read from
the environment by the optional AI adapter, never from an argument, and never
required by any default path.

### Browser network and privacy audit

Done in a real browser against the built static output, not by reading source.
Served `out/` and loaded every route:

| Route | Requests | External |
|---|---|---|
| `/` | 11 | **0** |
| `/lab` | 13 | **0** |
| `/science` | — | **0** |
| `/lab` after interacting with the player search | 61 cumulative | **0** |

Every request is same-origin. Fonts are self-hosted (2 `woff2`). **No
analytics, no tag manager, no third-party CDN, no external stylesheet, no
external script.** The external URLs present in the HTML are link targets a
reader may choose to follow — GitHub, DOI, Creative Commons, W3C namespaces —
not automatic requests.

A keyword scan initially flagged `plausible` in `index.html`. It is the English
word, in a heading about the shrinkage null result. Recorded because a reader
running the same scan will hit it too.

**One finding.** Two Next.js RSC prefetch payloads 404 on every page load. The
files are genuinely absent from the export while the client requests them.
Navigation is unaffected — verified by clicking through client-side — so this is
console noise and a wasted round trip rather than a correctness defect.
`scoutlens-uze.17`, non-blocking.

### Dependency audit

No unresolved critical or high issue. Both lockfiles are committed and pinned by
digest in the manifest; both CI toolchains install with `--frozen`.

## 6. Findings

Nothing found changes analytical output, so under this bead's stop rule the
candidate stands.

### Fixed in this candidate

1. **`DATA_LICENSES.md` contradicted `LICENSE`** on the code licence. §4.
2. **A test required a v1 payload no clean clone can obtain**, found by the §2.1
   clean-clone run. Fixed in `scoutlens-jtt.6.4` before this candidate.

### Recorded, non-blocking, with beads

| Finding | Bead |
|---|---|
| Two RSC prefetch payloads 404 on every page load | `scoutlens-uze.17` |
| The v1 cosine audit baseline has no CI coverage | `scoutlens-jtt.18` |
| `web/.node-version` pins 24.14.0; local development ran 24.18.0 | see below |

The Node divergence is local-only: CI installs from `.node-version`, so CI is
correct. It surfaced as a pnpm engine warning during this audit and is recorded
so nobody mistakes it for a CI problem.

### Not fixed, and not fixable here

**No demonstration model has been evaluated.** `scoutlens-jtt.6` AC4 asks the
reference adapter to pass an opt-in smoke test against a configurable
OpenAI-compatible endpoint, and `scoutlens-jtt.6.3` AC3 asks a demonstration
model to clear a preregistered threshold over three runs. Both harnesses exist
and are tested against stubs. Neither has been run against a real model: none
was available.

The live gate therefore records **`not_run`**, which is deliberately a third
outcome distinct from pass and drop. **This release makes no claim about any
model's behaviour.** The 2026-08-11 human policy permits exactly this — the
toolkit, the offline evaluations and the deterministic fallback ship without a
demonstration model.

**Public comprehension is n=1.** `D056`: one evaluator, recorded as a block at
2:53. Communication defects were remediated technically and the automated gates
were unchanged. This is not a retroactive pass, and comprehension is **not**
claimed as validated.

## 7. What a reader is not being told

Stated plainly because a release audit that only lists what passed is marketing.

- The AI evaluation report measures the **validator, the corpus and the
  fallback**, using responses the package synthesises deterministically from
  each bundle. No model produced them. The file says so in its own
  `response_source_note`, and `docs/ai-eval-method.md` §1 says it first.
- The retrieval task is **same-season**, and same-season club continuity is a
  known, published, critical confound that makes the task easier than it looks.
- The transferred-player evidence rests on a **small sample with wide
  uncertainty**, and the StatsBomb transferred-player result is **inconclusive**.
- The independent-provider replication is **positive but lower in magnitude**
  than the Wyscout result.
- Two experiments are **null results that are published rather than retried
  differently**: shrinkage did not improve retrieval, and neural contrastive
  representations did not clear the gate.

## 8. Outstanding before tagging

This document audits a candidate. It does not tag a release. Before `v1.0.0` is
tagged:

1. the candidate commit must be on `main` with CI green;
2. `python -m scoutlens.release.manifest` must be re-run **on that commit, from
   a clean tree**, and its output recorded — it exits non-zero otherwise;
3. deployment (`scoutlens-jtt.7.2`) and the case study (`scoutlens-jtt.7.3`)
   follow, and neither is in scope here.

Any finding that changes analytical output reopens the owning bead and
invalidates this candidate. None of the findings in §6 does.

## 9. Reproducing this audit

```bash
uv sync --frozen --all-groups
uv run --frozen python -m scoutlens.showcase.payload hydrate

# identity
uv run --frozen python -m scoutlens.release.manifest

# claims
uv run --frozen python -m scoutlens.release.claims

# python gates
uv run --frozen ruff check .
uv run --frozen mypy src/scoutlens
SCOUTLENS_REQUIRE_SHOWCASE=1 uv run --frozen pytest -q
uv build

# the recorded AI evaluation, offline
uv run --frozen python -m scoutlens.explanations.evals.run_report --check

# web gates
cd web && pnpm install --frozen-lockfile && pnpm release:check

# drift, requires local processed data
SCOUTLENS_DRIFT=1 uv run --frozen pytest tests/evaluation/test_artifact_drift.py
```

The secret scan and the browser audit were run ad hoc and are described in §5
precisely enough to repeat: scan tracked files for credential patterns, and load
each route of the built `out/` in a browser while recording network requests.
