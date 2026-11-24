/**
 * The `/case-study/` route's research trail (`scoutlens-rdz.13`, D075).
 *
 * Every expected value is read from the artifacts the site serves, never from
 * the page's code: each `data-metric` tag names an experiment and a metric, and
 * the printed number must be that metric at its published precision. A number
 * typed into the page carries no tag, and the sweep for untagged decimals
 * catches it.
 *
 * Content assertions run once, in desktop Chromium; the layout ones run in
 * both real-data projects.
 */

import { existsSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type APIRequestContext } from "@playwright/test";

import {
  SHOWCASE_BASE,
  expectNoPageOverflow,
  expectNoSeriousOrCriticalViolations,
  waitForStablePage,
} from "./helpers";

const ROUTE = "/case-study/";
const REPOSITORY_ROOT = join(__dirname, "..", "..");
const REPOSITORY_BLOB = "https://github.com/grunobuide/scoutlens/blob/main/";

interface Metric {
  metric_id: string;
  value: number;
  display_precision: number;
  ci_95: readonly [number, number] | null;
}

interface ResearchSummary {
  experiments: ReadonlyArray<{ experiment_id: string; metrics: readonly Metric[]; caveat_codes: readonly string[] }>;
  caveats: ReadonlyArray<{ code: string; message: string; severity: string }>;
}

async function fetchArtifact<T>(request: APIRequestContext, file: string): Promise<T> {
  const response = await request.get(`${SHOWCASE_BASE}${file}`);
  expect(response.ok(), `${SHOWCASE_BASE}${file} is not served`).toBe(true);
  return (await response.json()) as T;
}

function metricsByTag(research: ResearchSummary): Map<string, Metric> {
  return new Map(
    research.experiments.flatMap((experiment) =>
      experiment.metrics.map((metric) => [`${experiment.experiment_id}:${metric.metric_id}`, metric] as const),
    ),
  );
}

test.describe("the case study's research trail", () => {
  test.beforeEach(({}, testInfo) => {
    test.skip(testInfo.project.name !== "desktop", "content assertion, run once in desktop Chromium");
  });

  test("six decisions, in order, each linking to a document that exists", async ({ page }) => {
    await page.goto(ROUTE);
    await waitForStablePage(page);

    const steps = page.locator(".trail > li");
    await expect(steps).toHaveCount(6);
    await expect(steps.locator("h3")).toHaveText([
      "Freeze the question before seeing any result",
      "Start with a dumb baseline",
      "Test the fingerprint",
      "Attack my own result",
      "Replicate on someone else's data",
      "Say no to a fix that doesn't help",
    ]);

    const hrefs = await steps.locator(".trail-step__doc a").evaluateAll((links) =>
      links.map((link) => link.getAttribute("href") ?? ""),
    );
    expect(hrefs).toHaveLength(6);
    for (const href of [...hrefs, await page.locator(".case-study-trail__log a").getAttribute("href")]) {
      expect(href, "a trail link leaves the repository").toMatch(new RegExp(`^${REPOSITORY_BLOB.replaceAll(".", "\\.")}`));
      const path = href!.slice(REPOSITORY_BLOB.length).split("#", 1)[0]!;
      expect(existsSync(join(REPOSITORY_ROOT, path)), `${path} does not exist`).toBe(true);
    }
  });

  test("every number is the artifact's metric at its published precision", async ({ page, request }) => {
    const metrics = metricsByTag(await fetchArtifact<ResearchSummary>(request, "research-summary.json"));
    await page.goto(ROUTE);
    await waitForStablePage(page);

    const rendered = await page
      .locator(".trail [data-metric]")
      .evaluateAll((elements) => elements.map((element) => [element.getAttribute("data-metric") ?? "", element.textContent ?? ""]));
    expect(rendered.length, "the trail quotes no metric").toBeGreaterThanOrEqual(15);

    const mismatches: string[] = [];
    for (const [tag, text] of rendered) {
      const metric = metrics.get(tag!);
      if (metric === undefined) {
        mismatches.push(`${tag} is not a published metric`);
        continue;
      }
      const expected = metric.value.toFixed(metric.display_precision);
      if (text !== expected) {
        mismatches.push(`${tag} renders ${text}, the artifact says ${expected}`);
      }
    }
    expect(mismatches).toEqual([]);

    const intervals = await page
      .locator(".trail [data-metric-interval]")
      .evaluateAll((elements) => elements.map((element) => [element.getAttribute("data-metric-interval") ?? "", element.textContent ?? ""]));
    for (const [tag, text] of intervals) {
      const metric = metrics.get(tag!);
      expect(metric?.ci_95, `${tag} has no published interval`).toBeTruthy();
      const [low, high] = metric!.ci_95!.map((value) => value.toFixed(metric!.display_precision));
      expect(text).toContain(`${low} to ${high}`);
    }

    // No decimal outside a tagged value: a number typed into the prose would
    // carry no tag. The glossaries and caveats print no results.
    const untagged = await page.locator(".trail").evaluate((trail) => {
      const clone = trail.cloneNode(true) as HTMLElement;
      clone.querySelectorAll("[data-metric], [data-metric-interval], details").forEach((element) => element.remove());
      return clone.textContent?.match(/\d\.\d+/g) ?? [];
    });
    expect(untagged, "the trail prints a decimal that no artifact metric owns").toEqual([]);
  });

  test("each step carries the caveats of the experiments it quotes, the confound beside the team control", async ({
    page,
    request,
  }) => {
    const research = await fetchArtifact<ResearchSummary>(request, "research-summary.json");
    const message = (code: string) => research.caveats.find((caveat) => caveat.code === code)!.message;
    await page.goto(ROUTE);
    await waitForStablePage(page);

    const steps = page.locator(".trail > li");
    for (let index = 0; index < 6; index += 1) {
      const step = steps.nth(index);
      const experimentIds = await step
        .locator("[data-metric]")
        .evaluateAll((elements) => [...new Set(elements.map((element) => element.getAttribute("data-metric")!.split(":")[0]))]);
      const expected = [
        ...new Set(
          experimentIds.flatMap((id) => research.experiments.find((experiment) => experiment.experiment_id === id)!.caveat_codes),
        ),
      ].map(message);
      const rendered = await step.locator(".caveat").evaluateAll((caveats) =>
        caveats.map((caveat) => caveat.lastChild?.textContent ?? ""),
      );
      expect(rendered.sort()).toEqual(expected.sort());
    }

    const attack = steps.filter({ has: page.locator('[data-metric="wyscout_role_team_minutes:baseline_c_mrr"]') });
    await expect(attack.locator(".caveat--critical")).toContainText([message("same_season_team_confound")]);
  });

  test("the nav's fourth item is the case study", async ({ page }) => {
    await page.goto(ROUTE);
    await waitForStablePage(page);
    const links = page.getByRole("navigation", { name: "Primary navigation" }).getByRole("link");
    await expect(links).toHaveText(["Overview", "Fingerprint Lab", "How it works", "Case study"]);
    await expect(links.nth(3)).toHaveAttribute("href", ROUTE);
  });
});

test("the case study fits the viewport and has no serious accessibility violation", async ({ page }) => {
  await page.goto(ROUTE);
  await waitForStablePage(page);
  await expectNoPageOverflow(page);
  await expectNoSeriousOrCriticalViolations(page);
});
