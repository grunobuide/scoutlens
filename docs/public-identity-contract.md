# Public identity contract — Yumusarái Labs

Frozen by `scoutlens-vif.2`, decision [`D058`](decisions-log.md). The owner chose
the name in `scoutlens-vif.1` on 2026-09-24.

This contract exists so the rename can be executed by *surface*, not by search
and replace. It names every string that changes, every string that must not, and
the one reader-facing occurrence of the old name that **cannot** be changed at
all. It binds `scoutlens-vif.3`, `.4`, `.5` and `.6`.

**It does not widen any existing contract.** Every path below is already Allowed
or already Conditional in `docs/frontend-agent-contract.md` §1; this document
supplies the named-reviewer approval that the Conditional level requires, and
nothing more. Where the two disagree, the frontend contract wins and the
executor stops — the same rule `CLAUDE.md` applies to beads.

> **That file is not linked because it is not in the repository.**
> `.gitignore:77` ignores `docs/frontend-agent-contract.md` while its sibling
> `docs/modeling-agent-contract.md` is tracked. That is a known defect,
> `scoutlens-iex.8`, and it means a reader on GitHub cannot open the contract
> this one defers to. Fixing it is out of scope here; pretending the link works
> is not an option, so the path is quoted and the asymmetry is stated.

---

## 1. The frozen identity

| Field | Value |
|---|---|
| Display name | **Yumusarái Labs** — with the acute accent, exactly |
| ASCII slug | `yumusarai-labs` |
| Plain-text fallback | `Yumusarai Labs` (only where an accent cannot be carried) |
| Monogram | **YL** — two letters, replacing `SL` in the existing header mark |
| Product descriptor | **Player Fingerprint Lab** — unchanged |
| Title default | `Yumusarái Labs — Player Fingerprints` |
| Title template | `%s — Yumusarái Labs` |
| Attribution | *Nome inspirado em yumusarái, do nheengatu, associado a brincar e divertir-se.* |

**On the attribution.** The sources are recorded in `scoutlens-vif.1`: Taylor,
*Contos populares em nheengatu* (RBLA 17, 2025) glosses *divertir-se*, and the
UnB 2020 dissertation glosses `u-yumusarai` as *brincar*. Two things follow, and
both are binding on copy:

- The language is **Nheengatu**, named as such. Do not write "Tupi", do not
  merge language varieties, and do not imply Indigenous endorsement of anything
  this project publishes.
- *Celebrar* is the owner's intended brand association. It is **not** a verified
  dictionary translation and may not be presented as one. Brand intent may be
  stated as intent; a gloss may only be stated with its source.

**On availability.** The collision check in `vif.1` found no obvious same-name
Labs brand. That is not proof. Domains, handles and trademark status are
**unverified**, no availability claim may be published, and no registration or
purchase is authorised by this contract or by any child of `scoutlens-vif`.

---

## 2. The rule this whole contract reduces to

> **The brand is what a reader sees. The identity is what a machine resolves.
> They are now two different names, on purpose.**

A reader sees Yumusarái Labs. A build, an import, a URL, a dataset pin, an
environment variable, a schema string and a Beads id all still say `scoutlens`,
and will keep saying it. That is not lag to be cleaned up later — renaming any
of them would break a published artifact digest, a live deep link, or a
reproduction command printed in the case study.

Every ambiguity below resolves by asking which of those two a string is.

---

## 3. Display-surface inventory — what changes

Twelve strings in six files. This list is exhaustive: a string not on it is not
part of the rename, and finding a thirteenth is a stop condition for `vif.4`
(§9), not a licence to edit it.

| # | Location | Current | Becomes | Level (frontend §1) |
|---|---|---|---|---|
| 1 | [`layout.tsx:29`](../web/src/app/layout.tsx) | `ScoutLens — Player Fingerprints` | `Yumusarái Labs — Player Fingerprints` | Allowed |
| 2 | `layout.tsx:30` | `%s — ScoutLens` | `%s — Yumusarái Labs` | Allowed |
| 3 | `layout.tsx:34` | `applicationName: "ScoutLens"` | `applicationName: "Yumusarái Labs"` | Allowed |
| 4 | [`site-header.tsx:13`](../web/src/components/site-header.tsx) | `aria-label="ScoutLens home"` | `aria-label="Yumusarái Labs home"` | Allowed |
| 5 | `site-header.tsx:15` | mark `SL` | mark `YL` | Allowed |
| 6 | `site-header.tsx:17` | wordmark `ScoutLens` | wordmark `Yumusarái Labs` | Allowed |
| 7 | [`page.tsx:47`](../web/src/app/page.tsx) | `ScoutLens tests whether…` | `Yumusarái Labs tests whether…` | **Conditional** — copy string |
| 8 | `page.tsx:52` | `aria-label="Explore ScoutLens"` | `aria-label="Explore Yumusarái Labs"` | **Conditional** — copy string |
| 9 | [`science/page.tsx:9`](../web/src/app/science/page.tsx) | `…behind ScoutLens.` | `…behind Yumusarái Labs.` | **Conditional** — copy string |
| 10 | `science/page.tsx:28` | `ScoutLens asks one question…` | `Yumusarái Labs asks one question…` | **Conditional** — copy string |
| 11 | `science/page.tsx:50` | `ScoutLens is a static website.` | `Yumusarái Labs is a static website.` | **Conditional** — copy string |
| 12 | [`showcase-lab.ts:550`](../web/src/content/showcase-lab.ts) | `ScoutLens stopped before rendering any profile values.` | `Yumusarái Labs stopped before rendering any profile values.` | **Conditional** — `web/src/content/**`, reviewer `scoutlens-9a3` |

**Approval for the Conditional rows.** Rows 7–12 are approved by this contract's
author in the narrative/PM role, for a **name substitution only**. Nothing else
in those strings may move: not a number, not a caveat, not a boundary sentence,
not the conditions under which the integrity message is shown. Row 12 in
particular is the user-facing text of a fail-closed path — the words around the
name, the `canRetry` flag and every branch that selects it are Denied.

Two files follow the strings and are not themselves brand surfaces:

| Location | Change | Level |
|---|---|---|
| [`core-flow.spec.ts:22`](../web/e2e/core-flow.spec.ts) | the focus-order assertion names `ScoutLens home`; update the accessible name it looks for | Allowed (`web/e2e/**`). The assertion is **updated, never removed** — deleting it is Conditional and is not approved |
| `styles/shell.css` `.wordmark*` | spacing only, and only if the longer wordmark demands it | Allowed (frontend §4.1 row 4) |

`web/e2e/public-identity.spec.ts` and `web/tests/public-identity.test.tsx` are
new files under Allowed trees.

### 3.1 The surfaces the other beads change

The twelve strings above are `vif.4`'s. Two siblings touch brand strings
elsewhere, and their surfaces are enumerated here so the inventory is complete
across the epic rather than per bead.

**`scoutlens-vif.3` — one string, in a deploy gate.**
`.github/scripts/smoke-production.py:63` currently recognises the home page by
`EXPECTED_TEXT[""] == "ScoutLens"`. That sentinel is both brand-coupled and
weak: the same word appears in the header of every route, so it would pass on a
200 that served the wrong page. It is replaced by the home page's own h1 phrase,
`A player leaves a reproducible fingerprint` (`page.tsx:43`), which is
route-specific and survives the rename. The remaining `scoutlens` occurrences in
that file — the usage line, the bead id, the `scoutlens-smoke` user agent and
the doubled-prefix incident comments — are technical or historical and stay.
`.github/**` is Denied to frontend work, which is exactly why this is a separate
release-engineering bead and not part of `vif.4`.

**`scoutlens-vif.5` — README and case study, after the rename is deployed.**

| Location | Occurrence | Treatment |
|---|---|---|
| `README.md:1`, `:8`, `:21` | title and two editorial sentences | name-only replacement |
| `README.md:247` | the link `docs/00_ScoutLens_Project_Brief_v1.md` | **filename — do not rename.** Renaming the frozen brief breaks the link and rewrites a historical document's identity |
| `README.md:304` | `ScoutLens exposes StatsBomb only as aggregate replication evidence` | name-only. The licensing boundary around it is Denied |
| `README.md:307` | `**ScoutLens code:** [MIT](LICENSE)` | **do not rebrand.** The licence covers the code, and the code is still named `scoutlens` — `pyproject.toml:2`. It may be rephrased to *"This repository's code"*, approved by this contract's author; replacing it with the brand would misstate what MIT covers |
| `docs/case-study.md:1` | title | name-only replacement |
| `docs/case-study.md:36` | alt text quoting the Lab screenshot | changes **with the image**, not before it. `vif.5` re-captures from the new-identity deployment and rewrites the alt text to match what the new screenshot shows |

`LICENSE` is untouched: its copyright line names Bruno Guide, not a project.

### 3.2 Two things the longer wordmark will touch

**The breakpoint at risk is 769px, not 320px.** `shell.css:94` collapses
`.site-header__inner` to a single column at `max-width: 48rem`, so below 768px
the wordmark gets the full width and stacks above the nav. The tight case is
just *above* that — around 769px, where `Yumusarái Labs` (14 characters, five
more than `ScoutLens`) shares one row with three nav items whose labels are
already long. Keep 320px and 360px in the matrix; expect the failure at 769px.

**The accent is a font question.** Inter is pinned as two local `woff2` files
(`latin` and `latin-ext`). `á` (U+00E1) should fall in the `latin` subset, but a
missing glyph does not error — it silently falls back to Arial, and only a
rendered comparison shows it. `vif.4` verifies the accent by looking at the
wordmark, not by assuming the subset. Adding a font file is a non-goal.

---

## 4. Do-not-rename inventory

Every occurrence of `scoutlens` below stays. None of them is a leftover.

| Class | Examples | Why it stays |
|---|---|---|
| Repository and URLs | `github.com/grunobuide/scoutlens`, `grunobuide.github.io/scoutlens/`, the `/scoutlens` base path | Renaming breaks every published deep link, the release-asset URLs and the case study's own links |
| Python package and imports | `src/scoutlens/**`, `python -m scoutlens.showcase.export` | Printed as reproduction commands in the README and case study |
| Environment variables | `SCOUTLENS_MODEL_API_KEY`, `SCOUTLENS_BASE_PATH`, `SCOUTLENS_REQUIRE_SHOWCASE`, `SCOUTLENS_DRIFT` | Contract surface for anyone running the toolkit |
| Artifact contract strings | `scoutlens.showcase/2.0.0`, `scoutlens.showcase-payload-pack` | Validated fail-closed at the web boundary; a change is a schema change |
| Generated types | `ScoutLensShowcaseArtifacts100/200` in `web/src/contracts/generated/**` | Denied outright: generated, never hand-edited |
| Dataset and representation pins | `wyscout-2017-18-v2-332766e3a822`, `rep-f018e6041ccbad10` | Content-addressed; the site cannot drift from the numbers it renders |
| Beads ids | `scoutlens-vif.2`, and every id in every closure note | Identifiers, and they appear in code comments as provenance |
| Historical records | `decisions-log.md` D001–D057, closed beads, release audit, `artifacts/**` | Append-only. A past decision said `ScoutLens` because that was the name |
| Provenance strings in artifacts | `producer`, `config/experiment.json` description, evidence bundles | Recorded inputs to published digests |
| Licences | `DATA_LICENSES.md`, `LICENSE` | Legal text, not presentation |
| Already-published media | the five PNGs under `docs/media/` | Captured from the old-identity deployment; `vif.5` **re-captures** them from the new deployment rather than editing them |

---

## 5. The exception that cannot be fixed, and must therefore be explained

There is one occurrence of the old name that a reader sees **on every page of
the site** and that this rename must leave in place.

`web/src/components/data-provenance.tsx:64` renders
`manifest.source.redistribution_note`, whose value is:

> ScoutLens publishes attributed player-period aggregates only; raw provider
> rows remain excluded.

`ProviderBoundary` is imported by `/`, `/lab/` and `/science/` — all three
routes. The string is not in the website's source. It is baked into
`public/showcase/v2/manifest.json`, produced by
`src/scoutlens/showcase/export.py:193`, and pinned by
`config/showcase-payload-pack.json` as `manifest_sha256`
`ed01ff11b716d0cc1991251440e06c56e6c1b7ab3a79ecf3d07e47bd981f7c74`, inside an
archive whose own sha256 is part of a **release asset that is already
published** at an immutable URL.

Changing that one sentence would require regenerating the manifest, which
changes `manifest_sha256`, which invalidates the payload pack, which invalidates
the published archive, which changes the dataset identity the case study and the
release manifest both quote. A cosmetic edit would propagate into the
project's scientific identity. That trade is not available, and the frontend
contract already forbids it twice over: `public/showcase/**` and `config/**` are
Denied, and "the dataset version pin" is a named scientific invariant.

**So it stays, and the site explains it.** The requirement is not silence:

- `vif.4` must **not** touch it, and must not treat it as an oversight.
- `vif.5` writes the brand-versus-technical-name explanation that covers it,
  in README and case study.
- `vif.6` records it as an **accounted-for exception**, not an unexplained
  stale wordmark. Its AC1 is satisfied by this section plus `vif.5`'s
  explanation — not by the string being gone.

If a future regeneration of the v2 payload happens for a *scientific* reason,
the note may be reworded in that change. It is never a reason of its own.

---

## 6. Verification matrix

`vif.4` runs it; `vif.6` records it. Nothing here is new work for the frontend
contract — it is the existing gate set, pointed at the rename.

**Builds — both, in isolated output directories.** Root (`/`) and
`SCOUTLENS_BASE_PATH=/scoutlens`. On Windows prefix `MSYS_NO_PATHCONV=1`, or
Git Bash rewrites the base path into a filesystem path.

**Widths.** 320, 360, **769**, 1280. See §3.2 for why 769 is the one that bites.

**States.**

- Normal render on `/`, `/lab/`, `/science/`.
- Direct navigation to `/lab/?player=wy-8287-c-795` — the shareable deep link.
- **No-JS**: the wordmark, title and nav are server-rendered and must be
  correct with scripting off.
- **Fail-closed integrity error**: the string in row 12 renders with the new
  name, and the error boundary still refuses to show profile values.

**Accessibility.** Tab order unchanged: skip link → wordmark home link →
Overview → Fingerprint Lab → How it works. The home link's accessible name is
the new one. The `YL` mark stays `aria-hidden`; it is decoration, and a screen
reader must get the name once, not twice.

**Metadata.** Title default and template on all three routes, plus
`applicationName`.

---

## 7. Review and snapshots

Snapshots follow `docs/frontend-agent-contract.md` §5 unchanged. This contract
adds no exception and grants no relaxation. In particular:

- The wordmark change *is* the cause of the baseline diff, so updating those
  baselines is legitimate — but each update ships an **enumerated
  intended-difference list**, one line per changed region.
- **Both platforms move together.** `win32` and `linux` baselines are
  regenerated in the same change; the *Visual baseline pair guard* in
  `web-quality` fails a one-sided update, and the stale side stays green
  locally.
- Regions other than the header must be unchanged. If the landing hero moved,
  the diff is bigger than a rename and the bead stops.
- `maxDiffPixelRatio`, Lighthouse minimums and `quality-budgets.json` may not
  be raised to make a run green.

**Named reviewer.** The author of this contract, in the PM/narrative role, for
the Conditional rows in §3 and for `showcase-lab.ts:550`. `web/e2e/__screenshots__/**`
remains Conditional on the bead author under §5, with actual image review.

---

## 8. What this contract protects

**The release does not wait for the brand.** `scoutlens-jtt.7.4` tags and
publishes v1.0.0 under the identity that shipped, and nothing in `scoutlens-vif`
is a prerequisite of it. The dependency runs the other way: `vif.4` depends on
`jtt.7.4`, so the display rename lands *after* the tag, against a released and
verified baseline.

**Backlog health is scoped to the candidate.** An open identity bead is not an
unresolved blocker of the v1 release, and `jtt.7.4`'s criterion 6 classifies it
as out of release scope rather than demanding a globally empty backlog.

**`jtt.7.3` is closed and its output is read-only to `vif.4`.** README,
`docs/case-study.md` and `docs/media/**` converge later, in `vif.5`, and only
within that bead's enumerated paths — there is no blanket `docs/media/**`
permission.

**The inherited video gap stays a gap.** `jtt.7.3` did not deliver its 60–90
second captioned demo; it is filed as `scoutlens-jtt.20`. `vif.5` may not
present the stills as a video, and `vif.6` discloses the gap rather than
closing over it.

---

## 9. Stop conditions

Any of these stops the executing bead and returns to this contract:

1. A thirteenth reader-facing brand string, not in §3.
2. A required edit outside the named path for the bead in hand.
3. A rename that would touch a scientific value, claim, caveat, ordering,
   digest, dataset pin, schema string or threshold.
4. A snapshot that cannot be made green without relaxing a budget, masking a
   region, or updating one platform alone.
5. Content clipped or overflowing at any width in §6.
6. The accent failing to render, or the wordmark falling back to Arial.
7. Any request to buy a domain, register a handle, rename the repository,
   change the base path, or claim trademark availability.

---

## 10. What this contract does not authorize

No repository, package, import, environment-variable, Beads-prefix, URL, domain,
provider, dataset, schema or artifact rename. No visual redesign, palette, font,
icon system, navigation change or new dependency. No scientific copy, metric,
caveat or threshold change. No regeneration of a published payload for a
branding reason. No commit, push, merge, tag, deploy or external promotion
without current authority. `D056` (one evaluator, comprehension not claimed as
validated) and `D057` (the two named AI exceptions) are preserved exactly.
