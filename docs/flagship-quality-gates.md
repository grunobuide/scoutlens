# Flagship web quality gates

This record defines how the deterministic ScoutLens vertical slice is tested
before a release decision. It complements the product limits in
[`flagship-vertical-slice.md`](flagship-vertical-slice.md); it does not loosen
them.

## Single release command

After hydrating the pinned showcase player pack and installing the pinned Node,
pnpm and Chromium versions documented in [`web/README.md`](../web/README.md):

```bash
cd web
pnpm release:check
```

The command builds the static export once, then serves `web/out` through the
same built-in production fixture for Playwright and Lighthouse. The fixture
gzip-compresses text assets, keeps `manifest.json` revalidatable for dataset
discovery, and marks versioned non-manifest showcase files plus hashed Next.js
assets as one-year `immutable` resources.

## Reproducible measurement profile

| Surface | Frozen profile | Failure rule |
|---|---|---|
| Browser E2E | Chromium; 1280x900 desktop and 360x800 touch viewport; English/UTC/light; platform-qualified visual baselines | Any required flow, failure fixture, local link, cache header or responsive baseline fails |
| Automated accessibility | axe default rules, no excluded elements or disabled rules; all routes and open comparison drawer | Any `serious` or `critical` violation fails |
| Lighthouse | Three `/lab/` runs; median run; 360x800 mobile; Chromium Fast 4G preset (60 ms RTT, 9 Mbps down) and 4x CPU slowdown | Performance, Accessibility, Best Practices or SEO below 0.90; LCP above 2,500 ms; CLS above 0.10 |
| Interaction latency | Chromium Event Timing API during the percentile-toggle keyboard interaction | Longest interaction above 200 ms fails |
| Static budgets | Deterministic gzip level 9 over the production export | Initial JS above 204,800 B; catalog above 409,600 B; any profile above 30,720 B; initial `/lab` HTML+CSS+JS above 768,000 B |

The Event Timing assertion exercises the browser mechanism used by INP, but is
a synthetic release proxy rather than a field Core Web Vital. A real public
deployment would still need field telemetry before making a population-level
INP claim.

Visual snapshots include Playwright's `{platform}` token in their path so
Windows and Linux font rasterization are reviewed independently without
loosening the 3% pixel-difference limit. Linux baselines are generated and
verified with the official `mcr.microsoft.com/playwright:v1.62.0-noble` image,
which matches the pinned test dependency and GitHub runner browser.

## Covered product states

The Playwright suite covers selection and direct-URL reload, both percentile
scales, all three stored retrieval outcomes, five-neighbor evidence, modal
keyboard behavior, the empty filter, unknown profile, missing payload, checksum
mismatch, schema-invalid payload and pending uncertainty/stability. Corrupt
fixtures are intercepted at the HTTP boundary and never alter the published
showcase pack.

## Manual keyboard record

The release record is completed against the production export, not the
development server. The operator records the date, browser version and outcome
for this sequence:

| Step | Required observation |
|---:|---|
| 1 | Tab from the address bar reaches the skip link and site navigation with a visible focus indicator. |
| 2 | Search, role, competition and team controls are reachable in logical order; result count changes are announced. |
| 3 | A player result opens with Enter and updates the selected profile and URL. |
| 4 | Both percentile radios operate with arrow/space keys without losing the selected player. |
| 5 | All five neighbor buttons are reachable; Enter opens the comparison dialog with focus on Close. |
| 6 | Focus stays inside the modal, its internal table can receive focus, Escape closes it and focus returns to the invoking neighbor. |
| 7 | The science link and remaining 32-feature table are reachable; internal horizontal scrolling does not create page-level overflow. |

Measured results and the completed manual record are appended to the Beads
closure evidence for `scoutlens-jtt.4.6`, keeping operational state out of this
versioned protocol.
