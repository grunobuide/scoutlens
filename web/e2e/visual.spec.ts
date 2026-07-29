import { expect, test } from "@playwright/test";

import { waitForStablePage } from "./helpers";

test("retrieval and neighbor surface matches the responsive baseline", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/lab/");
  await waitForStablePage(page);
  await page.locator(".retrieval-replay").scrollIntoViewIfNeeded();
  await expect(page).toHaveScreenshot("retrieval-neighbors.png", {
    caret: "hide",
    fullPage: false,
  });
  await page.locator(".statistical-neighbors").scrollIntoViewIfNeeded();
  await expect(page).toHaveScreenshot("neighbor-cards.png", {
    caret: "hide",
    fullPage: false,
  });
});
