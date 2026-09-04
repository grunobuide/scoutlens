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

### 4.3 What images are for

`D054`: images assert **layout**; rendered-text assertions assert **claims**. At
`maxDiffPixelRatio: 0.03` the visual gate failed to notice a metric rename, a
method rename, unrounded rank bounds, a complete change of published rank
values, and the correction of the first of those. Three separate beads confirmed
it independently. Do not reach for a screenshot to hold a sentence.

## 5. Budgets

Unchanged by `scoutlens-uze.6`. Measured on `main` at `29f184f`:

| Budget | Measured | Cap | Headroom |
|---|---|---|---|
| Initial `/lab` JavaScript (gzip) | 161,454 | 204,800 | **43,346** |
| Initial `/lab` transfer, excl. fonts | ~285,810 | 768,000 | ~482,190 |

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
