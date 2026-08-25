/**
 * The Lab's content order (`scoutlens-uze.5.2`).
 *
 * Binds the implementation to `docs/lab-mobile-order.md` §2. That document
 * exists because `scoutlens-uze.5` AC1 required conformance to an "accepted
 * mobile narrative order" that had never been written down, so the criterion
 * could be neither met nor refuted.
 *
 * Asserted as **DOM order**, and separately as **visual order**, because the
 * two agreeing is the property that matters. A sequence achieved with CSS
 * `order` reads correctly to the eye and wrongly to a screen reader, which
 * `scoutlens-uze.5`'s stop condition forbids outright.
 */

import { expect, test, type Page } from "@playwright/test";

import { expectNoPageOverflow, waitForStablePage } from "./helpers";

const PROFILE = "/lab/?player=wy-8287-c-795";

/** §2 of docs/lab-mobile-order.md, in order. */
const ORDER = [
  "header.page-intro",
  ".challenge-panel",
  ".lab-selector",
  ".selected-profile__header",
  ".period-context-grid",
  ".retrieval-replay",
  ".method-disclosure",
  ".lab-analysis-grid",
  ".statistical-neighbors",
  ".fingerprint-table-section",
  ".provider-boundary",
] as const;

async function openLab(page: Page, width: number): Promise<void> {
  await page.setViewportSize({ width, height: 900 });
  await page.goto(PROFILE);
  await waitForStablePage(page);
}

test("the DOM follows the documented order at every narrow width", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Widths are asserted once from a resizable context");

  for (const width of [320, 360, 375]) {
    await openLab(page, width);

    const positions = await page.evaluate((selectors) => {
      const all = [...document.querySelectorAll("main *")];
      return selectors.map((selector) => {
        const element = document.querySelector(`main ${selector}`);
        return { selector, index: element === null ? -1 : all.indexOf(element) };
      });
    }, ORDER as unknown as string[]);

    const missing = positions.filter((entry) => entry.index === -1).map((entry) => entry.selector);
    expect(missing, `blocks absent at ${width}`).toEqual([]);

    const indices = positions.map((entry) => entry.index);
    const sorted = [...indices].sort((a, b) => a - b);
    expect(indices, `DOM order differs from the document at ${width}`).toEqual(sorted);
  }
});

test("the result precedes the fingerprint chart", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Asserted once from a resizable context");

  // §3 of the order document, and the one substantive change it makes. Before
  // `scoutlens-uze.5.2` the rank sat at 10,047 px on a 19,646 px page at 320,
  // behind a 4,156 px chart - a reader met the evidence before the finding it
  // was evidence for.
  for (const width of [320, 360, 375, 1280]) {
    await openLab(page, width);
    const geometry = await page.evaluate(() => {
      const top = (selector: string) => {
        const element = document.querySelector(selector);
        return element === null ? -1 : element.getBoundingClientRect().top + window.scrollY;
      };
      return { rank: top(".retrieval-replay"), plot: top(".lab-analysis-grid") };
    });
    expect(geometry.rank, `no retrieval section at ${width}`).toBeGreaterThan(-1);
    expect(
      geometry.rank,
      `the chart precedes the result at ${width}`,
    ).toBeLessThan(geometry.plot);
  }
});

test("visual order matches DOM order, with no CSS order anywhere", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Asserted once from a resizable context");

  for (const width of [320, 1280]) {
    await openLab(page, width);

    // Rule 1 of §4: no element in the Lab may carry a non-default `order`.
    const reordered = await page.evaluate(() =>
      [...document.querySelectorAll("main *")]
        .filter((element) => {
          const order = getComputedStyle(element).order;
          return order !== "" && order !== "0";
        })
        .map((element) => element.className.toString().split(" ")[0]),
    );
    expect(reordered, `CSS order used at ${width}`).toEqual([]);

    // And the stronger property that rule exists to protect: at 320 the blocks
    // are stacked, so their tops must increase with DOM index. At 1280 blocks 9
    // and 10 share a row by design, so equality is allowed there.
    const tops = await page.evaluate((selectors) =>
      selectors
        .map((selector) => document.querySelector(`main ${selector}`))
        .filter((element): element is Element => element !== null)
        .map((element) => Math.round(element.getBoundingClientRect().top + window.scrollY)),
      ORDER as unknown as string[],
    );
    for (let index = 1; index < tops.length; index += 1) {
      expect(
        tops[index]!,
        `block ${index} renders above block ${index - 1} at ${width}`,
      ).toBeGreaterThanOrEqual(tops[index - 1]!);
    }
  }
});

test("the reordered Lab still fits every narrow width", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Asserted once from a resizable context");

  // The order document changes sequence only - no block was added, removed,
  // resized or hidden - so the overflow baseline `scoutlens-uze.1` established
  // must be exactly as it was.
  for (const width of [320, 360, 375]) {
    await openLab(page, width);
    await expectNoPageOverflow(page);
  }
});

test("desktop keeps its two-column analysis layout", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Asserted once from a resizable context");

  // Rule 4 of §4: desktop differs by layout, never by sequence. The fingerprint
  // and the evidence rail share a row above 48 rem; losing that would be a
  // density regression, which `scoutlens-uze.5` AC6 forbids.
  await openLab(page, 1280);
  const sameRow = await page.evaluate(() => {
    const plot = document.querySelector(".fingerprint-lab-card");
    const rail = document.querySelector(".lab-evidence-rail");
    if (plot === null || rail === null) {
      return null;
    }
    return Math.abs(plot.getBoundingClientRect().top - rail.getBoundingClientRect().top) < 2;
  });
  expect(sameRow, "the desktop analysis grid is no longer two columns").toBe(true);
});
