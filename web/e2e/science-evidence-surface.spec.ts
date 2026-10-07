/**
 * /science answers its own questions (`scoutlens-9a3.23`, the residue of
 * `scoutlens-9a3.4`).
 *
 * The 2026-10-06 evidence backfill found six things the route did that no test
 * held, and two it did not do at all: it never stated the supported claim, and
 * it never linked the decision log. One test per gap:
 *
 * - AC2: the orientation is section 3 of the frozen narrative, and it comes
 *   before the first metric.
 * - AC3: the worked example's identity, periods and ranks are the featured
 *   artifact's.
 * - AC4: every metric on '/' and '/science/' opens its explanation.
 * - AC5: the supported claim, the historical-data label, the team confound and
 *   the not-recruitment boundary are shown without expanding anything, at
 *   320 px, at desktop width and before hydration.
 * - AC6: every link category a reader needs is one click away.
 *
 * Expected values come from the served artifacts and the narrative document,
 * never from literals typed here. The 320 and 768 baselines (AC7) live in
 * visual-landing-science.spec.ts with the other screenshots.
 */

import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type APIRequestContext, type Locator, type Page } from "@playwright/test";

import { SHOWCASE_BASE, waitForStablePage } from "./helpers";

const REPOSITORY_ROOT = join(__dirname, "..", "..");
const REPOSITORY_BLOB = "https://github.com/grunobuide/scoutlens/blob/main/";
const DISPLAY_NAME = "Yumusarái Labs";

interface Manifest {
  featured_profile: { profile_key: string };
  source: { season: string; source_url: string; licence_url: string };
  population: { feature_count: number };
  producer: { config_path: string };
}

interface Experiment {
  experiment_id: string;
  report_url: string;
  source_artifact: string;
}

interface ResearchSummary {
  supported_claim: string;
  unsupported_claims: readonly string[];
  experiments: readonly Experiment[];
  narrative_steps: ReadonlyArray<{ kind: string; experiment_ids: readonly string[] }>;
  caveats: ReadonlyArray<{ code: string; message: string }>;
}

interface Period {
  label: string;
  match_count: number;
}

interface Outcome {
  self_rank: number;
  candidate_count: number;
  uncertainty: { rank_ci_95: readonly [number, number] | null };
}

interface FeaturedProfile {
  identity: {
    display_name: string;
    role: string;
    competition: { name: string };
    period_contexts: { a: { teams: ReadonlyArray<{ name: string }> } };
  };
  periods: { a: Period; b: Period };
  retrieval: { global: Outcome; baseline_role_minutes: Outcome };
}

async function fetchArtifact<T>(request: APIRequestContext, file: string): Promise<T> {
  const response = await request.get(`${SHOWCASE_BASE}${file}`);
  expect(response.ok(), `${SHOWCASE_BASE}${file} is not served`).toBe(true);
  return (await response.json()) as T;
}

/** The published rank formatting rule, mirrored from components/rank-format.ts. */
function formatRank(value: number): string {
  const fixed = value.toFixed(1);
  return fixed.endsWith(".0") ? fixed.slice(0, -2) : fixed;
}

/** Every element that prints a result (the same union as claims-consistency.spec.ts). */
const RESULT_SELECTOR = [
  "main .signal-caveat",
  "main .fingerprint-plot p",
  "main .experiment-metric__value",
  "main [data-quantity]",
  "main [data-challenge-rank]",
  "main [data-challenge-result]",
].join(", ");

/** Section 3 of the frozen narrative, split into its sentences. */
function thirtySecondExplanation(): string[] {
  const lines = readFileSync(join(REPOSITORY_ROOT, "docs", "public-experience-narrative.md"), "utf8").split(/\r?\n/);
  const start = lines.findIndex((line) => line.startsWith("## 3. The 30-second explanation"));
  expect(start, "the narrative has no section 3").toBeGreaterThan(-1);
  const quote: string[] = [];
  for (const line of lines.slice(start + 1)) {
    if (line.startsWith(">")) {
      quote.push(line.replace(/^>\s?/, ""));
    } else if (quote.length > 0) {
      break;
    }
  }
  const sentences = quote.join(" ").replace(/\s+/g, " ").trim().split(/(?<=[.?])\s+(?=[A-Z])/);
  // A sentence added to or split in the document fails here, loudly, rather
  // than silently shifting which sentences the orientation is held to.
  expect(sentences, "section 3 is no longer four sentences").toHaveLength(4);
  return sentences;
}

/** How many of section 3's sentences the orientation renders. */
const ORIENTATION_SENTENCES = 2;

/**
 * The orientation the page must print: section 3's opening, with exactly the
 * substitutions the narrative permits. Each anchor must be present once before
 * it is replaced, so an unrelated "32" can never be rewritten.
 */
function expectedOrientation(manifest: Manifest): string {
  let text = thirtySecondExplanation().slice(0, ORIENTATION_SENTENCES).join(" ");
  for (const [anchor, replacement] of [
    ["ScoutLens", DISPLAY_NAME],
    ["the 2017/18 season", `the ${manifest.source.season} season`],
    ["whether 32 simple", `whether ${manifest.population.feature_count} simple`],
  ] as const) {
    expect(text.split(anchor).length - 1, `section 3 no longer contains "${anchor}" exactly once`).toBe(1);
    text = text.replace(anchor, replacement);
  }
  return text;
}

async function documentOrder(page: Page, selectors: readonly string[]): Promise<number[]> {
  return page.evaluate((list) => {
    const all = [...document.querySelectorAll("*")];
    return list.map((selector) => {
      const element = document.querySelector(selector);
      return element === null ? -1 : all.indexOf(element);
    });
  }, selectors);
}

/** Visible, and not inside a closed disclosure: shown without expanding anything. */
async function expectShownWithoutExpanding(locator: Locator, label: string): Promise<void> {
  await expect(locator, `${label} is not visible`).toBeVisible();
  const inClosedDisclosure = await locator.evaluate((element) => {
    const disclosure = element.closest("details");
    return disclosure !== null && !disclosure.open;
  });
  expect(inClosedDisclosure, `${label} is behind a closed disclosure`).toBe(false);
}

test.beforeEach(({}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Content assertions run once; widths are set per test");
});

async function expectOrientation(page: Page, manifest: Manifest, context: string): Promise<void> {
  const orientation = page.locator("main .science-orientation > p").first();
  await expect(orientation, `${context}: the orientation is not section 3's opening`).toHaveText(
    expectedOrientation(manifest),
  );
  await expectShownWithoutExpanding(orientation, `${context}: orientation`);
  const [orientationAt = -1, thesisAt = -1, firstMetricAt = -1] = await documentOrder(page, [
    "main .science-orientation > p",
    "main [data-thesis]",
    RESULT_SELECTOR,
  ]);
  expect(firstMetricAt, `${context}: no metric found`).toBeGreaterThan(-1);
  expect(orientationAt, `${context}: the first metric precedes the orientation`).toBeLessThan(firstMetricAt);
  expect(thesisAt, `${context}: the first metric precedes the thesis`).toBeLessThan(firstMetricAt);
}

async function expectBoundariesShown(page: Page, research: ResearchSummary, context: string): Promise<void> {
  await expect(page.locator("main [data-supported-claim]"), `${context}: supported claim`).toHaveText(
    research.supported_claim,
  );
  await expectShownWithoutExpanding(page.locator("main [data-supported-claim]"), `${context}: supported claim`);

  const historical = page.locator("main [data-vintage-badge] .data-vintage__label");
  await expect(historical, `${context}: historical-data label`).toHaveText("Historical reproducible benchmark");
  await expectShownWithoutExpanding(historical, `${context}: historical-data label`);

  const confound = research.caveats.find((caveat) => caveat.code === "same_season_team_confound");
  expect(confound, "the artifact carries no team-continuity caveat").toBeDefined();
  await expectShownWithoutExpanding(
    page.locator("main .caveat", { hasText: confound!.message }).first(),
    `${context}: team-continuity confound`,
  );

  const recruitment = research.unsupported_claims.find((claim) => /recruit/i.test(claim));
  expect(recruitment, "the artifact carries no not-recruitment claim").toBeDefined();
  await expectShownWithoutExpanding(
    page.locator("main .claims-matrix li", { hasText: recruitment! }),
    `${context}: not-recruitment boundary`,
  );
}

/** The links a reader needs, by category, each resolved from the artifacts. */
function linkCategories(manifest: Manifest, research: ResearchSummary): Record<string, (href: string) => boolean> {
  const reportsOf = (kind: string) => {
    const ids = new Set(research.narrative_steps.filter((step) => step.kind === kind).flatMap((step) => step.experiment_ids));
    return new Set(
      research.experiments.filter((experiment) => ids.has(experiment.experiment_id)).map((experiment) => `${REPOSITORY_BLOB}${experiment.report_url}`),
    );
  };
  const controls = reportsOf("challenge");
  const replication = reportsOf("replication");
  const nullResult = reportsOf("null_result");
  const artifacts = new Set([
    ...research.experiments.map((experiment) => `${REPOSITORY_BLOB}${experiment.source_artifact}`),
    `${REPOSITORY_BLOB}${manifest.producer.config_path}`,
    `${SHOWCASE_BASE}manifest.json`,
    `${SHOWCASE_BASE}research-summary.json`,
  ]);
  for (const [name, set] of Object.entries({ controls, replication, nullResult })) {
    expect(set.size, `no ${name} experiment in the artifact`).toBeGreaterThan(0);
  }
  return {
    controls: (href) => controls.has(href),
    "external replication": (href) => replication.has(href),
    "null result": (href) => nullResult.has(href),
    "uncertainty method": (href) => href === `${REPOSITORY_BLOB}docs/uncertainty-method.md`,
    "data source": (href) => href === manifest.source.source_url,
    licence: (href) => href === manifest.source.licence_url,
    artifacts: (href) => artifacts.has(href),
    "decision records": (href) => href === `${REPOSITORY_BLOB}docs/decisions-log.md`,
  };
}

async function expectLinkCategories(page: Page, manifest: Manifest, research: ResearchSummary, context: string): Promise<void> {
  const hrefs = await page.evaluate(() =>
    [...document.querySelectorAll("main a[href]")].map((node) => node.getAttribute("href") ?? ""),
  );
  const missing = Object.entries(linkCategories(manifest, research))
    .filter(([, matches]) => !hrefs.some(matches))
    .map(([category]) => category);
  expect(missing, `${context}: /science has no direct link for`).toEqual([]);
}

test("the orientation is section 3's opening, and it precedes the first metric (AC2)", async ({ page, request }) => {
  const manifest = await fetchArtifact<Manifest>(request, "manifest.json");
  for (const width of [1280, 320]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/science/");
    await waitForStablePage(page);
    await expectOrientation(page, manifest, `${width} px`);
  }
});

test("the worked example is the featured artifact's, periods included (AC3)", async ({ page, request }) => {
  const manifest = await fetchArtifact<Manifest>(request, "manifest.json");
  const profile = await fetchArtifact<FeaturedProfile>(request, `players/${manifest.featured_profile.profile_key}.json`);
  const { global, baseline_role_minutes: baseline } = profile.retrieval;
  const interval = (outcome: Outcome) =>
    outcome.uncertainty.rank_ci_95 === null
      ? null
      : `${formatRank(outcome.uncertainty.rank_ci_95[0])}–${formatRank(outcome.uncertainty.rank_ci_95[1])}`;

  const expected: Record<string, string | null> = {
    "display-name": profile.identity.display_name,
    team: profile.identity.period_contexts.a.teams.map((team) => team.name).join(" / "),
    role: profile.identity.role,
    competition: profile.identity.competition.name,
    "period-a-label": profile.periods.a.label.toLowerCase(),
    "period-a-matches": String(profile.periods.a.match_count),
    "period-b-label": profile.periods.b.label.toLowerCase(),
    "period-b-matches": String(profile.periods.b.match_count),
    "self-rank": String(global.self_rank),
    "candidate-count": global.candidate_count.toLocaleString("en-US"),
    "baseline-self-rank": String(baseline.self_rank),
  };

  await page.goto("/science/");
  await waitForStablePage(page);
  const example = page.locator("main [data-worked-example]");
  for (const [key, value] of Object.entries(expected)) {
    await expect(example.locator(`[data-value="${key}"]`), `worked example ${key}`).toHaveText(value!);
  }
  for (const [key, outcome] of [
    ["self-rank-interval", global],
    ["baseline-self-rank-interval", baseline],
  ] as const) {
    const text = interval(outcome);
    if (text === null) {
      await expect(example.locator(`[data-value="${key}"]`), `${key} printed without an interval`).toHaveCount(0);
    } else {
      await expect(example.locator(`[data-value="${key}"]`), key).toContainText(text);
    }
  }
  // The example names both periods in words, not only through its values.
  await expect(example).toContainText("Period A");
  await expect(example).toContainText("period B");
});

test("every metric on the landing and /science opens its explanation (AC4)", async ({ page }) => {
  for (const route of ["/", "/science/"]) {
    await page.goto(route);
    await waitForStablePage(page);
    const rows = await page.evaluate(() =>
      [...document.querySelectorAll("main .experiment-metrics > div")].map((row) => ({
        label: row.querySelector("dt")?.textContent?.trim() ?? "",
        disclosures: row.querySelectorAll(":scope > dd.experiment-metric__explanation > details").length,
        summary: row.querySelector("dd.experiment-metric__explanation summary")?.textContent?.trim() ?? "",
        meaning: row.querySelector("dd.experiment-metric__explanation details > p:not(.experiment-metric__boundary)")?.textContent?.trim() ?? "",
        boundary: row.querySelector("dd.experiment-metric__explanation .experiment-metric__boundary")?.textContent?.trim() ?? "",
      })),
    );
    expect(rows.length, `${route} renders no metric`).toBeGreaterThan(0);
    const unexplained = rows
      .filter((row) => row.disclosures !== 1 || row.summary !== "What this means" || row.meaning.length < 20 || row.boundary.length < 20)
      .map((row) => row.label);
    expect(unexplained, `${route} metrics without their explanation`).toEqual([]);
  }
});

test("the claim, the historical label, the confound and the not-recruitment boundary need no expanding (AC5)", async ({
  page,
  request,
}) => {
  const research = await fetchArtifact<ResearchSummary>(request, "research-summary.json");
  for (const width of [320, 1280]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/science/");
    await waitForStablePage(page);
    await expectBoundariesShown(page, research, `${width} px`);
  }
});

test("every link category a reader needs is one click from /science (AC6)", async ({ page, request }) => {
  const [manifest, research] = await Promise.all([
    fetchArtifact<Manifest>(request, "manifest.json"),
    fetchArtifact<ResearchSummary>(request, "research-summary.json"),
  ]);
  await page.goto("/science/");
  await waitForStablePage(page);
  await expectLinkCategories(page, manifest, research, "with JavaScript");
  // The decision log the new link names is the repository's own file.
  expect(existsSync(join(REPOSITORY_ROOT, "docs", "decisions-log.md"))).toBe(true);
});

test.describe("before hydration", () => {
  test.use({ javaScriptEnabled: false });

  test("the orientation, the boundaries and every link category are in the served HTML", async ({ page, request }) => {
    const [manifest, research] = await Promise.all([
      fetchArtifact<Manifest>(request, "manifest.json"),
      fetchArtifact<ResearchSummary>(request, "research-summary.json"),
    ]);
    await page.goto("/science/");
    await expectOrientation(page, manifest, "no JavaScript");
    await expectBoundariesShown(page, research, "no JavaScript");
    await expectLinkCategories(page, manifest, research, "no JavaScript");
  });
});
