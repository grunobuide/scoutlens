import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

import { expect, test } from "@playwright/test";

import { MESSI_PROFILE_KEY } from "./helpers";

test.beforeEach(async ({}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Failure fixtures run once in desktop Chromium");
});

test("unknown profile keeps the selector usable until a valid selection replaces the URL", async ({ page }) => {
  await page.goto("/lab/?player=unknown-profile");
  await expect(page.locator(".lab-state[role='alert']")).toContainText("That profile is not in this dataset version");
  await expect(page.getByRole("searchbox", { name: "Search players" })).toBeEnabled();
  await expect(page).toHaveURL(/player=unknown-profile/);

  await page.getByRole("searchbox", { name: "Search players" }).fill("L. Messi");
  await page.getByRole("button", { name: /L\. Messi/ }).first().click();
  await expect(page).toHaveURL(new RegExp(`player=${MESSI_PROFILE_KEY}`));
  await expect(page.locator(".selected-profile__header h2")).toHaveText("L. Messi");
});

test("missing profile asset renders the explicit recovery state", async ({ page }) => {
  await page.route(`**/showcase/v1/players/${MESSI_PROFILE_KEY}.json`, (route) =>
    route.fulfill({ status: 404, contentType: "text/plain", body: "missing fixture" }),
  );
  await page.goto(`/lab/?player=${MESSI_PROFILE_KEY}`);
  await expect(page.locator(".lab-state[role='alert']")).toContainText("The selected data file could not be loaded");
  await expect(page.getByRole("button", { name: "Retry verified data" })).toBeVisible();
});

test("checksum mismatch fails closed before profile values render", async ({ page }) => {
  await page.route(`**/showcase/v1/players/${MESSI_PROFILE_KEY}.json`, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "{}" }),
  );
  await page.goto(`/lab/?player=${MESSI_PROFILE_KEY}`);
  await expect(page.locator(".lab-state[role='alert']")).toContainText("This profile does not match the active manifest");
  await expect(page.locator(".selected-profile")).toHaveCount(0);
});

test("schema-invalid profile with a matching checksum renders the incompatible-data state", async ({ page }) => {
  const showcaseRoot = resolve("public", "showcase", "v1");
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

  await page.route("**/showcase/v1/manifest.json", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(manifest) }),
  );
  await page.route(`**/showcase/v1/players/${MESSI_PROFILE_KEY}.json`, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: invalidBytes }),
  );
  await page.goto(`/lab/?player=${MESSI_PROFILE_KEY}`);
  await expect(page.locator(".lab-state[role='alert']")).toContainText("The selected profile failed contract validation");
  await expect(page.locator(".selected-profile")).toHaveCount(0);
});
