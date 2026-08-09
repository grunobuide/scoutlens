import { expect, test } from "@playwright/test";

import { waitForStablePage } from "./helpers";

// scoutlens-uze.4 acceptance criterion 5: new mobile and desktop screenshots
// cover landing and /science. Baselines are per platform
// ({projectName}-{platform}); the snapshot policy in
// docs/frontend-agent-contract.md section 5 governs updates.

test("landing hero and evidence surfaces match the responsive baseline", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await waitForStablePage(page);
  await expect(page).toHaveScreenshot("landing-hero.png", {
    caret: "hide",
    fullPage: false,
  });

  await page.locator(".claims-matrix").scrollIntoViewIfNeeded();
  await expect(page).toHaveScreenshot("landing-claims.png", {
    caret: "hide",
    fullPage: false,
  });
});

test("science experiments and frozen-question block match the responsive baseline", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/science/");
  await waitForStablePage(page);
  await expect(page).toHaveScreenshot("science-stage-01.png", {
    caret: "hide",
    fullPage: false,
  });

  await page.locator(".research-stage").first().scrollIntoViewIfNeeded();
  await expect(page).toHaveScreenshot("science-experiments.png", {
    caret: "hide",
    fullPage: false,
  });
});
