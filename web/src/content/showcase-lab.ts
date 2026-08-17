import type {
  EvidenceItem,
  FeatureDefinition,
  FeatureValue,
  RetrievalOutcome,
  StatisticalNeighbor,
} from "@/contracts/generated/showcase";
import type {
  EvidenceItem as EvidenceItemV2,
  FeatureDefinition as FeatureDefinitionV2,
  FeatureValue as FeatureValueV2,
  RetrievalOutcome as RetrievalOutcomeV2,
  StatisticalNeighbor as StatisticalNeighborV2,
} from "@/contracts/generated/showcase-v2";
import type {
  AnyFeatureCatalogArtifact,
  AnyPlayerIndexItem,
  AnyPlayerProfileArtifact,
} from "@/contracts/showcase-repository";

export type AnyEvidenceItem = EvidenceItem | EvidenceItemV2;
export type AnyFeatureDefinition = FeatureDefinition | FeatureDefinitionV2;
export type AnyFeatureValue = FeatureValue | FeatureValueV2;
export type AnyRetrievalOutcome = RetrievalOutcome | RetrievalOutcomeV2;
export type AnyStatisticalNeighbor = StatisticalNeighbor | StatisticalNeighborV2;

/**
 * Which published field carries the score, per contract major.
 *
 * v2 renamed `cosine_similarity` to `similarity_score` because a weighted
 * metric must not be published under a name claiming plain cosine (D047).
 * These readers narrow on the field that is present. They never compute a
 * score, and there is no fallback branch that would let a missing field read
 * as zero - a missing field is a type error here, not a silent nought.
 */
export function retrievalScore(outcome: AnyRetrievalOutcome): number | null {
  return "similarity_score" in outcome ? outcome.similarity_score : outcome.cosine_similarity;
}

export function neighborScore(neighbor: AnyStatisticalNeighbor): number {
  return "similarity_score" in neighbor ? neighbor.similarity_score : neighbor.cosine_similarity;
}

/**
 * The contribution a subject's evidence is ordered and summed by.
 *
 * The rule is unchanged between majors - descending magnitude, ties broken by
 * catalog order - but it applies to each major's own contribution to the score
 * it publishes. In v2 `contribution` remains the unweighted cosine audit view,
 * so ordering by it would rank the explanation by a number the reader is never
 * shown, and summing it would fail to reconstruct `similarity_score`.
 */
export function evidenceContribution(item: AnyEvidenceItem): number {
  return "weighted_contribution" in item ? item.weighted_contribution : item.contribution;
}

export type PercentileScope = "within_role" | "global";

export interface ProfileFilters {
  query: string;
  role: string;
  competition: string;
  team: string;
}

export interface ProfileFilterOptions {
  roles: ReadonlyArray<string>;
  competitions: ReadonlyArray<string>;
  teams: ReadonlyArray<string>;
}

export interface FingerprintRow {
  definition: AnyFeatureDefinition;
  periodA: AnyFeatureValue;
  periodB: AnyFeatureValue;
}

export interface FingerprintFamily {
  family: string;
  label: string;
  rows: ReadonlyArray<FingerprintRow>;
}

export interface ContributionEvidence {
  features: ReadonlyArray<AnyEvidenceItem>;
  families: ReadonlyArray<AnyEvidenceItem>;
  featureSum: number;
  familySum: number;
}

export interface NeighborEvidence {
  neighbor: AnyStatisticalNeighbor;
  evidence: ContributionEvidence;
}

export interface ProfileEvidence {
  self: ContributionEvidence;
  neighbors: ReadonlyArray<NeighborEvidence>;
}

export type LabProblemKind =
  | "unknown-profile"
  | "missing-asset"
  | "integrity"
  | "incompatible-data"
  | "unavailable";

export interface LabProblem {
  kind: LabProblemKind;
  eyebrow: string;
  title: string;
  message: string;
  canRetry: boolean;
}

const identityCollator = new Intl.Collator("en", {
  numeric: true,
  sensitivity: "base",
});

const CONTRIBUTION_TOLERANCE = 1e-9;

export const EMPTY_PROFILE_FILTERS: ProfileFilters = {
  query: "",
  role: "",
  competition: "",
  team: "",
};

export function normalizeSearchText(value: string): string {
  return value
    .normalize("NFKD")
    .replace(/\p{M}/gu, "")
    .toLocaleLowerCase("en")
    .trim();
}

export function profileTeamNames(profile: AnyPlayerIndexItem): ReadonlyArray<string> {
  return [
    ...new Set(
      [...profile.period_contexts.a.teams, ...profile.period_contexts.b.teams].map((team) => team.name),
    ),
  ].sort(identityCollator.compare);
}

export function buildProfileFilterOptions(
  profiles: ReadonlyArray<AnyPlayerIndexItem>,
): ProfileFilterOptions {
  const uniqueSorted = (values: ReadonlyArray<string>) =>
    [...new Set(values)].sort(identityCollator.compare);

  return {
    roles: uniqueSorted(profiles.map((profile) => profile.role)),
    competitions: uniqueSorted(profiles.map((profile) => profile.competition.name)),
    teams: uniqueSorted(profiles.flatMap(profileTeamNames)),
  };
}

function compareProfiles(left: AnyPlayerIndexItem, right: AnyPlayerIndexItem): number {
  return (
    identityCollator.compare(left.display_name, right.display_name) ||
    identityCollator.compare(left.competition.name, right.competition.name) ||
    identityCollator.compare(left.profile_key, right.profile_key)
  );
}

export function filterProfiles(
  profiles: ReadonlyArray<AnyPlayerIndexItem>,
  filters: ProfileFilters,
): ReadonlyArray<AnyPlayerIndexItem> {
  const queryTokens = normalizeSearchText(filters.query).split(/\s+/).filter(Boolean);
  return profiles
    .filter((profile) => {
      const searchText = normalizeSearchText(
        [
          profile.display_name,
          profile.role,
          profile.competition.name,
          profile.competition.country,
          ...profileTeamNames(profile),
        ].join(" "),
      );
      return (
        queryTokens.every((token) => searchText.includes(token)) &&
        (filters.role === "" || profile.role === filters.role) &&
        (filters.competition === "" || profile.competition.name === filters.competition) &&
        (filters.team === "" || profileTeamNames(profile).includes(filters.team))
      );
    })
    .sort(compareProfiles);
}

function featureMap(values: ReadonlyArray<FeatureValue>, period: string): Map<string, FeatureValue> {
  const result = new Map<string, FeatureValue>();
  for (const value of values) {
    if (result.has(value.feature_id)) {
      throw new Error(`Period ${period} repeats feature ${value.feature_id}`);
    }
    result.set(value.feature_id, value);
  }
  return result;
}

export function buildFingerprintRows(
  catalog: AnyFeatureCatalogArtifact,
  profile: AnyPlayerProfileArtifact,
): ReadonlyArray<FingerprintRow> {
  if (
    catalog.features.length !== 32 ||
    profile.periods.a.features.length !== 32 ||
    profile.periods.b.features.length !== 32
  ) {
    throw new Error("The frozen fingerprint must contain exactly 32 features");
  }

  const periodA = featureMap(profile.periods.a.features, "A");
  const periodB = featureMap(profile.periods.b.features, "B");
  const definitions = [...catalog.features].sort((left, right) => left.order - right.order);

  return definitions.map((definition) => {
    const a = periodA.get(definition.feature_id);
    const b = periodB.get(definition.feature_id);
    if (a === undefined || b === undefined) {
      throw new Error(`Profile ${profile.profile_key} is missing ${definition.feature_id}`);
    }
    return { definition, periodA: a, periodB: b };
  });
}

export function familyLabel(family: string): string {
  return family.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function groupFingerprintRows(
  rows: ReadonlyArray<FingerprintRow>,
): ReadonlyArray<FingerprintFamily> {
  const groups = new Map<string, FingerprintRow[]>();
  for (const row of rows) {
    const group = groups.get(row.definition.family) ?? [];
    group.push(row);
    groups.set(row.definition.family, group);
  }
  return [...groups.entries()].map(([family, familyRows]) => ({
    family,
    label: familyLabel(family),
    rows: familyRows,
  }));
}

function contributionSum(items: ReadonlyArray<AnyEvidenceItem>): number {
  return items.reduce((sum, item) => sum + evidenceContribution(item), 0);
}

function assertContributionSum(
  actual: number,
  expected: number,
  label: string,
): void {
  if (Math.abs(actual - expected) > CONTRIBUTION_TOLERANCE) {
    throw new Error(
      `${label} contribution sum ${actual} does not reconstruct the stored score ${expected}`,
    );
  }
}

function sameOrderedIds(
  actual: ReadonlyArray<AnyEvidenceItem>,
  expected: ReadonlyArray<AnyEvidenceItem>,
): boolean {
  return actual.every((item, index) => item.evidence_id === expected[index]?.evidence_id);
}

export function resolveContributionEvidence(
  catalog: AnyFeatureCatalogArtifact,
  profile: AnyPlayerProfileArtifact,
  evidenceRefs: ReadonlyArray<string>,
  subject: string,
  expectedScore: number,
): ContributionEvidence {
  if (new Set(evidenceRefs).size !== evidenceRefs.length) {
    throw new Error(`${subject} repeats an evidence reference`);
  }

  const evidenceById = new Map<string, AnyEvidenceItem>();
  for (const item of profile.evidence_index) {
    if (evidenceById.has(item.evidence_id)) {
      throw new Error(`Evidence index repeats ${item.evidence_id}`);
    }
    evidenceById.set(item.evidence_id, item);
  }

  const resolved = evidenceRefs.map((reference) => {
    const item = evidenceById.get(reference);
    if (item === undefined) {
      throw new Error(`${subject} cannot resolve evidence ${reference}`);
    }
    if (item.subject !== subject) {
      throw new Error(`${reference} belongs to ${item.subject}, not ${subject}`);
    }
    return item;
  });
  const features = resolved.filter((item) => item.kind === "feature_contribution");
  const families = resolved.filter((item) => item.kind === "family_contribution");
  if (features.length !== 32 || families.length !== 8) {
    throw new Error(`${subject} must resolve 32 feature and eight family contributions`);
  }

  const definitions = [...catalog.features].sort((left, right) => left.order - right.order);
  const featureOrder = new Map(definitions.map((definition, index) => [definition.feature_id, index]));
  const familyOrder = new Map<string, number>();
  for (const definition of definitions) {
    if (!familyOrder.has(definition.family)) {
      familyOrder.set(definition.family, familyOrder.size);
    }
  }
  if (featureOrder.size !== 32 || familyOrder.size !== 8) {
    throw new Error("The evidence contract requires 32 features across eight families");
  }

  const observedFeatures = new Set<string>();
  for (const item of features) {
    if (item.feature_id === null || !featureOrder.has(item.feature_id) || observedFeatures.has(item.feature_id)) {
      throw new Error(`${subject} has an invalid or repeated feature contribution`);
    }
    observedFeatures.add(item.feature_id);
  }
  const observedFamilies = new Set<string>(families.map((item) => item.family));
  if (observedFamilies.size !== 8 || [...familyOrder.keys()].some((family) => !observedFamilies.has(family))) {
    throw new Error(`${subject} family contributions do not match the feature catalog`);
  }

  const sortedFeatures = [...features].sort(
    (left, right) =>
      Math.abs(evidenceContribution(right)) - Math.abs(evidenceContribution(left)) ||
      (featureOrder.get(left.feature_id ?? "") ?? Number.MAX_SAFE_INTEGER) -
        (featureOrder.get(right.feature_id ?? "") ?? Number.MAX_SAFE_INTEGER) ||
      identityCollator.compare(left.evidence_id, right.evidence_id),
  );
  const sortedFamilies = [...families].sort(
    (left, right) =>
      Math.abs(evidenceContribution(right)) - Math.abs(evidenceContribution(left)) ||
      (familyOrder.get(left.family) ?? Number.MAX_SAFE_INTEGER) -
        (familyOrder.get(right.family) ?? Number.MAX_SAFE_INTEGER) ||
      identityCollator.compare(left.evidence_id, right.evidence_id),
  );
  if (!sameOrderedIds(features, sortedFeatures) || !sameOrderedIds(families, sortedFamilies)) {
    throw new Error(`${subject} contribution evidence is not in deterministic contract order`);
  }

  const featureSum = contributionSum(features);
  const familySum = contributionSum(families);
  assertContributionSum(featureSum, expectedScore, `${subject} feature`);
  assertContributionSum(familySum, expectedScore, `${subject} family`);
  return { features, families, featureSum, familySum };
}

export function buildProfileEvidence(
  catalog: AnyFeatureCatalogArtifact,
  profile: AnyPlayerProfileArtifact,
): ProfileEvidence {
  if (profile.neighbors.length !== 5) {
    throw new Error("The retrieval evidence contract requires exactly five neighbors");
  }

  const globalScore = retrievalScore(profile.retrieval.global);
  const withinRoleScore = retrievalScore(profile.retrieval.within_role);
  if (globalScore === null || withinRoleScore === null) {
    throw new Error("Combined-scaler retrieval must expose a stored similarity score");
  }
  if (
    profile.retrieval.global.evidence_refs.join("\u0000") !==
    profile.retrieval.within_role.evidence_refs.join("\u0000")
  ) {
    throw new Error("Global and within-role retrieval must reference the same stored self evidence");
  }
  const self = resolveContributionEvidence(
    catalog,
    profile,
    profile.retrieval.global.evidence_refs,
    "self_retrieval",
    globalScore,
  );
  assertContributionSum(self.featureSum, withinRoleScore, "within-role self feature");
  if (
    retrievalScore(profile.retrieval.baseline_role_minutes) !== null ||
    profile.retrieval.baseline_role_minutes.evidence_refs.length !== 0
  ) {
    throw new Error("Role-and-minutes baseline cannot expose similarity evidence");
  }

  const seenProfiles = new Set<string>();
  const seenPlayers = new Set<string>();
  const neighbors = profile.neighbors.map((neighbor, index) => {
    if (
      neighbor.rank !== index + 1 ||
      neighbor.candidate_period !== "b" ||
      neighbor.role !== profile.identity.role ||
      neighbor.player_key === profile.identity.player_key ||
      seenProfiles.has(neighbor.profile_key) ||
      seenPlayers.has(neighbor.player_key)
    ) {
      throw new Error(`Neighbor rank ${index + 1} violates the stored non-self within-role contract`);
    }
    seenProfiles.add(neighbor.profile_key);
    seenPlayers.add(neighbor.player_key);
    return {
      neighbor,
      evidence: resolveContributionEvidence(
        catalog,
        profile,
        neighbor.evidence_refs,
        `neighbor:${neighbor.profile_key}`,
        neighborScore(neighbor),
      ),
    };
  });
  return { self, neighbors };
}

export function formatCosine(value: number): string {
  return value.toFixed(4);
}

export function formatContribution(value: number): string {
  if (Math.abs(value) < 0.00005) {
    return "0.0000";
  }
  return `${value > 0 ? "+" : ""}${value.toFixed(4)}`;
}

export function percentileFor(value: FeatureValue, scope: PercentileScope): number {
  return scope === "within_role" ? value.within_role_percentile : value.global_percentile;
}

export function formatPercentile(value: number): string {
  return value.toFixed(1);
}

export function formatZScore(value: number): string {
  if (value === 0) {
    return "0.00";
  }
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}`;
}

export function formatRawValue(value: FeatureValue, definition: FeatureDefinition): string {
  if (value.raw_value === null) {
    return "Not observed";
  }
  switch (definition.unit) {
    case "ratio":
      return `${(value.raw_value * 100).toFixed(Math.max(1, definition.display_precision - 2))}%`;
    case "pitch_percent":
      return `${value.raw_value.toFixed(definition.display_precision)}% pitch`;
    case "distance_per_90":
      return `${value.raw_value.toFixed(definition.display_precision)} pitch units /90`;
    case "per_90":
      return `${value.raw_value.toFixed(definition.display_precision)} /90`;
  }
}

export function formatSupport(value: FeatureValue): string {
  const minutes = `${value.support.minutes.toLocaleString("en-US")} min`;
  if (value.support.attempts === null) {
    return minutes;
  }
  if (value.support.successes === null) {
    return `${minutes}; ${value.support.attempts.toLocaleString("en-US")} attempts`;
  }
  return `${minutes}; ${value.support.successes.toLocaleString("en-US")}/${value.support.attempts.toLocaleString("en-US")} successes`;
}

export function buildFingerprintSummary(
  rows: ReadonlyArray<FingerprintRow>,
  scope: PercentileScope,
): string {
  const largestShift = rows
    .map((row) => ({
      label: row.definition.label,
      shift: Math.abs(percentileFor(row.periodB, scope) - percentileFor(row.periodA, scope)),
    }))
    .sort((left, right) => right.shift - left.shift || identityCollator.compare(left.label, right.label))[0];
  const familyCount = new Set(rows.map((row) => row.definition.family)).size;
  const scopeLabel = scope === "within_role" ? "within-role" : "global";
  return `${rows.length} features across ${familyCount} families compare period A with period B on the ${scopeLabel} percentile scale. The largest period shift is ${largestShift?.label ?? "unavailable"} at ${largestShift?.shift.toFixed(1) ?? "0.0"} percentile points.`;
}

export function profileHref(profileKey: string): string {
  return `/lab/?player=${encodeURIComponent(profileKey)}`;
}

export function describeLabError(error: unknown): LabProblem {
  const code =
    typeof error === "object" && error !== null && "code" in error && typeof error.code === "string"
      ? error.code
      : null;
  if (code !== null) {
    if (code === "profile_mismatch") {
      return {
        kind: "unknown-profile",
        eyebrow: "Profile unavailable",
        title: "That profile is not in this dataset version",
        message:
          "The catalog remains available. Choose another player and the outdated key will be replaced in the URL.",
        canRetry: false,
      };
    }
    if (code === "http_error") {
      return {
        kind: "missing-asset",
        eyebrow: "Static asset unavailable",
        title: "The selected data file could not be loaded",
        message:
          "No placeholder numbers are shown. Retry the verified asset or inspect the scientific record while the file is restored.",
        canRetry: true,
      };
    }
    if (code === "checksum_mismatch" || code === "byte_count_mismatch") {
      return {
        kind: "integrity",
        eyebrow: "Integrity check failed",
        title: "This profile does not match the active manifest",
        message:
          "ScoutLens stopped before rendering any profile values. Refresh the versioned assets, then retry.",
        canRetry: true,
      };
    }
    if (
      code === "schema_validation" ||
      code === "unsupported_schema_major" ||
      code === "artifact_kind" ||
      code === "dataset_mismatch" ||
      code === "invalid_json"
    ) {
      return {
        kind: "incompatible-data",
        eyebrow: "Incompatible data",
        title: "The selected profile failed contract validation",
        message:
          "The Lab fails closed when schema or dataset versions disagree. No partially trusted values are displayed.",
        canRetry: true,
      };
    }
  }
  return {
    kind: "unavailable",
    eyebrow: "Lab unavailable",
    title: "The verified showcase data could not be prepared",
    message:
      "Retry the data load or continue to the scientific record; the Lab will not invent fallback players or values.",
    canRetry: true,
  };
}

/**
 * The frozen v2 method disclosure, frozen by `scoutlens-qop.6.5`.
 *
 * One typed source, rendered in one place. Every sentence here is contractual:
 * the label, the fitted-weight disclosure, the unit-weight audit statement, the
 * unsupported-claim boundary and the advanced section were fixed by the bead
 * before the migration started, so a future edit is a decision rather than a
 * wording preference.
 *
 * No metric value is duplicated into this text. `featureCount` is read from the
 * published representation at render time, because a number retyped into copy
 * is a number that can silently disagree with the artifact it describes.
 */
export interface MethodDisclosure {
  label: string;
  summary: string;
  auditStatement: string;
  boundary: string;
  advancedTitle: string;
  advancedBody: string;
  decisionUrl: string;
}

const DECISION_LOG_D045 =
  "https://github.com/grunobuide/scoutlens/blob/main/docs/decisions-log.md#d045";

export function methodDisclosure(featureCount: number): MethodDisclosure {
  return {
    label: "Learned weighted similarity",
    summary:
      `Ranks use ${featureCount} non-negative feature weights fitted on the frozen ` +
      "Wyscout training split.",
    auditStatement:
      "Unit weights reproduce the cosine audit baseline exactly, so the frozen cosine " +
      "contract remains a faithful check on this one rather than a different family of method.",
    boundary:
      "The gain concerns temporal identity retrieval. It does not measure player quality, " +
      "tactical fit or recruitment value.",
    advancedTitle: "Why this model, and why not the neural one?",
    advancedBody:
      "Cosine remains the transparent audit baseline: it is published in full under the frozen " +
      "1.0.0 contract and any ranking here can be checked against it. The preregistered compact " +
      "neural arm lost to this interpretable weighted model, so it was not promoted.",
    decisionUrl: DECISION_LOG_D045,
  };
}
