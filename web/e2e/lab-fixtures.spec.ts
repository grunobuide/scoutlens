import { expect, test, type Locator, type Page } from "@playwright/test";

import { expectNoPageOverflow } from "./helpers";

// Delegated Lab fixture gate (scoutlens-uze.7). This spec runs only on the
// `fixtures-*` projects, which point Playwright at the test-only static export
// (web/out-fixtures/lab-max-content) whose showcase pack is built from the
// deterministic, version-controlled pack in web/e2e/fixtures/lab-max-content.
// It never runs against the production `web/out` export.

export const FIXTURE_IDS = {
  maxContent: "wy-900001-c-901",
  uncertaintyAvailable: "wy-900002-c-902",
  uncertaintyInsufficient: "wy-900003-c-903",
} as const;

// Published maximums, measured 2026-08-04 (scoutlens-uze.7 description).
const PUBLISHED_MAX_DISPLAY_NAME = 22;
const PUBLISHED_MAX_TEAM_JOIN = 35;
const PUBLISHED_MAX_COMPETITION = 22;

async function openProfile(page: Page, profileKey: string): Promise<void> {
  await page.goto(`/lab/?player=${profileKey}`);
  await expect(page.locator("#selected-profile")).toBeVisible();
  await expect(page.locator("#selected-profile .selected-profile__header h2")).toHaveText(
    profileKey === FIXTURE_IDS.maxContent
      ? "K. Théophile Catherine Saint-Michel"
      : profileKey === FIXTURE_IDS.uncertaintyAvailable
        ? "F. Fixture Avail"
        : "F. Fixture Insuff",
  );
  await expect(page.locator(".lab-state[role='alert']")).toHaveCount(0);
}

async function openFirstNeighborDrawer(page: Page): Promise<Locator> {
  await page.locator(".neighbor-card button").first().click();
  const dialog = page.locator("dialog[open]");
  await expect(dialog).toBeVisible();
  return dialog;
}

test("featured max-content identity exceeds every published maximum without overflow", async ({
  page,
}) => {
  await page.goto("/lab/");
  await expect(page.locator("#selected-profile")).toBeVisible();
  await expect(page.locator(".lab-state[role='alert']")).toHaveCount(0);

  const header = page.locator("#selected-profile .selected-profile__header h2");
  await expect(header).toHaveText("K. Théophile Catherine Saint-Michel");
  const displayLength = (await header.textContent())?.length ?? 0;
  expect(displayLength).toBeGreaterThan(PUBLISHED_MAX_DISPLAY_NAME + 10);

  const identityLine = await page.locator(".selected-profile__identity").textContent();
  expect(identityLine).toContain("Spanish first division championship");
  expect(identityLine?.length ?? 0).toBeGreaterThan(PUBLISHED_MAX_COMPETITION + 10);

  // The four-team period B stretches the row team join beyond the published max.
  await page.getByRole("searchbox", { name: "Search players" }).fill("Théophile");
  const result = page.locator(".profile-results li", { hasText: "K. Théophile Catherine Saint-Michel" });
  await expect(result).toHaveCount(1);
  const rowText = await result.textContent();
  const teamJoin = rowText ?? "";
  expect(teamJoin).toContain("Athletic de Bilbao");
  expect(teamJoin).toContain("Olympique Marseille");
  expect(teamJoin.length).toBeGreaterThan(PUBLISHED_MAX_TEAM_JOIN + 30);

  await expectNoPageOverflow(page);

  // The stretched selector row must be contained by the viewport at this width.
  const containment = await result.evaluate((element) => {
    const box = element.getBoundingClientRect();
    return { left: box.left, right: box.right, clientWidth: document.documentElement.clientWidth };
  });
  expect(containment.left).toBeGreaterThanOrEqual(-1);
  expect(containment.right).toBeLessThanOrEqual(containment.clientWidth + 1);
});

test("longest period-A team count exceeds the published catalogue maximum", async ({ page }) => {
  const profile = await page.request.get(`/showcase/v1/players/${FIXTURE_IDS.maxContent}.json`);
  expect(profile.status()).toBe(200);
  const body = (await profile.json()) as {
    identity: { period_contexts: { a: { teams: unknown[] }; b: { teams: unknown[] } } };
  };
  expect(body.identity.period_contexts.b.teams.length).toBeGreaterThan(2);
});

test("uncertainty 'available' renders retrieval, baseline and neighbor stability text", async ({
  page,
}) => {
  await openProfile(page, FIXTURE_IDS.uncertaintyAvailable);

  const stability = page.locator(".retrieval-outcome__stability");
  await expect(stability).toHaveCount(3);
  await expect(stability.first()).toContainText("Available from 500 valid resamples");
  // Fractional rank statistics must render at one decimal place, never as the
  // raw binary expansion — the fixture's upper bound is 111.09999999999991
  // (scoutlens-jtt.16, D046).
  await expect(stability.first()).toContainText("median rank 9.5");
  await expect(stability.first()).toContainText("rank interval 6.4–111.1");
  await expect(stability.first()).not.toContainText("111.09999999999991");

  await expect(page.locator(".neighbor-card__stability").first()).toContainText("available");
  await expect(page.locator(".neighbor-card__stability").first()).not.toContainText("91.57499999999993");

  const dialog = await openFirstNeighborDrawer(page);
  await expect(dialog).toContainText("Available from 500 valid resamples");
  await expect(dialog).toContainText("median rank 6.5");
  await expect(dialog).toContainText("rank interval 3.4–91.6");
  await expect(dialog).not.toContainText("91.57499999999993");
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();

  await expectNoPageOverflow(page);
});

test("uncertainty 'insufficient' renders retrieval and neighbor stability text", async ({ page }) => {
  await openProfile(page, FIXTURE_IDS.uncertaintyInsufficient);

  const stability = page.locator(".retrieval-outcome__stability");
  await expect(stability.first()).toContainText("Insufficient resamples");

  await expect(page.locator(".neighbor-card__stability").first()).toContainText("insufficient");

  const dialog = await openFirstNeighborDrawer(page);
  await expect(dialog).toContainText("Insufficient resamples");
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();

  await expectNoPageOverflow(page);
});

test("same fixture id renders identical DOM across two independent loads", async ({ page }) => {
  const snapshot = async () => {
    await openProfile(page, FIXTURE_IDS.uncertaintyAvailable);
    return page.evaluate(() => {
      const region = document.querySelector("#selected-profile") as HTMLElement | null;
      if (region === null) {
        throw new Error("selected profile region missing");
      }
      return region.outerHTML;
    });
  };

  const first = await snapshot();
  await page.goto("/lab/");
  const second = await snapshot();
  expect(second).toBe(first);
});
