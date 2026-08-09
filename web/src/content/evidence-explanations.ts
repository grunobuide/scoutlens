import type {
  FeatureCatalogArtifact,
  FeatureDefinition,
  ResearchMetric,
} from "@/contracts/generated/showcase";

// scoutlens-9a3.2: one typed, test-enforced explanation source for every
// public metric and feature concept. Values, intervals, labels, units and
// populations always come from the loaded showcase artifacts; this registry
// carries only presentation-owned plain language, so copy cannot drift into
// inventing scientific meaning.

export type ExplanationScope = "metric" | "feature";

export interface EvidenceExplanation {
  scope: ExplanationScope;
  key: string;
  plain_meaning: string;
  calculation_summary: string;
  scale_direction: string;
  interpretation_boundary: string;
  source_link: string;
}

export type MetricExplanations = Record<string, EvidenceExplanation>;

const METRIC_EXPLANATIONS: MetricExplanations = {
  baseline_a_mrr: {
    scope: "metric",
    key: "baseline_a_mrr",
    plain_meaning:
      "How well a simple rule — match on nominal role, then closest total minutes — finds the same player in the second half of the season.",
    calculation_summary:
      "Mean reciprocal rank of the true same-player profile when candidates are ordered first by role, then by proximity of minutes.",
    scale_direction:
      "A reciprocal-rank score in [0, 1]; higher means the true profile appears nearer the top of the ordering for this identity task.",
    interpretation_boundary:
      "This is the low-cost control, not a scouting model. It says nothing about player quality or transfer value.",
    source_link: "docs/feasibility-report.md",
  },
  baseline_c_mrr: {
    scope: "metric",
    key: "baseline_c_mrr",
    plain_meaning:
      "How well a rule that also knows the player's team and minutes finds them again — the strong same-season shortcut.",
    calculation_summary:
      "Mean reciprocal rank when candidates are ordered by same role, same primary team, then closest minutes.",
    scale_direction:
      "A reciprocal-rank score in [0, 1]; higher means the same-player profile is ranked closer to the top.",
    interpretation_boundary:
      "This control can nearly solve the task by exploiting club continuity within one season; its strength is a confound, not a competing method.",
    source_link: "docs/robustness-checks.md",
  },
  fingerprint_mrr: {
    scope: "metric",
    key: "fingerprint_mrr",
    plain_meaning:
      "How high the same player's second-half profile appears when every eligible profile is ordered by fingerprint similarity to their first half.",
    calculation_summary:
      "Mean reciprocal rank of the true same-player×competition profile under 32-feature cosine similarity with a combined-period z-score scaler.",
    scale_direction:
      "Score in [0, 1]; higher is better for the identity-retrieval task only — never a quality rating.",
    interpretation_boundary:
      "Measures whether event-derived profiles contain a stable individual signal, not whether a player is good, valuable, or a good signing.",
    source_link: "docs/feasibility-report.md",
  },
  mrr_delta: {
    scope: "metric",
    key: "mrr_delta",
    plain_meaning:
      "The improvement the fingerprint achieves over the role-and-minutes baseline on the same retrieval task.",
    calculation_summary:
      "Fingerprint MRR minus baseline MRR for a shared query set, reported with its bootstrap confidence interval.",
    scale_direction:
      "A positive value means the fingerprint finds the same player higher than the baseline does; interval away from 0 is the test of signal.",
    interpretation_boundary:
      "The delta is the headline evidence for a stable fingerprint. It does not make the result a recommendation, style proof, or prediction.",
    source_link: "docs/feasibility-report.md",
  },
  median_rank: {
    scope: "metric",
    key: "median_rank",
    plain_meaning:
      "The middle position at which the true same-player profile appears across all queries — a plain-language companion to MRR.",
    calculation_summary:
      "Median of the true-profile ranks over the query set; 1 would be a perfect identity match on every query.",
    scale_direction:
      "Lower is better for the identity task; 1 is the best possible value.",
    interpretation_boundary:
      "Rank depends on the candidate-pool size and the task definition; never read a rank as a talent position among players.",
    source_link: "docs/feasibility-report.md",
  },
  recall_at_5: {
    scope: "metric",
    key: "recall_at_5",
    plain_meaning:
      "The share of queries where the true same-player profile appears within the top five ranked candidates.",
    calculation_summary:
      "Fraction of queries whose true profile has rank at most 5 under the within-role fingerprint ordering.",
    scale_direction:
      "Value in [0, 1]; higher means the same player is more often found in the top five.",
    interpretation_boundary:
      "A top-five hit is an identity-retrieval event, not evidence that the player is among the 'five most similar' for any scouting purpose.",
    source_link: "docs/temporal-retrieval-within-role.md",
  },
  transferred_count: {
    scope: "metric",
    key: "transferred_count",
    plain_meaning:
      "How many eligible player×competition units changed primary team between the two chronological halves.",
    calculation_summary:
      "Count of eligible profiles whose primary team differs between period A and period B in the frozen Wyscout population.",
    scale_direction:
      "A plain count; larger samples tighten the confidence interval on the transferred-player result.",
    interpretation_boundary:
      "This small subset breaks the team-continuity shortcut, so it is the honest stress test — not a representative market sample.",
    source_link: "docs/transfer-analysis.md",
  },
  raw_global_mrr: {
    scope: "metric",
    key: "raw_global_mrr",
    plain_meaning:
      "Fingerprint MRR using the raw ratio features before empirical-Bayes shrinkage is applied.",
    calculation_summary:
      "Global MRR under the 32-feature cosine fingerprint with un-shrunk ratio features.",
    scale_direction:
      "Score in [0, 1]; higher is better for the identity task.",
    interpretation_boundary:
      "Reported as the comparison arm of the shrinkage experiment; raw ratios over-trust low-attempt values.",
    source_link: "docs/shrinkage-experiment.md",
  },
  shrunk_global_mrr: {
    scope: "metric",
    key: "shrunk_global_mrr",
    plain_meaning:
      "Fingerprint MRR after empirical-Bayes shrinkage pulls low-attempt ratio features toward the population mean.",
    calculation_summary:
      "Global MRR under the same fingerprint with per-feature Beta-Binomial shrinkage applied to the ratio features.",
    scale_direction:
      "Score in [0, 1]; higher is better for the identity task.",
    interpretation_boundary:
      "Shrinkage fixed the low-sample pathology per feature but did not change retrieval materially — the null result kept it out of the default catalog.",
    source_link: "docs/shrinkage-experiment.md",
  },
  raw_within_role_mrr: {
    scope: "metric",
    key: "raw_within_role_mrr",
    plain_meaning:
      "Within-role fingerprint MRR using raw ratio features, restricted to candidates sharing the query's nominal role.",
    calculation_summary:
      "Mean reciprocal rank among same-role candidates under the cosine fingerprint without shrinkage.",
    scale_direction:
      "Score in [0, 1]; higher is better for the identity task.",
    interpretation_boundary:
      "Controls for the position classifier concern; it is a bound on the identity claim, not a position-quality score.",
    source_link: "docs/shrinkage-experiment.md",
  },
  shrunk_within_role_mrr: {
    scope: "metric",
    key: "shrunk_within_role_mrr",
    plain_meaning:
      "Within-role fingerprint MRR with shrunken ratio features.",
    calculation_summary:
      "Mean reciprocal rank among same-role candidates under the cosine fingerprint with per-ratio shrinkage.",
    scale_direction:
      "Score in [0, 1]; higher is better for the identity task.",
    interpretation_boundary:
      "The null comparison confirms shrinkage does not add retrieval value; individual ratio reading remains its intended future use.",
    source_link: "docs/shrinkage-experiment.md",
  },
};

// Features already carry presentation-owned descriptions, direction semantics
// and method references in the versioned catalog. The registry therefore only
// needs a resolver that fails closed for unknown feature ids, so no component
// invents meaning ad hoc.
export interface FeatureExplanation {
  scope: "feature";
  key: string;
  plain_meaning: string;
  scale_direction: string;
  interpretation_boundary: string;
  source_link: string;
}

export function explainMetric(metric: ResearchMetric): EvidenceExplanation {
  const explanation = METRIC_EXPLANATIONS[metric.metric_id];
  if (explanation === undefined) {
    throw new Error(`No explanation for required metric id: ${metric.metric_id}`);
  }
  return explanation;
}

export function metricExplanationKeys(): ReadonlyArray<string> {
  return Object.keys(METRIC_EXPLANATIONS);
}

export function explainFeature(
  catalog: FeatureCatalogArtifact,
  featureId: string,
): FeatureExplanation {
  const definition = catalog.features.find((item) => item.feature_id === featureId);
  if (definition === undefined) {
    throw new Error(`No catalog definition for required feature id: ${featureId}`);
  }
  return {
    scope: "feature",
    key: featureId,
    plain_meaning: definition.description,
    scale_direction: directionSemanticsText(definition),
    interpretation_boundary: boundaryText(definition),
    source_link: definition.method_ref,
  };
}

function directionSemanticsText(definition: FeatureDefinition): string {
  if (definition.direction_semantics === "descriptive_not_quality") {
    return "Higher or lower values are descriptive of behaviour; neither is treated as better quality.";
  }
  return "Values are descriptive; no direction means better or worse.";
}

function boundaryText(definition: FeatureDefinition): string {
  const nullClause =
    definition.raw_null_meaning === "no_attempts"
      ? " When the player attempted none of the underlying action, the raw value is unobserved and mean-imputed to z=0 for similarity, displayed as 'not observed' in the profile."
      : definition.raw_null_meaning === "not_observed"
        ? " When the value was not observed, it is mean-imputed to z=0 for similarity and displayed as 'not observed' in the profile."
        : "";
  return `A measurement of one event-derived behaviour per 90 minutes in the frozen season.${nullClause} It describes activity; it does not rate talent or style quality.`;
}
