/**
 * The fingerprint preview as A/B dumbbells (`scoutlens-rdz.10`), on the
 * landing and on /science, which render the same component.
 *
 * Every expected value is computed here from the artifacts the site serves:
 * the featured profile's within-role percentiles, averaged per family, with
 * the families in the feature catalog's `order`. Nothing is copied from the
 * page's own code, so a change to how the page groups or orders families has
 * to agree with the artifact to pass.
 *
 * Runs in the two real-data projects. The geometry is checked in both,
 * because narrow screens stack each row and give the track the card's width.
 */

import { expect, test, type APIRequestContext } from "@playwright/test";

import { SHOWCASE_BASE, waitForStablePage } from "./helpers";

interface Manifest {
  featured_profile: { profile_key: string };
}

interface Catalog {
  features: Array<{ feature_id: string; family: string; order: number }>;
}

interface Profile {
  periods: Record<"a" | "b", { features: Array<{ feature_id: string; within_role_percentile: number }> }>;
}

interface FamilyRow {
  family: string;
  featureCount: number;
  periodA: number;
  periodB: number;
}

async function fetchArtifact<T>(request: APIRequestContext, file: string): Promise<T> {
  const response = await request.get(`${SHOWCASE_BASE}${file}`);
  expect(response.ok(), `${SHOWCASE_BASE}${file} is not served`).toBe(true);
  return (await response.json()) as T;
}

/** The featured profile's family averages, in the catalog's order. */
async function expectedRows(request: APIRequestContext): Promise<FamilyRow[]> {
  const manifest = await fetchArtifact<Manifest>(request, "manifest.json");
  const catalog = await fetchArtifact<Catalog>(request, "feature-catalog.json");
  const profile = await fetchArtifact<Profile>(request, `players/${manifest.featured_profile.profile_key}.json`);
  const percentile = (period: "a" | "b", featureId: string): number => {
    const item = profile.periods[period].features.find((feature) => feature.feature_id === featureId);
    expect(item, `the featured profile has no ${featureId} in period ${period}`).toBeDefined();
    return item!.within_role_percentile;
  };

  const ordered = [...catalog.features].sort((left, right) => left.order - right.order);
  const families = [...new Set(ordered.map((feature) => feature.family))];
  return families.map((family) => {
    const ids = ordered.filter((feature) => feature.family === family).map((feature) => feature.feature_id);
    const mean = (period: "a" | "b") => ids.reduce((sum, id) => sum + percentile(period, id), 0) / ids.length;
    return { family, featureCount: ids.length, periodA: mean("a"), periodB: mean("b") };
  });
}

test.beforeEach(async ({}, testInfo) => {
  test.skip(
    testInfo.project.name !== "desktop" && testInfo.project.name !== "mobile-360",
    "the real artifact's featured profile is served only in the real-data projects",
  );
});

for (const route of ["/", "/science/"]) {
  test(`${route} draws one dumbbell per family, at the artifact's values, in the artifact's order`, async ({
    page,
    request,
  }) => {
    const expected = await expectedRows(request);
    await page.goto(route);
    await waitForStablePage(page);

    const rows = await page.locator(".fingerprint-plot .fingerprint-row").evaluateAll((elements) =>
      elements.map((row) => {
        const centre = (selector: string) => {
          const box = row.querySelector(selector)!.getBoundingClientRect();
          return { x: box.left + box.width / 2, y: box.top + box.height / 2 };
        };
        const track = row.querySelector(".fingerprint-track")!.getBoundingClientRect();
        const span = row.querySelector(".fingerprint-span")!.getBoundingClientRect();
        const values = [...row.querySelectorAll("p > span")].map((value) => ({
          text: value.textContent ?? "",
          hidden: value.getAttribute("aria-hidden") === "true",
        }));
        return {
          count: row.querySelector("small")?.textContent ?? "",
          values,
          track: { left: track.left, width: track.width },
          span: { left: span.left, width: span.width },
          a: centre(".fingerprint-mark--a"),
          b: centre(".fingerprint-mark--b"),
        };
      }),
    );

    expect(rows.map((row) => row.count)).toEqual(expected.map((row) => `${row.featureCount} features`));
    rows.forEach((row, index) => {
      const want = expected[index]!;
      const at = (value: number) => row.track.left + (row.track.width * value) / 100;
      const where = `${route} ${want.family}`;

      // The two values a reader hears, with the arrow between them hidden.
      expect(row.values.filter((value) => !value.hidden).map((value) => value.text), where).toEqual([
        want.periodA.toFixed(0),
        want.periodB.toFixed(0),
      ]);
      // Both dots on one line, each at its own value on the 0-100 track.
      expect(Math.abs(row.a.y - row.b.y), `${where}: A and B share the track`).toBeLessThan(0.5);
      expect(Math.abs(row.a.x - at(want.periodA)), `${where}: A`).toBeLessThan(1);
      expect(Math.abs(row.b.x - at(want.periodB)), `${where}: B`).toBeLessThan(1);
      // The bar joins them, and only them.
      expect(Math.abs(row.span.left - at(Math.min(want.periodA, want.periodB))), `${where}: bar start`).toBeLessThan(1);
      expect(
        Math.abs(row.span.width - (row.track.width * Math.abs(want.periodA - want.periodB)) / 100),
        `${where}: bar length`,
      ).toBeLessThan(1);
    });
  });

  test(`${route} sets one 0-50-100 axis over the tracks, hidden from assistive technology`, async ({ page }) => {
    await page.goto(route);
    await waitForStablePage(page);

    const axis = page.locator(".fingerprint-axis");
    await expect(axis).toHaveAttribute("aria-hidden", "true");
    const geometry = await page.evaluate(() => {
      const ticks = [...document.querySelectorAll(".fingerprint-axis__ticks span")].map((tick) => {
        const box = tick.getBoundingClientRect();
        return { text: tick.textContent, left: box.left, right: box.right, centre: box.left + box.width / 2 };
      });
      const track = document.querySelector(".fingerprint-track")!.getBoundingClientRect();
      return { ticks, track: { left: track.left, right: track.right, centre: track.left + track.width / 2 } };
    });
    expect(geometry.ticks.map((tick) => tick.text)).toEqual(["0", "50", "100"]);
    const [zero, middle, hundred] = geometry.ticks;
    expect(Math.abs(zero!.left - geometry.track.left)).toBeLessThan(1);
    expect(Math.abs(middle!.centre - geometry.track.centre)).toBeLessThan(1);
    expect(Math.abs(hundred!.right - geometry.track.right)).toBeLessThan(1);
  });
}
