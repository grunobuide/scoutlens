import { readdir, readFile } from "node:fs/promises";
import { existsSync, readFileSync } from "node:fs";
import { join, relative, resolve } from "node:path";
import { describe, expect, it } from "vitest";

import type {
  FeatureCatalogArtifact,
  PlayerProfileArtifact,
  ResearchSummaryArtifact,
} from "@/contracts/generated/showcase-v2";
import {
  ExplanationNotFoundError,
  explainCaveat,
  explainEvidence,
  explainFamily,
  explainFeature,
  explainMetric,
  explainQuantity,
  experimentOverrideKeys,
  familyExplanationKeys,
  metricExplanationKeys,
  quantityExplanationKeys,
  scoreQuantity,
  type EvidenceExplanation,
} from "@/content/evidence-explanations";
import { describeLabError, formatContribution, formatScore } from "@/content/showcase-lab";
import { formatMetric, formatMetricInterval } from "@/content/showcase-story";

// `scoutlens-9a3.19`: the catalog is tested against the dataset the site
// serves, which is the one the payload pin names. It read `public/showcase/v1`
// while production served v2, so a v2-only metric could have shipped with no
// explainer and this file would have stayed green.
const REPO_ROOT = resolve(__dirname, "..", "..");
const PIN = JSON.parse(readFileSync(resolve(REPO_ROOT, "config", "showcase-payload-pack.json"), "utf8")) as {
  schema_version: string;
};
const PINNED_MAJOR = Number(PIN.schema_version.split(".")[0]);
const PUBLISHED_ROOT = resolve(REPO_ROOT, "public", "showcase", `v${PINNED_MAJOR}`);

const FORBIDDEN_LANGUAGE = [
  "is a recommendation",
  "recommends this player",
  "recommended signing",
  "replacement for",
  "best match",
  "top prospect",
  "better player",
  "quality score",
  "talent grade",
  "style dna",
  "unique identifier",
  "live data",
  "current season",
];

async function readJson<T>(path: string): Promise<T> {
  return JSON.parse(await readFile(resolve(PUBLISHED_ROOT, path), "utf8")) as T;
}

const loadResearch = () => readJson<ResearchSummaryArtifact>("research-summary.json");
const loadCatalog = () => readJson<FeatureCatalogArtifact>("feature-catalog.json");

/**
 * The featured profile of the pinned dataset. Player files are not committed;
 * a clone hydrates them (`python -m scoutlens.showcase.payload hydrate`), as CI
 * does before this suite runs.
 */
async function loadFeaturedProfile(): Promise<PlayerProfileArtifact> {
  const manifest = await readJson<{ featured_profile: { profile_key: string } }>("manifest.json");
  const path = join("players", `${manifest.featured_profile.profile_key}.json`);
  if (!existsSync(resolve(PUBLISHED_ROOT, path))) {
    throw new Error(`${path} is not hydrated; run: uv run --frozen python -m scoutlens.showcase.payload hydrate`);
  }
  return readJson<PlayerProfileArtifact>(path);
}

function prose(explanation: EvidenceExplanation): string {
  return [
    explanation.plain_meaning,
    explanation.calculation_summary,
    explanation.scale_direction,
    explanation.interpretation_boundary,
  ].join(" ");
}

function expectNoForbiddenLanguage(key: string, copy: string): void {
  const denial = /\b(not|never|no |no\.|isn't|doesn't|won't|cannot|can't)\b/;
  for (const sentence of copy.toLocaleLowerCase("en").split(/(?<=[.!?])\s+/)) {
    for (const forbidden of FORBIDDEN_LANGUAGE) {
      if (!denial.test(sentence) && sentence.includes(forbidden)) {
        throw new Error(`${key} affirmatively claims "${forbidden}" in: ${sentence.trim().slice(0, 120)}`);
      }
    }
  }
}

/** GitHub's heading anchor: lower case, punctuation dropped, spaces to hyphens. */
function githubSlug(heading: string): string {
  return heading
    .trim()
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s-]/gu, "")
    .replace(/\s/g, "-");
}

function expectSourceResolves(key: string, link: string): void {
  const [path, fragment] = link.split("#", 2);
  const file = resolve(REPO_ROOT, path ?? link);
  expect(existsSync(file), `${key} cites ${path}, which does not exist`).toBe(true);
  if (fragment !== undefined) {
    const anchors = readFileSync(file, "utf8")
      .split(/\r?\n/)
      .filter((line) => /^#{1,6}\s/.test(line))
      .map((line) => githubSlug(line.replace(/^#{1,6}\s/, "")));
    expect(anchors, `${key} cites #${fragment}, which is no heading in ${path}`).toContain(fragment);
  }
}

describe("scoutlens-9a3.2 evidence explanation catalog", () => {
  it("tests the dataset the payload pin names", async () => {
    const research = await loadResearch();
    expect(Number(research.schema_version.split(".")[0])).toBe(PINNED_MAJOR);
  });

  it("explains every metric rendered from production research experiments", async () => {
    const research = await loadResearch();
    const metrics = research.experiments.flatMap((experiment) => experiment.metrics);
    const missing: string[] = [];
    for (const metric of metrics) {
      try {
        const explanation = explainMetric(metric);
        expect(explanation.key).toBe(metric.metric_id);
        expect(explanation.plain_meaning.length).toBeGreaterThan(20);
        expect(explanation.calculation_summary.length).toBeGreaterThan(20);
        expect(explanation.scale_direction.length).toBeGreaterThan(10);
        expect(explanation.interpretation_boundary.length).toBeGreaterThan(20);
        expect(explanation.source_link.length).toBeGreaterThan(5);
      } catch (error) {
        missing.push(error instanceof Error ? error.message : String(error));
      }
    }
    expect(missing).toEqual([]);
    expect(new Set(metrics.map((metric) => metric.metric_id)).size).toBeGreaterThanOrEqual(11);
  });

  it("has no orphan metric explainers beyond the production metrics", async () => {
    const research = await loadResearch();
    const produced = new Set(
      research.experiments.flatMap((experiment) => experiment.metrics.map((metric) => metric.metric_id)),
    );
    const orphan = metricExplanationKeys().filter((key) => !produced.has(key));
    expect(orphan).toEqual([]);
  });

  it("has no duplicate explanation keys", () => {
    for (const keys of [metricExplanationKeys(), quantityExplanationKeys(), familyExplanationKeys()]) {
      expect(new Set(keys).size).toBe(keys.length);
    }
  });

  it("fails closed for an unknown metric id", () => {
    expect(() => explainMetric({ metric_id: "no_such_metric" })).toThrow(ExplanationNotFoundError);
    expect(() => explainMetric({ metric_id: "no_such_metric" })).toThrow(/No explanation for required metric id/);
  });

  it("keeps explanations free of forbidden recommendation, quality and currentness language", () => {
    for (const key of metricExplanationKeys()) {
      expectNoForbiddenLanguage(key, prose(explainMetric({ metric_id: key })));
    }
    for (const key of quantityExplanationKeys()) {
      expectNoForbiddenLanguage(key, prose(explainQuantity(key)));
    }
    for (const key of familyExplanationKeys()) {
      expectNoForbiddenLanguage(key, explainFamily(key).plain_meaning);
    }
  });

  it("cites a source that exists, down to the heading, for every metric and quantity", () => {
    for (const key of metricExplanationKeys()) {
      expectSourceResolves(key, explainMetric({ metric_id: key }).source_link);
    }
    for (const key of quantityExplanationKeys()) {
      expectSourceResolves(key, explainQuantity(key).source_link);
    }
  });

  it("explains every feature through the catalog without inventing meaning", async () => {
    const catalog = await loadCatalog();
    const missing: string[] = [];
    for (const feature of catalog.features) {
      try {
        const explanation = explainFeature(catalog, feature.feature_id);
        expect(explanation.key).toBe(feature.feature_id);
        // The artifact's own label, short label and unit, not ones derived
        // from the id (9a3.2 AC2).
        expect(explanation.label).toBe(feature.label);
        expect(explanation.short_label).toBe(feature.short_label);
        expect(explanation.unit).toBe(feature.unit);
        expect(explanation.plain_meaning).toBe(feature.description);
        expect(explanation.interpretation_boundary.length).toBeGreaterThan(20);
        expect(explanation.scale_direction).not.toMatch(/higher is better|lower is better/i);
        expect(explanation.source_link).toBe(feature.method_ref);
        expectSourceResolves(feature.feature_id, feature.method_ref);
      } catch (error) {
        missing.push(error instanceof Error ? error.message : String(error));
      }
    }
    expect(missing).toEqual([]);
  });

  it("explains each metric as its own experiment computed it (scoutlens-9a3.25)", async () => {
    // One metric id names different computations: `fingerprint_mrr` is the
    // Wyscout global test, the role-restricted test and the StatsBomb
    // replication. Each card's explanation must fit its experiment.
    const research = await loadResearch();
    const problems: string[] = [];
    for (const experiment of research.experiments) {
      const restricted = /restricted to/i.test(experiment.population);
      for (const metric of experiment.metrics) {
        const text = prose(explainMetric(metric, experiment.experiment_id));
        const where = `${experiment.experiment_id}:${metric.metric_id}`;
        if (experiment.provider === "statsbomb_open_data" && /wyscout/i.test(text)) {
          problems.push(`${where} is explained with Wyscout's data`);
        }
        if (restricted && /every eligible profile/i.test(text)) {
          problems.push(`${where} says every eligible profile, but candidates are restricted to role`);
        }
        if (restricted && metric.metric_id === "fingerprint_mrr" && !/role/i.test(text)) {
          problems.push(`${where} does not say candidates are restricted to role`);
        }
      }
    }
    expect(problems).toEqual([]);
  });

  it("has no override for an experiment and metric the artifact does not publish", async () => {
    const research = await loadResearch();
    const published = new Set(
      research.experiments.flatMap((experiment) =>
        experiment.metrics.map((metric) => `${experiment.experiment_id}:${metric.metric_id}`),
      ),
    );
    expect(experimentOverrideKeys().length).toBeGreaterThan(0);
    expect(experimentOverrideKeys().filter((key) => !published.has(key))).toEqual([]);
  });

  it("types no feature count into any explanation (scoutlens-9a3.25)", async () => {
    // The count is the artifact's - the metric label and the manifest carry it.
    // The registry said "32-feature" on cards whose experiment used 28.
    const research = await loadResearch();
    const texts = [
      ...research.experiments.flatMap((experiment) =>
        experiment.metrics.map((metric) => prose(explainMetric(metric, experiment.experiment_id))),
      ),
      ...quantityExplanationKeys().map((key) => prose(explainQuantity(key))),
    ];
    for (const text of texts) {
      expect(text).not.toMatch(/\b\d+(-feature|\s+(features|measurements|standardized))\b/i);
    }
  });

  it("fails closed for an unknown feature id", async () => {
    const catalog = await loadCatalog();
    expect(() => explainFeature(catalog, "no_such_feature")).toThrow(ExplanationNotFoundError);
    expect(() => explainFeature(catalog, "no_such_feature")).toThrow(/No catalog definition/);
  });
});

describe("scoutlens-9a3.19 per-profile quantities on /lab and in the challenge", () => {
  it("gives every quantity a term and all five parts", () => {
    for (const key of quantityExplanationKeys()) {
      const explanation = explainQuantity(key);
      expect(explanation.key).toBe(key);
      expect(explanation.scope).toBe("quantity");
      expect(explanation.term.length).toBeGreaterThan(2);
      expect(explanation.plain_meaning.length).toBeGreaterThan(20);
      expect(explanation.calculation_summary.length).toBeGreaterThan(10);
      expect(explanation.scale_direction.length).toBeGreaterThan(10);
      expect(explanation.interpretation_boundary.length).toBeGreaterThan(20);
    }
  });

  it("fails closed for an unknown quantity id", () => {
    expect(() => explainQuantity("no_such_quantity")).toThrow(ExplanationNotFoundError);
    // An inherited property is not an explanation.
    expect(() => explainQuantity("toString")).toThrow(ExplanationNotFoundError);
  });

  it("never explains the v2 score as a cosine (D047)", () => {
    const weighted = explainQuantity(scoreQuantity(2));
    expect(`${weighted.term} ${prose(weighted)}`).not.toMatch(/cosine/i);
    expect(explainQuantity(scoreQuantity(1)).term).toBe("Cosine");
  });

  it("has no orphan quantity: every one is printed by a component or is a major's score", async () => {
    const componentDir = resolve(__dirname, "..", "src", "components");
    const sources = await Promise.all(
      (await readdir(componentDir)).filter((name) => name.endsWith(".tsx")).map((name) =>
        readFile(join(componentDir, name), "utf8"),
      ),
    );
    const quoted = new Set([...sources.join("\n").matchAll(/"([a-z0-9_]+)"/g)].map((match) => match[1]));
    const reachable = new Set<string>([scoreQuantity(1), scoreQuantity(2)]);
    const orphan = quantityExplanationKeys().filter((key) => !quoted.has(key) && !reachable.has(key));
    expect(orphan).toEqual([]);
  });

  it("explains exactly the families the catalog files its features under", async () => {
    const catalog = await loadCatalog();
    expect(new Set(familyExplanationKeys())).toEqual(new Set(catalog.features.map((feature) => feature.family)));
    for (const key of familyExplanationKeys()) {
      expect(explainFamily(key).label.length).toBeGreaterThan(3);
      expect(explainFamily(key).plain_meaning.length).toBeGreaterThan(20);
    }
    expect(() => explainFamily("no_such_family")).toThrow(ExplanationNotFoundError);
  });

  it("resolves every evidence item of the featured profile to catalog labels", async () => {
    const [catalog, profile] = await Promise.all([loadCatalog(), loadFeaturedProfile()]);
    const items = profile.evidence_index;
    expect(items.length).toBeGreaterThan(40);
    for (const item of items) {
      const labels = explainEvidence(catalog.features, item);
      expect(labels.key).toBe(item.evidence_id);
      expect(labels.family_label).toBe(explainFamily(item.family).label);
      if (item.kind === "feature_contribution") {
        expect(labels.label).toBe(catalog.features.find((feature) => feature.feature_id === item.feature_id)?.label);
        expect(labels.label).not.toBe(item.feature_id);
      }
    }
  });

  it("refuses evidence the catalog cannot vouch for", async () => {
    const [catalog, profile] = await Promise.all([loadCatalog(), loadFeaturedProfile()]);
    const feature = profile.evidence_index.find((item) => item.kind === "feature_contribution");
    if (feature === undefined) {
      throw new Error("The featured profile has no feature evidence");
    }
    const otherFamily = familyExplanationKeys().find((family) => family !== feature.family)!;
    expect(() => explainEvidence(catalog.features, { ...feature, feature_id: "no_such_feature" })).toThrow(
      ExplanationNotFoundError,
    );
    expect(() => explainEvidence(catalog.features, { ...feature, feature_id: null })).toThrow(ExplanationNotFoundError);
    expect(() => explainEvidence(catalog.features, { ...feature, family: otherFamily })).toThrow(/the catalog files it/);
  });

  it("resolves a required caveat to the artifact's own message, and refuses a missing one", async () => {
    const profile = await loadFeaturedProfile();
    for (const caveat of profile.caveats) {
      expect(explainCaveat(profile.caveats, caveat.code)).toBe(caveat);
    }
    let thrown: unknown = null;
    try {
      explainCaveat(profile.caveats, "no_such_caveat");
    } catch (error) {
      thrown = error;
    }
    expect(thrown).toBeInstanceOf(ExplanationNotFoundError);
    // And the Lab shows its incompatible-data panel for it, not a blank page.
    expect(describeLabError(thrown).kind).toBe("incompatible-data");
  });
});

describe("no published number is retyped into page, component or registry source", () => {
  /**
   * Every value the pinned dataset publishes for the research summary and the
   * featured profile, formatted the way a surface prints it. Derived, not
   * listed: the hand-kept list this replaces held four numbers.
   *
   * Only literals with four or more digits are kept - `1` or `2.5` would match
   * any source file - and a value that rounds to all zeros carries no result.
   */
  async function publishedLiterals(): Promise<Map<string, string>> {
    const [research, profile] = await Promise.all([loadResearch(), loadFeaturedProfile()]);
    const literals = new Map<string, string>();
    const add = (printed: string, origin: string) => {
      // The magnitude is what a retyped copy would contain; its sign may be
      // written as +, - or the typographic minus.
      const literal = printed.replace(/^[+\-−]/, "");
      const digits = literal.replace(/\D/g, "");
      if (digits.length >= 4 && /[1-9]/.test(digits)) {
        literals.set(literal, origin);
      }
    };
    for (const experiment of research.experiments) {
      for (const metric of experiment.metrics) {
        add(formatMetric(metric), `${experiment.experiment_id}.${metric.metric_id}`);
        for (const bound of formatMetricInterval(metric)?.split(" to ") ?? []) {
          add(bound, `${experiment.experiment_id}.${metric.metric_id} interval`);
        }
      }
    }
    for (const [scope, outcome] of Object.entries(profile.retrieval).filter(
      (entry): entry is [string, PlayerProfileArtifact["retrieval"]["global"]] =>
        typeof entry[1] === "object" && entry[1] !== null && "self_rank" in entry[1],
    )) {
      add(outcome.reciprocal_rank.toFixed(4), `retrieval.${scope}.reciprocal_rank`);
      add(outcome.candidate_count.toLocaleString("en-US"), `retrieval.${scope}.candidate_count`);
      add(String(outcome.candidate_count), `retrieval.${scope}.candidate_count`);
      if (outcome.similarity_score !== null) {
        add(formatScore(outcome.similarity_score), `retrieval.${scope}.similarity_score`);
        add(outcome.similarity_score.toFixed(3), `retrieval.${scope}.similarity_score`);
      }
    }
    // `scoutlens-9a3.20`: the population's season and eligibility threshold.
    // The Lab's catalog heading had both typed in ("2017/18 · at least 450
    // minutes") and this scan missed them: the season was not in the set and
    // a bare three-digit number is too short to scan for. The threshold is
    // therefore scanned as the phrase a surface would print around it.
    const manifest = await readJson<{
      source: { season: string };
      population: { minutes_threshold_per_period: number };
    }>("manifest.json");
    add(manifest.source.season, "manifest.source.season");
    const threshold = manifest.population.minutes_threshold_per_period;
    for (const phrase of [`${threshold} minutes`, `${threshold} min`, `${threshold}-minute`]) {
      literals.set(phrase, "manifest.population.minutes_threshold_per_period");
    }
    // `scoutlens-9a3.25`: the measurement count and the resample count, as
    // copy prints them around the number ("the same 32 event-derived
    // measurements", "500 match-bootstrap resamples"). Both were typed in.
    const features = (await readJson<{ population: { feature_count: number } }>("manifest.json")).population
      .feature_count;
    for (const phrase of [
      `${features} measurements`,
      `${features}-feature`,
      `${features} standardized`,
      `${features} displayed`,
      `${features} event-derived`,
    ]) {
      literals.set(phrase, "manifest.population.feature_count");
    }
    const resamples = profile.uncertainty.requested_resamples;
    if (resamples !== null) {
      for (const phrase of [`${resamples} match-bootstrap`, `${resamples} resamples`, `${resamples} replicates`]) {
        literals.set(phrase, "profile.uncertainty.requested_resamples");
      }
    }
    // `scoutlens-9a3.32`: the small published integers - median ranks, the
    // transferred-player counts, the featured profile's ranks - are too short
    // to scan for bare, so, like the threshold, they are scanned as the
    // phrases copy prints around them.
    for (const experiment of research.experiments) {
      for (const metric of experiment.metrics) {
        if (metric.display_precision !== 0) {
          continue;
        }
        const printed = formatMetric(metric);
        const phrases =
          metric.metric_id === "median_rank"
            ? [`median rank ${printed}`, `median rank of ${printed}`, `median self-rank ${printed}`, `median self-rank of ${printed}`]
            : [`${printed} players`, `${printed} transferred`, `${printed} transfers`];
        for (const phrase of phrases) {
          literals.set(phrase, `${experiment.experiment_id}.${metric.metric_id}`);
        }
      }
    }
    for (const [scope, outcome] of Object.entries(profile.retrieval).filter(
      (entry): entry is [string, PlayerProfileArtifact["retrieval"]["global"]] =>
        typeof entry[1] === "object" && entry[1] !== null && "self_rank" in entry[1],
    )) {
      for (const phrase of [`rank ${outcome.self_rank} of`, `ranked ${outcome.self_rank}`, `ranked them ${outcome.self_rank}`]) {
        literals.set(phrase, `retrieval.${scope}.self_rank`);
      }
    }
    for (const neighbor of profile.neighbors) {
      add(formatScore(neighbor.similarity_score), `neighbor ${neighbor.rank} similarity_score`);
    }
    for (const item of profile.evidence_index) {
      add(formatContribution(item.weighted_contribution), `${item.evidence_id} weighted_contribution`);
      add(item.weighted_contribution.toFixed(3), `${item.evidence_id} weighted_contribution`);
      if (item.feature_weight !== null) {
        add(item.feature_weight.toFixed(3), `${item.evidence_id} feature_weight`);
      }
    }
    return literals;
  }

  async function sourceFiles(directory: string, pattern: RegExp): Promise<string[]> {
    const entries = await readdir(directory, { withFileTypes: true, recursive: true });
    return entries
      .filter((entry) => entry.isFile() && pattern.test(entry.name))
      .map((entry) => join(entry.parentPath, entry.name));
  }

  it("derives a non-trivial literal set from the pinned artifacts", async () => {
    // Non-vacuous: if the derivation broke, an empty set would pass the scan.
    expect((await publishedLiterals()).size).toBeGreaterThan(50);
  });

  it("finds none of them in src/app, src/components or src/content", async () => {
    const literals = await publishedLiterals();
    const src = resolve(__dirname, "..", "src");
    const files = [
      ...(await sourceFiles(join(src, "app"), /\.tsx?$/)),
      ...(await sourceFiles(join(src, "components"), /\.tsx?$/)),
      ...(await sourceFiles(join(src, "content"), /\.ts$/)),
    ];
    expect(files.map((file) => relative(src, file).replaceAll("\\", "/"))).toEqual(
      expect.arrayContaining([
        "components/lab-explorer.tsx",
        "components/neighbor-comparison-drawer.tsx",
        "components/identity-challenge-states.tsx",
        "components/quantity-glossary.tsx",
        "content/evidence-explanations.ts",
      ]),
    );
    const found: string[] = [];
    for (const file of files) {
      // Comment lines are dropped: they are never rendered, and they often cite
      // a measured value to explain a decision (page.tsx names the population
      // its comparison is drawn from). Code, copy and metadata are scanned.
      const source = (await readFile(file, "utf8"))
        // Block comments whole - a JSX `{/* ... */}` comment's inner lines do
        // not start with a comment marker, so the line filter below misses them.
        .replace(/\/\*[\s\S]*?\*\//g, "")
        .split(/\r?\n/)
        .filter((line) => !/^\s*(\/\/|\/\*|\*)/.test(line))
        .join("\n")
        // JSX wraps copy across lines, so "the same 32" and "event-derived"
        // can sit on two; the reader sees one space.
        .replace(/\s+/g, " ");
      for (const [literal, origin] of literals) {
        // Bounded by non-digits, so 0.2539 does not hit inside 10.25391.
        if (new RegExp(`(?<![\\d.])${literal.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?!\\d)`).test(source)) {
          found.push(`${relative(src, file)} repeats ${literal} (${origin})`);
        }
      }
    }
    expect(found).toEqual([]);
  });
});
