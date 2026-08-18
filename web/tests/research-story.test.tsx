import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { ACTIVE_SHOWCASE_MAJOR } from "@/contracts/showcase-repository";
import { describe, expect, it } from "vitest";

import { ClaimsMatrix, ExperimentCard } from "@/components/research-story";
import type { ResearchExperiment, ResearchSummaryArtifact } from "@/contracts/generated/showcase";
import { formatMetric, requireMetric } from "@/content/showcase-story";

function experimentWith(fingerprintMrr: number): ResearchExperiment {
  return {
    experiment_id: "fixture_global",
    title: "Fixture retrieval",
    provider: "wyscout_pappalardo",
    population: "Fixture population",
    metrics: [
      {
        metric_id: "fingerprint_mrr",
        label: "Fingerprint MRR",
        value: fingerprintMrr,
        ci_95: [fingerprintMrr - 0.01, fingerprintMrr + 0.01],
        unit: "mrr",
        display_precision: 4,
      },
    ],
    conclusion: "Fixture conclusion",
    caveat_codes: ["fingerprint_not_style_proof"],
    source_artifact: "artifacts/fixture.json",
    report_url: "docs/fixture.md",
  };
}

function researchWith(experiment: ResearchExperiment): ResearchSummaryArtifact {
  return {
    supported_claim: "Fixture supported claim.",
    unsupported_claims: [
      "Fixture unsupported claim one.",
      "Fixture unsupported claim two.",
      "Fixture unsupported claim three.",
    ],
    experiments: [experiment],
    narrative_steps: [],
    caveats: [
      {
        code: "fingerprint_not_style_proof",
        severity: "critical",
        message: "Fixture critical boundary.",
        evidence_refs: [],
      },
    ],
  } as unknown as ResearchSummaryArtifact;
}

describe("evidence-first research story", () => {
  it("renders a changed fixture metric instead of a copied headline value", () => {
    const first = experimentWith(0.4321);
    const second = experimentWith(0.8765);

    const firstHtml = renderToStaticMarkup(
      <ExperimentCard experiment={first} metricIds={["fingerprint_mrr"]} research={researchWith(first)} />,
    );
    const secondHtml = renderToStaticMarkup(
      <ExperimentCard experiment={second} metricIds={["fingerprint_mrr"]} research={researchWith(second)} />,
    );

    expect(firstHtml).toContain("0.4321");
    expect(firstHtml).not.toContain("0.8765");
    expect(secondHtml).toContain("0.8765");
  });

  it("renders the production headline directly from research-summary.json", async () => {
    const artifact = JSON.parse(
      await readFile(resolve("public", "showcase", `v${ACTIVE_SHOWCASE_MAJOR}`, "research-summary.json"), "utf8"),
    ) as ResearchSummaryArtifact;
    const experiment = artifact.experiments.find(
      (item) => item.experiment_id === "wyscout_global_gate2",
    );
    expect(experiment).toBeDefined();

    const metric = requireMetric(experiment!, "fingerprint_mrr");
    const html = renderToStaticMarkup(
      <ExperimentCard experiment={experiment!} metricIds={["fingerprint_mrr"]} research={artifact} />,
    );

    expect(html).toContain(formatMetric(metric));
    expect(html).toContain(experiment!.conclusion);
  });

  it("keeps supported and unsupported claims visible without an interactive disclosure", () => {
    const experiment = experimentWith(0.4321);
    const research = researchWith(experiment);
    const html = renderToStaticMarkup(<ClaimsMatrix research={research} />);

    expect(html).toContain(research.supported_claim);
    for (const claim of research.unsupported_claims) {
      expect(html).toContain(claim);
    }
    expect(html).not.toContain("<details");
  });

  it("does not duplicate frozen production metric literals in page source", async () => {
    const sources = await Promise.all(
      ["src/app/page.tsx", "src/app/science/page.tsx", "src/components/research-story.tsx"].map(
        (path) => readFile(resolve(path), "utf8"),
      ),
    );
    const source = sources.join("\n");

    for (const duplicatedLiteral of ["0.0256", "0.2539", "0.5893", "0.2031"]) {
      expect(source).not.toContain(duplicatedLiteral);
    }
  });
});
