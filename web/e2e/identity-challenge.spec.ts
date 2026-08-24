/**
 * The identity challenge transitions, URL semantics and history
 * (`scoutlens-9a3.6.3`).
 *
 * These run here rather than in vitest because the project's unit environment
 * is `node` with no DOM, and what §4 specifies is a real history stack: pushed
 * entries, back and forward, and a deep link that restores a state without
 * stepping through its predecessors. Simulating that with jsdom would add a
 * dependency to approximate what this suite already does natively.
 */

import { expect, test } from "@playwright/test";

import { waitForStablePage } from "./helpers";

const PANEL = '[data-challenge-panel="orientation"]';
const STATES = "[data-challenge-state]";

async function gotoLab(page: import("@playwright/test").Page, search = ""): Promise<void> {
  await page.goto(`/lab/${search}`);
  await waitForStablePage(page);
}

test("the challenge walks orientation to evidence and back", async ({ page }) => {
  await gotoLab(page);

  await expect(page.locator(STATES)).toHaveAttribute("data-challenge-state", "orientation");
  await expect(page.getByRole("button", { name: "See the fingerprint" })).toBeVisible();
  // §3.1 hides identity until the reveal.
  await expect(page.locator("[data-challenge-identity]")).toHaveCount(0);

  await page.getByRole("button", { name: "See the fingerprint" }).click();
  await expect(page.locator(STATES)).toHaveAttribute("data-challenge-state", "query");
  await expect(page).toHaveURL(/challenge=query/);
  // §3.2 shows period A only; the period-B fingerprint is hidden.
  await expect(page.locator('[data-challenge-fingerprint="a"]')).toBeVisible();
  await expect(page.locator('[data-challenge-fingerprint="ab"]')).toHaveCount(0);
  await expect(page.locator("[data-challenge-identity]")).toHaveCount(0);

  await page.getByRole("button", { name: "Reveal the result" }).click();
  await expect(page.locator(STATES)).toHaveAttribute("data-challenge-state", "reveal");
  await expect(page).toHaveURL(/challenge=reveal/);
  await expect(page.locator("[data-challenge-identity]")).toBeVisible();
  await expect(page.locator('[data-challenge-fingerprint="ab"]')).toBeVisible();

  await page.getByRole("button", { name: "See the evidence" }).click();
  await expect(page.locator(STATES)).toHaveAttribute("data-challenge-state", "evidence");
  await expect(page).toHaveURL(/challenge=evidence/);
  await expect(page.locator("[data-challenge-contributions] li")).toHaveCount(5);

  await page.getByRole("button", { name: "Back to result" }).click();
  await expect(page.locator(STATES)).toHaveAttribute("data-challenge-state", "reveal");
});

test("each transition pushes a history entry that back and forward traverse", async ({ page }) => {
  await gotoLab(page);
  await page.getByRole("button", { name: "See the fingerprint" }).click();
  await page.getByRole("button", { name: "Reveal the result" }).click();
  await page.getByRole("button", { name: "See the evidence" }).click();

  // §4: "each state push a URL entry ... Back/forward navigates between
  // challenge states." Back must move through the states, not leave the page.
  await page.goBack();
  await expect(page.locator(STATES)).toHaveAttribute("data-challenge-state", "reveal");
  await page.goBack();
  await expect(page.locator(STATES)).toHaveAttribute("data-challenge-state", "query");
  await page.goBack();
  await expect(page.locator(STATES)).toHaveAttribute("data-challenge-state", "orientation");

  await page.goForward();
  await expect(page.locator(STATES)).toHaveAttribute("data-challenge-state", "query");
  await page.goForward();
  await expect(page.locator(STATES)).toHaveAttribute("data-challenge-state", "reveal");
});

test("a deep link restores its state without stepping through the ramps", async ({ page }) => {
  // §4: "The orientation and query states are entry ramps, not gates."
  await gotoLab(page, "?challenge=reveal");
  await expect(page.locator(STATES)).toHaveAttribute("data-challenge-state", "reveal");
  await expect(page.locator("[data-challenge-identity]")).toBeVisible();

  await page.reload();
  await waitForStablePage(page);
  await expect(page.locator(STATES)).toHaveAttribute("data-challenge-state", "reveal");
});

test("an unrecognised challenge state recovers to orientation", async ({ page }) => {
  // §8: invalid URL state returns to the documented recovery state without
  // changing the scientific query.
  await gotoLab(page, "?challenge=not-a-state");
  await expect(page.locator(STATES)).toHaveAttribute("data-challenge-state", "orientation");
  await expect(page.getByRole("button", { name: "See the fingerprint" })).toBeVisible();
});

test("the challenge is operable by keyboard, and Escape returns to orientation", async ({
  page,
}) => {
  await gotoLab(page);

  const cta = page.getByRole("button", { name: "See the fingerprint" });
  await cta.focus();
  await page.keyboard.press("Enter");
  await expect(page.locator(STATES)).toHaveAttribute("data-challenge-state", "query");

  // §6.2: entering a state moves focus to the state's heading.
  await expect(page.locator(".challenge-panel__heading")).toBeFocused();

  await page.keyboard.press("Escape");
  await expect(page.locator(STATES)).toHaveAttribute("data-challenge-state", "orientation");
  await expect(page.locator(".challenge-panel__heading")).toBeFocused();
});

test("the reveal states the method, provenance and the weighted label", async ({ page }) => {
  await gotoLab(page, "?challenge=reveal");

  await expect(page.locator("[data-challenge-method]")).toHaveText("combined_scaler_diagonal_v1");
  await expect(page.locator("[data-challenge-representation]")).toContainText("rep-");
  // §3.3, D047: the published score is weighted and must never be labelled a
  // plain cosine.
  // Scoped to the panel: the Lab's method-disclosure heading below carries the
  // same frozen label, and an unscoped query matches both.
  await expect(page.locator(PANEL).getByText("Learned weighted similarity")).toBeVisible();
  await expect(page.locator(PANEL)).not.toContainText("Cosine similarity");
});

test("the resampling interval is rounded for display, not interpolated raw", async ({ page }) => {
  await gotoLab(page, "?challenge=reveal");
  const interval = page.locator("[data-challenge-interval]");
  await expect(interval).toBeVisible();

  // D046: resampled rank bounds are legitimately fractional, and interpolating
  // one straight into a template prints its full binary expansion. The
  // published upper bound rendered as "43.524999999999998" until this was
  // routed through formatRank - caught by looking at a baseline image, not by a
  // failing assertion, which is why the assertion now exists.
  const text = (await interval.textContent()) ?? "";
  expect(text).not.toMatch(/\d\.\d{3,}/);
  expect(text).toMatch(/95% resampling interval/);
});

test("every mandatory caveat stays visible in the result states", async ({ page }) => {
  for (const state of ["reveal", "evidence"]) {
    await gotoLab(page, `?challenge=${state}`);
    for (const code of [
      "fingerprint_not_style_proof",
      "same_season_team_confound",
      "similarity_not_recruitment",
      "within_role_display_differs_from_global_model",
    ]) {
      await expect(page.locator(`[data-caveat="${code}"]`).first()).toBeVisible();
    }
  }
});

test("Explore every fingerprint reaches the Lab explorer", async ({ page }) => {
  // §5 makes this the one CTA that is a link, scrolling rather than navigating.
  await gotoLab(page, "?challenge=reveal");
  const link = page.getByRole("link", { name: "Explore every fingerprint" });
  await expect(link).toHaveAttribute("href", "#lab-explorer");
  await link.click();
  await expect(page.locator("#lab-explorer")).toBeInViewport();
});
