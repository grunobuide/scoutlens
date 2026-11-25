/**
 * The landing hero of the redesign (`scoutlens-rdz.8`, D075, D076).
 *
 * Content assertions, so they run once in desktop Chromium, like
 * `claims-consistency.spec.ts`. Every expected value comes from the narrative
 * document on disk or from the artifact the site serves, never from a literal
 * here: a typed "32" or "#20" in this file could agree with a typed one in the
 * page and prove nothing.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type APIRequestContext } from "@playwright/test";

import { SHOWCASE_BASE, waitForStablePage } from "./helpers";

const REPOSITORY_ROOT = join(__dirname, "..", "..");

interface Manifest {
  featured_profile: { profile_key: string; reason: string };
  population: { feature_count: number };
  source: { season: string };
}

interface RetrievalOutcome {
  candidate_count: number;
  self_rank: number;
}

interface Profile {
  identity: { display_name: string; role: string; season: string };
  retrieval: { global: RetrievalOutcome; baseline_role_minutes: RetrievalOutcome };
}

async function fetchArtifact<T>(request: APIRequestContext, file: string): Promise<T> {
  const response = await request.get(`${SHOWCASE_BASE}${file}`);
  expect(response.ok(), `${SHOWCASE_BASE}${file} is not served`).toBe(true);
  return (await response.json()) as T;
}

/**
 * The narrative's §6.3 CTAs, read from the document: each numbered item's
 * quoted label and the route after its arrow, for items 1 and 2.
 */
function frozenCtas(): Array<{ label: string; href: string }> {
  const lines = readFileSync(join(REPOSITORY_ROOT, "docs", "public-experience-narrative.md"), "utf8").split(/\r?\n/);
  const start = lines.findIndex((line) => line.startsWith("### 6.3 Call-to-action order (frozen)"));
  expect(start, "the narrative has no section 6.3").toBeGreaterThan(-1);
  const ctas: Array<{ label: string; href: string }> = [];
  for (const line of lines.slice(start + 1)) {
    if (line.startsWith("### ") || line.startsWith("## ")) {
      break;
    }
    const [, label, href] = line.match(/^[12]\. \*\*(?:Primary|Secondary):\*\* "([^"]+)" → `([^`]+)`/) ?? [];
    if (label !== undefined && href !== undefined) {
      ctas.push({ label, href });
    }
  }
  expect(ctas, "section 6.3 no longer names a primary and a secondary CTA").toHaveLength(2);
  return ctas;
}

const withSlash = (href: string) => (href.endsWith("/") ? href : `${href}/`);

test.beforeEach(async ({}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "content assertions run once in desktop Chromium");
});

test("the hero's two CTAs are the narrative's §6.3 labels, in that order", async ({ page }) => {
  // D075: the secondary CTA read "Audit the science" from 2026-07-28 until
  // `scoutlens-rdz.8`, though §6.3 froze "How the science was checked" on
  // 2026-08-06; no test pinned either label, so nothing failed.
  await page.goto("/");
  await waitForStablePage(page);

  const links = page.locator("main .hero .actions a");
  const expected = frozenCtas();
  await expect(links, "the hero renders a CTA count other than §6.3's two").toHaveCount(expected.length);
  for (const [index, cta] of expected.entries()) {
    await expect(links.nth(index)).toHaveText(cta.label);
    await expect(links.nth(index)).toHaveAttribute("href", withSlash(cta.href));
  }
});

test("the h1's number is the catalogue's length, and the manifest publishes the same count", async ({
  page,
  request,
}) => {
  // D075 reads the h1's number from `feature-catalog.json`; /science's
  // orientation reads `manifest.population.feature_count`
  // (`science-evidence-surface.spec.ts`). Two published sources for one
  // number: if they ever diverge, the landing and /science print different
  // counts, so this fails first.
  const catalog = await fetchArtifact<{ features: unknown[] }>(request, "feature-catalog.json");
  const manifest = await fetchArtifact<Manifest>(request, "manifest.json");
  expect(catalog.features.length, "catalogue length and manifest feature_count disagree").toBe(
    manifest.population.feature_count,
  );

  await page.goto("/");
  await expect(page.locator("main h1")).toHaveText(`Can ${catalog.features.length} numbers recognise a footballer?`);
});

test("only the chip, the eyebrow, the h1 and the line naming both halves sit above the thesis", async ({
  page,
  request,
}) => {
  const manifest = await fetchArtifact<Manifest>(request, "manifest.json");
  await page.goto("/");
  await waitForStablePage(page);

  // Narrative §7.1 item 1, as D075 amended it.
  const above = await page.locator("main .hero__copy").evaluate((copy) => {
    const children = [...copy.children];
    const thesis = children.findIndex((child) => child.hasAttribute("data-thesis"));
    return {
      thesis,
      before: children.slice(0, Math.max(thesis, 0)).map((child) => {
        if (child.hasAttribute("data-vintage-badge")) return "chip";
        if (child.matches("p.eyebrow")) return "eyebrow";
        if (child.matches("h1")) return "h1";
        if (child.matches("p.hero__halves")) return "halves";
        return `<${child.tagName.toLowerCase()} class="${child.className}">`;
      }),
    };
  });
  expect(above.thesis, "no thesis in the hero copy").toBeGreaterThan(-1);
  expect(above.before).toEqual(["chip", "eyebrow", "h1", "halves"]);

  // The line names both halves of the manifest's season.
  const halves = page.locator("main .hero__halves");
  await expect(halves).toContainText(manifest.source.season);
  await expect(halves).toContainText(/first half/);
  await expect(halves).toContainText(/second half/);
});

test("the proof card shows the featured profile's two ranks, read from its artifact", async ({
  page,
  request,
}) => {
  const manifest = await fetchArtifact<Manifest>(request, "manifest.json");
  const profile = await fetchArtifact<Profile>(request, `players/${manifest.featured_profile.profile_key}.json`);
  const { global: search, baseline_role_minutes: guess } = profile.retrieval;

  await page.goto("/");
  await waitForStablePage(page);

  // D076: the card's player is `manifest.featured_profile`, never one that
  // ranks better, and it is shown with its editorial reason.
  const card = page.locator("main .hero__signal .proof-card");
  await expect(card).toHaveCount(1);
  await expect(card.locator(".proof-card__name")).toHaveText(profile.identity.display_name);
  await expect(card.locator(".proof-card__reason")).toHaveText(manifest.featured_profile.reason);

  const searchRank = card.locator('[data-quantity="self_rank"]');
  await expect(searchRank.locator("strong")).toHaveText(`#${search.self_rank}`);
  await expect(searchRank).toContainText(`out of ${search.candidate_count.toLocaleString("en-US")}`);

  const guessRank = card.locator('[data-quantity="baseline_self_rank"]');
  await expect(guessRank.locator("strong")).toHaveText(`#${guess.self_rank}`);
  await expect(guessRank).toContainText(`out of ${guess.candidate_count.toLocaleString("en-US")}`);

  // Both ranks are explained inside the card itself.
  for (const id of ["self_rank", "baseline_self_rank"]) {
    await expect(card.locator(`[data-quantity-explainer="${id}"]`)).toHaveCount(1);
  }
});

test("the aside opens with the proof card, then the supported claim, then its confound", async ({ page }) => {
  await page.goto("/");
  await waitForStablePage(page);

  // D076 and narrative §7.1 item 2: the most anecdotal number on the landing
  // is never read without the population-level claim and the confound.
  const order = await page.locator("main .hero__signal").evaluate((aside) => {
    const all = [...aside.querySelectorAll("*")];
    const indexOf = (selector: string) => {
      const element = aside.querySelector(selector);
      return element === null ? -1 : all.indexOf(element);
    };
    return {
      card: indexOf(".proof-card"),
      claim: indexOf("[data-supported-claim]"),
      confound: indexOf(".signal-confound"),
    };
  });
  expect(order.card, "no proof card in the aside").toBeGreaterThan(-1);
  expect(order.card, "the proof card does not open the aside").toBeLessThan(order.claim);
  expect(order.claim, "the confound precedes the claim").toBeLessThan(order.confound);
});
