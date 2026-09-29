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
