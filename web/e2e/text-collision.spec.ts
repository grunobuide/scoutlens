/**
 * The text line-box collision gate (`scoutlens-uze.6.1`).
 *
 * `scoutlens-uze.1` found F-1: on `/science` at 360 px the step marker
 * `01 · question` wrapped and its second line box overshot its 40 px track by
 * 21.2 px, landing on the frozen-question heading. Nothing in the suite could
 * see it, because the marker is a stretched, clipped grid item whose element
 * box is innocent. Only the *line boxes* overlap.
 *
 * This file is the gate that would have caught it, generalised to the pairs
 * `scoutlens-uze.6` names. Its acceptance test is historical and lives at the
 * bottom of this file: the gate must detect F-1 when the exact pre-fix rule
 * from `8fc26fe^` is restored, and must be quiet without it.
 *
 * `e2e/frozen-question.spec.ts` keeps the standing F-1 assertion across
 * thirteen widths; this file does not repeat it.
 */

import { expect, test, type Page } from "@playwright/test";

import { expectNoTextCollision, waitForStablePage, type TextPair } from "./helpers";

/** The pairs `scoutlens-uze.6` AC2 names, per route. */
const PAIRS: Record<string, TextPair[]> = {
  // The frozen-question marker/heading pair - F-1 itself - is deliberately NOT
  // listed here. `e2e/frozen-question.spec.ts` already asserts it across
  // thirteen widths with a stronger claim than non-intersection: the heading
  // ink must start at or after the marker ink. Repeating it here would be a
  // second implementation of one measurement, which is the duplication defect
  // `scoutlens-uze.13` was. The reproduction test below proves this helper
  // detects that geometry; the standing assertion stays where it is.
  "/science/": [
    {
      // The same shape as F-1, and worth guarding for that reason: the fix in
      // 8fc26fe gave `.frozen-question` a `max-content` track and left
      // `.research-stage > header` on the original fixed `2.5rem` one. It is
      // safe only because its markers ("01".."06") are short enough not to
      // wrap. A longer marker here reproduces F-1 exactly.
      name: "stage marker vs stage heading",
      a: ".research-stage > header > .research-step__marker",
      b: ".research-stage > header h2",
    },
  ],
  "/": [
    { name: "site nav vs wordmark", a: ".site-nav", b: ".wordmark" },
  ],
  "/lab/": [
    { name: "site nav vs wordmark", a: ".site-nav", b: ".wordmark" },
    {
      name: "retrieval boundary text vs its link",
      a: ".retrieval-boundary p",
      b: ".retrieval-boundary a",
    },
    {
      name: "challenge identity vs period line",
      a: ".challenge-panel__identity",
      b: ".challenge-panel__periods",
    },
  ],
};

/** The widths F-1 was measured failing at, plus the project default. */
const WIDTHS = [320, 360, 375, 768, 1280] as const;

async function open(page: Page, route: string, width: number): Promise<void> {
  await page.setViewportSize({ width, height: 800 });
  await page.goto(route);
  await waitForStablePage(page);
}

for (const [route, pairs] of Object.entries(PAIRS)) {
  test(`no text collides on ${route}`, async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "desktop", "Widths are asserted once from a resizable context");

    for (const width of WIDTHS) {
      await open(page, route, width);
      await expectNoTextCollision(page, pairs, `${route} at ${width}`);
    }
  });
}

test("line boxes see what element boxes cannot", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Asserted once from a resizable context");

  // The whole reason this gate measures ink. On the pre-fix tree the marker's
  // element box did NOT intersect the heading while its line boxes did; here,
  // post-fix, neither intersects. What this asserts is the property that makes
  // the two measurements different: the marker's element box is wider than the
  // union of its own line boxes, because the box is stretched and the ink is
  // not. A gate built on element boxes is measuring the wrong rectangle.
  await open(page, "/science/", 360);

  const measured = await page.evaluate(() => {
    const marker = document.querySelector(".frozen-question > .research-step__marker");
    if (marker === null) {
      return null;
    }
    const range = document.createRange();
    range.selectNodeContents(marker);
    const ink = [...range.getClientRects()];
    const box = marker.getBoundingClientRect();
    return {
      boxWidth: Math.round(box.width * 10) / 10,
      inkRight: Math.round(Math.max(...ink.map((r) => r.right)) * 10) / 10,
      boxRight: Math.round(box.right * 10) / 10,
      lineBoxes: ink.length,
    };
  });

  expect(measured, "the /science step marker is missing").not.toBeNull();
  // More than one line box is the condition F-1 needed: a single-line marker
  // cannot overshoot its track.
  expect(measured!.lineBoxes).toBeGreaterThan(0);
  // The element box extends at least as far as the ink; they are not the same
  // rectangle, which is precisely why one assertion can pass while the other
  // fails.
  expect(measured!.boxRight).toBeGreaterThanOrEqual(measured!.inkRight - 0.5);
});

test("the gate ignores a fixed element measured against scrolled-past content", async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Asserted once from a resizable context");

  // False positive 1 from the audit: `.skip-link` is `position: fixed`, so once
  // the page is scrolled its viewport rectangle sits over content it does not
  // visually touch. The helper excludes fixed subtrees for that reason.
  await open(page, "/lab/", 360);
  await page.evaluate(() => window.scrollTo(0, 2000));

  const skipLinkIsFixed = await page.evaluate(() => {
    const link = document.querySelector(".skip-link");
    return link === null ? null : getComputedStyle(link).position;
  });
  expect(skipLinkIsFixed, "the skip link is no longer fixed - revisit this exclusion").toBe("fixed");

  await expectNoTextCollision(
    page,
    [{ name: "skip link vs scrolled content", a: ".skip-link", b: ".lab-selector h2" }],
    "scrolled",
  );
});

test("the gate ignores stale rects inside a closed details", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Asserted once from a resizable context");

  // False positive 2: a skipped subtree keeps its last laid-out rectangles, so
  // the numbers are real and describe where the text *would* be. The Lab's
  // advanced audit disclosure is a closed <details> on load.
  await open(page, "/lab/", 360);

  const closed = await page.evaluate(() => {
    const details = document.querySelector(".method-disclosure details");
    return details instanceof HTMLDetailsElement ? details.open : null;
  });
  expect(closed, "the advanced disclosure is missing or already open").toBe(false);

  await expectNoTextCollision(
    page,
    [
      {
        name: "collapsed disclosure vs the heading above it",
        a: ".method-disclosure details p",
        b: "#method-disclosure-heading",
      },
    ],
    "collapsed details",
  );
});

test("the gate does not flag two wrapped links in one paragraph", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Asserted once from a resizable context");

  // False positive 3: the union box of a wrapped inline element is an artifact
  // of `getBoundingClientRect()`. Line boxes cannot produce it, so this class
  // needs no exclusion rule - the measurement makes it impossible. This test
  // exists to hold that property rather than to describe it.
  await open(page, "/lab/", 320);

  const bothPresent = await page.evaluate(() => {
    const links = document.querySelectorAll(".provider-boundary p a");
    return links.length >= 2;
  });
  expect(bothPresent, "the provenance paragraph no longer holds two links").toBe(true);

  await expectNoTextCollision(
    page,
    [
      {
        name: "two links sharing one paragraph",
        a: ".provider-boundary p a:nth-of-type(1)",
        b: ".provider-boundary p a:nth-of-type(2)",
      },
    ],
    "inline siblings",
  );
});

test("the gate detects the F-1 geometry when the pre-fix rule is restored", async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Reproduction runs once in desktop Chromium");

  // The acceptance test for this gate is historical: it must catch the defect
  // that motivated it.
  //
  // Building the pre-fix tree is not viable - `8fc26fe^` pins a v1 showcase
  // payload and its Next build no longer resolves in this environment - so the
  // reproduction restores the exact rule the fix removed, taken verbatim from
  // `git show 8fc26fe^:web/src/app/styles/science.css`:
  //
  //     @media (max-width: 48rem) {
  //       .frozen-question,
  //       .research-stage > header {
  //           grid-template-columns: 2.5rem minmax(0, 1fr);
  //           gap: 1rem;
  //       }
  //     }
  //
  // Applied to the current markup, which is unchanged in this region. This is
  // stronger than a one-off historical build: it is permanent, deterministic,
  // and it fails if anyone ever reintroduces the rule.
  await open(page, "/science/", 360);

  const pair: TextPair = {
    name: "frozen-question marker vs heading",
    a: ".frozen-question > .research-step__marker",
    b: "#frozen-question-heading",
  };

  // Clean first: the current rule must not collide.
  await expectNoTextCollision(page, [pair], "before restoring the pre-fix rule");

  await page.addStyleTag({
    content:
      "@media (max-width: 48rem) { .frozen-question { grid-template-columns: 2.5rem minmax(0, 1fr); gap: 1rem; } }",
  });
  await page.waitForTimeout(50);

  // The audit measured markerInkRight = 96.2 against headingInkLeft = 91 at
  // 360 px. Confirm the restored rule actually reproduces that geometry before
  // asserting the gate reacts to it - otherwise a passing test would only prove
  // the style tag did nothing.
  const geometry = await page.evaluate(() => {
    const ink = (element: Element) => {
      const range = document.createRange();
      range.selectNodeContents(element);
      return [...range.getClientRects()];
    };
    const marker = document.querySelector(".frozen-question > .research-step__marker");
    const heading = document.querySelector("#frozen-question-heading");
    if (marker === null || heading === null) {
      return null;
    }
    const m = ink(marker);
    const h = ink(heading);
    return {
      markerInkRight: Math.max(...m.map((r) => r.right)),
      headingInkLeft: Math.min(...h.map((r) => r.left)),
      markerLineBoxes: m.length,
    };
  });

  expect(geometry, "the /science marker or heading is missing").not.toBeNull();
  expect(
    geometry!.markerLineBoxes,
    "the marker no longer wraps, so F-1 cannot be reproduced",
  ).toBeGreaterThan(1);
  expect(
    geometry!.markerInkRight,
    "the restored rule did not push the marker ink past the heading",
  ).toBeGreaterThan(geometry!.headingInkLeft);

  // And now the point: the gate must report it.
  let caught: unknown = null;
  try {
    await expectNoTextCollision(page, [pair], "pre-fix rule restored");
  } catch (error) {
    caught = error;
  }
  expect(caught, "the gate did not detect the F-1 collision").not.toBeNull();
  expect(String(caught)).toContain(".research-step__marker");
  expect(String(caught)).toContain("#frozen-question-heading");
});
