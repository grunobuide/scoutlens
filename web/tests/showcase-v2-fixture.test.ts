/**
 * The v2 fixture pack, loaded through the real repository (`scoutlens-qop.6.5`).
 *
 * These assertions run against `StaticShowcaseRepository` rather than a private
 * copy of the rules, so what is proven here is what the Lab will do: the same
 * schema, the same binding checks, the same refusals. A test that re-implements
 * the validator proves the test.
 *
 * The v1 pack is loaded alongside, because "v2 works" is only half the contract
 * - the leaf must not have quietly broken the major the site still serves.
 */

import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import {
  ShowcaseContractError,
  StaticShowcaseRepository,
  type ShowcaseFetch,
  type ShowcaseMajor,
} from "@/contracts/showcase-repository";
import { evidenceContribution, neighborScore, retrievalScore } from "@/content/showcase-lab";

const FIXTURES = resolve(__dirname, "..", "e2e", "fixtures");
const V2_REPRESENTATION_ID = "rep-f018e6041ccbad10";

function packReader(packId: string, major: ShowcaseMajor): ShowcaseFetch {
  const prefix = `/showcase/v${major}/`;
  return async (input: string) => {
    if (!input.startsWith(prefix)) {
      return new Response(null, { status: 404 });
    }
    try {
      const bytes = await readFile(resolve(FIXTURES, packId, input.slice(prefix.length)));
      return new Response(new Uint8Array(bytes).buffer, { status: 200 });
    } catch {
      return new Response(null, { status: 404 });
    }
  };
}

function repositoryFor(packId: string, major: ShowcaseMajor): StaticShowcaseRepository {
  return new StaticShowcaseRepository(packReader(packId, major), `/showcase/v${major}/`, major);
}

const v2 = () => repositoryFor("lab-max-content-v2", 2);
const v1 = () => repositoryFor("lab-max-content", 1);

describe("the v2 fixture pack loads through the real repository", () => {
  it("publishes a representation the manifest agrees with", async () => {
    const representation = await v2().getRepresentation();
    expect(representation).not.toBeNull();
    expect(representation!.representation.id).toBe(V2_REPRESENTATION_ID);
    expect(representation!.representation.ranking_method).toBe("weighted_cosine_diagonal_v1");
    expect(representation!.representation.weights).toHaveLength(28);
  });

  it("reports a similarity score and never a cosine", async () => {
    const repository = v2();
    const manifest = await repository.getManifest();
    const profile = await repository.getProfile(manifest.featured_profile.profile_key);

    expect(profile.retrieval.method).toBe("combined_scaler_diagonal_v1");
    expect(profile.retrieval.global).not.toHaveProperty("cosine_similarity");
    expect(retrievalScore(profile.retrieval.global)).toBeTypeOf("number");
    for (const neighbor of profile.neighbors) {
      expect(neighbor).not.toHaveProperty("cosine_similarity");
      expect(neighborScore(neighbor)).toBeTypeOf("number");
    }
  });

  it("reconstructs the published score from the weighted contributions", async () => {
    const repository = v2();
    const manifest = await repository.getManifest();
    const profile = await repository.getProfile(manifest.featured_profile.profile_key);

    const subjects = new Map<string, number>([
      ["self_retrieval", retrievalScore(profile.retrieval.global)!],
      ...profile.neighbors.map(
        (neighbor) => [`neighbor:${neighbor.profile_key}`, neighborScore(neighbor)] as const,
      ),
    ]);

    for (const [subject, score] of subjects) {
      const features = profile.evidence_index.filter(
        (item) => item.subject === subject && item.kind === "feature_contribution",
      );
      expect(features).toHaveLength(32);
      const sum = features.reduce((total, item) => total + evidenceContribution(item), 0);
      // The normative v2 tolerance. Evidence that does not reconstruct the
      // number it explains is not evidence.
      expect(Math.abs(sum - score)).toBeLessThan(1e-6);
    }
  });

  it("orders evidence by the contribution to the score it publishes", async () => {
    const repository = v2();
    const manifest = await repository.getManifest();
    const profile = await repository.getProfile(manifest.featured_profile.profile_key);
    // Contract order is carried by `evidence_refs`, not by position in
    // `evidence_index` - the index is in catalog order and the refs are the
    // ranking. Resolving through the refs is what the consumer does.
    const byId = new Map(profile.evidence_index.map((item) => [item.evidence_id, item]));
    const features = profile.retrieval.global.evidence_refs
      .map((reference) => byId.get(reference)!)
      .filter((item) => item.kind === "feature_contribution");
    expect(features).toHaveLength(32);

    const magnitudes = features.map((item) => Math.abs(evidenceContribution(item)));
    expect(magnitudes).toEqual([...magnitudes].sort((left, right) => right - left));

    // The unweighted audit view is a genuinely different series, so ordering by
    // it would produce a different sequence. If these ever coincide the fixture
    // has stopped exercising the distinction.
    const unweighted = features.map((item) => Math.abs(item.contribution));
    expect(unweighted).not.toEqual([...unweighted].sort((left, right) => right - left));
  });

  it("names one representation everywhere and only the diagonal design", async () => {
    const repository = v2();
    const manifest = await repository.getManifest();
    const profile = await repository.getProfile(manifest.featured_profile.profile_key);

    const ids = new Set<unknown>();
    const designs = new Set<unknown>();
    const walk = (node: unknown): void => {
      if (Array.isArray(node)) {
        node.forEach(walk);
        return;
      }
      if (node === null || typeof node !== "object") {
        return;
      }
      for (const [key, value] of Object.entries(node)) {
        if (key === "representation_id") ids.add(value);
        else if (key === "design_version") designs.add(value);
        else walk(value);
      }
    };
    walk(profile);

    expect([...ids]).toEqual([V2_REPRESENTATION_ID]);
    for (const design of designs) {
      expect(design === null || design === "match_bootstrap_diagonal_v1").toBe(true);
    }
  });
});

describe("the repository refuses what a v2 dataset must not contain", () => {
  it("refuses a v1 pack read as v2", async () => {
    await expect(repositoryFor("lab-max-content", 2).getManifest()).rejects.toThrow(
      ShowcaseContractError,
    );
  });

  it("refuses a v2 pack read as v1", async () => {
    await expect(repositoryFor("lab-max-content-v2", 1).getManifest()).rejects.toThrow(
      /declares major 2, but this dataset is major 1|Unsupported showcase schema major/,
    );
  });

  it("refuses a profile whose blocks name a foreign representation", async () => {
    const base = packReader("lab-max-content-v2", 2);
    const tampering: ShowcaseFetch = async (input) => {
      const response = await base(input);
      if (!input.includes("/players/") || !response.ok) {
        return response;
      }
      const artifact = JSON.parse(await response.text());
      artifact.uncertainty.representation_id = "rep-ffffffffffffffff";
      return new Response(JSON.stringify(artifact), { status: 200 });
    };
    const repository = new StaticShowcaseRepository(tampering, "/showcase/v2/", 2);
    const manifest = await repository.getManifest();
    // The byte check fires first on a rewritten profile, which is itself the
    // point: a tampered artifact never reaches the binding rule.
    await expect(repository.getProfile(manifest.featured_profile.profile_key)).rejects.toThrow(
      ShowcaseContractError,
    );
  });
});

describe("the v1 pack still loads as v1", () => {
  it("reports a cosine and no similarity score", async () => {
    const repository = v1();
    const manifest = await repository.getManifest();
    const profile = await repository.getProfile(manifest.featured_profile.profile_key);

    expect(manifest.schema_version).toBe("1.0.0");
    expect(profile.retrieval.method).toBe("combined_scaler_cosine_v1");
    expect(profile.retrieval.global).not.toHaveProperty("similarity_score");
    expect(retrievalScore(profile.retrieval.global)).toBeTypeOf("number");
  });

  it("has no representation to publish", async () => {
    await expect(v1().getRepresentation()).resolves.toBeNull();
  });
});
