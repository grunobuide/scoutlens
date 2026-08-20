/**
 * The identity challenge view model (`scoutlens-9a3.6.1`).
 *
 * This module is the whole boundary between the published
 * `scoutlens.showcase/2.0.0` artifacts and the challenge UI. Components render
 * what this returns; they never read an artifact themselves, and they never
 * compute. That division is the point of the slice: §3.3 and §3.4 of
 * `docs/identity-challenge-contract.md` require evidence in *published order*
 * and a score the browser did not derive, and a rule like that survives only
 * if there is exactly one place values can enter the page.
 *
 * Two properties are load-bearing here:
 *
 * 1. **No calculation.** Nothing in this file sorts, ranks, sums, rescales or
 *    otherwise derives a number. Evidence is resolved by reference and cut
 *    with a prefix; a score is copied. A test asserts the source contains no
 *    comparator, and separate tests prove the behaviour rather than the text.
 *
 * 2. **Fail closed, whole.** Every refusal in §8 returns a typed, complete
 *    refusal rather than a partly-populated view. There is no branch that
 *    lets a missing binding read as a default, a zero or an empty list.
 *
 * **Layering.** `StaticShowcaseRepository` is the first gate: it validates
 * each artifact against its schema and already refuses a foreign
 * `representation_id` or a non-diagonal uncertainty design. This module is the
 * second, and deliberately re-checks both. It is a pure function over plain
 * objects, so it cannot assume its caller came through the repository, and §8
 * requires failing closed *before rendering any value*. The cross-artifact
 * bindings below - manifest to profile to representation to research summary -
 * are checks no single-artifact validator can make.
 */

import { formatRank } from "@/components/rank-format";
import type {
  Caveat,
  EvidenceItem,
  Manifest,
  PeriodContext,
  PeriodFingerprint,
  PlayerProfileArtifact,
  RepresentationArtifact,
  ResearchSummaryArtifact,
  RetrievalOutcome,
} from "@/contracts/generated/showcase-v2";

/** The uncertainty design a v2 interval must carry to be shown beside a rank. */
const V2_UNCERTAINTY_DESIGN = "match_bootstrap_diagonal_v1";

/** The retrieval method a v2 profile must declare (`D047`, `D049`). */
const V2_RETRIEVAL_METHOD = "combined_scaler_diagonal_v1";

/**
 * Caveats every challenge state must carry, from §3.1-§3.4.
 *
 * The uncertainty caveat is not here: which one applies depends on
 * `uncertainty.status`, and the challenge renders the code the artifact
 * publishes rather than asserting a state (§3.3).
 */
const MANDATORY_CAVEATS = [
  "fingerprint_not_style_proof",
  "same_season_team_confound",
  "similarity_not_recruitment",
  "within_role_display_differs_from_global_model",
] as const;

/**
 * The uncertainty caveat required for each status the artifact can declare.
 *
 * `insufficient` is absent on purpose. §3.3 says to render "the artifact-
 * provided caveat explaining why" without naming a code, so requiring a
 * particular one would invent a rule the contract does not state.
 */
const UNCERTAINTY_CAVEAT_BY_STATUS: Readonly<Record<string, string | undefined>> = {
  available: "uncertainty_sampling_only",
  pending: "uncertainty_pending",
};

/** How many contributions each state shows. §3.3 takes three, §3.4 takes five. */
const REVEAL_FAMILY_COUNT = 3;
const EVIDENCE_FEATURE_COUNT = 5;

export type ChallengeRefusalCode =
  | "profile_mismatch"
  | "dataset_mismatch"
  | "representation_mismatch"
  | "retrieval_method_mismatch"
  | "uncertainty_design_mismatch"
  | "uncertainty_interval_missing"
  | "evidence_unresolved"
  | "evidence_empty"
  | "missing_caveat"
  | "missing_narrative";

export interface ChallengeRefusal {
  readonly available: false;
  readonly code: ChallengeRefusalCode;
  readonly message: string;
}

export interface ChallengePeriod {
  readonly label: string;
  readonly minutes: number;
  readonly matchCount: number;
  readonly fingerprint: PeriodFingerprint;
}

export interface ChallengeUncertainty {
  readonly status: "pending" | "available" | "insufficient";
  /** Present only when `status` is `available`; never synthesised. */
  readonly rankCi95: readonly [number, number] | null;
  readonly designVersion: string | null;
  /** The artifact's own caveat for this status, or `null` for `insufficient`. */
  readonly caveat: Caveat | null;
}

export interface ChallengeRetrieval {
  readonly method: string;
  readonly selfRank: number;
  readonly candidateCount: number;
  /** The published score. `null` when the artifact publishes none. */
  readonly similarityScore: number | null;
  readonly representationId: string;
  readonly baselineSelfRank: number;
  readonly uncertainty: ChallengeUncertainty;
}

export interface ChallengeCopy {
  readonly orientationQuestion: string;
  readonly orientationHeading: string;
  readonly orientationBody: string;
  readonly orientationEditorial: string;
  readonly orientationCta: string;
  readonly queryHeading: string;
  readonly queryBody: string;
  readonly queryCta: string;
  readonly revealHeading: string;
  readonly revealIdentity: string;
  readonly revealBaseline: string;
  readonly revealCtaEvidence: string;
  readonly revealCtaLab: string;
  readonly evidenceHeading: string;
  readonly evidenceCta: string;
  readonly degradedHeading: string;
  readonly degradedResult: string;
}

export interface IdentityChallengeView {
  readonly available: true;
  readonly profileKey: string;
  readonly datasetVersion: string;
  readonly editorialReason: string;
  readonly identity: {
    readonly displayName: string;
    readonly role: string;
    readonly competition: string;
  };
  readonly periods: { readonly a: ChallengePeriod; readonly b: ChallengePeriod };
  readonly retrieval: ChallengeRetrieval;
  /** Weights are fitted for this many of the 32 displayed features (§3.4). */
  readonly fittedFeatureCount: number;
  /** Leading three `family_contribution` items, published order (§3.3). */
  readonly revealFamilies: readonly EvidenceItem[];
  /** Every `family_contribution` item, published order (§3.4). */
  readonly families: readonly EvidenceItem[];
  /** Leading five `feature_contribution` items, published order (§3.4). */
  readonly featureContributions: readonly EvidenceItem[];
  readonly caveats: readonly Caveat[];
  readonly copy: ChallengeCopy;
}

export type IdentityChallenge = IdentityChallengeView | ChallengeRefusal;

export interface IdentityChallengeInput {
  readonly manifest: Manifest;
  readonly profile: PlayerProfileArtifact;
  readonly representation: RepresentationArtifact;
  readonly research: ResearchSummaryArtifact;
}

function refuse(code: ChallengeRefusalCode, message: string): ChallengeRefusal {
  return { available: false, code, message };
}

function period(fingerprint: PeriodFingerprint, context: PeriodContext): ChallengePeriod {
  return {
    label: fingerprint.label,
    minutes: context.minutes,
    matchCount: context.match_count,
    fingerprint,
  };
}

/**
 * Resolve `evidence_refs` against the profile's evidence index.
 *
 * Order is the reference list's order, which is the artifact's published
 * order. The map is a lookup, not a ranking: it never decides which item comes
 * first. A reference that does not resolve, resolves to another subject, or
 * repeats is a refusal, because a partial explanation of a published score is
 * a different explanation.
 */
function resolveEvidence(
  profile: PlayerProfileArtifact,
  outcome: RetrievalOutcome,
): readonly EvidenceItem[] | ChallengeRefusal {
  const index = new Map<string, EvidenceItem>();
  for (const item of profile.evidence_index) {
    if (index.has(item.evidence_id)) {
      return refuse("evidence_unresolved", `Evidence index repeats ${item.evidence_id}`);
    }
    index.set(item.evidence_id, item);
  }

  const seen = new Set<string>();
  const resolved: EvidenceItem[] = [];
  for (const reference of outcome.evidence_refs) {
    if (seen.has(reference)) {
      return refuse("evidence_unresolved", `Evidence reference ${reference} is repeated`);
    }
    seen.add(reference);

    const item = index.get(reference);
    if (item === undefined) {
      return refuse("evidence_unresolved", `Evidence reference ${reference} does not resolve`);
    }
    if (item.subject !== "self_retrieval") {
      return refuse(
        "evidence_unresolved",
        `Evidence ${reference} belongs to ${item.subject}, not self_retrieval`,
      );
    }
    if (item.representation_id !== outcome.representation_id) {
      return refuse(
        "representation_mismatch",
        `Evidence ${reference} names representation ${item.representation_id}, ` +
          `but the retrieval names ${outcome.representation_id}`,
      );
    }
    resolved.push(item);
  }
  return resolved;
}

/**
 * Build the challenge view model, or refuse.
 *
 * Every value on the returned view is copied from an artifact field §11 of the
 * contract allows. Nothing is derived.
 */
export function buildIdentityChallenge(input: IdentityChallengeInput): IdentityChallenge {
  const { manifest, profile, representation, research } = input;

  const profileKey = manifest.featured_profile.profile_key;
  if (profile.profile_key !== profileKey) {
    return refuse(
      "profile_mismatch",
      `The manifest features ${profileKey} but the profile is ${profile.profile_key}`,
    );
  }

  // One dataset version across every artifact. A profile from another export
  // may be internally valid and still describe a different population, which
  // would put a rank beside a candidate count it was never computed against.
  const dataset = manifest.dataset_version;
  for (const [name, version] of [
    ["profile", profile.dataset_version],
    ["representation", representation.dataset_version],
    ["research summary", research.dataset_version],
  ] as const) {
    if (version !== dataset) {
      return refuse(
        "dataset_mismatch",
        `The ${name} is from dataset ${version}, but the manifest publishes ${dataset}`,
      );
    }
  }

  const expectedRepresentation = manifest.representation_id;
  if (representation.representation.id !== expectedRepresentation) {
    return refuse(
      "representation_mismatch",
      `The manifest names representation ${expectedRepresentation}, ` +
        `but the published representation is ${representation.representation.id}`,
    );
  }

  const retrieval = profile.retrieval;
  if (retrieval.method !== V2_RETRIEVAL_METHOD) {
    return refuse(
      "retrieval_method_mismatch",
      `The profile declares method ${retrieval.method}, expected ${V2_RETRIEVAL_METHOD}`,
    );
  }

  // Every outcome the challenge reads must name the same representation. A
  // profile that cannot say which representation produced it is not
  // renderable (§8), and a baseline rank produced under a different one is not
  // comparable to the fingerprint rank shown beside it.
  for (const [name, outcome] of [
    ["global", retrieval.global],
    ["baseline_role_minutes", retrieval.baseline_role_minutes],
  ] as const) {
    if (outcome.representation_id !== expectedRepresentation) {
      return refuse(
        "representation_mismatch",
        `Retrieval ${name} names representation ${outcome.representation_id}, ` +
          `but the manifest names ${expectedRepresentation}`,
      );
    }
  }

  const global = retrieval.global;
  const uncertainty = profile.uncertainty;

  // A design that is present and wrong fails closed: a v1 interval describes
  // the sampling stability of a different metric (§8, `D047`). A null design
  // is not wrong - it is what `pending` and `insufficient` carry, and neither
  // renders an interval, so there is nothing false to show.
  if (uncertainty.design_version !== null && uncertainty.design_version !== V2_UNCERTAINTY_DESIGN) {
    return refuse(
      "uncertainty_design_mismatch",
      `Uncertainty design ${uncertainty.design_version} is not ${V2_UNCERTAINTY_DESIGN}`,
    );
  }
  if (global.uncertainty.status === "available") {
    if (uncertainty.design_version !== V2_UNCERTAINTY_DESIGN) {
      return refuse(
        "uncertainty_design_mismatch",
        `Uncertainty is available but names design ${String(uncertainty.design_version)}`,
      );
    }
    if (global.uncertainty.rank_ci_95 === null) {
      return refuse(
        "uncertainty_interval_missing",
        "Uncertainty reports available but publishes no rank_ci_95 interval",
      );
    }
  }

  const caveatByCode = new Map<string, Caveat>();
  for (const caveat of profile.caveats) {
    caveatByCode.set(caveat.code, caveat);
  }
  for (const code of MANDATORY_CAVEATS) {
    if (!caveatByCode.has(code)) {
      return refuse("missing_caveat", `The profile does not publish the ${code} caveat`);
    }
  }
  const uncertaintyCaveatCode = UNCERTAINTY_CAVEAT_BY_STATUS[global.uncertainty.status];
  if (uncertaintyCaveatCode !== undefined && !caveatByCode.has(uncertaintyCaveatCode)) {
    return refuse(
      "missing_caveat",
      `Uncertainty is ${global.uncertainty.status} but the profile does not publish ` +
        `the ${uncertaintyCaveatCode} caveat`,
    );
  }

  const resolved = resolveEvidence(profile, global);
  if ("available" in resolved) {
    return resolved;
  }

  // Filtering selects by the artifact's own `kind`; it does not reorder. The
  // prefixes below are cuts of a published sequence, not a top-N selection.
  const families = resolved.filter((item) => item.kind === "family_contribution");
  const featureContributions = resolved.filter((item) => item.kind === "feature_contribution");
  if (families.length === 0 || featureContributions.length === 0) {
    return refuse(
      "evidence_empty",
      "The retrieval publishes no family or feature contribution evidence",
    );
  }

  const question = research.narrative_steps.find((step) => step.kind === "question");
  if (question === undefined) {
    return refuse("missing_narrative", "The research summary publishes no question step");
  }

  const identity = profile.identity;
  const displayName = identity.display_name;
  const selfRank = formatRank(global.self_rank);
  const candidateCount = formatRank(global.candidate_count);
  const baselineRank = formatRank(retrieval.baseline_role_minutes.self_rank);

  return {
    available: true,
    profileKey,
    datasetVersion: dataset,
    editorialReason: manifest.featured_profile.reason,
    identity: {
      displayName,
      role: identity.role,
      competition: identity.competition.name,
    },
    periods: {
      a: period(profile.periods.a, identity.period_contexts.a),
      b: period(profile.periods.b, identity.period_contexts.b),
    },
    retrieval: {
      method: retrieval.method,
      selfRank: global.self_rank,
      candidateCount: global.candidate_count,
      similarityScore: global.similarity_score,
      representationId: global.representation_id,
      baselineSelfRank: retrieval.baseline_role_minutes.self_rank,
      uncertainty: {
        status: global.uncertainty.status,
        rankCi95: global.uncertainty.rank_ci_95,
        designVersion: uncertainty.design_version,
        caveat:
          uncertaintyCaveatCode === undefined
            ? null
            : (caveatByCode.get(uncertaintyCaveatCode) ?? null),
      },
    },
    fittedFeatureCount: representation.representation.feature_count,
    revealFamilies: families.slice(0, REVEAL_FAMILY_COUNT),
    families,
    featureContributions: featureContributions.slice(0, EVIDENCE_FEATURE_COUNT),
    caveats: profile.caveats,
    // §12 freezes this copy. Values are interpolated through `formatRank`, the
    // project's declared display rounding, which leaves integers
    // byte-identical (`D046`).
    copy: {
      orientationQuestion: question.title,
      orientationHeading: "Can a player's actions identify them?",
      orientationBody:
        "We take the first half of their season as a query and test whether 32 " +
        "measurements of how they act can find that same player again in the second half.",
      orientationEditorial: manifest.featured_profile.reason,
      orientationCta: "See the fingerprint",
      queryHeading: "One player's first-half fingerprint",
      queryBody:
        "This is one player's first-half fingerprint. Can the same measurements " +
        "find them again in the second half?",
      queryCta: "Reveal the result",
      revealHeading: `The fingerprint found them at rank ${selfRank} of ${candidateCount}.`,
      revealIdentity: `${displayName} · ${identity.role} · ${identity.competition.name}`,
      revealBaseline: `A role-and-minutes baseline ranked them ${baselineRank}.`,
      revealCtaEvidence: "See the evidence",
      revealCtaLab: "Explore every fingerprint",
      evidenceHeading: "What drove the match",
      evidenceCta: "Back to result",
      degradedHeading: "Can a player's actions identify them?",
      degradedResult:
        `${displayName}'s second-half profile was ranked ${selfRank} of ${candidateCount} ` +
        `by fingerprint similarity, versus ${baselineRank} by the role-and-minutes baseline.`,
    },
  };
}
