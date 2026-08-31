/**
 * Identity challenge responsive geometry, accessibility and baselines
 * (`scoutlens-9a3.6.4`).
 *
 * Runs from the desktop project and resizes, following the precedent in
 * `404-page.spec.ts`: the 320 and 768 widths have no standing project against
 * the real export, and asserting them from a resizable context is cheaper than
 * adding two projects to `playwright.config.ts` for one spec.
 *
 * Baselines are platform-scoped (`{projectName}-{platform}`) and both platforms
 * must move together — `pnpm check:baseline-pairs` fails a pull request that
 * updates one and not the other (`scoutlens-uze.11`).
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

test("both period marks stay independently visible on every row", async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Geometry is asserted once from a resizable context");

  // `scoutlens-9a3.10`. Both marks used to sit at `top: 50%`, so a feature whose
  // period-A and period-B percentiles nearly coincide drew one glyph over the
  // other - "Box entries" and "Mean y" in the published profile. Fixed lanes
  // 1.2rem apart, against a 1.15rem glyph, make that impossible by construction
  // rather than by detection.
  for (const width of WIDTHS) {
    await openChallenge(page, "reveal", width);

    const result = await page.evaluate(() => {
      const overlapping: string[] = [];
      const escaping: string[] = [];
      for (const row of document.querySelectorAll("[data-challenge-fingerprint-row]")) {
        const a = row.querySelector(".challenge-fingerprint__mark--a");
        const b = row.querySelector(".challenge-fingerprint__mark--b");
        if (a === null || b === null) {
          continue;
        }
        const id = row.getAttribute("data-challenge-fingerprint-row") ?? "?";
        const ra = a.getBoundingClientRect();
        const rb = b.getBoundingClientRect();
        // Any vertical intersection means one glyph can cover the other once
        // their horizontal positions converge.
        if (ra.bottom > rb.top && rb.bottom > ra.top) {
          overlapping.push(id);
        }
        const rr = row.getBoundingClientRect();
        if (ra.top < rr.top - 0.5 || rb.bottom > rr.bottom + 0.5) {
          escaping.push(id);
        }
      }
      return { overlapping, escaping };
    });

    expect(result.overlapping, `marks overlap at ${width}`).toEqual([]);
    expect(result.escaping, `marks escape their row at ${width}`).toEqual([]);
  }
});

test("the lanes move marks vertically and never horizontally", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Geometry is asserted once from a resizable context");

  // The horizontal centre is the scientific part of a mark's position: it is
  // the feature's percentile. `scoutlens-9a3.10` may move a glyph in y and must
  // not move one in x, so this recomputes each centre from the track box and
  // the row's own custom property rather than trusting that `left` was left
  // alone.
  for (const width of WIDTHS) {
    await openChallenge(page, "reveal", width);

    const drift = await page.evaluate(() => {
      const wrong: string[] = [];
      for (const row of document.querySelectorAll("[data-challenge-fingerprint-row]")) {
        const track = row.querySelector(".challenge-fingerprint__track");
        if (track === null) {
          continue;
        }
        const box = track.getBoundingClientRect();
        const style = getComputedStyle(track);
        const id = row.getAttribute("data-challenge-fingerprint-row") ?? "?";
        for (const [selector, property] of [
          [".challenge-fingerprint__mark--a", "--period-a-position"],
          [".challenge-fingerprint__mark--b", "--period-b-position"],
        ] as const) {
          const mark = row.querySelector(selector);
          const percent = Number.parseFloat(style.getPropertyValue(property));
          if (mark === null || Number.isNaN(percent)) {
            continue;
          }
          const rect = mark.getBoundingClientRect();
          const expected = box.left + (percent / 100) * box.width;
          const actual = rect.left + rect.width / 2;
          if (Math.abs(expected - actual) > 1) {
            wrong.push(`${id} ${property}`);
          }
        }
      }
      return wrong;
    });

    expect(drift, `a mark centre drifted from its percentile at ${width}`).toEqual([]);
  }
});

test("the challenge panel matches its responsive baselines", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Baselines are captured once per platform");

  // The reveal state is the richest: identity, five result rows, the A/B plot,
  // family chips and every mandatory caveat. A regression in any of them shows
  // here.
  for (const width of WIDTHS) {
    await openChallenge(page, "reveal", width);
    await expect(page.locator(PANEL)).toHaveScreenshot(`challenge-reveal-${width}.png`, {
      caret: "hide",
    });
  }
});
