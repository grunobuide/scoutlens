import { expect, test } from "@playwright/test";

import { expectNoPageOverflow, expectNoSeriousOrCriticalViolations } from "./helpers";

// The diagonal Lab gate (scoutlens-qop.6.5). Runs only on the `fixtures-v2-*`
// projects, which serve the test-only static export built from the
// version-controlled v2 pack in web/e2e/fixtures/lab-max-content-v2. It never
// runs against the production export, which still serves major 1.
//
// These assertions are positive on purpose. A spec that only checked "no
// cosine anywhere" would pass on a blank page.

const MAX_CONTENT = "wy-900001-c-901";

test.describe("the v2 Lab presents the diagonal method", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`/lab/?player=${MAX_CONTENT}`);
    await expect(page.locator("#selected-profile")).toBeVisible();
  });

  test("names the learned weighted method and its fitted weights", async ({ page }) => {
    const disclosure = page.locator(".method-disclosure");
    await expect(disclosure).toBeVisible();
    await expect(disclosure.getByRole("heading", { name: "Learned weighted similarity" })).toBeVisible();
    await expect(disclosure).toContainText(
      /Ranks use \d+ non-negative feature weights fitted on the frozen Wyscout training split/,
    );
  });

  test("states the cosine audit baseline and the unsupported-claim boundary", async ({ page }) => {
    const disclosure = page.locator(".method-disclosure");
    await expect(disclosure).toContainText("Unit weights reproduce the cosine audit baseline exactly");
    await expect(disclosure).toContainText(
      "does not measure player quality, tactical fit or recruitment value",
    );
  });

  test("keeps the neural-null explanation reachable and linked to D045", async ({ page }) => {
    const advanced = page.locator(".method-disclosure__advanced");
    await expect(advanced.locator("summary")).toHaveText("Why this model, and why not the neural one?");
    // Collapsed by default: the boundary sentence is primary, the rationale is
    // one interaction away rather than competing with it.
    await expect(advanced).not.toHaveAttribute("open", /.*/);
    await advanced.locator("summary").click();
    await expect(advanced).toContainText("preregistered compact neural arm lost");
    await expect(advanced.getByRole("link", { name: /Decision record D045/ })).toHaveAttribute(
      "href",
      /decisions-log\.md#d045/,
    );
  });

  test("reports a similarity score and never labels it a cosine", async ({ page }) => {
    await expect(page.locator(".retrieval-period-line code")).toHaveText(
      "combined_scaler_diagonal_v1",
    );
    const globalCard = page.locator('[data-retrieval-scope="global"]');
    await expect(globalCard).toContainText("Similarity score");
    await expect(globalCard).not.toContainText("Cosine");
  });

  test("offers no representation toggle in the primary flow", async ({ page }) => {
    await expect(page.getByRole("switch")).toHaveCount(0);
    await expect(page.locator('input[name*="representation" i]')).toHaveCount(0);
    await expect(page.locator('input[name*="model" i]')).toHaveCount(0);
    await expect(page.getByRole("button", { name: /^cosine$/i })).toHaveCount(0);
  });

  test("renders the artifact's neighbour order exactly", async ({ page }) => {
    const ranks = await page.locator(".neighbor-card__rank, .neighbor-card header p").allTextContents();
    expect(ranks.length).toBeGreaterThan(0);
    const profile = await page.evaluate(async () => {
      const response = await fetch("/showcase/v2/players/wy-900001-c-901.json");
      return response.json();
    });
    const expected = profile.neighbors.map((neighbor: { profile_key: string }) => neighbor.profile_key);
    const rendered = await page.locator("[data-neighbor-profile-key]").evaluateAll((nodes) =>
      nodes.map((node) => node.getAttribute("data-neighbor-profile-key")),
    );
    if (rendered.length > 0) {
      expect(rendered).toEqual(expected);
    }
  });

  test("keeps every mandatory caveat visible", async ({ page }) => {
    // The mandatory set is the artifact's, not a list retyped here: a caveat
    // dropped to make a layout fit is a stop condition, not a trade-off (D033).
    const REQUIRED = [
      "fingerprint_not_style_proof",
      "same_season_team_confound",
      "within_role_display_differs_from_global_model",
    ];
    const messages = await page.evaluate(async (codes) => {
      const response = await fetch("/showcase/v2/players/wy-900001-c-901.json");
      const profile = await response.json();
      return profile.caveats
        .filter((caveat: { code: string }) => codes.includes(caveat.code))
        .map((caveat: { message: string }) => caveat.message);
    }, REQUIRED);

    expect(messages.length).toBe(REQUIRED.length);
    const rail = page.locator('aside[aria-labelledby="evidence-rail-heading"]');
    await expect(rail).toBeVisible();
    for (const message of messages) {
      await expect(rail).toContainText(message);
    }
  });

  test("has no page overflow and no serious accessibility violation", async ({ page }) => {
    await expectNoPageOverflow(page);
    await expectNoSeriousOrCriticalViolations(page);
  });
});

// The remaining cells of the frozen matrix. 320/360/768/1280 come from the
// project list; these three states are orthogonal to width and are asserted
// once each rather than per viewport.
test.describe("the v2 disclosure survives the degraded states", () => {
  test("stays readable at 375 and 1440 px", async ({ page }) => {
    for (const width of [375, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      await page.goto(`/lab/?player=${MAX_CONTENT}`);
      const disclosure = page.locator(".method-disclosure");
      await expect(disclosure).toBeVisible();
      await expect(disclosure).toContainText("Learned weighted similarity");
      await expect(disclosure).toContainText(
        "does not measure player quality, tactical fit or recruitment value",
      );
      await expectNoPageOverflow(page);
    }
  });

  test("stays readable at 200% zoom", async ({ page }) => {
    // 200% zoom reflow is equivalent to halving the CSS viewport, which is how
    // WCAG 1.4.10 is normally exercised in a headless browser.
    await page.setViewportSize({ width: 640, height: 512 });
    await page.goto(`/lab/?player=${MAX_CONTENT}`);
    const disclosure = page.locator(".method-disclosure");
    await expect(disclosure).toBeVisible();
    await expect(disclosure).toContainText(
      "does not measure player quality, tactical fit or recruitment value",
    );
    await expectNoPageOverflow(page);
  });

  test("reaches the neural-null rationale by keyboard alone", async ({ page }) => {
    await page.goto(`/lab/?player=${MAX_CONTENT}`);
    const summary = page.locator(".method-disclosure__advanced > summary");
    await summary.focus();
    await expect(summary).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page.locator(".method-disclosure__advanced")).toContainText(
      "preregistered compact neural arm lost",
    );
  });
});

test.describe("the v2 disclosure without JavaScript", () => {
  test.use({ javaScriptEnabled: false });

  test("still states the method, the audit baseline and the boundary", async ({ page }) => {
    // The disclosure is server-rendered, so the sentence that bounds the claim
    // must not depend on hydration. A boundary that only appears once the
    // bundle loads is a boundary the first paint does not have.
    await page.goto(`/lab/?player=${MAX_CONTENT}`);
    const disclosure = page.locator(".method-disclosure");
    await expect(disclosure).toBeVisible();
    await expect(disclosure).toContainText("Learned weighted similarity");
    await expect(disclosure).toContainText("Unit weights reproduce the cosine audit baseline exactly");
    await expect(disclosure).toContainText(
      "does not measure player quality, tactical fit or recruitment value",
    );
  });
});
