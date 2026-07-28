/** Generated from src/scoutlens/showcase/schemas/showcase-1.0.0.schema.json.
 * Do not edit by hand; run pnpm contracts:generate.
 */

export type ScoutLensShowcaseArtifacts100 =
  Manifest | FeatureCatalogArtifact | PlayerIndexArtifact | PlayerProfileArtifact | ResearchSummaryArtifact;
export type DatasetVersion = string;
export type ProfileKey = string;
export type Sha256 = string;
export type Family =
  | "passing"
  | "progression"
  | "chance_creation"
  | "shooting"
  | "defensive"
  | "spatial"
  | "possession"
  | "carrying_proxy";
export type PlayerKey = string;
export type Role = "Goalkeeper" | "Defender" | "Midfielder" | "Forward";
export type CaveatCode =
  | "fingerprint_not_style_proof"
  | "similarity_not_recruitment"
  | "same_season_team_confound"
  | "small_transfer_sample"
  | "provider_replication_lower_magnitude"
  | "within_role_display_differs_from_global_model"
  | "uncertainty_pending"
  | "uncertainty_sampling_only"
  | "goalkeeper_feature_coverage_weak";

export interface Manifest {
  contract: "scoutlens.showcase";
  schema_version: "1.0.0";
  dataset_version: DatasetVersion;
  generated_at: string;
  featured_profile: {
    profile_key: ProfileKey;
    editorial: true;
    reason: string;
  };
  source: {
    provider: "wyscout_pappalardo";
    season: "2017/18";
    title: string;
    citation: string;
    source_url: string;
    licence: "CC BY 4.0";
    licence_url: string;
    redistribution_note: string;
  };
  population: {
    analytical_unit: "player_competition";
    chronological_periods: ["a", "b"];
    /**
     * @minItems 1
     */
    domestic_competition_ids: [number, ...number[]];
    minutes_threshold_per_period: 450;
    profile_count: number;
    feature_count: 32;
  };
  producer: {
    git_commit: string | null;
    git_dirty: boolean | null;
    source_sha256: Sha256;
    config_path: "config/experiment.json";
    config_sha256: Sha256;
    python_version: string;
    polars_version: string;
  };
  /**
   * @minItems 1
   */
  inputs: [
    {
      logical_name: string;
      sha256: Sha256;
      bytes: number;
      public: false;
    },
    ...{
      logical_name: string;
      sha256: Sha256;
      bytes: number;
      public: false;
    }[]
  ];
  /**
   * @minItems 4
   */
  files: [
    {
      path: string;
      media_type: "application/json";
      sha256: Sha256;
      bytes: number;
      records: number;
    },
    {
      path: string;
      media_type: "application/json";
      sha256: Sha256;
      bytes: number;
      records: number;
    },
    {
      path: string;
      media_type: "application/json";
      sha256: Sha256;
      bytes: number;
      records: number;
    },
    {
      path: string;
      media_type: "application/json";
      sha256: Sha256;
      bytes: number;
      records: number;
    },
    ...{
      path: string;
      media_type: "application/json";
      sha256: Sha256;
      bytes: number;
      records: number;
    }[]
  ];
}
export interface FeatureCatalogArtifact {
  contract: "scoutlens.showcase";
  schema_version: "1.0.0";
  dataset_version: DatasetVersion;
  /**
   * @minItems 32
   * @maxItems 32
   */
  features: [
    FeatureDefinition,
    FeatureDefinition,
    FeatureDefinition,
    FeatureDefinition,
    FeatureDefinition,
    FeatureDefinition,
    FeatureDefinition,
    FeatureDefinition,
    FeatureDefinition,
    FeatureDefinition,
    FeatureDefinition,
    FeatureDefinition,
    FeatureDefinition,
    FeatureDefinition,
    FeatureDefinition,
    FeatureDefinition,
    FeatureDefinition,
    FeatureDefinition,
    FeatureDefinition,
    FeatureDefinition,
    FeatureDefinition,
    FeatureDefinition,
    FeatureDefinition,
    FeatureDefinition,
    FeatureDefinition,
    FeatureDefinition,
    FeatureDefinition,
    FeatureDefinition,
    FeatureDefinition,
    FeatureDefinition,
    FeatureDefinition,
    FeatureDefinition
  ];
}
export interface FeatureDefinition {
  feature_id: string;
  label: string;
  short_label: string;
  family: Family;
  order: number;
  description: string;
  unit: "per_90" | "ratio" | "pitch_percent" | "distance_per_90";
  display_precision: number;
  raw_null_meaning: "no_attempts" | "not_observed" | null;
  model_null_handling: "population_mean_then_z_zero";
  direction_semantics: "descriptive_not_quality";
  support_kind: "minutes" | "attempts";
  method_ref: string;
}
export interface PlayerIndexArtifact {
  contract: "scoutlens.showcase";
  schema_version: "1.0.0";
  dataset_version: DatasetVersion;
  profiles: PlayerIndexItem[];
}
export interface PlayerIndexItem {
  player_key: PlayerKey;
  profile_key: ProfileKey;
  display_name: string;
  role: Role;
  competition: Competition;
  period_contexts: {
    a: PeriodContext;
    b: PeriodContext;
  };
  total_minutes: number;
  self_rank_within_role: number;
  uncertainty_status: "pending" | "available" | "insufficient";
  artifact_path: string;
}
export interface Competition {
  id: number;
  name: string;
  country: string;
}
export interface PeriodContext {
  minutes: number;
  match_count: number;
  /**
   * @minItems 1
   */
  teams: [TeamMinutes, ...TeamMinutes[]];
}
export interface TeamMinutes {
  id: number;
  name: string;
  minutes: number;
}
export interface PlayerProfileArtifact {
  contract: "scoutlens.showcase";
  schema_version: "1.0.0";
  dataset_version: DatasetVersion;
  profile_key: ProfileKey;
  identity: {
    player_key: PlayerKey;
    display_name: string;
    role: Role;
    competition: Competition;
    season: "2017/18";
    period_contexts: {
      a: PeriodContext;
      b: PeriodContext;
    };
  };
  cohort: {
    global_profile_count: number;
    within_role_profile_count: number;
    minutes_threshold_per_period: 450;
    scaler_scope: "eligible_period_a_and_b_combined";
    default_display_percentile_scope: "within_role";
  };
  periods: {
    a: PeriodFingerprint;
    b: PeriodFingerprint;
  };
  retrieval: IdentityRetrieval;
  /**
   * @minItems 5
   * @maxItems 5
   */
  neighbors: [StatisticalNeighbor, StatisticalNeighbor, StatisticalNeighbor, StatisticalNeighbor, StatisticalNeighbor];
  uncertainty: UncertaintyBlock;
  /**
   * @minItems 5
   */
  caveats: [Caveat, Caveat, Caveat, Caveat, Caveat, ...Caveat[]];
  /**
   * @minItems 240
   */
  evidence_index: [
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    EvidenceItem,
    ...EvidenceItem[]
  ];
  provenance_ref: "manifest.json";
}
export interface PeriodFingerprint {
  label: string;
  date_start: string;
  date_end: string;
  minutes: number;
  match_count: number;
  /**
   * @minItems 32
   * @maxItems 32
   */
  features: [
    FeatureValue,
    FeatureValue,
    FeatureValue,
    FeatureValue,
    FeatureValue,
    FeatureValue,
    FeatureValue,
    FeatureValue,
    FeatureValue,
    FeatureValue,
    FeatureValue,
    FeatureValue,
    FeatureValue,
    FeatureValue,
    FeatureValue,
    FeatureValue,
    FeatureValue,
    FeatureValue,
    FeatureValue,
    FeatureValue,
    FeatureValue,
    FeatureValue,
    FeatureValue,
    FeatureValue,
    FeatureValue,
    FeatureValue,
    FeatureValue,
    FeatureValue,
    FeatureValue,
    FeatureValue,
    FeatureValue,
    FeatureValue
  ];
}
export interface FeatureValue {
  feature_id: string;
  raw_value: number | null;
  global_z_score: number;
  global_percentile: number;
  within_role_percentile: number;
  imputed_for_model: boolean;
  support: {
    minutes: number;
    attempts: number | null;
    successes: number | null;
  };
  uncertainty: FeatureUncertainty;
}
export interface FeatureUncertainty {
  status: "pending" | "available" | "insufficient";
  valid_resamples: number | null;
  raw_ci_95: null | never[];
  within_role_percentile_ci_95: null | never[];
}
export interface IdentityRetrieval {
  query_period: "a";
  candidate_period: "b";
  method: "combined_scaler_cosine_v1";
  global: RetrievalOutcome;
  within_role: RetrievalOutcome;
  baseline_role_minutes: RetrievalOutcome;
}
export interface RetrievalOutcome {
  candidate_count: number;
  self_rank: number;
  reciprocal_rank: number;
  cosine_similarity: number | null;
  evidence_refs: string[];
  uncertainty: RankUncertainty;
}
export interface RankUncertainty {
  status: "pending" | "available" | "insufficient";
  valid_resamples: number | null;
  median_rank: number | null;
  rank_ci_95: null | never[];
  recall_at_1_rate: number | null;
  recall_at_5_rate: number | null;
  recall_at_10_rate: number | null;
}
export interface StatisticalNeighbor {
  rank: 1 | 2 | 3 | 4 | 5;
  player_key: PlayerKey;
  profile_key: ProfileKey;
  display_name: string;
  role: Role;
  competition: Competition;
  /**
   * @minItems 1
   */
  teams: [
    {
      id: number;
      name: string;
    },
    ...{
      id: number;
      name: string;
    }[]
  ];
  candidate_period: "b";
  cosine_similarity: number;
  /**
   * @minItems 40
   * @maxItems 40
   */
  evidence_refs: [
    string,
    string,
    string,
    string,
    string,
    string,
    string,
    string,
    string,
    string,
    string,
    string,
    string,
    string,
    string,
    string,
    string,
    string,
    string,
    string,
    string,
    string,
    string,
    string,
    string,
    string,
    string,
    string,
    string,
    string,
    string,
    string,
    string,
    string,
    string,
    string,
    string,
    string,
    string,
    string
  ];
  stability: NeighborStability;
}
export interface NeighborStability {
  status: "pending" | "available" | "insufficient";
  valid_resamples: number | null;
  top_5_selection_rate: number | null;
  median_rank: number | null;
  rank_ci_95: null | never[];
}
export interface UncertaintyBlock {
  status: "pending" | "available" | "insufficient";
  design_version: "match_bootstrap_v1" | null;
  seed: 1729 | null;
  requested_resamples: 500 | null;
  valid_resamples: number | null;
  interval: "percentile_95" | null;
  resampling_unit: "whole_match_stratified_by_competition_and_period" | null;
  cohort_policy: "fixed_observed_eligible_cohort" | null;
  warning: string;
}
export interface Caveat {
  code: CaveatCode;
  severity: "context" | "important" | "critical";
  message: string;
  evidence_refs: string[];
}
export interface EvidenceItem {
  evidence_id: string;
  subject: "self_retrieval" | string;
  kind: "feature_contribution" | "family_contribution";
  feature_id: string | null;
  family: Family;
  query_global_z: number | null;
  candidate_global_z: number | null;
  contribution: number;
  interpretation: "alignment" | "disagreement" | "neutral";
}
export interface ResearchSummaryArtifact {
  contract: "scoutlens.showcase";
  schema_version: "1.0.0";
  dataset_version: DatasetVersion;
  supported_claim: string;
  /**
   * @minItems 3
   */
  unsupported_claims: [string, string, string, ...string[]];
  /**
   * @minItems 8
   */
  experiments: [
    ResearchExperiment,
    ResearchExperiment,
    ResearchExperiment,
    ResearchExperiment,
    ResearchExperiment,
    ResearchExperiment,
    ResearchExperiment,
    ResearchExperiment,
    ...ResearchExperiment[]
  ];
  /**
   * @minItems 6
   */
  narrative_steps: [
    {
      order: number;
      kind: "question" | "result" | "challenge" | "correction" | "replication" | "null_result";
      title: string;
      summary: string;
      experiment_ids: string[];
    },
    {
      order: number;
      kind: "question" | "result" | "challenge" | "correction" | "replication" | "null_result";
      title: string;
      summary: string;
      experiment_ids: string[];
    },
    {
      order: number;
      kind: "question" | "result" | "challenge" | "correction" | "replication" | "null_result";
      title: string;
      summary: string;
      experiment_ids: string[];
    },
    {
      order: number;
      kind: "question" | "result" | "challenge" | "correction" | "replication" | "null_result";
      title: string;
      summary: string;
      experiment_ids: string[];
    },
    {
      order: number;
      kind: "question" | "result" | "challenge" | "correction" | "replication" | "null_result";
      title: string;
      summary: string;
      experiment_ids: string[];
    },
    {
      order: number;
      kind: "question" | "result" | "challenge" | "correction" | "replication" | "null_result";
      title: string;
      summary: string;
      experiment_ids: string[];
    },
    ...{
      order: number;
      kind: "question" | "result" | "challenge" | "correction" | "replication" | "null_result";
      title: string;
      summary: string;
      experiment_ids: string[];
    }[]
  ];
  /**
   * @minItems 4
   */
  caveats: [Caveat, Caveat, Caveat, Caveat, ...Caveat[]];
}
export interface ResearchExperiment {
  experiment_id: string;
  title: string;
  provider: "wyscout_pappalardo" | "statsbomb_open_data";
  population: string;
  /**
   * @minItems 1
   */
  metrics: [ResearchMetric, ...ResearchMetric[]];
  conclusion: string;
  caveat_codes: CaveatCode[];
  source_artifact: string;
  report_url: string;
}
export interface ResearchMetric {
  metric_id: string;
  label: string;
  value: number;
  ci_95: null | never[];
  unit: "mrr" | "median_rank" | "recall" | "count";
  display_precision: number;
}
