import { expect, test } from "@playwright/test";

import {
  expectNoPageOverflow,
  expectNoSeriousOrCriticalViolations,
  waitForStablePage,
} from "./helpers";

const MISSING_PATH = "/definitely-missing/";

test("unknown routes serve the built 404 page with shell, primary navigation and focusable content", async ({
  page,
}) => {
  const response = await page.goto(MISSING_PATH);
  expect(response?.status()).toBe(404);
  expect(response?.headers()["content-type"]).toContain("text/html");

  await expect(page.locator(".site-header")).toBeVisible();
  await expect(page.locator(".site-footer")).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Primary navigation" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 1, name: "404" })).toBeVisible();

  const focusable = page.locator(
    'a[href], button, input, select, textarea, [tabindex]:not([tabindex="-1"])',
  );
  const focusableCount = await focusable.count();
  expect(focusableCount, "The 404 page must offer a way back through focusable elements").toBeGreaterThan(0);
});

test("the 404 document body carries the built shell and HEAD returns no body", async ({ request }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Raw body and HEAD checks run once");

  const response = await request.get(MISSING_PATH, { headers: { "Accept-Encoding": "gzip" } });
  expect(response.status()).toBe(404);
  expect(response.headers()["content-type"]).toContain("text/html");
  const body = await response.text();
  expect(body).toContain("site-header");
  expect(body).toContain("site-footer");
  expect(body).toContain("<h1");
  expect(body).toMatch(/<h1[^>]*>\s*404\s*<\/h1>/);

  const head = await request.head(MISSING_PATH);
  expect(head.status()).toBe(404);
  expect(head.headers()["content-type"]).toContain("text/html");
  expect((await head.body()).byteLength).toBe(0);
});

test("the served 404 page has no overflow or serious or critical axe violations at 1280 CSS px", async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Explicit geometry is asserted once");
  await page.setViewportSize({ width: 1280, height: 900 });
  const response = await page.goto(MISSING_PATH);
  expect(response?.status()).toBe(404);
  await waitForStablePage(page);
  await expectNoPageOverflow(page);
  await expectNoSeriousOrCriticalViolations(page);
});

test("the served 404 page has no overflow or serious or critical axe violations at 320 CSS px", async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "320 geometry is asserted once from a resizable context");
  await page.setViewportSize({ width: 320, height: 800 });
  const response = await page.goto(MISSING_PATH);
  expect(response?.status()).toBe(404);
  await waitForStablePage(page);
  await expectNoPageOverflow(page);
  await expectNoSeriousOrCriticalViolations(page);
});
