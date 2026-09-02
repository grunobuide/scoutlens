import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

import { expect, test, type Page } from "@playwright/test";

import {
  MESSI_PROFILE_KEY,
  SHOWCASE_BASE,
  expectNoPageOverflow,
  expectNoSeriousOrCriticalViolations,
  waitForStablePage,
} from "./helpers";

test.beforeEach(async ({}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Failure fixtures run once in desktop Chromium");
});


/**
 * The four failure states, each as a reusable setup (`scoutlens-uze.6.4`).
 *
 * Extracted so the assertions below and the narrow-width walk at the bottom
 * drive the same fixtures. Duplicating the route mocks would put two
 * definitions of one failure in the file, which is the defect
 * `scoutlens-uze.13` was.
 *
 * Each returns the copy its recovery panel must show, so the walk can assert
 * the reader is told what happened without restating it.
 */
async function openUnknownProfile(page: Page): Promise<string> {
  await page.goto("/lab/?player=unknown-profile");
  return "That profile is not in this dataset version";
}

async function openMissingAsset(page: Page): Promise<string> {
  await page.route(`**${SHOWCASE_BASE}players/${MESSI_PROFILE_KEY}.json`, (route) =>
    route.fulfill({ status: 404, contentType: "text/plain", body: "missing fixture" }),
  );
  await page.goto(`/lab/?player=${MESSI_PROFILE_KEY}`);
  return "The selected data file could not be loaded";
}

async function openChecksumMismatch(page: Page): Promise<string> {
  await page.route(`**${SHOWCASE_BASE}players/${MESSI_PROFILE_KEY}.json`, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "{}" }),
  );
  await page.goto(`/lab/?player=${MESSI_PROFILE_KEY}`);
  return "This profile does not match the active manifest";
}

async function openSchemaInvalid(page: Page): Promise<string> {
  const showcaseRoot = resolve("public", SHOWCASE_BASE.replace(/^\/|\/$/g, ""));
  const manifest = JSON.parse(await readFile(resolve(showcaseRoot, "manifest.json"), "utf8")) as {
    files: Array<{ bytes: number; path: string; sha256: string }>;
  };
  const profilePath = `players/${MESSI_PROFILE_KEY}.json`;
  const invalidProfile = JSON.parse(
    await readFile(resolve(showcaseRoot, ...profilePath.split("/")), "utf8"),
  ) as Record<string, unknown>;
  delete invalidProfile.identity;
  const invalidBytes = Buffer.from(JSON.stringify(invalidProfile));
  const manifestFile = manifest.files.find((file) => file.path === profilePath);
  if (manifestFile === undefined) {
    throw new Error(`Manifest is missing ${profilePath}`);
  }
  manifestFile.bytes = invalidBytes.byteLength;
  manifestFile.sha256 = createHash("sha256").update(invalidBytes).digest("hex");

  await page.route(`**${SHOWCASE_BASE}manifest.json`, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(manifest) }),
  );
  await page.route(`**${SHOWCASE_BASE}players/${MESSI_PROFILE_KEY}.json`, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: invalidBytes }),
  );
  await page.goto(`/lab/?player=${MESSI_PROFILE_KEY}`);
  return "The selected profile failed contract validation";
}

const FAILURE_STATES = [
  { name: "unknown profile", open: openUnknownProfile },
  { name: "missing profile asset", open: openMissingAsset },
  { name: "checksum mismatch", open: openChecksumMismatch },
  { name: "schema-invalid profile", open: openSchemaInvalid },
] as const;

test("unknown profile keeps the selector usable until a valid selection replaces the URL", async ({ page }) => {
  await openUnknownProfile(page);
  await expect(page.locator(".lab-state[role='alert']")).toContainText("That profile is not in this dataset version");
  await expect(page.getByRole("searchbox", { name: "Search players" })).toBeEnabled();
  await expect(page).toHaveURL(/player=unknown-profile/);

  await page.getByRole("searchbox", { name: "Search players" }).fill("L. Messi");
  await page.getByRole("button", { name: /L\. Messi/ }).first().click();
  await expect(page).toHaveURL(new RegExp(`player=${MESSI_PROFILE_KEY}`));
  await expect(page.locator(".selected-profile__header h2")).toHaveText("L. Messi");
});

test("missing profile asset renders the explicit recovery state", async ({ page }) => {
  await openMissingAsset(page);
  await expect(page.locator(".lab-state[role='alert']")).toContainText("The selected data file could not be loaded");
  await expect(page.getByRole("button", { name: "Retry verified data" })).toBeVisible();
});

test("checksum mismatch fails closed before profile values render", async ({ page }) => {
  await openChecksumMismatch(page);
  await expect(page.locator(".lab-state[role='alert']")).toContainText("This profile does not match the active manifest");
  await expect(page.locator(".selected-profile")).toHaveCount(0);
});

test("schema-invalid profile with a matching checksum renders the incompatible-data state", async ({ page }) => {
  await openSchemaInvalid(page);
  await expect(page.locator(".lab-state[role='alert']")).toContainText("The selected profile failed contract validation");
  await expect(page.locator(".selected-profile")).toHaveCount(0);
});

/**
 * The same four states at mobile widths (`scoutlens-uze.6.4`).
 *
 * `scoutlens-uze.1` swept these at 320/360/768/zoom200 by hand and recorded
 * PASS, but nothing held it: this file skipped itself outside desktop, so every
 * assertion above ran at 1280 only. The gap was found while mapping the audit
 * matrix to gates in `scoutlens-uze.6.3` and is recorded in
 * `docs/frontend-release-gates.md` §3.1.
 *
 * These are the states a reader reaches when something has *already* gone
 * wrong. The recovery action has to be reachable on a phone, and a failure
 * panel is exactly the kind of surface that gets styled once at desktop and
 * never looked at again.
 */
for (const state of FAILURE_STATES) {
  test(`${state.name} recovers cleanly at mobile widths`, async ({ page }) => {
    for (const width of [320, 360]) {
      await page.setViewportSize({ width, height: 800 });
      const copy = await state.open(page);
      await waitForStablePage(page);

      const alert = page.locator(".lab-state[role='alert']");
      await expect(alert, `${state.name} at ${width}: no recovery panel`).toContainText(copy);

      // The panel must not push the page sideways, and must be readable.
      await expectNoPageOverflow(page);
      const box = await alert.boundingBox();
      expect(box, `${state.name} at ${width}: panel has no box`).not.toBeNull();
      expect(
        box!.width,
        `${state.name} at ${width}: panel is wider than the viewport`,
      ).toBeLessThanOrEqual(width);

      // The recovery action itself. Every one of these states leaves the
      // selector usable - choosing another player is the way out of all four -
      // so it has to be reachable and operable, not merely present in the DOM.
      //
      // Reachable, not above the fold: measured at 320 the selector sits at
      // 1,693 px and the alert at 3,863 px on a 5,699 px page, because the
      // challenge panel and the page intro come first. Asserting it were
      // on-screen at load would be asserting a different design, not a
      // regression.
      const search = page.getByRole("searchbox", { name: "Search players" });
      await expect(search, `${state.name} at ${width}: no way to recover`).toBeVisible();
      await expect(search).toBeEnabled();
      await search.scrollIntoViewIfNeeded();
      await expect(
        search,
        `${state.name} at ${width}: the selector cannot be scrolled to`,
      ).toBeInViewport();

      await expectNoSeriousOrCriticalViolations(page);
    }
  });
}
