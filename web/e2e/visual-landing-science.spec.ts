import { expect, test } from "@playwright/test";

import { waitForStablePage } from "./helpers";

// scoutlens-uze.4 acceptance criterion 5: new mobile and desktop screenshots
// cover landing and /science. Baselines are per platform
// ({projectName}-{platform}); the snapshot policy in
// docs/frontend-agent-contract.md section 5 governs updates.
//
// One screenshot per test (`scoutlens-uze.22`). These were pairs, and `expect`
// throws, so a failing first screenshot meant the second was never compared.
// That is not hypothetical here: `landing-claims` was recorded as passing at a
// zero tolerance when in fact its test had aborted at `landing-hero` and it had
// never run. Measured once the first baseline was current, it differed by 6,474
// pixels.

test("landing hero matches the responsive baseline", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await waitForStablePage(page);
  await expect(page).toHaveScreenshot("landing-hero.png", {
    caret: "hide",
    fullPage: false,
  });
});

test("landing claims matrix matches the responsive baseline", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await waitForStablePage(page);
  await page.locator(".claims-matrix").scrollIntoViewIfNeeded();
  await expect(page).toHaveScreenshot("landing-claims.png", {
    caret: "hide",
    fullPage: false,
  });
});

test("science frozen-question block matches the responsive baseline", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/science/");
  await waitForStablePage(page);
  await expect(page).toHaveScreenshot("science-stage-01.png", {
    caret: "hide",
    fullPage: false,
  });
});

test("science experiments match the responsive baseline", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/science/");
  await waitForStablePage(page);
  await page.locator(".research-stage").first().scrollIntoViewIfNeeded();
  await expect(page).toHaveScreenshot("science-experiments.png", {
    caret: "hide",
    fullPage: false,
  });
});

// `scoutlens-9a3.23` (9a3.4 AC7): /science had baselines at 1280 and 360 only.
// The same top-of-page framing at the two remaining frozen widths, taken from
// the desktop project as the challenge panel's per-width baselines are, so
// there is one file per width and platform rather than a new project.
for (const width of [320, 768] as const) {
  test(`science frozen-question block matches the ${width} px baseline`, async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "desktop", "Per-width baselines are captured once per platform");
    await page.setViewportSize({ width, height: width === 320 ? 800 : 900 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/science/");
    await waitForStablePage(page);
    await expect(page).toHaveScreenshot(`science-stage-01-${width}.png`, {
      caret: "hide",
      fullPage: false,
    });
  });
}
