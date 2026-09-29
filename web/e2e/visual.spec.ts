import { expect, test } from "@playwright/test";

import { waitForStablePage } from "./helpers";

/**
 * One screenshot per test (`scoutlens-uze.22`).
 *
 * These two lived in a single test. `expect` throws, so a failing
 * `retrieval-neighbors` meant `neighbor-cards` was never compared at all — and
 * the blind spot appeared exactly when someone was already debugging the first
 * one. It cost a real miss: `landing-claims` in the sibling spec was recorded as
 * passing when its test had aborted before reaching it, and it turned out to
 * differ by 6,474 pixels.
 *
 * The scroll sequence is preserved rather than simplified. `scrollIntoViewIfNeeded`
 * scrolls the *minimum* distance, so where an element lands depends on where the
 * viewport already was. Jumping straight to `.statistical-neighbors` from the top
 * would frame it differently and silently invalidate the baseline.
 */

test("retrieval surface matches the responsive baseline", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/lab/");
  await waitForStablePage(page);
  await page.locator(".retrieval-replay").scrollIntoViewIfNeeded();
  await expect(page).toHaveScreenshot("retrieval-neighbors.png", {
    caret: "hide",
    fullPage: false,
  });
});

test("neighbor surface matches the responsive baseline", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/lab/");
  await waitForStablePage(page);
  // Same two-step scroll as before the split; see the note above.
  await page.locator(".retrieval-replay").scrollIntoViewIfNeeded();
  await page.locator(".statistical-neighbors").scrollIntoViewIfNeeded();
  await expect(page).toHaveScreenshot("neighbor-cards.png", {
    caret: "hide",
    fullPage: false,
  });
});
