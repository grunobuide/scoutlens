/**
 * Reduced motion, as behaviour (`scoutlens-uze.28`, uze.4 AC6).
 *
 * The visual specs emulate `prefers-reduced-motion: reduce` only to make their
 * screenshots stable, so nothing checked what the preference *does*. On `/` and
 * `/science/` the one motion the stylesheets declare is smooth scrolling
 * (`html { scroll-behavior: smooth }`, `base.css`), which the reduce query turns
 * back to `auto`. These hold that, by what a scroll does rather than by what a
 * stylesheet says, and hold that no animation or transition runs on these
 * routes for a reader who asked for none.
 */

import { expect, test, type Page } from "@playwright/test";

import { waitForStablePage } from "./helpers";

const ROUTES = ["/", "/science/"] as const;

test.beforeEach(({}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Motion preference is viewport-independent; asserted once");
});

/**
 * Asks the page to scroll a far element into view with its default behaviour,
 * and reads the scroll position in the same task. An instant scroll has
 * already moved; a smooth one has only been scheduled.
 */
async function scrollJump(page: Page): Promise<{ before: number; after: number; target: number }> {
  return page.evaluate(() => {
    window.scrollTo({ top: 0, behavior: "instant" });
    const before = window.scrollY;
    const far = [...document.querySelectorAll<HTMLElement>("main section, main article")].at(-1);
    if (far === undefined) {
      throw new Error("no section to scroll to");
    }
    far.scrollIntoView();
    return { before, after: window.scrollY, target: far.getBoundingClientRect().top + window.scrollY };
  });
}

for (const route of ROUTES) {
  test(`${route} scrolls instantly when the reader asks for reduced motion`, async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto(route);
    await waitForStablePage(page);

    const jump = await scrollJump(page);
    expect(jump.after, `${route}: the scroll had not happened yet - it was animated`).toBeGreaterThan(jump.before);
  });

  // Not vacuous: without the preference the same call is animated, so the
  // assertion above is measuring the media query, not a page that never
  // smooth-scrolls.
  test(`${route} smooth-scrolls when the reader has no motion preference`, async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "no-preference" });
    await page.goto(route);
    await waitForStablePage(page);

    const jump = await scrollJump(page);
    expect(jump.after, `${route}: the scroll was instant without the preference`).toBe(jump.before);
  });

  test(`${route} runs no animation or transition under reduced motion, disclosures and hovers included`, async ({
    page,
  }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto(route);
    await waitForStablePage(page);

    // The interactions that could start one: every disclosure toggled, every
    // link and button hovered and focused.
    for (const summary of await page.locator("main summary").all()) {
      await summary.click();
    }
    for (const control of await page.locator("main a, main button").all()) {
      if (await control.isVisible()) {
        await control.hover();
        await control.focus();
      }
    }
    const running = await page.evaluate(() =>
      document.getAnimations().map((animation) => {
        const target = (animation.effect as KeyframeEffect | null)?.target;
        return `${animation.constructor.name} on ${target instanceof Element ? target.className : "?"}`;
      }),
    );
    expect(running, `${route}: motion under prefers-reduced-motion: reduce`).toEqual([]);
  });
}
