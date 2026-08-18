import { expect, test } from "@playwright/test";

import {
  expectNoSeriousOrCriticalViolations,
  waitForStablePage,
  SHOWCASE_BASE,
  MESSI_PROFILE_KEY,
} from "./helpers";

for (const route of ["/", "/lab/", "/science/"]) {
  test(`${route} has no serious or critical automated accessibility violations`, async ({ page }) => {
    await page.goto(route);
    await waitForStablePage(page);
    await expectNoSeriousOrCriticalViolations(page);
  });
}

test("the open neighbor drawer has no serious or critical automated accessibility violations", async ({ page }) => {
  await page.goto("/lab/");
  await page.locator('[data-neighbor-rank="1"] button').click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expectNoSeriousOrCriticalViolations(page);
});

test("all rendered local links and static assets resolve", async ({ page, request }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "The route crawl runs once");
  const paths = new Set<string>([
    `${SHOWCASE_BASE}manifest.json`,
    `${SHOWCASE_BASE}feature-catalog.json`,
    `${SHOWCASE_BASE}players.index.json`,
  ]);
  for (const route of ["/", "/lab/", "/science/"]) {
    await page.goto(route);
    const discovered = await page.locator("a[href], link[href], script[src]").evaluateAll((elements) =>
      elements.map((element) => element.getAttribute("href") ?? element.getAttribute("src")),
    );
    for (const value of discovered) {
      if (value === null) {
        continue;
      }
      const url = new URL(value, page.url());
      if (url.origin === new URL(page.url()).origin) {
        paths.add(`${url.pathname}${url.search}`);
      }
    }
  }

  for (const path of [...paths].sort()) {
    const response = await request.get(path);
    expect(response.status(), `${path} must resolve`).toBeLessThan(400);
  }
});

test("static delivery applies the declared cache policy and gzip", async ({ page, request }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Header checks run once");
  await page.goto("/lab/");
  const nextAsset = await page.locator('script[src*="/_next/static/"]').first().getAttribute("src");
  expect(nextAsset).not.toBeNull();

  const cases = [
    [`${SHOWCASE_BASE}manifest.json`, /max-age=60.*must-revalidate/],
    [`${SHOWCASE_BASE}feature-catalog.json`, /max-age=31536000.*immutable/],
    [`${SHOWCASE_BASE}players/${MESSI_PROFILE_KEY}.json`, /max-age=31536000.*immutable/],
    [nextAsset!, /max-age=31536000.*immutable/],
  ] as const;
  for (const [path, expectedCache] of cases) {
    const response = await request.get(path, { headers: { "Accept-Encoding": "gzip" } });
    expect(response.status()).toBe(200);
    expect(response.headers()["cache-control"]).toMatch(expectedCache);
    expect(response.headers()["content-encoding"]).toBe("gzip");
    expect(response.headers()["x-content-type-options"]).toBe("nosniff");
  }
});
