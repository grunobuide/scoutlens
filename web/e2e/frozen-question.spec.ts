import { expect, test, type Page } from "@playwright/test";

import { waitForStablePage } from "./helpers";

/**
 * Defect F-1 (scoutlens-uze.4): at widths <= 48rem the frozen-question marker
 * ("01 · question") overflowed its fixed 2.5rem grid track and its second line
 * box collided with the heading ink. The acceptance assertion is a
 * Range.getClientRects() comparison, because the element bounding boxes never
 * intersect (the marker item is clipped to its track while only the rendered
 * text overflows). Measured failing range: 320-768 px; clears at 769 px.
 *
 * See docs/frontend-qa-audit.md, sections 2-3 (F-1).
 */

const WIDTHS = [320, 340, 360, 375, 400, 420, 480, 560, 640, 700, 766, 767, 768] as const;

test.beforeEach(async ({}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "F-1 geometry runs once in desktop Chromium");
});

async function measureFrozenQuestion(page: Page) {
  return page.evaluate(() => {
    const ink = (element: Element) => {
      const range = document.createRange();
      range.selectNodeContents(element);
      return [...range.getClientRects()];
    };
    const marker = document.querySelector(".frozen-question > .research-step__marker");
    const heading = document.querySelector("#frozen-question-heading");
    if (marker === null || heading === null) {
      throw new Error("frozen-question marker/heading missing from /science");
    }
    const markerRects = ink(marker);
    const headingRects = ink(heading);
    const markerInkRight = Math.max(...markerRects.map((rect) => rect.right));
    const headingInkLeft = Math.min(...headingRects.map((rect) => rect.left));
    const intersects = markerRects.some((markerRect) =>
      headingRects.some(
        (headingRect) =>
          markerRect.left < headingRect.right &&
          markerRect.right > headingRect.left &&
          markerRect.top < headingRect.bottom &&
          markerRect.bottom > headingRect.top,
      ),
    );
    return { headingInkLeft, intersects, markerInkRight };
  });
}

test("frozen-question marker ink clears the heading ink at every measured mobile width", async ({ page }) => {
  await page.goto("/science/");
  await waitForStablePage(page);

  for (const width of WIDTHS) {
    await test.step(`viewport ${width}px`, async () => {
      await page.setViewportSize({ width, height: 800 });
      const { headingInkLeft, intersects, markerInkRight } = await measureFrozenQuestion(page);
      expect(headingInkLeft, `${width}px: heading must start at or after the marker ink`).toBeGreaterThanOrEqual(
        markerInkRight,
      );
      expect(intersects, `${width}px: marker and heading line boxes must not intersect`).toBe(false);
    });
  }
});
