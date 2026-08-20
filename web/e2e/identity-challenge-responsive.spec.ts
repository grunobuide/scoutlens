/**
 * Identity challenge responsive geometry, accessibility and baselines
 * (`scoutlens-9a3.6.4`).
 *
 * Runs from the desktop project and resizes, following the precedent in
 * `404-page.spec.ts`: the 320 and 768 widths have no standing project against
 * the real export, and asserting them from a resizable context is cheaper than
 * adding two projects to `playwright.config.ts` for one spec.
 *
 * **There is deliberately no screenshot assertion here yet.** Baselines are
 * platform-scoped (`{projectName}-{platform}`) and both platforms must move
 * together (`scoutlens-uze.11`); generating the Linux pair needs the
 * `playwright:v1.62.0-noble` container, which was unavailable when this landed.
 * Committing win32 baselines alone would have shipped exactly the half-paired
 * state that guard exists to prevent. `scoutlens-9a3.6.5` adds them.
 *
 * Everything above is geometry, accessibility and motion policy, none of which
 * needs a reference image - so the coverage that does not depend on a container
 * is not held hostage to one.
 */

import { expect, test, type Page } from "@playwright/test";

import {
  expectNoPageOverflow,
  expectNoSeriousOrCriticalViolations,
  waitForStablePage,
} from "./helpers";

/** The widths `scoutlens-uze.6` fixed for responsive evidence. */
const WIDTHS = [320, 360, 768, 1280] as const;

const PANEL = '[data-challenge-panel="orientation"]';
const STATES = "[data-challenge-state]";

async function openChallenge(page: Page, state: string, width: number): Promise<void> {
  await page.setViewportSize({ width, height: 900 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto(state === "orientation" ? "/lab/" : `/lab/?challenge=${state}`);
  await waitForStablePage(page);
}

for (const state of ["orientation", "query", "reveal", "evidence"]) {
  test(`the ${state} state fits and passes axe at every frozen width`, async ({
    page,
  }, testInfo) => {
    test.skip(testInfo.project.name !== "desktop", "Widths are asserted once from a resizable context");

    for (const width of WIDTHS) {
      await openChallenge(page, state, width);
      await expect(page.locator(STATES)).toHaveAttribute("data-challenge-state", state);

      // No horizontal page scrollbar at any width, and nothing clipped out of
      // the panel's own box.
      await expectNoPageOverflow(page);
      const panel = page.locator(PANEL);
      const box = await panel.boundingBox();
      expect(box, `${state} panel has no box at ${width}`).not.toBeNull();
      expect(box!.width, `${state} panel overflows at ${width}`).toBeLessThanOrEqual(width);

      await expectNoSeriousOrCriticalViolations(page);
    }
  });
}

test("every CTA meets the 44 px touch target at 320 px", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Touch geometry is asserted once");

  // §6.4: "All CTA buttons and interactive elements are at least 44 × 44 CSS
  // pixels." 320 is the tightest width, so it is where a target is squeezed.
  for (const state of ["orientation", "query", "reveal", "evidence"]) {
    await openChallenge(page, state, 320);
    const ctas = page.locator(`${PANEL} .button`);
    const count = await ctas.count();
    expect(count, `${state} renders no CTA`).toBeGreaterThan(0);
    for (let index = 0; index < count; index += 1) {
      const box = await ctas.nth(index).boundingBox();
      expect(box, `${state} CTA ${index} has no box`).not.toBeNull();
      expect(box!.height, `${state} CTA ${index} is under 44 px tall`).toBeGreaterThanOrEqual(44);
      expect(box!.width, `${state} CTA ${index} is under 44 px wide`).toBeGreaterThanOrEqual(44);
    }
  }
});

test("the fingerprint rows meet the 44 px row target on touch", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Touch geometry is asserted once");

  // §6.4: "The fingerprint plot rows are at least 44px tall on touch devices."
  await openChallenge(page, "query", 360);
  const rows = page.locator("[data-challenge-fingerprint-row]");
  await expect(rows).toHaveCount(32);
  for (const index of [0, 15, 31]) {
    const box = await rows.nth(index).boundingBox();
    expect(box, `row ${index} has no box`).not.toBeNull();
    expect(box!.height, `row ${index} is under 44 px tall`).toBeGreaterThanOrEqual(44);
  }
});

test("the 320 px reading order is the DOM order section 6.6 fixes", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Reading order is asserted once");
  await openChallenge(page, "query", 320);

  // §6.6: "The reading order is the DOM order; no CSS `order` is used." A
  // visual order achieved with flex `order` reads correctly and is announced
  // wrongly, so the absence of the property is the assertion.
  const orders = await page.locator(`${PANEL} *`).evaluateAll((nodes) =>
    nodes
      .map((node) => getComputedStyle(node as Element).order)
      .filter((order) => order !== "0" && order !== ""),
  );
  expect(orders).toEqual([]);

  // Badge, then panel, then explorer: the vintage disclosure precedes the
  // content it qualifies.
  const positions = await page.evaluate(() => {
    const index = (selector: string) => {
      const element = document.querySelector(selector);
      if (element === null) {
        return -1;
      }
      return [...document.querySelectorAll("*")].indexOf(element);
    };
    return {
      badge: index("[data-vintage-badge]"),
      panel: index('[data-challenge-panel="orientation"]'),
      explorer: index("#lab-explorer"),
    };
  });
  expect(positions.badge).toBeGreaterThan(-1);
  expect(positions.badge).toBeLessThan(positions.panel);
  expect(positions.panel).toBeLessThan(positions.explorer);
});

test("no transition animates the challenge panel", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Motion policy is asserted once");
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto("/lab/");
  await waitForStablePage(page);

  // §6.5: "No animation accompanies state transitions ... there is no motion to
  // suppress." Asserted without emulating reduced motion on purpose: the
  // guarantee is that the default carries no motion, not that reduced-motion
  // users get a special case.
  await page.getByRole("button", { name: "See the fingerprint" }).click();
  await expect(page.locator(STATES)).toHaveAttribute("data-challenge-state", "query");

  const animated = await page.locator(`${PANEL} *`).evaluateAll((nodes) =>
    nodes
      .filter((node) => {
        const style = getComputedStyle(node as Element);
        const hasTransition =
          style.transitionDuration !== "0s" && style.transitionProperty !== "none";
        const hasAnimation = style.animationName !== "none" && style.animationDuration !== "0s";
        return hasTransition || hasAnimation;
      })
      .map((node) => (node as Element).className.toString()),
  );
  expect(animated).toEqual([]);
});
