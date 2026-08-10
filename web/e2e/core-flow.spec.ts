import { expect, test } from "@playwright/test";

import {
  INTERACTION_BUDGET_MS,
  MESSI_PROFILE_KEY,
  expectNoPageOverflow,
  measureNextInteraction,
  waitForStablePage,
} from "./helpers";

test("complete selected-player flow works by keyboard at desktop and 360 px", async ({ page }, testInfo) => {
  await page.goto("/lab/");
  await waitForStablePage(page);

  const search = page.getByRole("searchbox", { name: "Search players" });
  const skipLink = page.getByRole("link", { name: "Skip to content" });
  await page.keyboard.press("Tab");
  await expect(skipLink).toBeFocused();
  await expect(skipLink).toBeInViewport();
  await expect(skipLink).toHaveCSS("outline-width", "3px");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "ScoutLens home" })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Overview" })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Fingerprint Lab" })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "How it works" })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(search).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("combobox", { name: "Role" })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("combobox", { name: "Competition" })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("combobox", { name: "Team context" })).toBeFocused();

  await search.focus();
  await search.fill("L. Messi");
  const result = page.getByRole("button", { name: /L\. Messi/ }).first();
  await result.focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(new RegExp(`player=${MESSI_PROFILE_KEY}`));
  await expect(page.locator(".selected-profile__header h2")).toHaveText("L. Messi");

  await page.reload();
  await waitForStablePage(page);
  await expect(page.locator(".selected-profile__header h2")).toHaveText("L. Messi");
  await expect(page.locator("[data-retrieval-scope]")).toHaveCount(3);
  await expect(page.locator("[data-neighbor-rank]")).toHaveCount(5);
  await expect(page.getByText("Stability pending", { exact: false }).first()).not.toBeVisible();
  await expect(page.getByText("Available from 500 valid resamples", { exact: false }).first()).toBeVisible();

  const globalToggle = page.getByRole("radio", { name: "Global" });
  const interactionDuration = await measureNextInteraction(page, async () => {
    await globalToggle.focus();
    await page.keyboard.press("Space");
  });
  expect(interactionDuration).toBeLessThanOrEqual(INTERACTION_BUDGET_MS);
  console.log(`[${testInfo.project.name}] synthetic interaction duration: ${interactionDuration} ms`);
  await expect(globalToggle).toBeChecked();
  await page.keyboard.press("ArrowLeft");
  await expect(page.getByRole("radio", { name: "Within role" })).toBeChecked();
  await expect(page.locator(".selected-profile__header h2")).toHaveText("L. Messi");
  await page.keyboard.press("ArrowRight");
  await expect(globalToggle).toBeChecked();

  const neighborTrigger = page.locator('[data-neighbor-rank="1"] button');
  const selectedUrl = page.url();
  await neighborTrigger.focus();
  await page.keyboard.press("Enter");
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(page.locator("[data-feature-contribution]")).toHaveCount(32);
  await expect(page.locator("[data-family-contribution]")).toHaveCount(8);
  const closeComparison = page.getByRole("button", { name: "Close comparison" });
  const contributionTable = page.getByRole("region", {
    name: "Scrollable feature contribution table",
  });
  const scienceLink = page.getByRole("link", {
    name: "Inspect the retrieval method and aggregate evidence →",
  });
  await expect(closeComparison).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(contributionTable).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(scienceLink).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(closeComparison).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(scienceLink).toBeFocused();
  expect(page.url()).toBe(selectedUrl);
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(neighborTrigger).toBeFocused();
  expect(page.url()).toBe(selectedUrl);

  await search.fill("profile-that-does-not-exist");
  await expect(page.getByRole("status")).toContainText("0 profiles found");
  await expect(page.getByRole("heading", { name: "No profiles match all active filters" })).toBeVisible();
  await page.getByRole("button", { name: "Reset all filters" }).click();
  await expect(page.getByRole("status")).toContainText("1,257 profiles found");
  await expectNoPageOverflow(page);
});

test("selection updates the URL without adding a horizontal page scrollbar", async ({ page }) => {
  await page.goto("/lab/");
  await page.getByRole("searchbox", { name: "Search players" }).fill("L. Messi");
  await page.getByRole("button", { name: /L\. Messi/ }).first().click();
  await expect(page).toHaveURL(new RegExp(`player=${MESSI_PROFILE_KEY}`));
  await expectNoPageOverflow(page);
});
