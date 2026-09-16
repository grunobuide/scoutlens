/**
 * Cross-route claim and value agreement (`scoutlens-9a3.7`, AC3 and AC4).
 *
 * **What this file is for.** `rendered-values.spec.ts` asserts known defect
 * classes on one route: a stale method name, an unrounded rank, a cosine label.
 * This file asserts something different and route-crossing — that the same
 * quantity says the same thing everywhere it appears, and that what it says
 * came out of the published artifact rather than out of a template.
 *
 * The distinction matters because the failure it guards is not a wrong number.
 * It is *two* numbers: a value correct on `/lab/` and stale on `/`, which no
 * single-route assertion can see, because each route is self-consistent. The
 * artifact is the tiebreaker — not one of the routes.
 *
 * **Why the artifact is fetched over HTTP rather than read from disk.** AC3
 * requires every displayed value to "originate in a versioned artifact". The
 * versioned artifact is the one the site actually serves under
 * `/showcase/v<major>/`, not the one in the repository working tree. Reading
 * `public/showcase/` from disk would pass while the site served a stale copy —
 * the exact class of staleness `scoutlens-uze.12` found sitting green for six
 * days.
 *
 * Runs once on `desktop`. These are content assertions; a viewport cannot
 * change whether two routes agree, and running them per project would buy
 * nothing for four times the wall-clock.
 */

import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type Page, type APIRequestContext } from "@playwright/test";

import { SHOWCASE_BASE, waitForStablePage } from "./helpers";

const REPOSITORY_ROOT = join(__dirname, "..", "..");

/** Routes that render provenance and claim surfaces. */
const ROUTES = ["/", "/science/", "/lab/"] as const;

interface Metric {
  metric_id: string;
  label: string;
  value: number;
  display_precision: number;
  ci_95: readonly [number, number] | null;
}

interface Experiment {
  experiment_id: string;
  title: string;
  report_url: string;
  metrics: readonly Metric[];
}

interface ResearchSummary {
  supported_claim: string;
  unsupported_claims: readonly string[];
  experiments: readonly Experiment[];
}

interface Manifest {
  dataset_version: string;
  source: { season: string; licence: string; licence_url: string; source_url: string };
}

test.beforeEach(async ({}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "content agreement runs once in desktop Chromium");
});

async function fetchArtifact<T>(request: APIRequestContext, file: string): Promise<T> {
  const response = await request.get(`${SHOWCASE_BASE}${file}`);
  expect(response.ok(), `${SHOWCASE_BASE}${file} is not served`).toBe(true);
  return (await response.json()) as T;
}

/** The published formatting rule, mirrored from `content/showcase-story.ts`. */
function formatMetric(metric: Metric): string {
  return metric.value.toFixed(metric.display_precision);
}

/**
 * Every metric on a route, keyed by the experiment that owns it.
 *
 * Reads the `dt`/`dd` pairing that `ExperimentCard` emits. The value carries
 * `.experiment-metric__value`; the interval and explanation `dd`s beside it are
 * deliberately not collected — the interval has its own assertion below and the
 * explanation is prose.
 *
 * **Keyed by experiment title *and* metric label, not by label alone.** A label
 * is not an identifier: "Role + minutes baseline MRR" belongs to both
 * `wyscout_global_gate2` (0.0256) and `statsbomb_global_replication` (0.0381),
 * and the landing page renders both. Keying by label called that legitimate
 * pair a contradiction — a false positive that would have made this gate
 * unusable on the first run. The identity of a rendered metric is the pair.
 */
async function readRenderedMetrics(page: Page): Promise<Map<string, string>> {
  const pairs = await page.evaluate(() =>
    [...document.querySelectorAll("main .experiment-card")].flatMap((card) => {
      const experiment = card.querySelector("h3")?.textContent?.trim() ?? "";
      return [...card.querySelectorAll(".experiment-metrics > div")].flatMap((row) => {
        const label = row.querySelector("dt")?.textContent?.trim();
        const value = row.querySelector("dd.experiment-metric__value")?.textContent?.trim();
        return label === undefined || value === undefined
          ? []
          : [[`${experiment} :: ${label}`, value] as const];
      });
    }),
  );

  const metrics = new Map<string, string>();
  for (const [key, value] of pairs) {
    const seen = metrics.get(key);
    // The same metric of the same experiment rendered twice with two values on
    // one route is a contradiction, before any cross-route comparison.
    expect(seen ?? value, `${key} renders two different values on one route`).toBe(value);
    metrics.set(key, value);
  }
  return metrics;
}

test("every rendered metric value matches the published artifact", async ({ page, request }) => {
  const research = await fetchArtifact<ResearchSummary>(request, "research-summary.json");

  const expected = new Map<string, string>();
  for (const experiment of research.experiments) {
    for (const metric of experiment.metrics) {
      expected.set(`${experiment.title} :: ${metric.label}`, formatMetric(metric));
    }
  }

  const mismatches: string[] = [];
  for (const route of ROUTES) {
    await page.goto(route);
    await waitForStablePage(page);

    for (const [key, rendered] of await readRenderedMetrics(page)) {
      const artifactValue = expected.get(key);
      if (artifactValue === undefined) {
        // A metric card the artifact does not define is a value with no
        // provenance - AC3's "originates in a versioned artifact".
        mismatches.push(`${route} renders ${key} = ${rendered}, absent from the artifact`);
        continue;
      }
      if (artifactValue !== rendered) {
        mismatches.push(`${route} renders ${key} = ${rendered}, artifact says ${artifactValue}`);
      }
    }
  }

  expect(mismatches, "rendered values disagree with the artifact").toEqual([]);
});

test("a metric shown on two routes shows the same value on both", async ({ page }) => {
  // The cross-route half of AC3, and the reason this file is not folded into
  // rendered-values. Each route can be internally consistent and still
  // contradict its neighbour; only comparing them catches that.
  const byRoute = new Map<string, Map<string, string>>();
  for (const route of ROUTES) {
    await page.goto(route);
    await waitForStablePage(page);
    byRoute.set(route, await readRenderedMetrics(page));
  }

  const conflicts: string[] = [];
  const everyKey = new Set([...byRoute.values()].flatMap((metrics) => [...metrics.keys()]));

  for (const key of everyKey) {
    const renderings = [...byRoute.entries()]
      .map(([route, metrics]) => ({ route, value: metrics.get(key) }))
      .filter((entry): entry is { route: string; value: string } => entry.value !== undefined);

    const distinct = new Set(renderings.map((entry) => entry.value));
    if (distinct.size > 1) {
      const detail = renderings.map((entry) => `${entry.route}=${entry.value}`).join(", ");
      conflicts.push(`${key} disagrees across routes: ${detail}`);
    }
  }

  expect(conflicts, "the same metric renders differently on different routes").toEqual([]);
});

test("every rendered confidence interval matches the artifact", async ({ page, request }) => {
  const research = await fetchArtifact<ResearchSummary>(request, "research-summary.json");

  const expected = new Set(
    research.experiments.flatMap((experiment) =>
      experiment.metrics
        .filter((metric) => metric.ci_95 !== null)
        .map((metric) => {
          const [low, high] = metric.ci_95 as readonly [number, number];
          const precision = metric.display_precision;
          return `95% CI: ${low.toFixed(precision)} to ${high.toFixed(precision)}`;
        }),
    ),
  );

  for (const route of ROUTES) {
    await page.goto(route);
    await waitForStablePage(page);

    const rendered = await page.evaluate(() =>
      [...document.querySelectorAll("main dd.experiment-metric__interval")].map((node) =>
        (node.textContent ?? "").replace(/\s+/g, " ").trim(),
      ),
    );

    for (const interval of rendered) {
      expect(
        [...expected],
        `${route} renders an interval the artifact does not define: ${interval}`,
      ).toContain(interval);
    }
  }
});

test("the supported and unsupported claims are the artifact's, verbatim", async ({ page, request }) => {
  const research = await fetchArtifact<ResearchSummary>(request, "research-summary.json");

  await page.goto("/");
  await waitForStablePage(page);
  const main = page.locator("main");

  // Verbatim, not "contains the gist". A claim boundary that has been reworded
  // in the template is a claim the artifact no longer backs, however similar it
  // reads - and Q2/Q4 of the comprehension checklist are scored against these
  // exact strings (docs/public-understanding-check.md section 3).
  //
  // `toContainText` rather than a one-shot innerText() for the same determinism
  // reason as the vintage test below: the matcher polls, a scrape does not.
  await expect(main, "the supported claim is not rendered verbatim").toContainText(
    research.supported_claim,
  );

  for (const claim of research.unsupported_claims) {
    await expect(main, `unsupported-claim boundary not rendered: ${claim}`).toContainText(claim);
  }
});

test("the data vintage is identical on every route that shows it", async ({ page, request }) => {
  const manifest = await fetchArtifact<Manifest>(request, "manifest.json");

  // Asserted per route against the manifest with auto-retrying matchers, rather
  // than scraped into an array and compared afterwards. Two reasons, and the
  // first was found the hard way:
  //
  // 1. `innerText()` is a one-shot read that depends on layout. Under parallel
  //    workers this file produced a single intermittent failure here while
  //    passing serially - a rendered-but-not-yet-laid-out badge reads as "".
  //    `toHaveText` polls until the timeout, so it cannot observe that state.
  //    The uze.6 stop condition is explicit that a test which cannot tell a
  //    regression from unstable timing gets made deterministic, not retried.
  // 2. Equality to a shared source is a stronger statement than equality to
  //    each other: three routes agreeing on a *stale* pin would satisfy
  //    "identical across routes" and fail this.
  let routesWithBadge = 0;

  for (const route of ROUTES) {
    await page.goto(route);
    await waitForStablePage(page);

    const badge = page.locator("[data-vintage-badge]");
    if ((await badge.count()) === 0) {
      continue;
    }
    routesWithBadge += 1;

    await expect(badge.locator(".data-vintage__season"), `${route} season`).toHaveText(
      manifest.source.season,
    );
    await expect(badge.locator(".data-vintage__licence"), `${route} licence`).toHaveText(
      manifest.source.licence,
    );
    await expect(badge.locator("code"), `${route} dataset pin`).toHaveText(
      manifest.dataset_version,
    );
  }

  expect(routesWithBadge, "no route renders a data-vintage badge").toBeGreaterThan(0);
});

test("source and licence links point where the artifact says", async ({ page, request }) => {
  const manifest = await fetchArtifact<Manifest>(request, "manifest.json");

  // Deliberately NOT a reachability check. Whether doi.org answers today is not
  // this project's regression to catch, and a gate that fails on someone else's
  // outage is the flakiness the uze.6 stop condition forbids. What is ours is
  // whether the href still agrees with the artifact it is citing.
  for (const route of ROUTES) {
    await page.goto(route);
    await waitForStablePage(page);

    const hrefs = await page.evaluate(() =>
      [...document.querySelectorAll("main a[href]")].map((node) => node.getAttribute("href") ?? ""),
    );
    if (hrefs.length === 0) {
      continue;
    }

    const external = hrefs.filter((href) => href.startsWith("http"));
    const citesSource = external.some((href) => href === manifest.source.source_url);
    const citesLicence = external.some((href) => href === manifest.source.licence_url);

    if (route === "/lab/") {
      continue; // The Lab links provenance through the shared boundary only.
    }
    expect(citesSource, `${route} does not link the artifact's source_url`).toBe(true);
    expect(citesLicence, `${route} does not link the artifact's licence_url`).toBe(true);
  }
});

/**
 * The four dead anchors this gate found on its first run, awaiting the bundle
 * repin in `scoutlens-jtt.17`.
 *
 * **Why an enumerated exception rather than a weakened assertion.** `report_url`
 * is published content: `builder.py` derives `dataset_version` from a content
 * digest over every artifact and stamps it into all of them, so correcting these
 * four strings repins the whole bundle — measured at 1,262 of 1,262 files
 * changed, zero byte-identical — and requires a new immutable release asset.
 * `scoutlens-jtt.7.1` (freeze the v1 RC) repins once; doing it here would repin
 * twice. `jtt.7.1` depends on `jtt.17`, so the RC cannot be frozen with these
 * still dead.
 *
 * The form follows the rule AC5 of `scoutlens-9a3.7` states for exceptions —
 * "evidence-linked and explicitly enumerated rather than regex-disabled
 * globally" — applied here to an AC4 assertion, because the reasoning is the
 * same and the project should have one shape for a waiver, not two. A *fifth*
 * dead anchor still fails. The verified replacements are recorded on `jtt.17`;
 * when the repin lands, this constant goes to empty and the test tightens with
 * no other edit.
 */
const KNOWN_DEAD_ANCHORS: readonly string[] = [
  "docs/gate-2-decision.md#wyscout-global-retrieval",
  "docs/robustness-checks.md#team-aware-baseline",
  "docs/statsbomb-replication.md#within-role-retrieval",
  "docs/statsbomb-replication.md#transferred-players",
];

test("the known dead anchors are still exactly the ones jtt.17 records", async ({ request }) => {
  // Guards the exception itself. Without this, the repin could land, the four
  // could be fixed, and KNOWN_DEAD_ANCHORS would silently go on excusing four
  // report_urls that no longer need excusing - turning a temporary waiver into
  // a permanent blind spot.
  const research = await fetchArtifact<ResearchSummary>(request, "research-summary.json");
  const published = new Set(research.experiments.map((experiment) => experiment.report_url));

  const stale = KNOWN_DEAD_ANCHORS.filter((entry) => !published.has(entry));
  expect(
    stale,
    "a waived report_url is no longer published - remove it from KNOWN_DEAD_ANCHORS",
  ).toEqual([]);
});

test("every method link points at a document that exists", async ({ request }) => {
  const research = await fetchArtifact<ResearchSummary>(request, "research-summary.json");

  // `report_url` is rendered as a GitHub blob URL, so it cannot be fetched
  // without leaving the sandbox. The regression worth catching is not GitHub
  // being down - it is a renamed or deleted document leaving a dead "Read
  // method" link behind. That is answerable from the repository itself, and
  // deterministically.
  const broken: string[] = [];
  for (const experiment of research.experiments) {
    if (KNOWN_DEAD_ANCHORS.includes(experiment.report_url)) {
      continue;
    }
    const [filePath, fragment] = experiment.report_url.split("#", 2);
    const absolute = join(REPOSITORY_ROOT, filePath ?? "");

    if (!existsSync(absolute)) {
      broken.push(`${experiment.experiment_id} -> ${experiment.report_url} (file missing)`);
      continue;
    }
    if (fragment === undefined) {
      continue;
    }

    // GitHub derives a heading anchor by lowercasing, dropping punctuation and
    // hyphenating spaces. Two variants are accepted because GitHub turns each
    // space into its own hyphen, so a heading containing an em dash ("Check 3 —
    // Baseline C") yields a doubled hyphen where a naive collapse yields one.
    // Being generous here is deliberate: a false positive blocks a release on a
    // normalization detail rather than on a dead link, and a dead link is still
    // caught because neither variant will match a heading that is not there.
    const headings = readFileSync(absolute, "utf8")
      .split("\n")
      .filter((line) => line.startsWith("#"))
      .map((line) =>
        line
          .replace(/^#+\s*/, "")
          .trim()
          .toLowerCase()
          .replace(/[^\w\s-]/g, ""),
      );
    const anchors = new Set([
      ...headings.map((heading) => heading.replace(/\s/g, "-")),
      ...headings.map((heading) => heading.replace(/\s+/g, "-")),
    ]);
    if (!anchors.has(fragment)) {
      broken.push(`${experiment.experiment_id} -> ${experiment.report_url} (anchor missing)`);
    }
  }

  expect(broken, "a method link points at a document or anchor that no longer exists").toEqual([]);
});

test.describe("without JavaScript", () => {
  test.use({ javaScriptEnabled: false });

  test("the thesis, vintage, claims and provenance survive the first paint", async ({
    page,
    request,
  }) => {
    // AC4. Everything a reader needs to not misread the project has to be in
    // the served HTML. A boundary that appears only after hydration is a
    // boundary the first paint does not have - and the comprehension checklist
    // is scored on what a reader sees, not on what eventually loads.
    const research = await fetchArtifact<ResearchSummary>(request, "research-summary.json");
    const manifest = await fetchArtifact<Manifest>(request, "manifest.json");

    await page.goto("/");
    const main = page.locator("main");

    await expect(main).toContainText("A player leaves a reproducible fingerprint");
    await expect(main).toContainText(research.supported_claim);
    for (const claim of research.unsupported_claims) {
      await expect(main).toContainText(claim);
    }

    const badge = page.locator("[data-vintage-badge]");
    await expect(badge).toContainText(manifest.source.season);
    await expect(badge).toContainText(manifest.source.licence);
    await expect(badge).toContainText(manifest.dataset_version);
  });

  test("the /science AI boundary survives the first paint", async ({ page }) => {
    await page.goto("/science/");
    const main = page.locator("main");

    // Q6 of the comprehension checklist is scored against this section. If it
    // needs hydration, a reviewer can answer "an AI made these numbers" from a
    // page that had not finished loading, and they would not be wrong to.
    await expect(main).toContainText("No live LLM is required for any current page");
    await expect(main).toContainText("AI never recomputes a value");
  });
});

/**
 * The hero's team-continuity confound (`scoutlens-9a3.13`).
 *
 * Run 1's reader answered "what is the strongest reason to doubt that result?"
 * with "it could be biased, too much data to check individual records" — they
 * took that *a* limit exists without reaching *which* one, though the hero
 * named a critical-severity confound and its number. The old sentence asked the
 * reader to already know what MRR is and what the fingerprint scores, then
 * assemble the comparison themselves.
 *
 * These assertions hold the shape of the repair, not the reader's understanding
 * of it. No element-read trace was captured in run 1, so which surface failed is
 * inference; under `D056` this lands without a fresh reviewer and claims no
 * comprehension improvement.
 */
test.describe("the team-continuity confound", () => {
  test("names the shortcut in plain language before any number", async ({ page }) => {
    await page.goto("/");
    await waitForStablePage(page);

    const caveat = page.locator(".signal-confound .signal-caveat");
    await expect(caveat).toContainText("most players stayed at the same club");
    await expect(caveat).toContainText("identifies them better than the fingerprint does");
    // The stop condition: the confound narrows the result, it does not retract it.
    await expect(caveat).toContainText("does not retract it");
  });

  test("states both sides of the comparison, from the artifact", async ({ page, request }) => {
    const research = await fetchArtifact<ResearchSummary>(request, "research-summary.json");
    const value = (experimentId: string, metricId: string) => {
      const experiment = research.experiments.find((item) => item.experiment_id === experimentId);
      const metric = experiment?.metrics.find((item) => item.metric_id === metricId);
      if (metric === undefined) {
        throw new Error(`artifact is missing ${experimentId}.${metricId}`);
      }
      return formatMetric(metric);
    };

    // Prose, not a metric tile, so the cross-route metric assertions above do not
    // reach it. The confound is only legible next to the number it beats, and a
    // hand-typed literal here would be the one place on the page a value could
    // drift from the artifact unnoticed.
    await page.goto("/");
    await waitForStablePage(page);

    const caveat = page.locator(".signal-confound .signal-caveat");
    await expect(caveat).toContainText(value("wyscout_role_team_minutes", "baseline_c_mrr"));
    await expect(caveat).toContainText(value("wyscout_global_gate2", "fingerprint_mrr"));
  });

  test("follows the supported claim and links to the control that produced it", async ({ page }) => {
    await page.goto("/");
    await waitForStablePage(page);

    const order = await page.evaluate(() => {
      const all = [...document.querySelectorAll("main *")];
      const indexOf = (selector: string) => {
        const element = document.querySelector(`main ${selector}`);
        return element === null ? -1 : all.indexOf(element);
      };
      return { claim: indexOf(".signal-copy"), caveat: indexOf(".signal-confound") };
    });
    expect(order.claim, "no supported claim in the hero").toBeGreaterThan(-1);
    expect(
      order.claim,
      "the confound precedes the claim it is supposed to narrow",
    ).toBeLessThan(order.caveat);

    const link = page.locator(".signal-confound a.signal-evidence");
    await expect(link).toHaveAttribute("href", "/science/#stage-03");

    // A link to an anchor that does not exist lands the reader at the top of a
    // 290-block page, which is how `scoutlens-jtt.17` went unnoticed.
    await page.goto("/science/");
    await expect(page.locator("#stage-03")).toHaveCount(1);
  });

  test("the evidence link meets the 44 px touch target", async ({ page }) => {
    // `scoutlens-uze.4` and `uze.6.5` each fixed this defect class after it
    // shipped. A new standalone link at 0.8rem is exactly that class, so it is
    // asserted here rather than found by the next audit.
    for (const width of [320, 360]) {
      await page.setViewportSize({ width, height: 900 });
      await page.goto("/");
      await waitForStablePage(page);

      const box = await page.locator(".signal-confound a.signal-evidence").boundingBox();
      expect(box, `no evidence link at ${width}`).not.toBeNull();
      expect(box?.height ?? 0, `evidence link hit area at ${width}`).toBeGreaterThanOrEqual(44);
    }
  });
});

/**
 * The hero's temporal framing (`scoutlens-9a3.14`).
 *
 * Run 1's reader answered "in one sentence, what does this site say it has
 * shown?" with "an experiment showing how a player can be identified by their
 * actions in the game" — graded PARTIAL, because the two chronological periods
 * dropped out. That is close to a paraphrase of the old `h1`, which ended at
 * "in the shape of their actions" and contained no time at all. The lede has
 * always carried the periods; the headline is what gets repeated back.
 *
 * So this guards the property, not the sentence: the headline must locate the
 * claim in time, and the lede must still name the same-player question and the
 * two halves. A future editor may rewrite either, but not back into a
 * time-free claim.
 */
test.describe("the hero's temporal framing", () => {
  test("the headline locates the claim in time", async ({ page }) => {
    await page.goto("/");
    await waitForStablePage(page);

    const heading = (await page.locator("main h1").innerText()).replace(/\s+/g, " ").trim();

    // Pattern, not the exact sentence. The regression is a headline with no
    // temporal relation in it, which is what run 1 read back.
    expect(
      /half a season|second half|later|two chronological halves|across two/i.test(heading),
      `the headline states no temporal relation: "${heading}"`,
    ).toBe(true);
  });

  test("the lede still names the same-player question and both periods", async ({ page }) => {
    await page.goto("/");
    await waitForStablePage(page);

    const lede = page.locator("main .lede");
    await expect(lede).toContainText("the same player");
    await expect(lede).toContainText("two chronological halves");
  });

  test("the headline precedes the lede, and the claim is still rendered once", async ({
    page,
    request,
  }) => {
    const research = await fetchArtifact<ResearchSummary>(request, "research-summary.json");

    await page.goto("/");
    await waitForStablePage(page);

    const order = await page.evaluate(() => {
      const all = [...document.querySelectorAll("main *")];
      const indexOf = (selector: string) => {
        const element = document.querySelector(`main ${selector}`);
        return element === null ? -1 : all.indexOf(element);
      };
      return { heading: indexOf("h1"), lede: indexOf(".lede"), boundary: indexOf(".hero__boundary") };
    });
    expect(order.heading, "no h1 in main").toBeGreaterThan(-1);
    expect(order.heading, "the lede precedes the headline").toBeLessThan(order.lede);
    expect(order.lede, "the claim boundary precedes the lede").toBeLessThan(order.boundary);

    // `scoutlens-9a3.12` removed the second rendering of the supported claim.
    // Editing the hero is exactly when it could come back, so the count is
    // asserted here rather than left to the earlier verbatim check, which only
    // proves the claim appears at least once.
    const occurrences = await page.evaluate((claim) => {
      const text = (document.querySelector("main")?.textContent ?? "").replace(/\s+/g, " ");
      return text.split(claim).length - 1;
    }, research.supported_claim.replace(/\s+/g, " "));
    expect(occurrences, "the supported claim is rendered more than once again").toBe(1);
  });
});
