/**
 * The landing's facts strip and "The idea in 30 seconds" (`scoutlens-rdz.9`,
 * D076, narrative §7.1 items 3 and 4).
 *
 * Content assertions, so they run once in desktop Chromium, like
 * `landing-hero.spec.ts`. Every expected value comes from the artifact the site
 * serves or from the narrative document on disk, never from a literal here.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import { SHOWCASE_BASE, waitForStablePage } from "./helpers";

const REPOSITORY_ROOT = join(__dirname, "..", "..");

interface Manifest {
  dataset_version: string;
  population: {
    profile_count: number;
    feature_count: number;
    minutes_threshold_per_period: number;
    domestic_competition_ids: number[];
  };
  source: { licence: string; season: string };
}

/** The question §3 opens with, read from the narrative: "can a player's …?" */
function sectionThreeQuestion(): string {
  const lines = readFileSync(join(REPOSITORY_ROOT, "docs", "public-experience-narrative.md"), "utf8").split(/\r?\n/);
  const start = lines.findIndex((line) => line.startsWith("## 3. The 30-second explanation"));
  expect(start, "the narrative has no section 3").toBeGreaterThan(-1);
  // The quoted explanation wraps across lines; read it as one paragraph.
  const quote = lines
    .slice(start + 1)
    .filter((line) => line.startsWith("> "))
    .map((line) => line.slice(2))
    .join(" ");
  const [, question] = quote.match(/^\S+ asks one question: (.+?\?)/) ?? [];
  expect(question, "the narrative's §3 no longer opens with its one question").toBeDefined();
  return question!.charAt(0).toUpperCase() + question!.slice(1);
}

test.beforeEach(async ({}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "content assertions run once in desktop Chromium");
});

test("the facts strip shows the manifest's facts, the licence and the pin among them", async ({ page, request }) => {
  const response = await request.get(`${SHOWCASE_BASE}manifest.json`);
  expect(response.ok()).toBe(true);
  const manifest = (await response.json()) as Manifest;
  const { population, source } = manifest;

  await page.goto("/");
  await waitForStablePage(page);

  const values = await page.locator(".facts-strip__value").allTextContents();
  expect(values).toEqual([
    population.profile_count.toLocaleString("en-US"),
    String(population.domestic_competition_ids.length),
    String(population.feature_count),
    source.licence,
    manifest.dataset_version,
  ]);
  const strip = (await page.locator(".facts-strip").textContent()) ?? "";
  expect(strip).toContain(`at least ${population.minutes_threshold_per_period.toLocaleString("en-US")} minutes`);
  expect(strip).toContain(source.season);
  // D076: no result value. No metric, rank or share belongs in the strip.
  expect(strip).not.toMatch(/MRR|rank|%/i);
});

test("the facts strip and the idea follow the hero, in that order, before the claim matrix", async ({ page }) => {
  await page.goto("/");
  await waitForStablePage(page);

  const order = await page.evaluate(() =>
    [".hero", ".facts-strip", ".idea", ".claims-matrix"].map((selector) => {
      const element = document.querySelector(selector);
      return element === null ? -1 : [...document.querySelectorAll("main *")].indexOf(element);
    }),
  );
  expect(order.every((position) => position >= 0), `missing: ${order.join(", ")}`).toBe(true);
  expect([...order].sort((a, b) => a - b)).toEqual(order);
});

test("the idea asks §3's question and states the method with the manifest's numbers", async ({ page, request }) => {
  const response = await request.get(`${SHOWCASE_BASE}manifest.json`);
  const { population, source } = (await response.json()) as Manifest;

  await page.goto("/");
  await waitForStablePage(page);

  const idea = page.locator(".idea");
  await expect(idea.getByRole("heading", { level: 2 })).toHaveText(sectionThreeQuestion());
  await expect(idea.locator(".idea__steps > li")).toHaveCount(3);
  const text = (await idea.textContent()) ?? "";
  for (const fact of [
    source.season,
    `at least ${population.minutes_threshold_per_period.toLocaleString("en-US")} minutes`,
    `${population.feature_count} simple measurements`,
    `All ${population.profile_count.toLocaleString("en-US")} second-half profiles`,
  ]) {
    expect(text).toContain(fact);
  }
});
