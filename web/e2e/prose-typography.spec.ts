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
 * This gate does not just re-assert that one fix. It generalises: open
 * every disclosure on a route and assert none of its prose (`summary`, `p`)
 * carries the three properties that are legitimate on a numeric/heading/badge
 * figure in this codebase and illegitimate on prose - heavy negative
 * letter-spacing, an oversized value-scale font-size, or tabular-nums - so a
 * future rule of the same shape, anywhere, is caught the same way.
 */

import { expect, test, type Page } from "@playwright/test";

import { waitForStablePage } from "./helpers";

interface ProseLeak {
  selector: string;
  text: string;
  fontSizePx: number;
  letterSpacingPx: number;
  fontVariantNumeric: string;
}

async function openEveryDisclosure(page: Page): Promise<void> {
  // `explainMetric`'s disclosure renders once per metric, so a route with
  // several `ExperimentCard`s carries many more `<details>` instances than
  // the three places `<details>` appears in source. Setting `open` directly
  // is the "all disclosures open" state the audit scope names, and is exact
  // regardless of count - no click-convergence loop to get wrong.
  const opened = await page.evaluate(() => {
    const closed = [...document.querySelectorAll<HTMLDetailsElement>("details:not([open])")];
    for (const details of closed) {
      details.open = true;
    }
    return closed.length;
  });
  expect(opened, "at least one disclosure exists to open").toBeGreaterThan(0);
}

async function probeProseLeaks(page: Page): Promise<ProseLeak[]> {
  return page.evaluate(() => {
    const leaks: Array<{
      selector: string;
      text: string;
      fontSizePx: number;
      letterSpacingPx: number;
      fontVariantNumeric: string;
    }> = [];
    const openDetails = [...document.querySelectorAll<HTMLDetailsElement>("details[open]")];
    for (const details of openDetails) {
      for (const el of details.querySelectorAll<HTMLElement>("summary, p")) {
        const style = getComputedStyle(el);
        const fontSizePx = Number.parseFloat(style.fontSize);
        const letterSpacingPx = style.letterSpacing === "normal" ? 0 : Number.parseFloat(style.letterSpacing);
        const leaked = letterSpacingPx < -1 || fontSizePx > 24 || style.fontVariantNumeric === "tabular-nums";
        if (leaked) {
          leaks.push({
            selector: `${el.tagName.toLowerCase()}${el.className ? `.${String(el.className).replace(/\s+/g, ".")}` : ""}`,
            text: (el.textContent ?? "").trim().slice(0, 60),
            fontSizePx,
            letterSpacingPx,
            fontVariantNumeric: style.fontVariantNumeric,
          });
        }
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

for (const route of ROUTES) {
  test(`${route} disclosures stay legible fully expanded`, async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "desktop", "Geometry and computed style are asserted once per route");

    await page.goto(route);
    await waitForStablePage(page);
    await openEveryDisclosure(page);

    const leaks = await probeProseLeaks(page);
    expect(leaks, `${route} prose typography leaks`).toEqual([]);
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
