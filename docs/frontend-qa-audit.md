# Frontend responsive and accessibility QA audit

Dated evidence report for `scoutlens-uze.1`. This document records what was
measured; it is **not** the source of truth for the work that follows. Every
actionable defect below is owned by a Beads issue, and those issues — not this
file — carry the acceptance criteria.

- **Audit date:** 2026-08-04
- **Commit under test:** `b28b921` (`codex/deterministic-match-bootstrap`), working tree clean except `.beads/*.jsonl`
- **Build:** `cd web && pnpm build` (Next.js 16.2.12 static export, `web/out`)
- **Server:** `node scripts/serve-static.mjs --port 4173` — the same production fixture used by `pnpm release:check`
- **Browser:** Chromium 151.0.7922.34 via `@playwright/test` 1.62.0
- **Environment deviation:** Node **v24.18.0**; `web/package.json` pins `24.14.x`. pnpm 11.9.0 matched. The build printed `Unsupported engine` and otherwise succeeded. All findings below are geometry and DOM facts that do not depend on the Node patch level, but a re-run on the pinned Node is the correct confirmation step.
- **Harness and raw evidence:** `web/test-results/frontend-qa-audit/` (gitignored): `audit.mjs`, `probe.mjs`, `probe2.mjs`, `probe3.mjs`, `probe4.mjs`, `analyze.mjs`, `findings*.json`, `probe*.json`, `screenshots/`.

> These artifacts are **disposable by design** — `playwright test` clears
> `web/test-results/`, so treat them as regenerable rather than durable. Every
> number in this report is restated inline with a self-contained reproduction
> command, so no finding depends on the files surviving. To regenerate the full
> set:
>
> ```bash
> cd web && pnpm build
> node scripts/serve-static.mjs --port 4173 &
> node test-results/frontend-qa-audit/audit.mjs
> node test-results/frontend-qa-audit/probe.mjs
> node test-results/frontend-qa-audit/probe2.mjs
> node test-results/frontend-qa-audit/probe3.mjs
> node test-results/frontend-qa-audit/analyze.mjs
> ```

## 1. What was measured, and separately

Acceptance criterion 4 of `scoutlens-uze.1` requires these dimensions to be
evaluated independently. They are, and each has its own verdict per cell:

| # | Dimension | How it was measured |
|---|---|---|
| D1 | Page scroll width | `documentElement.scrollWidth`/`body.scrollWidth` vs `documentElement.clientWidth` |
| D2 | Essential element bounding boxes | `getBoundingClientRect()` on 20 named landmarks per route; flagged when `right > clientWidth + 1` or `left < -1` |
| D3 | Text-on-text collision | `Range.getClientRects()` **line boxes** (not element boxes) for every element owning a direct text node; pairwise intersection ≥ 20 px² between non-nested elements |
| D4 | Focus visibility and order | 45 sequential `Tab` presses; per stop record `outline-width`/`outline-style`/`box-shadow`, horizontal containment, and top-coordinate inversions |
| D5 | Touch-target size | Every `a/button/input/select/summary/[tabindex]/[role=button]`; flagged below 44×44 CSS px, then re-judged against the WCAG 2.5.8 24×24 rule and its spacing exception |
| D6 | Internal scroll labelling | Elements with `overflow-x: auto\|scroll` and `scrollWidth > clientWidth`; checked for `role`, accessible name and `tabindex >= 0` |
| D7 | 200% reflow | Dedicated 640×512 viewport (= 1280×1024 at 200% zoom). The 320 px column is the 400%-zoom equivalent of 1280 px |
| D8 | Automated accessibility | axe-core 4.12.1, default ruleset, no exclusions; `serious` and `critical` only |

Passing one dimension never marked another as passing.

## 2. Frozen matrix

**Viewports (CSS px).** 320 (also = 1280 @ 400% zoom), 360 (release baseline
mobile), 375, 768 (last width of the `48rem` block), 1024 (last width of the
`64rem` block), 1280 (release baseline desktop), 1440, and `zoom200` = 640×512.

**States.** 16, covering both public routes plus every currently reachable Lab
state. `C` = full 8-viewport sweep, `E` = 320/360/768/1280/zoom200.

**93 cells** were executed. Legend: `PASS` = all eight dimensions clean;
`D3` etc. = that dimension failed; `BLOCKED` = fixture cannot represent the state.

| State | Route / query | Sweep | 320 | 360 | 375 | 768 | 1024 | 1280 | 1440 | zoom200 |
|---|---|---|---|---|---|---|---|---|---|---|
| landing | `/` | C | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| science | `/science/` | C | **D3** | **D3** | **D3** | **D3** | PASS | PASS | PASS | **D3** |
| science, provenance collapsed | `/science/` + click `summary` | E | PASS | PASS | – | PASS | – | PASS | – | PASS |
| lab default | `/lab/` | C | **D5** | **D5** | **D5** | **D5** | PASS | PASS | PASS | PASS |
| lab selected | `/lab/?player=wy-3359-c-795` | C | **D5** | **D5** | **D5** | **D5** | PASS | PASS | PASS | PASS |
| lab filters empty | `/lab/` + query `qqqqqzzzz` | E | PASS | PASS | – | PASS | – | PASS | – | PASS |
| lab filters active | `/lab/` + query `Deportivo` | E | PASS | PASS | – | PASS | – | PASS | – | PASS |
| lab unknown profile | `/lab/?player=unknown-profile` | E | PASS | PASS | – | PASS | – | PASS | – | PASS |
| lab missing artifact | profile route → 404 | E | PASS | PASS | – | PASS | – | PASS | – | PASS |
| lab incompatible artifact | profile route → `{}` (checksum mismatch) | E | PASS | PASS | – | PASS | – | PASS | – | PASS |
| lab neighbor drawer open | rank-1 `Open evidence comparison` | C | **D5** | **D5** | PASS | PASS | PASS | PASS | PASS | PASS |
| lab max content, stored | `/lab/?player=wy-25999-c-412` | E | **D5** | **D5** | – | **D5** | – | PASS | – | PASS |
| lab max content, synthetic | long Unicode identity via HTTP fixture | E | **D5** | **D5** | – | **D5** | – | PASS | – | PASS |
| lab uncertainty available | synthetic `status: available` | E | **D5** | **D5** | – | **D5** | – | PASS | – | PASS |
| lab uncertainty insufficient | synthetic `status: insufficient` | E | **D5** | **D5** | – | **D5** | – | PASS | – | PASS |
| unknown route | `/this-route-does-not-exist/` | 320/360/1280 | **D2/D4** | **D2/D4** | – | **D2/D4** | – | – | – | – |

Notes on cells that are not a plain pass:

- `science` **D3** is defect **F-1** (marker/heading collision). It fails at
  every width ≤ 768 px, including `zoom200` (640 px). The 1024/1280/1440
  columns pass. `science, provenance collapsed` passes D3 because it was
  measured after scrolling to the page bottom, where the marker is not in play;
  the same D3 failure is present on that route.
- `lab …` **D5** is defect **F-4** (17 px-tall navigation targets in the shared
  header) plus the in-sentence evidence links. D5 is only assessed on touch
  viewports, hence blank at 1024/1280/1440/zoom200. It is present on every
  route, and is listed on the Lab rows only where the sweep covered a touch
  width.
- `unknown route` **D2/D4** is defect **F-2**: the served body has no
  landmarks and zero focusable elements.
- The `/lab` 32-feature table (**F-3**) is a D6 *pass* — it is correctly
  labelled and keyboard-reachable at every width — and a separate usability
  defect. It is deliberately not folded into the D6 verdict.

### Blocked cells

| Cell | Why | Owner |
|---|---|---|
| Lab selector list under maximum identity content | `players.index.json` is consumed by a server component and baked into the static export. HTTP-boundary interception cannot change the rendered result list, only the lazily fetched profile. Stretching it would require editing a production artifact. | `scoutlens-uze.7` (new) |
| Uncertainty `available` / `insufficient`, as published data | All 1,257 stored profiles carry `uncertainty_status: "pending"`. Both other states were audited through an HTTP fixture with a recomputed manifest checksum, which is a valid substitute for layout evidence but is not published data. | `scoutlens-uze.7` (new), depends on `scoutlens-jtt.5.3` |
| Open neighbor / open challenge states beyond the comparison drawer | Not implemented on this commit. | `scoutlens-9a3.6` |

No cell was left blank and no cell was closed on a subjective judgement.

## 3. Defects

| Severity | Problem | Where | Impact | Bead |
|---|---|---|---|---|
| High | `01 · question` marker text overflows its grid track and collides with the section heading | `web/src/app/globals.css:1006` (`.frozen-question`), `:2510` (`48rem` block); markup `web/src/app/science/page.tsx:27` | The first thing a reader meets on `/science` is two strings printed on top of each other at every mobile width | `scoutlens-uze.4` (refined) |
| Medium | Unknown routes serve a bare `text/plain` body instead of the built `404.html` | `web/scripts/serve-static.mjs:75` | A mistyped or stale URL produces an unstyled dead end with no navigation, and the built 404 page is never exercised by any gate | `scoutlens-uze.8` (new) |
| Medium | 32-feature value table scrolls horizontally at every viewport with a non-sticky row header | `web/src/app/globals.css` (`.fingerprint-table-scroll`, `.fingerprint-value-table`); markup `web/src/components/lab-explorer.tsx:838` | Scrolling right to reach z-scores or uncertainty hides the feature name, so cells cannot be attributed to a row | `scoutlens-uze.5` (refined) |
| Medium | Primary navigation targets are 17 px tall | `web/src/app/globals.css` (`.site-nav`); markup `web/src/components/site-header.tsx:20` | Every route change on touch requires hitting a 17 px strip | `scoutlens-uze.4` (refined) |
| Low | Retrieval rank figure does not use tabular numerals | `web/src/app/globals.css:1897` (`.retrieval-outcome__rank`) | The three retrieval cards' headline numbers shift horizontally between profiles, unlike every other numeric surface | `scoutlens-uze.9` (new) |
| Low | No `color-scheme` declaration | `web/src/app/globals.css:400` (`:root`) | In a dark OS the page keeps its light palette, but UA-rendered scrollbars and the form-control fallback are left to the browser | `scoutlens-uze.9` (new) |

### F-1 · `/science` marker collides with the frozen-question heading — High

**Reproduce**

```bash
cd web && pnpm build && node scripts/serve-static.mjs --port 4173
```

Open `http://127.0.0.1:4173/science/` at 360×800 and run in the console:

```js
const ink = (el) => { const r = document.createRange(); r.selectNodeContents(el); return [...r.getClientRects()]; };
const m = ink(document.querySelector('.frozen-question > .research-step__marker'));
const h = ink(document.querySelector('#frozen-question-heading'));
({ markerInkRight: Math.max(...m.map(r => r.right)), headingInkLeft: Math.min(...h.map(r => r.left)) })
```

**Expected** `headingInkLeft >= markerInkRight`.
**Observed** `markerInkRight = 96.2`, `headingInkLeft = 91` → the marker's second
line box (`question`) intersects the heading's line boxes by **5.2 × 14.8 px**
and again by **5.2 × 5.3 px**.

**Mechanism.** `.frozen-question` is `grid-template-columns: 5rem minmax(0, 1fr)`,
narrowed to `2.5rem minmax(0, 1fr)` with a `1rem` gap inside
`@media (max-width: 48rem)`. The marker string `01 · question` has an intrinsic
single-line width of **91 px**; the word `question` alone measures **61.2 px**
against a **40 px** track. It wraps to two lines and the second line overshoots
the track by **21.2 px**, which is more than the 16 px gap.

**Failing widths.** Measured at 320, 340, 360, 375, 400, 420, 480, 560, 640,
700, 766, 767 and **768** — clearance is a constant **−5.2 px**. Clears at
**769 px** and above (+50.8 px), exactly where the `48rem` block stops applying.
The `zoom200` cell (640 px) fails, so the defect is also a 200%-zoom failure at
1280×1024.

**Why the existing acceptance wording is not sufficient.** `scoutlens-uze.4`
currently proposes asserting that the marker and heading *bounding boxes* do not
intersect at 320/360 px. Both assertions would pass today while the defect is on
screen: the marker's grid item is `align-items: stretch`-ed to the full row
height and clipped to the 40 px track, so its `getBoundingClientRect()` is
`35..75` and never intersects the heading box at `91..`. Only the rendered text
line boxes collide. The refined bead therefore requires a `Range.getClientRects()`
assertion across 320–768 px.

**Evidence.** `screenshots/probe-frozen-question-{320,360,768,769,1280}.png`,
`probe2.json#markerInk`, `probe3.json#markerBoundary`.

**Not reproduced as described.** The seed text in `scoutlens-uze.1` and
`scoutlens-uze.4` describes an *element* overlap. The element boxes do not
overlap at any width; the *text* does. The defect is real; the locator in the
seed description is wrong and has been corrected in `scoutlens-uze.4`.

### F-2 · Unknown routes bypass the built 404 page — Medium

**Reproduce**

```bash
curl -i http://127.0.0.1:4173/definitely-missing/
```

**Expected** the built `web/out/404.html` — which exists, returns 200 when
requested directly, renders the site header/footer and an `h1` of `404`.
**Observed** `HTTP/1.1 404`, `Content-Type: text/plain; charset=utf-8`, body
`Not found`. The rendered document contains zero `.site-header`, zero
`.site-footer` and **0 focusable elements** (D2 and D4 both fail).

`scripts/serve-static.mjs:75` returns the plain string for any unresolved
pathname instead of falling back to `out/404.html` with a 404 status. Because
this fixture is what `pnpm release:check` serves to Playwright and Lighthouse,
the built 404 page has never been exercised by a gate, and the fixture does not
match how a static host would behave.

**Evidence.** `probe.json#notFound`, `probe.json#notFoundAsset`,
`screenshots/probe-404-served-360.png`, `screenshots/probe-404-asset-360.png`.

### F-3 · 32-feature table loses row identity while scrolling — Medium

**Reproduce** — `/lab/` at 320×800, console:

```js
const s = document.querySelector('.fingerprint-table-scroll');
const th = document.querySelector(".fingerprint-value-table tbody th[scope='row']");
({ ratio: s.scrollWidth / s.clientWidth, hidden: s.scrollWidth - s.clientWidth, rowHeader: getComputedStyle(th).position })
```

**Observed** the table carries a fixed `min-width: 1472px`:

| Viewport | 320 | 360 | 375 | 768 | 1024 | 1280 | 1440 |
|---|---|---|---|---|---|---|---|
| Scroll ratio | 5.75× | 4.97× | 4.73× | 2.16× | 1.62× | 1.40× | 1.40× |

At 320 px, **1,216 px of 1,472 px** are off-screen. The `th[scope="row"]`
carrying the feature name is 272 px wide and `position: static`, so scrolling to
the `A global z` / `Uncertainty` columns removes the only row identifier. The
table never fits, even at 1440 px.

**Compliance vs usability, kept separate.** D6 **passes**: the container is
`role="region"`, `aria-label="Scrollable 32-feature value table"`, `tabIndex=0`,
so it is announced and keyboard-scrollable, and WCAG 1.4.10 exempts data tables
from the no-horizontal-scroll requirement. This is filed as a usability defect,
not a conformance failure.

**Evidence.** `probe3.json#tableScroll`, `screenshots/probe-table-320.png`.

### F-4 · Primary navigation targets are 17 px tall — Medium

**Reproduce** — any route at 360×800, console:

```js
[...document.querySelectorAll('.site-nav a')].map(a => { const b = a.getBoundingClientRect(); return [a.textContent, Math.round(b.width), Math.round(b.height)]; })
```

**Observed** `Overview` 66×17, `Fingerprint Lab` 105×17, `Science` 55×17. The
`.wordmark` is 123×34. The header wraps to two rows at every width ≤ 768 px
(`.site-header__inner` height 110 px vs 80 px at 1280 px), with a 28 px vertical
gap and 12–23 px horizontal gaps.

**Conformance verdict, computed rather than assumed.** WCAG 2.5.8 (AA) requires
24×24 unless the spacing exception applies. Minimum centre-to-centre distance
between any two header targets at 360 px is **60.5 px**, so no pair of 24 px
circles intersects → **2.5.8 AA passes**. WCAG 2.5.5 (AAA, 44×44) fails, and a
17 px strip is a poor touch target regardless of conformance. Severity is set on
ergonomics, not on a conformance failure.

The in-sentence links (`.evidence-links a` at 77×19, `.provenance-drawer__content
a`, `.source-grid a`) meet the WCAG 2.5.8 *inline* exception and are **not**
defects; they are listed in the raw findings for completeness only.

**Evidence.** `probe2.json#header`, `probe3.json#navSpacing`,
`screenshots/probe-header-360.png`.

### F-5 · Retrieval rank figure lacks tabular numerals — Low

`.lab-fingerprint-row__values span` and `.fingerprint-value-table td` compute
`font-variant-numeric: tabular-nums`. `.retrieval-outcome__rank` — the largest
number on the Lab page — computes `normal`, so `Rank 1` and `Rank 118` sit at
different optical positions across the three retrieval cards.
**Evidence.** `findings.json#numericSamples`.

### F-6 · No `color-scheme` declaration — Low

`:root` does not set `color-scheme`, no `meta[name=color-scheme]` is emitted,
and `globals.css` contains no `prefers-color-scheme` block. Rendering with
`colorScheme: dark` produces a byte-identical light palette — body background
`rgb(245, 242, 233)`, search input and selects unchanged — so **nothing breaks**;
the site is deliberately light-only. The residue is that UA surfaces (scrollbars,
form-control fallbacks, `::-webkit-*` chrome) are left undeclared.
**Evidence.** `probe.json#scheme_light`, `probe.json#scheme_dark`.

## 4. Verified passes

Recorded so future work does not re-audit them, and so a regression here is
visible as a change from a stated baseline.

- **D1 — page overflow: 0 failures in 93/93 cells.** No route, state or viewport
  produced `documentElement.scrollWidth > clientWidth` or
  `body.scrollWidth > clientWidth`, including 320 px, `zoom200`, both maximum
  content fixtures and all four failure states.
- **D2 — viewport containment: 0 elements** crossed the viewport edge outside a
  declared horizontal scroller, in any cell except the served 404 body.
- **D4 — focus indicator: 100% of tab stops** across all cells had a computed
  `outline-width > 0` with `outline-style != none`, or a non-`none` `box-shadow`.
  Zero stops were horizontally clipped. Tab-stop counts are stable across every
  viewport for a given state (landing 38, science 44, lab 38, drawer 45,
  unknown-profile 29, missing/incompatible artifact 30).
- **D4 — modal behaviour.** Opening the comparison drawer with `Enter` places
  focus on **`Close comparison`**; `Escape` closes it and returns focus to the
  invoking **`Open evidence comparison`** button. This matches steps 5–6 of the
  manual record in `flagship-quality-gates.md`.
- **D6 — internal scroll labelling.** Both horizontal scrollers
  (`.fingerprint-table-scroll`, `.neighbor-drawer__table-scroll`) expose
  `role="region"`, an accessible name and `tabindex="0"` at every viewport.
- **D7 — 200% reflow.** The dedicated 640×512 pass is clean on every state
  except F-1. The 320 px column doubles as the 400%-zoom check of a 1280 px
  window and is likewise clean except F-1.
- **D8 — axe.** **0 serious and 0 critical violations** across 55 audited cells:
  landing, `/science`, `/lab` default and selected at all eight viewports, plus
  the open drawer, empty filters, unknown profile and the synthetic
  maximum-content profile. This covers colour contrast, which is why no separate
  contrast defect is filed.
- **Modal geometry.** The drawer never exceeds the viewport at any of the eight
  viewports (full-bleed ≤ 768 px, 832 px wide above), and never introduces its
  own horizontal or vertical overflow.
- **Reduced motion.** The stylesheet declares exactly one animation
  (`lab-skeleton-pulse`) and **zero CSS transitions** site-wide. Under
  `prefers-reduced-motion: reduce`, `scroll-behavior` switches `smooth → auto`
  and the skeleton animation is disabled. Computed animation/transition count on
  `/`, `/science` and `/lab` is 0 in both modes.
- **JavaScript errors.** Zero `pageerror` events in 93/93 cells.
- **Failure states.** All four (unknown profile, missing artifact, checksum
  mismatch, incompatible artifact) render a `role="alert"` panel that is clean on
  D1–D8 at 320/360/768/1280/zoom200.

### Measurement artifacts, explicitly dismissed

Recorded so they are not re-filed as defects:

- **`.skip-link` "overlaps"** in the raw findings. Its computed transform is
  always `translateY(-69.56px)` and its rect is `top -62 … bottom -15`; it is
  never `:focus`-matched during measurement. The intersections are an artifact of
  comparing a `position: fixed` box against scrolled-past content in viewport
  coordinates. Verified in `probe2.json#skipLinkStates`.
- **Collapsed provenance drawer "overlapping" `.provenance-version`.** The
  `<details>` ships `open`; after collapsing, `getBoundingClientRect()` on a
  subtree under `content-visibility: hidden` still returns a stale box.
  `screenshots/probe-provenance-open-360.png` shows a correct collapse.
- **`Official repository` / `User Agreement` "overlap"** at 320 px. `User
  Agreement` wraps, so its *union* box spans both lines and overlaps its sibling;
  the actual line boxes are disjoint (`183..219` on line 1, `35..118` on line 2).
  Verified in `probe4.mjs`.
- **Focus "inversions"** on landing/science at ≥ 1024 px, and inside the drawer.
  The first are DOM-order-correct traversals of a multi-column provenance list;
  the second is the focus trap wrapping. Neither breaks meaning (WCAG 2.4.3).

## 5. Existing automated coverage mapped to the matrix

| Gate | What it covers today | Matrix cells it protects | Gap |
|---|---|---|---|
| `e2e/visual.spec.ts` | 2 screenshots (`retrieval-neighbors`, `neighbor-cards`) of `/lab` | `lab default` @ 360, 1280 | Landing and `/science` have **no** visual baseline — F-1 is invisible to CI. No 320, no tablet, no zoom, no error state, no drawer, no maximum content |
| `e2e/core-flow.spec.ts` | Keyboard flow + `expectNoPageOverflow` on `/lab` | D1, D4 for `lab default`/`lab selected` @ 360, 1280 | D1 is not asserted on `/` or `/science`; D3 is not asserted anywhere; 320 and zoom absent |
| `e2e/quality-contract.spec.ts` | axe on 3 routes + open drawer; link crawl; cache headers | D8 for landing, science, lab, drawer @ 360, 1280 | No axe on empty-filter, failure or maximum-content states; no 320/zoom |
| `e2e/failure-states.spec.ts` | 4 failure fixtures, desktop only | Content correctness of the failure states | No responsive assertion — runs at 1280 only |
| `lighthouserc.json` | `/lab/` ×3, mobile 360 | Perf/a11y/BP/SEO, LCP, CLS on one route | Landing and `/science` unmeasured |
| `scripts/check-static-output.mjs` | Route + landmark presence in the export | Build completeness | Does not exercise the 404 path (F-2) |
| `scripts/check-budgets.mjs` | gzip budgets | Payload size | n/a |

Uncovered critical cells assigned to `scoutlens-uze.6`: `/science` at
320/360/768 and `zoom200` (would catch F-1); D3 line-box geometry on all routes;
D1/D2 on landing and `/science`; a 320 px project; failure and maximum-content
states at mobile widths; the unknown-route response (F-2).

## 6. Beads created or refined by this audit

| Bead | Action | Carries |
|---|---|---|
| `scoutlens-uze.4` | refined | F-1 with the corrected locator, the `Range.getClientRects()` acceptance assertion and the measured 320–768 px failing range; F-4 with measured target sizes and the computed 2.5.8 verdict |
| `scoutlens-uze.5` | refined | F-3 with per-viewport scroll ratios and the sticky-row-header requirement |
| `scoutlens-uze.6` | refined | The coverage gaps in §5, cell by cell |
| `scoutlens-uze.7` | created | Deterministic maximum-content and uncertainty-state fixtures for the two blocked cells |
| `scoutlens-uze.8` | created | F-2, the unknown-route response in the release fixture |
| `scoutlens-uze.9` | created | F-5 and F-6, the two low-severity polish items |

No source, stylesheet or visual snapshot was modified by this audit.
