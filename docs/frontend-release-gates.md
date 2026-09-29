# Frontend Release Gates

**Status:** current as of 2026-09-02, `main` at `29f184f`

**Tracking:** `scoutlens-uze.6.3`, closing `scoutlens-uze.6`.

This document answers one question: for every cell of the QA matrix in
[`frontend-qa-audit.md`](frontend-qa-audit.md) §2, **what would catch it now?**
Either an automated gate, or a named manual check, or it is listed in §3 as a
gap with a bead against it.

The audit measured 93 cells by hand on 2026-08-04. That was a snapshot. This is
the standing replacement.

---

## 1. Which gate owns each dimension

The audit's eight dimensions (§1), and what asserts them today. Everything
listed runs inside `pnpm release:check`; there is no separate command.

| # | Dimension | Owned by |
|---|---|---|
| D1 | Page scroll width | `expectNoPageOverflow` — used by `responsive-baseline`, `core-flow`, `404-page`, `lab-fixtures`, `lab-v2-diagonal`, `lab-mobile-hardening`, `lab-content-order`, `identity-challenge-responsive` |
| D2 | Essential element bounding boxes | `probeEdgeCrossings` in `responsive-baseline`; panel containment in `identity-challenge-responsive`; **dialog containment in `dialog-geometry`** |
| D3 | Text-on-text collision | `expectNoTextCollision` (`scoutlens-uze.6.1`), used by `text-collision`, `responsive-baseline` and `dialog-geometry`; plus `frozen-question` for F-1 at thirteen widths |
| D4 | Focus visibility and order | `probeFocusRings` in `responsive-baseline`; keyboard walk in `core-flow`; focus movement in `identity-challenge`; focus return in `dialog-geometry` |
| D5 | Touch-target size | `probeNavTargets` in `responsive-baseline`; the enumerating check in `lab-mobile-hardening`; CTA and row checks in `identity-challenge-responsive`; `probeProviderBoundaryTargets` (`responsive-baseline`) and the dedicated `lab-mobile-hardening` check (`scoutlens-uze.6.5`) for the three shared provider-boundary links |
| D6 | Internal scroll labelling | `lab-mobile-hardening` asserts the 32-value scroller keeps `role`, accessible name and `tabindex`, and that its row header stays readable while scrolled |
| D7 | 200% reflow | 640×512 in `responsive-baseline` (landing, science) and `lab-v2-diagonal` (Lab) |
| D8 | Automated accessibility | `expectNoSeriousOrCriticalViolations` — `quality-contract` (three routes + open dialog), and since `scoutlens-uze.6.2` also `responsive-baseline` at **every reflow width**, plus `lab-mobile-hardening`, `lab-v2-diagonal`, `404-page`, `identity-challenge-responsive` |

**The gap D8 used to have.** Until `scoutlens-uze.6.2`, axe ran only at the
project viewports — 1280 and 360. The narrow-width walk asserted geometry and no
accessibility at all. Reflow is where these defects appear, so that was the
wrong half to leave uncovered.

## 2. Matrix cell → gate

Each row is a state from §2 of the audit. "Widths" is what the gate actually
exercises, not what the audit swept.

| State | Gate | Widths | Dimensions |
|---|---|---|---|
| landing | `responsive-baseline`, `text-collision`, `quality-contract`, `visual-landing-science` | 320, 360, 640×512, 768, 1280 | D1–D5, D7, D8 |
| science | `responsive-baseline`, `text-collision`, `frozen-question`, `quality-contract`, `visual-landing-science` | 320–768 sweep, 640×512, 1280; F-1 at thirteen widths | D1–D5, D7, D8 |
| science, provenance collapsed | `text-collision` (the closed-`<details>` exclusion is asserted on the Lab equivalent) | 320, 1280 | D3 |
| lab default | `core-flow`, `lab-mobile-hardening`, `lab-content-order`, `text-collision`, `quality-contract` | 320, 360, 375, 768, 1280 | D1–D6, D8 |
| lab selected | same, with `?player=` | 320, 360, 1280 | D1–D6, D8 |
| lab filters empty | `core-flow` (search flow) | 360, 1280 | D1, D4 |
| lab filters active | `core-flow` | 360, 1280 | D1, D4 |
| lab unknown profile | `failure-states` | 320, 360, 1280 | D1, D2, D8 |
| lab missing artifact | `failure-states` | 320, 360, 1280 | D1, D2, D8 |
| lab incompatible artifact | `failure-states` | 320, 360, 1280 | D1, D2, D8 |
| lab neighbor drawer open | **`dialog-geometry`** (`scoutlens-uze.6.2`), `quality-contract`, `core-flow` | 320, 360, 768, 1280 | D1, D2, D3, D4, D8 |
| lab max content, stored | `lab-fixtures` | 320, 360, 768, 1280 | D1, D2 |
| lab max content, fixture `wy-900001-c-901` | `lab-fixtures`, `lab-v2-diagonal` | 320, 360, 768, 1280 | D1, D7, D8 |
| lab uncertainty available `wy-900002-c-902` | `lab-fixtures`, `lab-v2-diagonal` | 320, 360, 768, 1280 | D1, D8 |
| lab uncertainty insufficient `wy-900003-c-903` | `lab-fixtures`, `lab-v2-diagonal` | 320, 360, 768, 1280 | D1, D8 |
| unknown route | `404-page` | 320, 1280 | D1, D2, D8 |
| **identity challenge** (4 states, not in the audit — it did not exist) | `identity-challenge`, `identity-challenge-responsive` | 320, 360, 768, 1280 | D1, D2, D4, D5, D8 + baselines |

Beyond the matrix, two gates assert things the audit could not: `rendered-values`
checks what the page *claims* (`scoutlens-uze.13`), and
`check-visual-baseline-pairs` enforces that both platform baselines move together
(`scoutlens-uze.11`).

## 3. Gaps

### 3.1 Failure states at mobile widths — closed

`scoutlens-uze.6.4` closed this. `failure-states.spec.ts` now walks all four
fixtures — unknown profile, missing artifact, checksum mismatch, schema-invalid
— at 320 and 360 as well as 1280, asserting the recovery panel's copy, no page
overflow, panel containment, no serious or critical axe violation, and that the
selector is reachable and operable.

**Reachable, not above the fold.** Measured at 320, the selector sits at
1,693 px and the alert at 3,863 px on a 5,699 px page, because the challenge
panel and the page intro come first. Asserting either were on-screen at load
would assert a different design rather than guard a regression. Whether a
failure panel *should* sit that far down on a phone is a live question and
belongs with the mobile order in
[`lab-mobile-order.md`](lab-mobile-order.md), not in a gate.

### 3.2 `ProviderBoundary` links now hold their 44×44 target

Recorded in `scoutlens-uze.5.1` and closed by `scoutlens-uze.6.5`: "Canonical
source", "CC BY 4.0 licence" and "See the replication and its limitations"
measured 17–20 px tall. They are styled by `research-story.css` and the
component renders on `/`, `/science/` and `/lab/`, so a Lab-scoped bead could
not own the fix.

The rule lives in the same mobile-only breakpoint as `.site-nav a`
(`scoutlens-uze.4`): `display: inline-flex`, `align-items: center`,
`min-height: 2.75rem`, with `padding-inline`/negative `margin-inline` holding
the visual position. Desktop (1280) is unchanged — 17–20 px there still passes
WCAG 2.5.8 via the inline-text exception; this closes the touch-target gap,
not a conformance failure. Asserted by `responsive-baseline` at 320 for `/`
and `/science/`, and by `lab-mobile-hardening` at 320/360 for `/lab/` — the
same test that excludes this component from its own Lab-owned sweep now
points at where it is actually held.

### 3.3 Four `report_url` anchors — fixed, and the waiver is gone

Found by `scoutlens-9a3.7`'s link audit on its first run: all four `report_url`
values carrying a `#fragment` pointed at headings that did not exist, so the
"Read method" link landed at the top of the right document instead of the cited
section. The four without a fragment were always correct, so these were never
rotted links — every anchor in the file was aspirational.

**Closed 2026-09-18** by `scoutlens-jtt.17` (source) and `scoutlens-uze.16`
(web). `KNOWN_DEAD_ANCHORS` and its companion staleness test are deleted;
"every method link points at a document that exists" now runs unwaived.

**What the waiver cost, recorded because the shape recurs.** `report_url` is
published content, and `builder.py` derives `dataset_version` from a content
digest over every artifact, so correcting four strings repinned the whole
bundle — measured at 1,262 of 1,262 files changed, none byte-identical. That
required a new immutable release asset, which is outward-facing and outside a
modeling agent's authority, so §4.4 of the modeling contract had it stop after
building the pack and hand off. The waiver existed to keep the gate honest
across that gap rather than to hide it.

The companion test is what made the waiver safe to hold: it failed the moment
the repin landed, naming the entries that no longer needed excusing. A waiver
without one is indistinguishable from a permanent blind spot.

### 3.4 Forbidden-copy and currentness assertions

`scoutlens-9a3.7` AC5, in `scripts/check-static-output.mjs` — beside the
recommendation-wording check that was already there, not in a second mechanism
under `e2e/`. Three additions, over all three public routes:

| Check | What it holds |
|---|---|
| `forbiddenClaims` | assertive phrasings of what the project may never claim — "proves playing style", "should sign", "predicts transfer success" |
| `forbiddenCurrentness` | wording that would tell a reader the data is live — "real-time", "current season", "updated daily" |
| `currentnessDisclaimers` | the positive half: every route must carry "not current scouting information" |

**The trap this had to avoid.** The site states each forbidden claim *verbatim*
in order to disclaim it — `ClaimsMatrix` renders "Statistical similarity proves
playing style." under "Where the evidence stops". A substring ban on the
assertive phrasing fires on the disclaimer that exists to prevent it. So each
route is scanned with the published claim boundaries removed first, and that
exception list is read from the shipped artifact's `unsupported_claims` rather
than hardcoded — reword a boundary and the exception follows it in the same
build, instead of leaving a stale waiver behind.

Matching is on a trailing word boundary. The first run failed `/science/` on
"live data" inside "no live **data**base" — the site correctly saying it has no
live database. A ban whose cheapest fix is deleting the reassurance is worse
than no ban.

Tamper-rehearsed four ways: injected claim copy, injected currentness wording,
a removed disclaimer, and — for the exception mechanism itself — dropping one
entry from `unsupported_claims`, which correctly turns the still-rendered
sentence into a violation.

### 3.5 RSC prefetch 404s on a Windows build — accepted, upstream

`scoutlens-uze.17`. Serving a locally built export on Windows produces two
console 404s on every page load:

```
GET /lab/__next.lab.__PAGE__.txt?_rsc=…      404
GET /science/__next.science.__PAGE__.txt?_rsc=…  404
```

**The cause is a path bug in the exporter, not in this project.** The client
router requests the flat, dot-separated segment name. The exporter builds that
name by replacing path separators with dots, but on Windows `path.relative()`
returns backslashes and only forward slashes are replaced — so the leftover
backslashes are read as directory separators and the file lands at
`out/lab/__next.lab/__PAGE__.txt`. Measured on a Windows build: three such
directories exist (`lab`, `science` and `_not-found`), and none of the flat
files the client asks for does.

Upstream: [vercel/next.js#85374](https://github.com/vercel/next.js/issues/85374),
with [#92339](https://github.com/vercel/next.js/issues/92339) closed as its
duplicate. [PR #99058](https://github.com/vercel/next.js/pull/99058) normalises
the separators; at Next 16.2.12 it is **still open against `canary`**, so there
is no fixed version to pin to.

**Production is not affected, and that is verified rather than assumed.** CI
builds on Linux, where the separator is already a forward slash. Driven with a
browser against the deployed site: `/`, `/lab/` and `/science/` each load with
**zero console errors**, and `/lab/__next.lab.__PAGE__.txt` and
`/science/__next.science.__PAGE__.txt` both return 200. Navigation was never
broken in either case — Next falls back to a full navigation when a prefetch
payload is missing.

**What guards it.** `check-static-output.mjs` now walks the export for
`__next.*` *directories*, and its response is deliberately asymmetric:

- on Linux and macOS it **fails the build**, because a nested segment directory
  there is a real regression and would reach production;
- on Windows it **warns**, naming the upstream issue, because failing would make
  `pnpm build` red for every Windows contributor over a defect that cannot reach
  production and that this project cannot fix.

The warning is the point. A developer who opens devtools on a local build finds
the explanation instead of hunting a phantom — which is how this was filed in
the first place, during the `scoutlens-jtt.7.1` audit.

Revisit when PR #99058 lands in a release: pin that version and make the
Windows branch fail too.

## 4. Baselines and their review protocol

### 4.1 The set

| Baseline | What it holds |
|---|---|
| `landing-hero`, `landing-claims` | landing above the fold and the claims matrix |
| `science-stage-01`, `science-experiments` | How-it-works orientation and result |
| `retrieval-neighbors`, `neighbor-cards` | Lab retrieval and neighbour surfaces |
| `challenge-reveal-{320,360,768,1280}` | the challenge's richest state at four widths |

Each exists for `desktop-win32`, `desktop-linux`, and where the project applies
`mobile-360-*`. The fingerprint plot has no baseline of its own: it is asserted
by geometry — 32 rows, lane separation, no overflow — which is more precise than
a reference image and does not churn when a percentile moves.

### 4.2 The protocol

1. **A baseline is updated only when the bead's own diff caused it.** Never
   because a snapshot is red.
2. **Read the image before accepting it.** §5.9 of the frontend agent contract.
   This is not ceremony: three defects this session were found that way and by
   nothing else — an interval rendered as `1–43.524999999999998`
   (`scoutlens-9a3.6.4`), baselines still asserting v1 cosine content
   (`scoutlens-uze.12`), and overlapping A/B marks (`scoutlens-9a3.10`).
3. **Enumerate the intended differences**, one line per changed region, naming
   what changed and why. Four worked examples: `uze.12`, `uze.5.1`, `uze.5.2`,
   `9a3.10`.
4. **Both platforms move together.** `check:baseline-pairs` fails a pull request
   that updates one and not the other.
5. **A passing baseline is not a current one.** `--update-snapshots` rewrites
   only what *fails*, so a stale baseline inside tolerance is never refreshed by
   the routine command, and CI writes an actual only on failure. To refresh one,
   delete both platforms' copies together — that keeps the pair guard satisfied
   and forces a render. This is how `uze.12` and `9a3.10` were done.
   `--update-snapshots=all` rewrites regardless, which is the blunt instrument
   for the same problem; prefer the delete, because `=all` also rewrites files
   whose pixels are identical and hides which ones actually moved.
6. **Copy `web/test-results` before doing anything else after a failure.**
   Playwright wipes `outputDir` at the start of every run, so the trace,
   the `-actual.png` and the diff image are gone the moment you re-run —
   including when you re-run *to see whether it reproduces*. `scoutlens-uze.21`
   is the bead where that happened: a keyboard test failed once under
   full-suite parallelism, and re-running to check destroyed the only evidence
   of why.
7. **Retries are 1 in CI and 0 locally, and that is the wrong way round for
   diagnosis.** `playwright.config.ts` sets `retries: process.env.CI ? 1 : 0`.
   A non-deterministic failure therefore fails the whole gate on a
   contributor's machine and is silently absorbed in CI, so the environment
   with the better diagnostics reports it least. The asymmetry is deliberate —
   CI retries to absorb infrastructure noise, and a local run should not hide
   flakiness behind a second attempt — but it means **a green CI run is not
   evidence that a test is stable.** Read the run summary for a retried job
   before treating it as clean.

### 4.3 What images are for

`D054`: images assert **layout**; rendered-text assertions assert **claims**. At
`maxDiffPixelRatio: 0.03` the visual gate failed to notice a metric rename, a
method rename, unrounded rank bounds, a complete change of published rank
values, and the correction of the first of those. Three separate beads confirmed
it independently. Do not reach for a screenshot to hold a sentence.

That stays true at any tolerance — §4.4 replaced the ratio with an absolute
budget, which narrows the blind spot without closing it. A sentence still
belongs in a text assertion.

### 4.4 The tolerance is an absolute pixel budget, not a ratio

`scoutlens-uze.19`. It was `maxDiffPixelRatio: 0.03`. It is now
**`maxDiffPixels: 2000`**. The change of *instrument* matters more than the
change of number, and it was learned the hard way — the first attempt lowered
the ratio to `0.002` and CI went red.

**Why a ratio cannot work here.** The only difference this gate has to tolerate
is CI rendering one monospace element with a different font stack from the
`v1.62.0-noble` container §5.7 pins for regenerating baselines. That artefact is
roughly **constant in pixels** — about 1,052 — because it is one piece of text.
A ratio divides by image area, so the same artefact reads as 0.0009 on a
1280×900 desktop shot and 0.0037 on a 360×800 mobile one. There is no single
ratio above the second and below a real change.

Everything below is Playwright's own arithmetic, taken at a zero budget:

| measured | pixels |
|---|---|
| two renders, same machine | **0** |
| CI vs container, desktop, content unchanged | 497 |
| CI vs container, mobile-360, content unchanged | **1,052** ← the floor |
| `science-stage-01`, mobile-360 (wordmark + space fix) | 3,605 |
| `landing-claims`, desktop (wordmark) | 6,474 |
| `landing-hero`, mobile-360 (wordmark) | 6,825 |
| `landing-hero`, desktop (wordmark) | 6,944 |
| `science-stage-01`, desktop (wordmark + space fix) | 11,099 |

`2000` is ~1.9× the floor, ~1.8× below the smallest real change, and means the
same thing on every image in the suite. For comparison, `0.03` on the mobile
shots was a budget of **8,640 pixels** — larger than any content change in that
table, which is why the site wordmark could change on every page unnoticed.

**Two problems that fixed, not one.** Nothing in the table was caught. And
`landing-hero` at mobile-360 had reached 83% of the old ratio budget, so the
gate was also heading for a red nobody would have connected to a rename three
beads earlier.

**Set only one of the two.** Playwright treats `maxDiffPixels` and
`maxDiffPixelRatio` as independent limits, so setting both would reintroduce the
area-scaled one as a hidden second gate.

**The floor is removable.** CI installs a browser onto `ubuntu-latest`; the
container ships its own fonts. Running `web-quality` inside the pinned image
makes them the same renderer and takes the floor to zero, after which this can
go far lower. That is `scoutlens-uze.23`, and until it lands the mobile shots
are the binding constraint.

May only move down (§5.5). If it ever has to move up, that is a finding about
the two environments, not a budget decision.

## 5. Budgets

Unchanged by `scoutlens-uze.6`. First measured on `main` at `29f184f` and
re-measured at closure on `bc51cec`, after `uze.6.4`, `uze.6.5` and the two
prose-typography merges landed — the JavaScript total is byte-identical:

| Budget | Measured | Cap | Headroom |
|---|---|---|---|
| Initial `/lab` JavaScript (gzip) | 161,454 | 204,800 | **43,346** |
| Initial `/lab` transfer, excl. fonts | ~285,830 | 768,000 | ~482,170 |

The transfer figure moves by a byte or two between builds, as a content hash
lands differently; it is written approximately for that reason. The
JavaScript total is stable, and it is the one the cap is written against.

`scoutlens-uze.6` AC6 requires at least **20 KiB** (20,480 bytes) of initial-JS
headroom before closure. The measured 43,346 is **2.1×** that. Lighthouse
assertions match the versioned budgets; no threshold moved in any direction.

`D052` binds any future challenge client code to measure this before and after.

## 6. Handoff drill

`scoutlens-9a3.6.2` — the challenge's server-rendered states — walked as the
test of whether the contract's handoff is sufficient in practice.

| Question | Answer |
|---|---|
| Were the allowed files knowable before starting? | **No.** The bead listed a glob, and §1 of the frontend agent contract names four component files with no wildcard, so a *new* component was Denied by default. Three surfaces needed approval that the bead had not identified. |
| Was the stop condition reachable? | Yes — "stop if orientation cannot render without a client component" was checkable and did not trigger. |
| Did it produce the evidence a reviewer needs? | Yes: byte counts before and after, tamper rehearsal, and the built export inspected. |
| What failed? | The bead's ownership boundary was written by the executor and under-specified. Code was written before the contract was re-read. |

**The fix that came out of it**, applied from `scoutlens-9a3.6.3` onward: name
the exact files in the bead *before* the first edit, and treat anything not in
§1's table as Denied until named. Two later beads (`uze.5.2`, `9a3.10`) recorded
their surfaces before editing and needed no approval round-trip.

A second lesson, from `scoutlens-uze.6.1`: survey for the **mechanism** a bead
proposes, not only the outcome it names. That slice built a line-box helper
before discovering `frozen-question.spec.ts` already measured the same thing.
`uze.6.2` applied the correction and shipped two files instead of a rebuilt
matrix.
