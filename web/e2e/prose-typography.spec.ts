/**
 * Prose typography leak gate (`scoutlens-r0`, `docs/product-roadmap.md`).
 *
 * Sentinel defect the R0 epic names: on `/` and `/science/`, a metric
 * explanation's "What this means" disclosure inherited the large numeric
 * value's -0.06em letter-spacing - computed to -2.4px at the value's own
 * 40px font size - because `.experiment-metrics dd` was a bare tag
 * selector. It matched every `dd` in the `dl`, including
 * `.experiment-metric__explanation`, the second `dd` holding the
 * disclosure. That `dd` set its own smaller font-size in `science.css` but
 * never reset tracking or `font-variant-numeric`, and letter-spacing is
 * inherited as the ancestor's *computed absolute px value*, not
 * recalculated per descendant font-size - so its prose rendered squeezed to
 * the point of illegibility, words running into each other.
 *
 * The fix scopes the rule to a dedicated `.experiment-metric__value` class
 * (`web/src/components/research-story.tsx`,
 * `web/src/app/styles/research-story.css`) rather than compensating with a
 * reset on the explanation's own rules - matching R0's "fix root causes"
 * requirement.
 *
 * This gate does not just re-assert that one fix. It generalises across R0's
 * four named computed-style dimensions - letter spacing, line height,
 * overflow, and inherited numeric typography - and opens every disclosure on
 * a route so a rule of the same shape, anywhere, is caught the same way:
 *
 *   - letter spacing: heavy negative tracking (< -1px) on prose.
 *   - inherited numeric typography: `tabular-nums`, or a value-scale
 *     font-size (> 24px), on prose.
 *   - line height: below 1.2x the element's own font-size - loose enough
 *     that no legitimate prose rule in this codebase (1.35-1.6x) is close,
 *     tight enough to catch a heading's 1.06x leaking in.
 *   - overflow: `scrollHeight`/`scrollWidth` exceeding the element's own box,
 *     which is what "clipped or overprinted" looks like from computed
 *     geometry - the acceptance criterion's own words.
 *
 * Swept at the widths R0's acceptance gate names - 320, 360, 768, 1280, and
 * the 640x512 200%-reflow viewport - following `responsive-baseline`'s
 * pattern of resizing within a test rather than relying on project defaults
 * alone, run across both the desktop and mobile-360 projects so every width
 * is covered by at least one.
 */

import { expect, test, type Page } from "@playwright/test";

import { waitForStablePage } from "./helpers";

interface ProseLeak {
  selector: string;
  text: string;
  fontSizePx: number;
  letterSpacingPx: number;
  fontVariantNumeric: string;
  lineHeightRatio: number;
  overflowsBox: boolean;
}

async function openEveryDisclosure(page: Page): Promise<void> {
  // `explainMetric`'s disclosure renders once per metric, so a route with
  // several `ExperimentCard`s carries many more `<details>` instances than
  // the three places `<details>` appears in source. Setting `open` directly
  // is the "all disclosures open" state the audit scope names, and is exact
  // regardless of count - no click-convergence loop to get wrong.
  await page.evaluate(() => {
    for (const details of document.querySelectorAll<HTMLDetailsElement>("details:not([open])")) {
      details.open = true;
    }
  });
}

/**
 * `summary` is always rendered, open or closed - the disclosure's "closed"
 * state is exactly its (visible) summary alone, so summaries are probed
 * unconditionally. `p` content is hidden by the UA stylesheet while its
 * `<details>` is closed, so only open ones are probed - `openEveryDisclosure`
 * is expected to have run first for the "all-open" state this gate targets.
 */
async function probeProseLeaks(page: Page): Promise<ProseLeak[]> {
  return page.evaluate(() => {
    const leaks: Array<{
      selector: string;
      text: string;
      fontSizePx: number;
      letterSpacingPx: number;
      fontVariantNumeric: string;
      lineHeightRatio: number;
      overflowsBox: boolean;
    }> = [];
    const prose = new Set<HTMLElement>();
    for (const summary of document.querySelectorAll<HTMLElement>("details > summary")) {
      prose.add(summary);
    }
    for (const details of document.querySelectorAll<HTMLDetailsElement>("details[open]")) {
      for (const p of details.querySelectorAll<HTMLElement>("p")) {
        prose.add(p);
      }
    }
    for (const el of prose) {
      const style = getComputedStyle(el);
      const fontSizePx = Number.parseFloat(style.fontSize);
      const letterSpacingPx = style.letterSpacing === "normal" ? 0 : Number.parseFloat(style.letterSpacing);
      const lineHeightPx =
        style.lineHeight === "normal" ? fontSizePx * 1.2 : Number.parseFloat(style.lineHeight);
      const lineHeightRatio = lineHeightPx / fontSizePx;
      const overflowsBox = el.scrollHeight > el.clientHeight + 1 || el.scrollWidth > el.clientWidth + 1;
      const leaked =
        letterSpacingPx < -1 ||
        fontSizePx > 24 ||
        style.fontVariantNumeric === "tabular-nums" ||
        lineHeightRatio < 1.2 ||
        overflowsBox;
      if (leaked) {
        leaks.push({
          selector: `${el.tagName.toLowerCase()}${el.className ? `.${String(el.className).replace(/\s+/g, ".")}` : ""}`,
          text: (el.textContent ?? "").trim().slice(0, 60),
          fontSizePx,
          letterSpacingPx,
          fontVariantNumeric: style.fontVariantNumeric,
          lineHeightRatio,
          overflowsBox,
        });
      }
    }
    return leaks;
  });
}

// R0 scope: `/`, `/science/` render the affected `ExperimentCard`. `/lab/`
// carries the suite's other two disclosures (`method-disclosure__advanced`,
// `provenance-drawer`) and is walked for the same invariant even though
// neither currently sits inside a numeric-value container.
const ROUTES = ["/", "/science/", "/lab/"];

// R0's acceptance gate names these five widths explicitly. `320`/`640x512`/
// `768` are swept within each test via explicit resize, matching
// `responsive-baseline`; `1280` and `360` come from running on both the
// `desktop` and `mobile-360` projects, each at its own default viewport.
const SWEPT_WIDTHS = [
  { width: 320, height: 800 },
  { width: 640, height: 512 },
  { width: 768, height: 900 },
] as const;

async function assertNoLeaksAt(page: Page, route: string, width: number): Promise<void> {
  await openEveryDisclosure(page);
  const leaks = await probeProseLeaks(page);
  expect(leaks, `${route} at ${width} prose typography leaks`).toEqual([]);
}

for (const route of ROUTES) {
  test(`${route} disclosures stay legible fully expanded, swept widths`, async ({ page }) => {
    await page.goto(route);
    await waitForStablePage(page);

    for (const viewport of SWEPT_WIDTHS) {
      await page.setViewportSize(viewport);
      await assertNoLeaksAt(page, route, viewport.width);
    }
  });

  test(`${route} disclosures stay legible fully expanded, project viewport`, async ({ page }) => {
    await page.goto(route);
    await waitForStablePage(page);
    const width = page.viewportSize()?.width ?? 0;
    await assertNoLeaksAt(page, route, width);
  });
}

test("the gate detects the sentinel when the pre-fix bare dd selector is restored", async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Reproduction runs once in desktop Chromium");

  await page.goto("/science/");
  await waitForStablePage(page);
  await openEveryDisclosure(page);

  // Clean first: the current, scoped rule must not leak.
  expect(await probeProseLeaks(page), "before restoring the pre-fix rule").toEqual([]);

  // The exact rule this fix replaced (`web/src/app/styles/research-story.css`,
  // before this change), reintroduced verbatim as a page-level override. Its
  // selector is a bare `dd` under `.experiment-metrics`, so it matches the
  // explanation's `dd` again exactly as it did before the fix.
  await page.addStyleTag({
    content: `
      .experiment-metrics dd {
        margin: 0.35rem 0 0;
        color: var(--teal);
        font-size: clamp(1.6rem, 4vw, 2.5rem);
        font-variant-numeric: tabular-nums;
        font-weight: 620;
        letter-spacing: -0.06em;
      }
    `,
  });
  await page.waitForTimeout(50);

  const leaks = await probeProseLeaks(page);
  expect(leaks.length, "restoring the pre-fix rule must reproduce the leak").toBeGreaterThan(0);
  expect(leaks.some((leak) => leak.letterSpacingPx <= -2), "expected the sentinel's ~-2.4px tracking").toBe(
    true,
  );
});
