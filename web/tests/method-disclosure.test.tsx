/**
 * The frozen v2 copy contract (`scoutlens-qop.6.5`, AC3).
 *
 * Every sentence asserted here was fixed by the bead before the migration
 * started. These are not style checks: the label, the audit statement and the
 * boundary sentence are the difference between describing a retrieval result
 * and making a recruitment claim, so they are pinned rather than reviewed.
 *
 * Rendered with `renderToStaticMarkup`, like the rest of the suite - the frozen
 * copy is static text and proving it needs no browser and no new dependency.
 */

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { FingerprintProfile } from "@/components/lab-explorer";
import { methodDisclosure } from "@/content/showcase-lab";

import catalog from "../e2e/fixtures/lab-max-content-v2/feature-catalog.json";
import index from "../e2e/fixtures/lab-max-content-v2/players.index.json";
import profile from "../e2e/fixtures/lab-max-content-v2/players/wy-900001-c-901.json";

const REPRESENTATION_FEATURE_COUNT = 28;

function labMarkup(major: 1 | 2, weightedFeatureCount: number | null): string {
  return renderToStaticMarkup(
    <FingerprintProfile
      major={major}
      weightedFeatureCount={weightedFeatureCount}
      catalog={catalog as never}
      profiles={index.profiles as never}
      profile={profile as never}
    />,
  );
}

describe("the frozen v2 method disclosure", () => {
  it("states the label, the fitted weights, the audit baseline and the boundary", () => {
    const markup = labMarkup(2, REPRESENTATION_FEATURE_COUNT);

    expect(markup).toContain("Learned weighted similarity");
    expect(markup).toContain(
      "28 non-negative feature weights fitted on the frozen Wyscout training split",
    );
    expect(markup).toContain("Unit weights reproduce the cosine audit baseline exactly");
    expect(markup).toContain(
      "does not measure player quality, tactical fit or recruitment value",
    );
  });

  it("explains why this model and not the neural one, and links D045", () => {
    const markup = labMarkup(2, REPRESENTATION_FEATURE_COUNT);

    expect(markup).toContain("Why this model, and why not the neural one?");
    expect(markup).toContain("transparent audit baseline");
    expect(markup).toContain("preregistered compact neural arm lost");
    expect(markup).toContain("decisions-log.md#d045");
  });

  it("offers no representation toggle in the primary flow", () => {
    const markup = labMarkup(2, REPRESENTATION_FEATURE_COUNT);

    // Cosine is reachable as the published audit baseline and as the decision
    // record, never as a control that invites a reader to pick a number.
    expect(markup).not.toMatch(/<input[^>]+name="[^"]*(representation|model|method)/i);
    expect(markup).not.toMatch(/role="switch"/);
    expect(markup).not.toMatch(/<button[^>]*>[^<]*[Cc]osine[^<]*<\/button>/);
  });

  it("takes the weight count from the artifact rather than the copy", () => {
    // A dataset weighting a different number of features must say so; the
    // sentence is a template, not a transcribed number.
    expect(methodDisclosure(9).summary).toContain("9 non-negative feature weights");
    expect(methodDisclosure(28).summary).toContain("28 non-negative feature weights");
  });

  it("is absent from a v1 Lab, which keeps its own copy", () => {
    const markup = labMarkup(1, null);

    expect(markup).not.toContain("Learned weighted similarity");
    expect(markup).not.toContain("Why this model, and why not the neural one?");
  });
});
