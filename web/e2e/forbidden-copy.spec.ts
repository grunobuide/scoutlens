/**
 * Forbidden copy in the client-rendered challenge states (`scoutlens-9a3.29`).
 *
 * `scripts/check-static-output.mjs` scans the prerendered HTML of `/`, `/lab/`
 * and `/science/`. The challenge's query, reveal and evidence states exist only
 * after the client reads `?challenge=`, so none of their text is in that HTML.
 * This reads what a reader of each state actually sees - `main`'s `innerText`
 * in a real browser - and holds it to the same list, imported from the same
 * module, with the same rule: the artifact's `unsupported_claims` removed, then
 * a case-insensitive match.
 *
 * `tests/forbidden-copy.test.tsx` covers the same states from server markup;
 * this is the browser-side half, where client-only code paths and hydration
 * are real.
 */

import { expect, test } from "@playwright/test";

import { findForbiddenClaims, findForbiddenCurrentness, scannableText } from "../scripts/forbidden-copy.mjs";
import { SHOWCASE_BASE, waitForStablePage } from "./helpers";

const STATES = ["query", "reveal", "evidence"] as const;

for (const state of STATES) {
  test(`the ${state} state asserts no quality, recommendation or currentness claim`, async ({
    page,
    request,
  }, testInfo) => {
    test.skip(testInfo.project.name !== "desktop", "Copy is viewport-independent; scanned once in desktop Chromium");

    const summary = await request.get(`${SHOWCASE_BASE}research-summary.json`);
    expect(summary.ok()).toBe(true);
    const unsupportedClaims = ((await summary.json()) as { unsupported_claims: string[] }).unsupported_claims;
    expect(unsupportedClaims.length).toBeGreaterThan(0);

    await page.goto(`/lab/?challenge=${state}`);
    await waitForStablePage(page);
    await expect(page.locator("[data-challenge-state]")).toHaveAttribute("data-challenge-state", state);

    const scannable = scannableText(await page.locator("main").innerText(), unsupportedClaims);
    expect(scannable.length).toBeGreaterThan(200);
    expect([...findForbiddenClaims(scannable), ...findForbiddenCurrentness(scannable)]).toEqual([]);
  });
}
