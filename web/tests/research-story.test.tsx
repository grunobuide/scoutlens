import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { ACTIVE_SHOWCASE_MAJOR } from "@/contracts/showcase-repository";
import { describe, expect, it } from "vitest";

import { ClaimsMatrix, ExperimentCard } from "@/components/research-story";
import type { ResearchExperiment, ResearchSummaryArtifact } from "@/contracts/generated/showcase";
import { formatMetric, requireMetric } from "@/content/showcase-story";
import { ExplanationNotFoundError, explainMetric } from "@/content/evidence-explanations";

/** What React's server renderer does to text content. */
function escapeHtml(text: string): string {
  return text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#x27;");
}

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

  it("refuses to render a metric the registry cannot explain (scoutlens-9a3.19)", () => {
    // This card used to catch the resolver's throw and print the number with
    // no explanation. A metric without one now stops the static build.
    const experiment = experimentWith(0.4321);
    const unexplained = {
      ...experiment,
      metrics: [{ ...experiment.metrics[0]!, metric_id: "no_such_metric" }],
    } as ResearchExperiment;
    expect(() =>
      renderToStaticMarkup(<ExperimentCard experiment={unexplained} research={researchWith(unexplained)} />),
    ).toThrow(ExplanationNotFoundError);
  });

  it("puts the registry's meaning and boundary behind a native disclosure for every metric", () => {
    const experiment = experimentWith(0.4321);
    const html = renderToStaticMarkup(<ExperimentCard experiment={experiment} research={researchWith(experiment)} />);
    const explanation = explainMetric({ metric_id: "fingerprint_mrr" });
    expect(html).toContain("<details><summary>What this means</summary>");
    expect(html).toContain(escapeHtml(explanation.plain_meaning));
    expect(html).toContain(escapeHtml(explanation.interpretation_boundary));
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

  it("keeps every unsupported claim visible without an interactive disclosure", () => {
    const experiment = experimentWith(0.4321);
    const research = researchWith(experiment);
    const html = renderToStaticMarkup(<ClaimsMatrix research={research} />);

    for (const claim of research.unsupported_claims) {
      expect(html).toContain(claim);
    }
    expect(html).not.toContain("<details");
  });

  it("does not restate the supported claim (scoutlens-9a3.12)", () => {
    // The landing hero states the claim four blocks above this section, under
    // the same "Supported claim" label. Run 1 of the comprehension check could
    // not name a single unsupported claim — which is what sits immediately
    // after it. That the evaluator read the repeat as "you have been here
    // already" and skimmed is inference: run 1 captured no element-read trace
    // (docs/public-understanding-check.md §6), so the cause was not observed.
    //
    // This asserts the absence, because the defect was a duplicate rather than
    // a missing string: a test that only checks the boundary renders would stay
    // green if the restatement came back.
    const research = researchWith(experimentWith(0.4321));
    const html = renderToStaticMarkup(<ClaimsMatrix research={research} />);

    expect(html).not.toContain(research.supported_claim);
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
