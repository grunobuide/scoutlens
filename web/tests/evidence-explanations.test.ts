import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import type {
  FeatureCatalogArtifact,
  ResearchSummaryArtifact,
} from "@/contracts/generated/showcase";
import {
  explainFeature,
  explainMetric,
  metricExplanationKeys,
} from "@/content/evidence-explanations";

const PUBLISHED_ROOT = resolve("..", "public", "showcase", "v1");

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

const FORBIDDEN_NUMERIC_LITERALS = [
  "0.0256",
  "0.2539",
  "0.5893",
  "0.2031",
  "0.2083",
  "0.2479",
  "1,257",
  "1257",
];

async function loadResearch(): Promise<ResearchSummaryArtifact> {
  return JSON.parse(await readFile(resolve(PUBLISHED_ROOT, "research-summary.json"), "utf8")) as ResearchSummaryArtifact;
}

async function loadCatalog(): Promise<FeatureCatalogArtifact> {
  return JSON.parse(await readFile(resolve(PUBLISHED_ROOT, "feature-catalog.json"), "utf8")) as FeatureCatalogArtifact;
}

describe("scoutlens-9a3.2 evidence explanation catalog", () => {
  it("explains every metric rendered from production research experiments", async () => {
    const research = await loadResearch();
    const renderedMetricIds = new Set<string>();
    for (const experiment of research.experiments) {
      for (const metric of experiment.metrics) {
        renderedMetricIds.add(metric.metric_id);
      }
    }
    const missing: string[] = [];
    for (const metricId of renderedMetricIds) {
      const metric = research.experiments
        .flatMap((experiment) => experiment.metrics)
        .find((candidate) => candidate.metric_id === metricId);
      if (metric === undefined) {
        throw new Error(`Metric ${metricId} not found anywhere in research summary`);
      }
      try {
        const explanation = explainMetric(metric);
        expect(explanation.key).toBe(metricId);
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
    expect(renderedMetricIds.size).toBeGreaterThanOrEqual(11);
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
    const keys = metricExplanationKeys();
    expect(new Set(keys).size).toBe(keys.length);
  });

  it("keeps explanations free of forbidden recommendation, quality and currentness language", async () => {
    const research = await loadResearch();
    const denial = /\b(not|never|no |no\.|isn't|doesn't|won't|cannot|can't)\b/;
    for (const key of metricExplanationKeys()) {
      const metric = research.experiments
        .flatMap((experiment) => experiment.metrics)
        .find((candidate) => candidate.metric_id === key);
      if (metric === undefined) {
        throw new Error(`Missing metric ${key}`);
      }
      const explanation = explainMetric(metric);
      const copy = [
        explanation.plain_meaning,
        explanation.calculation_summary,
        explanation.scale_direction,
        explanation.interpretation_boundary,
      ]
        .join(" ")
        .toLocaleLowerCase("en");
      for (const forbidden of FORBIDDEN_LANGUAGE) {
        for (const sentence of copy.split(/(?<=[.!?])\s+/)) {
          if (!denial.test(sentence) && sentence.includes(forbidden)) {
            throw new Error(`${key} affirmatively claims "${forbidden}" in: ${sentence.trim().slice(0, 120)}`);
          }
        }
      }
    }
  });

  it("does not duplicate numeric result literals in explanation copy", async () => {
    const research = await loadResearch();
    for (const key of metricExplanationKeys()) {
      const metric = research.experiments
        .flatMap((experiment) => experiment.metrics)
        .find((candidate) => candidate.metric_id === key);
      if (metric === undefined) {
        throw new Error(`Missing metric ${key}`);
      }
      const explanation = explainMetric(metric);
      const copy = [
        explanation.plain_meaning,
        explanation.calculation_summary,
        explanation.scale_direction,
        explanation.interpretation_boundary,
      ].join(" ");
      for (const literal of FORBIDDEN_NUMERIC_LITERALS) {
        expect(copy, `${key} must not contain result literal "${literal}"`).not.toContain(literal);
      }
    }
  });

  it("explains every feature through the catalog without inventing meaning", async () => {
    const catalog = await loadCatalog();
    const missing: string[] = [];
    for (const feature of catalog.features) {
      try {
        const explanation = explainFeature(catalog, feature.feature_id);
        expect(explanation.key).toBe(feature.feature_id);
        expect(explanation.plain_meaning.length).toBeGreaterThan(20);
        expect(explanation.interpretation_boundary.length).toBeGreaterThan(20);
        expect(explanation.source_link).toBe(feature.method_ref);
      } catch (error) {
        missing.push(error instanceof Error ? error.message : String(error));
      }
    }
    expect(missing).toEqual([]);
  });

  it("fails closed for an unknown feature id", async () => {
    const catalog = await loadCatalog();
    expect(() => explainFeature(catalog, "no_such_feature")).toThrow(/No catalog definition/);
  });

  it("the explanation registry itself carries no duplicated numeric result literals", async () => {
    const source = await readFile(resolve("src", "content", "evidence-explanations.ts"), "utf8");
    for (const literal of FORBIDDEN_NUMERIC_LITERALS) {
      expect(source).not.toContain(literal);
    }
  });
});
