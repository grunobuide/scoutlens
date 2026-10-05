/**
 * Value-level assertions on what the Lab actually renders (`scoutlens-uze.12`).
 *
 * **Why this file exists.** The visual baselines were asserting v1 content for
 * six days after the v2 repin and the gate stayed green, because
 * `maxDiffPixelRatio` is 3% and the changed text is a small fraction of a
 * mostly-white card. One committed reference image simultaneously asserted
 * three superseded decisions as correct:
 *
 * | in the baseline | should be | decision |
 * |---|---|---|
 * | `combined_scaler_cosine_v1` | `combined_scaler_diagonal_v1` | `D049` |
 * | "Cosine" as the score label | "Similarity score" | `D047` |
 * | `rank interval 1–111.09999999999991` | `1–111.1` | `D046` |
 *
 * A screenshot answers "do these pixels match?". These assertions answer "does
 * the page say the right thing?", which is the question the decisions are
 * about. They would have failed on the day each rename landed, and they cost
 * milliseconds.
 *
 * This is a complement to the baselines, not a replacement: images still catch
 * layout, spacing and clipping that no text assertion sees.
 */

import { expect, test, type Page } from "@playwright/test";

import { waitForStablePage } from "./helpers";

const PROFILE = "/lab/?player=wy-8287-c-795";

async function openLab(page: Page): Promise<void> {
  await page.goto(PROFILE);
  await waitForStablePage(page);
}

test("the retrieval replay names the diagonal method, never the cosine one", async ({ page }) => {
  await openLab(page);

  // D049 renamed the published method. A page still naming the v1 method is
  // describing a different experiment than the one that produced the numbers
  // beside it.
  const replay = page.locator(".retrieval-replay");
  await expect(replay).toContainText("combined_scaler_diagonal_v1");
  await expect(replay).not.toContainText("combined_scaler_cosine_v1");
});

test("no score anywhere is labelled a cosine while serving v2", async ({ page }) => {
  await openLab(page);

  // D047: the published score is weighted, and a weighted metric must not carry
  // a name claiming plain cosine.
  //
  // Deliberately NOT scoped to one component. The defect this assertion exists
  // for (`scoutlens-uze.13`) was that the retrieval cards read a major-aware
  // label while the neighbour card and the comparison drawer hard-coded
  // "Stored cosine" - so an assertion scoped to the retrieval surface would
  // have passed while the page still said cosine two sections below.
  //
  // The advanced audit disclosure is excluded because there the unweighted
  // `contribution` genuinely is the cosine baseline view, and saying so is
  // accurate.
  const cosineLabels = await page.evaluate(() =>
    [...document.querySelectorAll("main dt, main th")]
      .filter((element) => element.closest("details") === null)
      .map((element) => (element.textContent ?? "").trim())
      .filter((text) => /cosine/i.test(text)),
  );
  expect(cosineLabels, "a score is still labelled with cosine").toEqual([]);
});

test("no rendered rank statistic prints a raw binary expansion", async ({ page }) => {
  await openLab(page);

  // D046: resampled rank bounds are legitimately fractional, and interpolating
  // one straight into a template prints its full binary expansion. One decimal
  // place is the display precision, so anything with three or more decimals in
  // a rank context is unrounded.
  const text = (await page.locator("main").innerText()).replace(/\s+/g, " ");
  const raw = text.match(/rank interval \d+(?:\.\d+)?[–-]\d+\.\d{3,}/gi) ?? [];
  expect(raw, "an unrounded rank bound is rendered").toEqual([]);

  const medians = text.match(/median rank \d+\.\d{3,}/gi) ?? [];
  expect(medians, "an unrounded median rank is rendered").toEqual([]);
});

test("the served dataset is the major the pin names", async ({ page }) => {
  await openLab(page);

  // The staleness this file exists for began at a major repin. Asserting the
  // served dataset version here means a future repin that leaves a surface
  // behind fails on a sentence rather than on a pixel ratio.
  const pin = page.locator("[data-vintage-badge] code");
  await expect(pin).toContainText("-v2-");
});

/** Neighbor 1's evidence drawer, open. */
async function openFirstComparison(page: Page) {
  await openLab(page);
  await page
    .locator('[data-neighbor-rank="1"]')
    .getByRole("button", { name: "Open evidence comparison" })
    .click();
  const drawer = page.getByRole("dialog");
  await expect(drawer).toBeVisible();
  return drawer;
}

const sum = (values: ReadonlyArray<string>): number =>
  values.reduce((total, value) => total + Number(value.trim()), 0);

test("the comparison drawer never calls the v2 score a cosine", async ({ page }) => {
  // `scoutlens-uze.25`. The assertion above reads `dt` and `th` with the drawer
  // CLOSED - a <dialog> rendered on demand is not in the DOM it inspects - so
  // the drawer's heading, summary and reconstruction lines kept saying "cosine"
  // about the weighted score for as long as that assertion was green.
  const drawer = await openFirstComparison(page);
  expect(await drawer.innerText(), "the drawer names the weighted score a cosine").not.toMatch(/cosine/i);
});

test("a neighbor's contributions reconstruct the score printed beside them", async ({ page }) => {
  // D047's normative rule, read off the page: evidence that does not
  // reconstruct the number it explains is not evidence. In v2 the published
  // `contribution` is the unweighted cosine audit view and
  // `weighted_contribution` is each feature's share of `similarity_score`. A
  // surface that renders the first beside a sum of the second shows eight rows
  // that do not add up to the total printed under them (`scoutlens-uze.25`).
  const drawer = await openFirstComparison(page);
  const score = Number((await drawer.locator(".neighbor-drawer__score dd").first().innerText()).trim());

  const families = await drawer.locator("[data-family-contribution] strong").allInnerTexts();
  expect(families).toHaveLength(8);
  // Eight values rounded to 4 dp, plus the rounded score: at most 9 half-units.
  expect(Math.abs(sum(families) - score), "family rows do not add up to the score").toBeLessThanOrEqual(0.00045);

  const features = await drawer.locator("[data-feature-contribution] td:nth-of-type(3)").allInnerTexts();
  expect(features).toHaveLength(32);
  expect(Math.abs(sum(features) - score), "feature rows do not add up to the score").toBeLessThanOrEqual(0.00165);

  // The card and the drawer describe the same neighbor; a family's value may
  // not change between them.
  const inDrawer = new Map<string, string>();
  for (const row of await drawer.locator("[data-family-contribution]").all()) {
    inDrawer.set((await row.locator("span").innerText()).trim(), (await row.locator("strong").innerText()).trim());
  }
  const card = page.locator('[data-neighbor-rank="1"] .neighbor-card__evidence li');
  expect(await card.count()).toBeGreaterThan(0);
  for (const row of await card.all()) {
    const family = (await row.locator("span").innerText()).trim();
    expect((await row.locator("strong").innerText()).trim(), `${family} differs between card and drawer`).toBe(
      inDrawer.get(family),
    );
  }
});
