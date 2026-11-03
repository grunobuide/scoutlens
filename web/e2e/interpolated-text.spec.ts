import { expect, test, type Page } from "@playwright/test";

import { SHOWCASE_BASE, waitForStablePage } from "./helpers";

/**
 * Interpolated artifact values must not fuse with the words around them
 * (`scoutlens-9a3.16`).
 *
 * The sentinel: `/science/` rendered "…event data from the 2017/18season,
 * split every player's play time…". The source looked right —
 *
 *     We take public football event data from the {story.manifest.source.season} season,
 *
 * there is plainly a space before `season`. JSX drops it: a text node that
 * follows an expression and ends its line is trimmed. Reading the source does
 * not reveal the defect. **Only the render does**, which is why this gate
 * probes the rendered page and a source-reading test would have passed on it.
 *
 * It also survived every other gate. The string sits inside a paragraph, so no
 * content assertion covered it, and one missing space was far under the
 * screenshot tolerance of the time, a ratio of 0.03, so the visual baselines
 * carried it silently through several regenerations. `scoutlens-uze.19`
 * replaced that ratio with an absolute budget, now `maxDiffPixels: 250`
 * (`D072`), but this gate does not rely on it. It was eventually
 * found by a human reading a screenshot — and by then it had reached the
 * committed portfolio media.
 *
 * So this does not assert one repaired sentence. It takes the values the pages
 * actually interpolate from the published artifact and asserts that **no
 * occurrence of any of them, on any public route, is glued to a letter**. That
 * is the class the defect belongs to, stated in a form a machine can check
 * without guessing anyone's intent.
 */

const ROUTES = ["/", "/science/", "/lab/"] as const;

interface Manifest {
  dataset_version: string;
  source: { season: string; licence: string };
  population: {
    profile_count: number;
    feature_count: number;
    minutes_threshold_per_period: number;
  };
}

/** The values the routes interpolate, as a reader sees them formatted. */
function interpolatedValues(manifest: Manifest): string[] {
  const { population } = manifest;
  return [
    manifest.source.season,
    manifest.dataset_version,
    manifest.source.licence,
    String(population.feature_count),
    String(population.minutes_threshold_per_period),
    String(population.profile_count),
    population.profile_count.toLocaleString("en-US"),
  ];
}

async function loadManifest(page: Page): Promise<Manifest> {
  const response = await page.request.get(`${SHOWCASE_BASE}manifest.json`);
  expect(response.ok(), `${SHOWCASE_BASE}manifest.json must be served`).toBe(true);
  return (await response.json()) as Manifest;
}

/** Every place `value` appears in `text` whose next character is a letter. */
function fusedOccurrences(text: string, value: string): string[] {
  const found: string[] = [];
  let index = text.indexOf(value);
  while (index !== -1) {
    const next = text[index + value.length];
    if (next !== undefined && /\p{L}/u.test(next)) {
      found.push(text.slice(Math.max(0, index - 30), index + value.length + 20));
    }
    index = text.indexOf(value, index + 1);
  }
  return found;
}

for (const route of ROUTES) {
  test(`${route} never fuses an interpolated value to the next word`, async ({ page }) => {
    await page.goto(route);
    await waitForStablePage(page);

    const manifest = await loadManifest(page);
    // `innerText`, not `textContent`: it is what a reader sees, with the
    // element boundaries rendered as whitespace the way the browser lays them
    // out. `textContent` would paper over the defect by concatenating nodes
    // exactly as the DOM stores them.
    const text = await page.locator("body").innerText();

    const fused: string[] = [];
    for (const value of interpolatedValues(manifest)) {
      // A one- or two-character value would match inside ordinary words.
      if (value.length < 3) continue;
      fused.push(...fusedOccurrences(text, value).map((context) => `${value}: …${context}…`));
    }

    expect(fused, `${route} renders an artifact value glued to a letter`).toEqual([]);
  });
}

test("the repaired sentence reads correctly, with the value still interpolated", async ({
  page,
}) => {
  await page.goto("/science/");
  await waitForStablePage(page);

  const manifest = await loadManifest(page);
  const intro = page.locator(".science-orientation p").first();

  // Both halves matter. The space is the fix; the value coming from the
  // artifact is what must not have been "fixed" by hard-coding the season.
  await expect(intro).toContainText(`from the ${manifest.source.season} season,`);
  expect(manifest.source.season.length).toBeGreaterThan(0);
});

test("the gate catches the defect when it is put back", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Reproduction runs once in desktop Chromium");

  await page.goto("/science/");
  await waitForStablePage(page);
  const manifest = await loadManifest(page);

  // Clean first.
  const before = await page.locator("body").innerText();
  expect(fusedOccurrences(before, manifest.source.season)).toEqual([]);

  // Re-create exactly what JSX produced: the season, then the next word with
  // no separator. Done in the DOM rather than by editing the component, so the
  // reproduction cannot drift away from the assertion it is proving.
  await page.evaluate((season) => {
    const intro = document.querySelector(".science-orientation p");
    if (intro === null) throw new Error("the orientation paragraph is missing");
    intro.textContent = `We take public football event data from the ${season}season, split every`;
  }, manifest.source.season);

  const after = await page.locator("body").innerText();
  const fused = fusedOccurrences(after, manifest.source.season);
  expect(fused.length, "restoring the defect must reproduce a fused occurrence").toBeGreaterThan(0);
});
