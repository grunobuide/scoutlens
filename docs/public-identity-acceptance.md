# Public identity — acceptance packet

`scoutlens-vif.6`. Verification of the Yumusarái Labs delivery against
[`public-identity-contract.md`](public-identity-contract.md) and `D058`.

**This document changes nothing.** It is a read-only verification pass. Where it
found defects they are filed as beads and named below, not fixed here — a QA
commit that repairs what it is auditing cannot be trusted to have audited it.

---

## 1. Three states, kept separate

The design note for this bead asks for these not to be reported as one another,
because they are usually conflated and the difference is where a release goes
wrong.

| State | Status | Evidence |
|---|---|---|
| **Implementation integrated** | ✅ | `vif.2` `dedd5cd`, `vif.3` `c30f4ba`, `vif.4` `0045ea4`, `vif.5` `af96be6`, all on `main` with `quality` green |
| **Deployed identity verified** | ✅ | Served from `af96be6` by `deploy` run [36139469798](https://github.com/grunobuide/scoutlens/actions/runs/36139469798), smoke 9/9; every surface checked against the live site in §2. The commit had to be taken from the Actions run, because the served page does not name it — `scoutlens-uze.20`, §7 |
| **Promotion ready** | ⛔ **No** | The GitHub repository description claims RAG and AI this project does not have — `scoutlens-vif.7`, §7. Sending anyone to the repository today leads with a false claim |

The third row is the point of separating them. The implementation is complete
and the deployment is correct; the project is still not ready to be pointed at.

---

## 2. The identity, as served

Fetched from <https://grunobuide.github.io/scoutlens/> on 2026-09-25.

### 2.1 Every route

| Route | `<title>` | `YL` mark | wordmark | `… home` label |
|---|---|---|---|---|
| `/` | `Yumusarái Labs — Player Fingerprints` | ✅ | ✅ | ✅ |
| `/lab/` | `Fingerprint Lab — Yumusarái Labs` | ✅ | ✅ | ✅ |
| `/science/` | `How it works — Yumusarái Labs` | ✅ | ✅ | ✅ |
| `/lab/?player=wy-8287-c-795` | `Fingerprint Lab — Yumusarái Labs` | ✅ | ✅ | ✅ |

Both halves of the metadata contract are exercised: the **default** title on `/`
and the **template** on the other three. The accent is served everywhere, and
the ASCII fallback `Yumusarai Labs` appears on **no** route — it is a convention
for places that cannot carry an accent, and a rendered page is not one.

### 2.2 The shareable deep link

`/lab/?player=wy-8287-c-795` returns **200**, with `<h1>Compare one player with
himself.</h1>`, the profile (`L. Modrić`) and the *Share this profile* control
present **in the server-rendered HTML**. A static host has no router, so this
only resolves because the path itself is a real file.

The skip link and the wordmark are likewise in the served HTML, which is the
no-JS guarantee at the source rather than at a browser: nothing about the
identity depends on scripting.

### 2.3 Narrow widths, focus order, fail-closed state

Verified in `vif.4` and quoted here rather than re-run, per this bead's
instruction not to invent a success:

- widths **320, 360, 769, 1280** — no page overflow, no header overflow, the
  wordmark text exact and not clipped (`scrollWidth` vs `clientWidth`, because
  an element reports its box happily while glyphs are cut off);
- focus order unchanged — skip link → wordmark home → Overview → Fingerprint Lab
  → How it works, with the home link answering to the new accessible name;
- the fail-closed integrity state renders the renamed message **and still
  refuses to show profile values** (`.selected-profile` count 0);
- `á` renders in the pinned Inter subset, asked of Chromium through CDP rather
  than assumed — a missing glyph does not error, it falls back to Arial silently.

---

## 3. The old name, fully accounted for

AC1 asks that no **unexplained** old brand remain. Counted on the served HTML of
each route:

| Route | occurrences of `ScoutLens` | all accounted for? |
|---|---|---|
| `/` | 2 | ✅ |
| `/lab/` | 2 | ✅ |
| `/science/` | 2 | ✅ |
| `/lab/?player=wy-8287-c-795` | 2 | ✅ |

Every one is the same string:

> ScoutLens publishes attributed player-period aggregates only; raw provider
> rows remain excluded.

Two per route because it appears once in the rendered DOM and once in the RSC
flight payload. It comes from `manifest.source.redistribution_note` in a
content-addressed artifact whose digest is pinned by
`config/showcase-payload-pack.json` and belongs to an already published release
asset. Contract §5 covers it; `README.md` and `docs/case-study.md` explain it to
readers; `web/e2e/public-identity.spec.ts` asserts that *every* occurrence on the
page is this one, so a missed display surface fails the build.

**Zero was never the target.** "No unexplained old brand" is, and it is met.

---

## 4. What a rename was not allowed to touch

### 4.1 Scientific identity, served and local

| | served | pinned locally | agree |
|---|---|---|---|
| contract | `scoutlens.showcase` | `scoutlens.showcase` | ✅ |
| dataset | `wyscout-2017-18-v2-332766e3a822` | same | ✅ |
| representation | `rep-f018e6041ccbad10` | same | ✅ |
| schema | `2.0.0` | `2.0.0` | ✅ |
| profiles | 1,257 | 1,257 | ✅ |

`public/showcase/v2/manifest.json` hashes to
`ed01ff11b716d0cc1991251440e06c56e6c1b7ab3a79ecf3d07e47bd981f7c74`, exactly the
`manifest_sha256` the payload pack pins.

### 4.2 Claims, caveats and the model that was not run

`python -m scoutlens.release.claims` exits 0: 8 claims, 4 published caveats,
every claim naming its evidence and carrying at least one caveat. The
`same_season_team_confound` at severity `critical` is still attached to every
claim it qualifies, and `0.5893` is still the headline limitation in the case
study.

`run_report --check` exits 0 and the committed artifact is byte-identical to the
command's output. The live gate still records **`not_run`** — deliberately
distinct from a pass — and no demonstration model has been evaluated.

### 4.3 Offline by default, still enforced

The default path takes no credential and opens no socket; `SCOUTLENS_MODEL_API_KEY`
remains the only credential channel and is never a CLI argument. Unchanged by
this delivery and covered by the existing suite.

---

## 5. The v1.0.0 release is untouched

| | |
|---|---|
| Tag object | `d982262c54a0eea02681757ae3cdb6519f91966e` |
| Points at | `dedd5cd36c1abe5d7f1bff5cff523355a78343ed` |
| Published | 2026-09-24T14:34:12Z, not a draft, not a prerelease |
| Assets | `scoutlens-release-manifest-v1.0.0.json` (unchanged) |

The tag predates every identity commit. Nothing in this delivery re-tagged,
re-pointed or overwrote it, and `v1.0.0` still describes the site as it shipped
under the old name — which is correct, because that is what it released.

---

## 6. Gates

Integrated runs, quoted:

| Gate | Where | Result |
|---|---|---|
| `quality` on `0045ea4` (the rename) | run [36062559347](https://github.com/grunobuide/scoutlens/actions/runs/36062559347) | success — pytest 3.11, pytest 3.14, `static-quality`, `web-quality` |
| `deploy` + `smoke` on `0045ea4` | run [36063429790](https://github.com/grunobuide/scoutlens/actions/runs/36063429790) | success, smoke 9/9 |
| `quality` on `5a150b2` (vif.5 head) | run [36063961263](https://github.com/grunobuide/scoutlens/actions/runs/36063961263) | success |
| `quality` on `af96be6` (this tree) | run [36138741183](https://github.com/grunobuide/scoutlens/actions/runs/36138741183) | success — all four jobs |
| `deploy` + `smoke` on `af96be6` | run [36139469798](https://github.com/grunobuide/scoutlens/actions/runs/36139469798) | success, smoke 9/9 |

Re-run for this packet, on `af96be6`:

```
uv run --frozen pytest -q                       1145 passed, 40 skipped
uv run --frozen ruff check .                    All checks passed
uv run --frozen mypy src/scoutlens              no issues in 101 source files
uv run --frozen python -m scoutlens.release.claims          exit 0
uv run --frozen python -m …explanations.evals.run_report --check   exit 0
uv run --frozen python .github/scripts/smoke-production.py …       9/9, exit 0
cd web && pnpm release:check                    exit 0
git diff --check                                clean
bd dep cycles --json                            []
```

---

## 7. Findings

None of these blocks the *deployed identity*. One blocks **promotion**.

| Bead | P | Finding |
|---|---|---|
| **`scoutlens-vif.7`** | **P1** | **The GitHub repository description reads "AI and RAG in Football Analysis…". There is no RAG anywhere in this project, no AI in the deployed site, and no model has been evaluated. It is the first thing a visitor reads, above the README, and it outranks every disclaimer in the documents.** The homepage field is also empty, so the repository does not link the live site |
| `scoutlens-uze.19` | P2 | The visual gate's `maxDiffPixelRatio: 0.03` was large enough to hide the wordmark changing on every page. Measured at zero tolerance: 6,944 and 4,671 pixels, both ratio 0.01. The committed baselines still depict the old brand and still pass |
| `scoutlens-uze.20` | P2 | Deploying a **docs-only** commit changed the served HTML. Two consecutive builds of an identical tree differ by exactly one thing: a 21-character random Next.js build ID embedded in every page. So a no-op deploy is indistinguishable from a real one by digest, and the served site cannot name the commit that built it |
| `scoutlens-9a3.16` | P2 | `/science` renders "2017/18season" with no space — and it is now visible in committed portfolio media. Disclosed in `docs/media/README.md` rather than retouched; raised P3 → P2 because the defect did not get worse, its audience did |
| `scoutlens-jtt.20` | P3 | The inherited 60–90 second captioned demo (`jtt.7.3` AC3) was never delivered. Still disclosed as a gap in both the case study and the media note; the stills are not presented as a substitute |
| `scoutlens-jtt.21` | P2 | `manifest_digest()` hashes `git.branch`, so a verifier re-running it detached from the tag gets a different digest while every content digest agrees |

### Why the served commit had to be inferred

This packet wanted to bind the live site to a commit by reading it. It cannot,
and finding out why produced `uze.20`.

The home page served before this delivery's last deploy hashed to
`1e8a581a…`; afterwards, `2b0901b1…`. But `af96be6` is a **docs-only** commit —
`git diff --name-only 0045ea4 af96be6` touches README, `docs/**` and `tests/**`
and no web build input at all. Stable across three fetches, so not CDN variance.

Reproduced locally by building the same tree twice. The two `index.html` files
are the **same length**, 69,007 bytes, and differ in exactly one place:

```
build A   "b":"tj2dXAxVkp57Bhy4D9mx6"
build B   "b":"TFAwgk1gj5XiOVEOy_bj8"
```

A random 21-character Next.js build ID, embedded in every page's flight payload.
Nothing else moves; even the chunk filenames are stable.

Two consequences, and the second is the one that bit this bead. A no-op deploy
cannot be distinguished from a real one by digest — which is the one check a
project this careful about content addressing ought to have. And the delivered
HTML names no commit, so "which version am I looking at" is answerable only from
the Actions log. Deriving the build ID from the commit fixes both at once.

### Why `vif.7` was missed

The contract's §3 inventory enumerated display surfaces **in files**, which is
what a test can reach. The repository description, topics, homepage field and
social preview live in GitHub settings. Nothing in the rename touched them and
nothing in the suite can see them. That gap is `vif.7`'s AC4: the contract
should gain a settings-side section so the next identity change does not repeat
it.

---

## 8. What remains, and whose call it is

**For the owner, before pointing anyone at this project:**

1. Rewrite the repository description (`vif.7`). Repository settings are
   outward-facing and were read-only to this bead, so no change was made. A
   proposed wording is in the bead, for acceptance or replacement.
2. Set the homepage field to <https://grunobuide.github.io/scoutlens/>.

**Not blocking, already routed:** `uze.19`, `9a3.16`, `jtt.20`, `jtt.21`.

**Explicitly not claimed by this packet:** that public comprehension was
validated — it was not, `D056` stands with one evaluator and no independent
post-fix re-run; that any model has been evaluated — none has; and that the
name is legally available — domain, handle and trademark status remain
unverified, and no registration was made or authorised.
