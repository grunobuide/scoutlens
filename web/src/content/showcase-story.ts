import type {
  Caveat,
  FeatureCatalogArtifact,
  Manifest,
  PlayerProfileArtifact,
  ResearchExperiment,
  ResearchMetric,
  ResearchSummaryArtifact,
} from "@/contracts/generated/showcase";

export const EXPERIMENT_IDS = {
  global: "wyscout_global_gate2",
  withinRole: "wyscout_within_role_gate2",
  teamControl: "wyscout_role_team_minutes",
  transferred: "wyscout_transferred_players",
  replication: "statsbomb_global_replication",
  replicationWithinRole: "statsbomb_within_role_replication",
  replicationTransferred: "statsbomb_transferred_players",
  shrinkage: "wyscout_ratio_shrinkage",
} as const;

export interface FingerprintFeature {
  featureId: string;
  family: string;
  label: string;
  periodA: number;
  periodB: number;
}

export interface ShowcaseStory {
  manifest: Manifest;
  research: ResearchSummaryArtifact;
  featuredProfile: PlayerProfileArtifact;
  featuredName: string;
  featuredTeam: string;
  fingerprintFeatures: ReadonlyArray<FingerprintFeature>;
  experiments: Record<keyof typeof EXPERIMENT_IDS, ResearchExperiment>;
}

function requireExperiment(
  research: ResearchSummaryArtifact,
  experimentId: string,
): ResearchExperiment {
  const experiment = research.experiments.find((item) => item.experiment_id === experimentId);
  if (experiment === undefined) {
    throw new Error(`Required research experiment is missing: ${experimentId}`);
  }
  return experiment;
}

export function requireMetric(experiment: ResearchExperiment, metricId: string): ResearchMetric {
  const metric = experiment.metrics.find((item) => item.metric_id === metricId);
  if (metric === undefined) {
    throw new Error(`Required metric ${metricId} is missing from ${experiment.experiment_id}`);
  }
  return metric;
}

export function formatMetric(metric: ResearchMetric): string {
  return metric.value.toFixed(metric.display_precision);
}

export function formatMetricInterval(metric: ResearchMetric): string | null {
  if (metric.ci_95 === null) {
    return null;
  }
  return metric.ci_95.map((value) => value.toFixed(metric.display_precision)).join(" to ");
}

export function caveatsFor(
  research: ResearchSummaryArtifact,
  experiment: ResearchExperiment,
): ReadonlyArray<Caveat> {
  return experiment.caveat_codes.map((code) => {
    const caveat = research.caveats.find((item) => item.code === code);
    if (caveat === undefined) {
      throw new Error(`Required caveat is missing: ${code}`);
    }
    return caveat;
  });
}

function decodeEscapedUnicode(value: string): string {
  return value.replace(/\\u([0-9a-fA-F]{4})/g, (_, code: string) =>
    String.fromCodePoint(Number.parseInt(code, 16)),
  );
}

function selectFingerprintFeatures(
  catalog: FeatureCatalogArtifact,
  profile: PlayerProfileArtifact,
): ReadonlyArray<FingerprintFeature> {
  const definitionsByFamily = new Map<string, Array<(typeof catalog.features)[number]>>();
  for (const definition of catalog.features) {
    const definitions = definitionsByFamily.get(definition.family) ?? [];
    definitions.push(definition);
    definitionsByFamily.set(definition.family, definitions);
  }

  const periodA = new Map(profile.periods.a.features.map((item) => [item.feature_id, item]));
  const periodB = new Map(profile.periods.b.features.map((item) => [item.feature_id, item]));

  return [...definitionsByFamily.entries()].map(([family, definitions]) => {
    const values = definitions.map((definition) => {
      const a = periodA.get(definition.feature_id);
      const b = periodB.get(definition.feature_id);
      if (a === undefined || b === undefined) {
        throw new Error(`Featured profile is missing ${definition.feature_id}`);
      }
      return { a: a.within_role_percentile, b: b.within_role_percentile };
    });
    const title = family.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
    return {
      featureId: `family:${family}`,
      family: `${definitions.length} features`,
      label: title,
      periodA: values.reduce((sum, item) => sum + item.a, 0) / values.length,
      periodB: values.reduce((sum, item) => sum + item.b, 0) / values.length,
    };
  });
}

export function buildShowcaseStory(
  manifest: Manifest,
  research: ResearchSummaryArtifact,
  featuredProfile: PlayerProfileArtifact,
  catalog: FeatureCatalogArtifact,
): ShowcaseStory {
  if (featuredProfile.profile_key !== manifest.featured_profile.profile_key) {
    throw new Error("The loaded profile is not the editorially featured profile");
  }

  const experiments = Object.fromEntries(
    Object.entries(EXPERIMENT_IDS).map(([key, experimentId]) => [
      key,
      requireExperiment(research, experimentId),
    ]),
  ) as ShowcaseStory["experiments"];

  const teams = featuredProfile.identity.period_contexts.a.teams.map((team) => team.name);
  return {
    manifest,
    research,
    featuredProfile,
    featuredName: decodeEscapedUnicode(featuredProfile.identity.display_name),
    featuredTeam: teams.join(" / "),
    fingerprintFeatures: selectFingerprintFeatures(catalog, featuredProfile),
    experiments,
  };
}
