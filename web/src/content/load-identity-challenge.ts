/**
 * Server-side loading for the identity challenge (`scoutlens-9a3.6.2`).
 *
 * Two failure surfaces meet here, and they are different in kind:
 *
 * - the repository **throws** when an artifact cannot be fetched, fails its
 *   schema, or breaks a checksum (§8's "missing artifact" and "checksum/schema
 *   mismatch" rows). `describeLabError` already turns those into the Lab's
 *   problem vocabulary, so they reuse it rather than growing a parallel one.
 * - `buildIdentityChallenge` **returns** a typed refusal when the artifacts
 *   load cleanly but do not bind to each other - a profile the manifest does
 *   not feature, evidence from another representation. Nothing throws, because
 *   nothing is broken at the transport layer; the data is simply not
 *   renderable together.
 *
 * Both end at the same place: a `LabProblem`, and no view. §8 requires failing
 * closed without rendering partial data, so there is deliberately no shape here
 * that carries a problem *and* a half-built challenge.
 */

import { buildIdentityChallenge, type IdentityChallengeView } from "@/content/identity-challenge";
import { describeLabError, type LabProblem } from "@/content/showcase-lab";
import { createServerShowcaseRepository } from "@/content/showcase-server";
import type {
  Manifest,
  PlayerProfileArtifact,
  RepresentationArtifact,
  ResearchSummaryArtifact,
} from "@/contracts/generated/showcase-v2";

export interface ReadyIdentityChallengeData {
  status: "ready";
  datasetVersion: string;
  view: IdentityChallengeView;
}

export interface FailedIdentityChallengeData {
  status: "error";
  datasetVersion: string | null;
  problem: LabProblem;
}

export type IdentityChallengeData = ReadyIdentityChallengeData | FailedIdentityChallengeData;

/**
 * A binding refusal, in the Lab's problem vocabulary.
 *
 * Every refusal maps to `incompatible-data` and says the same thing, because
 * from a reader's position they are the same event: artifacts that disagree,
 * and a page that stopped rather than show a number it could not stand behind.
 * The specific code stays in the refusal message for the server log, not in
 * copy that would ask a visitor to care which binding failed.
 */
function describeRefusal(): LabProblem {
  return {
    kind: "incompatible-data",
    eyebrow: "Incompatible data",
    title: "The evidence for this profile could not be loaded",
    message:
      "The challenge fails closed when the published artifacts disagree. No partially trusted " +
      "values are displayed; the full Lab below reads the same verified dataset.",
    canRetry: true,
  };
}

export async function loadIdentityChallenge(): Promise<IdentityChallengeData> {
  const repository = createServerShowcaseRepository();
  let datasetVersion: string | null = null;

  try {
    // The challenge is a v2 surface. Major 1 published no representation and no
    // weighted evidence, so there is nothing to fail closed *about* - the
    // challenge simply does not exist there, and saying so is honest where
    // rendering a v1-shaped approximation would not be.
    if (repository.major !== 2) {
      return {
        status: "error",
        datasetVersion,
        problem: describeRefusal(),
      };
    }

    const manifest = (await repository.getManifest()) as Manifest;
    datasetVersion = manifest.dataset_version;

    const [profile, representation, research] = await Promise.all([
      repository.getProfile(manifest.featured_profile.profile_key),
      repository.getRepresentation(),
      repository.getResearchSummary(),
    ]);

    if (representation === null) {
      return { status: "error", datasetVersion, problem: describeRefusal() };
    }

    const challenge = buildIdentityChallenge({
      manifest,
      profile: profile as PlayerProfileArtifact,
      representation: representation as RepresentationArtifact,
      research: research as ResearchSummaryArtifact,
    });

    if (!challenge.available) {
      return { status: "error", datasetVersion, problem: describeRefusal() };
    }

    return { status: "ready", datasetVersion, view: challenge };
  } catch (error) {
    return {
      status: "error",
      datasetVersion,
      problem: describeLabError(error),
    };
  }
}
