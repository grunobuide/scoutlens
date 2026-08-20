/**
 * The identity challenge view model (`scoutlens-9a3.6.1`).
 *
 * The happy path loads the `lab-max-content-v2` pack through the real
 * `StaticShowcaseRepository`, so what is proven is what the Lab will do: the
 * same schema validation, the same binding refusals, the same artifacts. A
 * test that hand-builds its input proves the test.
 *
 * The refusal and ordering cases mutate a deep clone of that loaded pack. That
 * is deliberate: they need artifacts that the *repository* would reject, which
 * cannot be fetched through it, and they must still be production-shaped in
 * every other respect. Each mutation is one field, so a passing test names one
 * cause.
 */

import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

import { beforeAll, describe, expect, it } from "vitest";

import { buildIdentityChallenge, type IdentityChallengeInput } from "@/content/identity-challenge";
import {
  StaticShowcaseRepository,
  type ShowcaseFetch,
  type ShowcaseMajor,
} from "@/contracts/showcase-repository";
import type {
  Manifest,
  PlayerProfileArtifact,
  RepresentationArtifact,
  ResearchSummaryArtifact,
} from "@/contracts/generated/showcase-v2";

const FIXTURES = resolve(__dirname, "..", "e2e", "fixtures");
const PACK = "lab-max-content-v2";
const MAJOR: ShowcaseMajor = 2;

function packReader(): ShowcaseFetch {
  const prefix = `/showcase/v${MAJOR}/`;
  return async (input: string) => {
    if (!input.startsWith(prefix)) {
      return new Response(null, { status: 404 });
    }
    try {
      const bytes = await readFile(resolve(FIXTURES, PACK, input.slice(prefix.length)));
      return new Response(new Uint8Array(bytes).buffer, { status: 200 });
    } catch {
      return new Response(null, { status: 404 });
    }
  };
}

let published: IdentityChallengeInput;

beforeAll(async () => {
  const repository = new StaticShowcaseRepository(packReader(), `/showcase/v${MAJOR}/`, MAJOR);
  const manifest = (await repository.getManifest()) as Manifest;
  const representation = await repository.getRepresentation();
  expect(representation).not.toBeNull();
  published = {
    manifest,
    profile: (await repository.getProfile(
      manifest.featured_profile.profile_key,
    )) as PlayerProfileArtifact,
    representation: representation as RepresentationArtifact,
    research: (await repository.getResearchSummary()) as ResearchSummaryArtifact,
  };
});

/**
 * Narrow a lookup the fixture guarantees. Throwing names the fixture as the
 * problem, rather than letting an absent element surface later as a confusing
 * assertion failure about `undefined`.
 */
function required<T>(value: T | undefined, what: string): T {
  if (value === undefined) {
    throw new Error(`The fixture is missing ${what}`);
  }
  return value;
}

/** A deep clone, so a mutation in one case cannot leak into another. */
function clone(): IdentityChallengeInput {
  return structuredClone(published) as IdentityChallengeInput;
}

function expectAvailable(input: IdentityChallengeInput) {
  const result = buildIdentityChallenge(input);
  if (!result.available) {
    throw new Error(`Expected an available challenge, got ${result.code}: ${result.message}`);
  }
  return result;
}

function expectRefusal(input: IdentityChallengeInput, code: string) {
  const result = buildIdentityChallenge(input);
  expect(result.available).toBe(false);
  if (result.available) {
    throw new Error("unreachable");
  }
  expect(result.code).toBe(code);
  expect(result.message).not.toBe("");
  return result;
}

describe("the challenge reproduces the stored artifact", () => {
  it("carries identity, ranks and provenance exactly as published", () => {
    const view = expectAvailable(clone());
    const profile = published.profile;
    const global = profile.retrieval.global;

    expect(view.profileKey).toBe(published.manifest.featured_profile.profile_key);
    expect(view.identity.displayName).toBe(profile.identity.display_name);
    expect(view.identity.role).toBe(profile.identity.role);
    expect(view.identity.competition).toBe(profile.identity.competition.name);

    expect(view.retrieval.selfRank).toBe(global.self_rank);
    expect(view.retrieval.candidateCount).toBe(global.candidate_count);
    expect(view.retrieval.similarityScore).toBe(global.similarity_score);
    expect(view.retrieval.representationId).toBe(global.representation_id);
    expect(view.retrieval.baselineSelfRank).toBe(
      profile.retrieval.baseline_role_minutes.self_rank,
    );
    expect(view.retrieval.method).toBe("combined_scaler_diagonal_v1");
    expect(view.datasetVersion).toBe(published.manifest.dataset_version);
  });

  it("reports the fitted-weight count from the representation, not the display count", () => {
    const view = expectAvailable(clone());
    // 28 weights are fitted for the 32 displayed features (§3.4). Reading this
    // from the manifest's feature_count would silently claim all 32 carry one.
    expect(view.fittedFeatureCount).toBe(published.representation.representation.feature_count);
    expect(view.fittedFeatureCount).toBe(28);
    expect(published.manifest.population.feature_count).toBe(32);
  });

  it("carries the period contexts each state reads", () => {
    const view = expectAvailable(clone());
    const contexts = published.profile.identity.period_contexts;
    expect(view.periods.a.minutes).toBe(contexts.a.minutes);
    expect(view.periods.a.matchCount).toBe(contexts.a.match_count);
    expect(view.periods.a.label).toBe(published.profile.periods.a.label);
    expect(view.periods.b.minutes).toBe(contexts.b.minutes);
    expect(view.periods.b.matchCount).toBe(contexts.b.match_count);
  });

  it("renders the frozen copy with stored values interpolated", () => {
    const view = expectAvailable(clone());
    const global = published.profile.retrieval.global;
    const baseline = published.profile.retrieval.baseline_role_minutes.self_rank;

    expect(view.copy.orientationHeading).toBe("Can a player's actions identify them?");
    expect(view.copy.orientationCta).toBe("See the fingerprint");
    expect(view.copy.queryCta).toBe("Reveal the result");
    expect(view.copy.evidenceHeading).toBe("What drove the match");
    expect(view.copy.revealHeading).toBe(
      `The fingerprint found them at rank ${global.self_rank} of ${global.candidate_count}.`,
    );
    expect(view.copy.revealBaseline).toBe(`A role-and-minutes baseline ranked them ${baseline}.`);
    expect(view.copy.degradedResult).toContain(published.profile.identity.display_name);
    expect(view.copy.degradedResult).toContain(`${global.self_rank} of ${global.candidate_count}`);
    // The orientation question is the artifact's, not a copy of it in code.
    expect(view.copy.orientationQuestion).toBe(
      published.research.narrative_steps.find((step) => step.kind === "question")?.title,
    );
  });

  it("carries the mandatory caveats and the artifact's own uncertainty caveat", () => {
    const view = expectAvailable(clone());
    const codes = view.caveats.map((caveat) => caveat.code);
    expect(codes).toContain("fingerprint_not_style_proof");
    expect(codes).toContain("same_season_team_confound");
    expect(codes).toContain("similarity_not_recruitment");

    // The published fixture reports `pending`, so the challenge must carry the
    // pending caveat and no interval - and must have read that from the
    // artifact rather than assuming a state (§3.3).
    expect(view.retrieval.uncertainty.status).toBe("pending");
    expect(view.retrieval.uncertainty.rankCi95).toBeNull();
    expect(view.retrieval.uncertainty.caveat?.code).toBe("uncertainty_pending");
    expect(view.retrieval.uncertainty.caveat?.message).toBe(
      published.profile.caveats.find((caveat) => caveat.code === "uncertainty_pending")?.message,
    );
  });

  it("renders an interval when the artifact reports one available", () => {
    const input = clone();
    input.profile.uncertainty.status = "available";
    input.profile.uncertainty.design_version = "match_bootstrap_diagonal_v1";
    input.profile.retrieval.global.uncertainty.status = "available";
    input.profile.retrieval.global.uncertainty.rank_ci_95 = [3, 19];
    input.profile.caveats = [
      ...input.profile.caveats.filter((caveat) => caveat.code !== "uncertainty_pending"),
      {
        code: "uncertainty_sampling_only",
        severity: "context",
        message: "Intervals describe resampling stability, not measurement error.",
        evidence_refs: [],
      },
    ] as unknown as PlayerProfileArtifact["caveats"];

    const view = expectAvailable(input);
    expect(view.retrieval.uncertainty.status).toBe("available");
    expect(view.retrieval.uncertainty.rankCi95).toEqual([3, 19]);
    expect(view.retrieval.uncertainty.caveat?.code).toBe("uncertainty_sampling_only");
  });
});

describe("the challenge computes nothing", () => {
  it("returns family evidence in published order, not in contribution order", () => {
    const input = clone();
    const refs = input.profile.retrieval.global.evidence_refs;
    const index = new Map(input.profile.evidence_index.map((item) => [item.evidence_id, item]));
    const familyRefs = refs.filter((ref) => index.get(ref)?.kind === "family_contribution");
    expect(familyRefs.length).toBeGreaterThan(3);

    // Move the weakest family to the front of the published order. A view that
    // sorts would put it back; a view that reads published order keeps it
    // first. This is the assertion that the "no sorting" rule actually holds -
    // in the untouched fixture, published order already is descending, so a
    // sorting implementation would pass every other test here.
    const weakest = required(familyRefs.at(-1), "a family evidence reference");
    const reordered = [weakest, ...refs.filter((ref) => ref !== weakest)];
    input.profile.retrieval.global.evidence_refs = reordered;

    const view = expectAvailable(input);
    expect(required(view.families[0], "a family").evidence_id).toBe(weakest);
    expect(required(view.revealFamilies[0], "a reveal family").evidence_id).toBe(weakest);
    expect(view.families.map((item) => item.evidence_id)).toEqual(
      reordered.filter((ref) => index.get(ref)?.kind === "family_contribution"),
    );

    // And the reordering really did break descending magnitude, so the test
    // would fail against a sorting implementation rather than pass by luck.
    const magnitudes = view.families.map((item) => Math.abs(item.weighted_contribution));
    expect(required(magnitudes[0], "a magnitude")).toBeLessThan(
      required(magnitudes[1], "a second magnitude"),
    );
  });

  it("reports a tampered similarity score verbatim rather than recomputing it", () => {
    const input = clone();
    input.profile.retrieval.global.similarity_score = 0.123456;
    const view = expectAvailable(input);
    expect(view.retrieval.similarityScore).toBe(0.123456);
  });

  it("takes the leading three families and five feature contributions", () => {
    const view = expectAvailable(clone());
    expect(view.revealFamilies).toHaveLength(3);
    expect(view.revealFamilies).toEqual(view.families.slice(0, 3));
    expect(view.featureContributions).toHaveLength(5);

    const refs = published.profile.retrieval.global.evidence_refs;
    const index = new Map(published.profile.evidence_index.map((i) => [i.evidence_id, i]));
    expect(view.featureContributions.map((item) => item.evidence_id)).toEqual(
      refs.filter((ref) => index.get(ref)?.kind === "feature_contribution").slice(0, 5),
    );
  });

  it("exposes weighted contributions, and never substitutes the cosine audit view", () => {
    const view = expectAvailable(clone());
    for (const item of view.featureContributions) {
      const stored = published.profile.evidence_index.find(
        (candidate) => candidate.evidence_id === item.evidence_id,
      );
      expect(item.weighted_contribution).toBe(stored?.weighted_contribution);
      expect(item.contribution).toBe(stored?.contribution);
    }
    // The two differ in this fixture, so a view that confused them would fail.
    const drifted = view.featureContributions.some(
      (item) => item.weighted_contribution !== item.contribution,
    );
    expect(drifted).toBe(true);
  });

  it("contains no comparator in its source", async () => {
    const source = await readFile(
      resolve(__dirname, "..", "src", "content", "identity-challenge.ts"),
      "utf8",
    );
    const code = source.replace(/\/\*\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
    for (const forbidden of [".sort(", ".reverse(", "localeCompare", "Intl.Collator"]) {
      expect(code).not.toContain(forbidden);
    }
  });
});

describe("the challenge fails closed", () => {
  it("refuses a profile the manifest does not feature", () => {
    const input = clone();
    input.profile.profile_key = "wy-000000-c-000";
    expectRefusal(input, "profile_mismatch");
  });

  it("refuses a profile from another dataset version", () => {
    const input = clone();
    input.profile.dataset_version = "wyscout-2017-18-v2-deadbeefdead";
    expectRefusal(input, "dataset_mismatch");
  });

  it("refuses a representation from another dataset version", () => {
    const input = clone();
    input.representation.dataset_version = "wyscout-2017-18-v2-deadbeefdead";
    expectRefusal(input, "dataset_mismatch");
  });

  it("refuses a representation the manifest does not name", () => {
    const input = clone();
    input.representation.representation.id = "rep-0000000000000000";
    expectRefusal(input, "representation_mismatch");
  });

  it("refuses a retrieval produced by another representation", () => {
    const input = clone();
    input.profile.retrieval.global.representation_id = "rep-0000000000000000";
    expectRefusal(input, "representation_mismatch");
  });

  it("refuses a baseline produced by another representation", () => {
    const input = clone();
    input.profile.retrieval.baseline_role_minutes.representation_id = "rep-0000000000000000";
    expectRefusal(input, "representation_mismatch");
  });

  it("refuses evidence produced by another representation", () => {
    const input = clone();
    const first = input.profile.retrieval.global.evidence_refs[0];
    const item = input.profile.evidence_index.find(
      (candidate) => candidate.evidence_id === first,
    );
    expect(item).toBeDefined();
    item!.representation_id = "rep-0000000000000000";
    expectRefusal(input, "representation_mismatch");
  });

  it("refuses a v1 uncertainty design beside a diagonal rank", () => {
    const input = clone();
    // A v1 design is off the generated union by construction, which is the
    // point: the guard exists for an artifact that predates it.
    (input.profile.uncertainty as { design_version: string }).design_version =
      "match_bootstrap_v1";
    expectRefusal(input, "uncertainty_design_mismatch");
  });

  it("refuses an available uncertainty that names no diagonal design", () => {
    const input = clone();
    input.profile.retrieval.global.uncertainty.status = "available";
    input.profile.retrieval.global.uncertainty.rank_ci_95 = [3, 19];
    // design_version stays null, as the pending fixture publishes it
    expectRefusal(input, "uncertainty_design_mismatch");
  });

  it("refuses an available uncertainty that publishes no interval", () => {
    const input = clone();
    input.profile.uncertainty.status = "available";
    input.profile.uncertainty.design_version = "match_bootstrap_diagonal_v1";
    input.profile.retrieval.global.uncertainty.status = "available";
    input.profile.retrieval.global.uncertainty.rank_ci_95 = null;
    expectRefusal(input, "uncertainty_interval_missing");
  });

  it("refuses a retrieval method that is not the diagonal one", () => {
    const input = clone();
    (input.profile.retrieval as { method: string }).method = "combined_scaler_cosine_v1";
    expectRefusal(input, "retrieval_method_mismatch");
  });

  it("refuses an evidence reference that does not resolve", () => {
    const input = clone();
    input.profile.retrieval.global.evidence_refs = [
      ...input.profile.retrieval.global.evidence_refs,
      "evidence-self_retrieval-f-does-not-exist",
    ];
    expectRefusal(input, "evidence_unresolved");
  });

  it("refuses a repeated evidence reference", () => {
    const input = clone();
    const refs = input.profile.retrieval.global.evidence_refs;
    input.profile.retrieval.global.evidence_refs = [
      ...refs,
      required(refs[0], "an evidence reference"),
    ];
    expectRefusal(input, "evidence_unresolved");
  });

  it("refuses evidence belonging to another subject", () => {
    const input = clone();
    const first = input.profile.retrieval.global.evidence_refs[0];
    const item = input.profile.evidence_index.find((c) => c.evidence_id === first);
    item!.subject = "neighbor:wy-10252-c-364";
    expectRefusal(input, "evidence_unresolved");
  });

  it("refuses a duplicated evidence index entry", () => {
    const input = clone();
    input.profile.evidence_index = [
      ...input.profile.evidence_index,
      required(input.profile.evidence_index[0], "an evidence item"),
    ] as PlayerProfileArtifact["evidence_index"];
    expectRefusal(input, "evidence_unresolved");
  });

  it("refuses a retrieval with no contribution evidence", () => {
    const input = clone();
    const index = new Map(input.profile.evidence_index.map((item) => [item.evidence_id, item]));
    input.profile.retrieval.global.evidence_refs =
      input.profile.retrieval.global.evidence_refs.filter(
        (ref) => index.get(ref)?.kind !== "family_contribution",
      );
    expectRefusal(input, "evidence_empty");
  });

  it.each([
    "fingerprint_not_style_proof",
    "same_season_team_confound",
    "similarity_not_recruitment",
    "within_role_display_differs_from_global_model",
  ])("refuses a profile missing the %s caveat", (code) => {
    const input = clone();
    input.profile.caveats = input.profile.caveats.filter(
      (caveat) => caveat.code !== code,
    ) as PlayerProfileArtifact["caveats"];
    expectRefusal(input, "missing_caveat");
  });

  it("refuses a pending uncertainty with no pending caveat", () => {
    const input = clone();
    input.profile.caveats = input.profile.caveats.filter(
      (caveat) => caveat.code !== "uncertainty_pending",
    ) as PlayerProfileArtifact["caveats"];
    expectRefusal(input, "missing_caveat");
  });

  it("refuses a research summary with no question step", () => {
    const input = clone();
    input.research.narrative_steps = input.research.narrative_steps.filter(
      (step) => step.kind !== "question",
    ) as ResearchSummaryArtifact["narrative_steps"];
    expectRefusal(input, "missing_narrative");
  });

  it("never returns a partial view alongside a refusal", () => {
    const input = clone();
    input.profile.profile_key = "wy-000000-c-000";
    const result = buildIdentityChallenge(input);
    expect(result.available).toBe(false);
    expect(Object.keys(result).sort()).toEqual(["available", "code", "message"]);
  });
});
