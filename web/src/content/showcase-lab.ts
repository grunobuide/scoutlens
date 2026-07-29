import type {
  FeatureCatalogArtifact,
  FeatureDefinition,
  FeatureValue,
  PlayerIndexItem,
  PlayerProfileArtifact,
} from "@/contracts/generated/showcase";

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
  definition: FeatureDefinition;
  periodA: FeatureValue;
  periodB: FeatureValue;
}

export interface FingerprintFamily {
  family: string;
  label: string;
  rows: ReadonlyArray<FingerprintRow>;
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

export const EMPTY_PROFILE_FILTERS: ProfileFilters = {
  query: "",
  role: "",
  competition: "",
  team: "",
};

export function decodeIdentityText(value: string): string {
  return value.replace(/\\u([0-9a-fA-F]{4})/g, (_, code: string) =>
    String.fromCodePoint(Number.parseInt(code, 16)),
  );
}

export function normalizeSearchText(value: string): string {
  return decodeIdentityText(value)
    .normalize("NFKD")
    .replace(/\p{M}/gu, "")
    .toLocaleLowerCase("en")
    .trim();
}

export function profileTeamNames(profile: PlayerIndexItem): ReadonlyArray<string> {
  return [
    ...new Set(
      [...profile.period_contexts.a.teams, ...profile.period_contexts.b.teams].map((team) =>
        decodeIdentityText(team.name),
      ),
    ),
  ].sort(identityCollator.compare);
}

export function buildProfileFilterOptions(
  profiles: ReadonlyArray<PlayerIndexItem>,
): ProfileFilterOptions {
  const uniqueSorted = (values: ReadonlyArray<string>) =>
    [...new Set(values.map(decodeIdentityText))].sort(identityCollator.compare);

  return {
    roles: uniqueSorted(profiles.map((profile) => profile.role)),
    competitions: uniqueSorted(profiles.map((profile) => profile.competition.name)),
    teams: uniqueSorted(profiles.flatMap(profileTeamNames)),
  };
}

function compareProfiles(left: PlayerIndexItem, right: PlayerIndexItem): number {
  return (
    identityCollator.compare(
      decodeIdentityText(left.display_name),
      decodeIdentityText(right.display_name),
    ) ||
    identityCollator.compare(left.competition.name, right.competition.name) ||
    identityCollator.compare(left.profile_key, right.profile_key)
  );
}

export function filterProfiles(
  profiles: ReadonlyArray<PlayerIndexItem>,
  filters: ProfileFilters,
): ReadonlyArray<PlayerIndexItem> {
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
  catalog: FeatureCatalogArtifact,
  profile: PlayerProfileArtifact,
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
