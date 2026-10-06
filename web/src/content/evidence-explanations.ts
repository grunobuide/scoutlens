import type {
  Caveat,
  EvidenceItem,
  Family,
  FeatureCatalogArtifact,
  FeatureDefinition,
  ResearchMetric,
} from "@/contracts/generated/showcase";

// scoutlens-9a3.2: one typed, test-enforced explanation source for every
// public metric and feature concept. Values, intervals, labels, units and
// populations always come from the loaded showcase artifacts; this registry
// carries only presentation-owned plain language, so copy cannot drift into
// inventing scientific meaning.

export type ExplanationScope = "metric" | "feature" | "quantity";

/**
 * Thrown for any key the registry or the artifact cannot resolve.
 *
 * One named type, so a caller can tell "this content is incompatible with the
 * page" from an ordinary bug - and so nothing can catch it by accident and
 * render a number with no explanation instead (`scoutlens-9a3.19`: the first
 * consumer did exactly that, in research-story.tsx).
 */
export class ExplanationNotFoundError extends Error {
  /** Read by `describeLabError`, which routes it to the incompatible-data panel. */
  readonly code = "explanation_missing";
  readonly scope: string;
  readonly key: string;

  constructor(scope: string, key: string, message: string) {
    super(message);
    this.name = "ExplanationNotFoundError";
    this.scope = scope;
    this.key = key;
  }
}

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
  /** The artifact's own label, short label and unit - never inferred from the id. */
  label: string;
  short_label: string;
  unit: FeatureDefinition["unit"];
  plain_meaning: string;
  scale_direction: string;
  interpretation_boundary: string;
  source_link: string;
}

export function explainMetric(metric: Pick<ResearchMetric, "metric_id">): EvidenceExplanation {
  const explanation = METRIC_EXPLANATIONS[metric.metric_id];
  if (explanation === undefined) {
    throw new ExplanationNotFoundError(
      "metric",
      metric.metric_id,
      `No explanation for required metric id: ${metric.metric_id}`,
    );
  }
  return explanation;
}

export function metricExplanationKeys(): ReadonlyArray<string> {
  return Object.keys(METRIC_EXPLANATIONS);
}

export function explainFeature(
  catalog: Pick<FeatureCatalogArtifact, "features">,
  featureId: string,
): FeatureExplanation {
  return explainFeatureFrom(catalog.features, featureId);
}

/**
 * The same resolver over a bare list of definitions, for a surface that holds
 * the catalog's rows rather than the catalog (the identity challenge).
 */
export function explainFeatureFrom(
  features: ReadonlyArray<FeatureDefinition>,
  featureId: string,
): FeatureExplanation {
  const definition = features.find((item) => item.feature_id === featureId);
  if (definition === undefined) {
    throw new ExplanationNotFoundError(
      "feature",
      featureId,
      `No catalog definition for required feature id: ${featureId}`,
    );
  }
  return {
    scope: "feature",
    key: featureId,
    label: definition.label,
    short_label: definition.short_label,
    unit: definition.unit,
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

// ---------------------------------------------------------------------------
// Per-profile quantities on /lab and in the identity challenge
// (`scoutlens-9a3.19`).
//
// The research-summary metrics above are aggregate results. These are the
// numbers the Lab and the challenge print for one player: a rank, a score, an
// interval, a percentile, a contribution, a weight. Each has the same five
// parts as a metric, plus the `term` the surface prints, and the same rule:
// no value, interval, rank, population size or season constant lives here.
// ---------------------------------------------------------------------------

export interface QuantityExplanation extends EvidenceExplanation {
  scope: "quantity";
  term: string;
}

const CONTRACT_V1 = "docs/showcase-artifact-contract.md";
const CONTRACT_V2 = "docs/showcase-artifact-contract-v2.md";
const UNCERTAINTY = "docs/uncertainty-method.md";

const QUANTITY_EXPLANATIONS = {
  self_rank: {
    scope: "quantity",
    key: "self_rank",
    term: "Self rank",
    plain_meaning:
      "Where this player's own second-half profile lands when every eligible second-half profile is ordered by similarity to their first half.",
    calculation_summary:
      "The period-A profile is the query. Every eligible period-B profile in the scope is ordered by its score against it, and the rank is the position of the same player × competition unit, out of the candidate count printed beside it.",
    scale_direction:
      "First place is the top of the ordering, and a lower rank is better for the identity task only. Read it against the candidate count: the same rank means more in a larger pool.",
    interpretation_boundary:
      "An identity-test result for one player, not a position in a table of players. It says nothing about quality, value or fit.",
    source_link: `${CONTRACT_V1}#identity-retrieval`,
  },
  baseline_self_rank: {
    scope: "quantity",
    key: "baseline_self_rank",
    term: "Role-and-minutes baseline rank",
    plain_meaning:
      "Where the same player lands when the period-B pool is ordered by context alone - same nominal role first, then the closest total minutes - instead of by the fingerprint.",
    calculation_summary:
      "Candidates sharing the query's nominal role come first, each group ordered by how close its minutes are to the query's; the rank is the true profile's position in that ordering.",
    scale_direction:
      "A lower rank is better for the identity task. It is the control the fingerprint rank is read against, and it publishes no similarity score.",
    interpretation_boundary:
      "A control built without any event data. When it finds the player as well as the fingerprint does, the fingerprint rank is not evidence of an individual signal.",
    source_link: "docs/feasibility-report.md#baselines",
  },
  reciprocal_rank: {
    scope: "quantity",
    key: "reciprocal_rank",
    term: "Reciprocal rank",
    plain_meaning:
      "The self rank turned into a score: one player's term in the mean reciprocal rank that the science page reports for the whole population.",
    calculation_summary: "One divided by the self rank.",
    scale_direction:
      "Greater than zero and at most one. A value of one means the player's own profile came first, and it falls quickly as the rank grows.",
    interpretation_boundary:
      "One query from the aggregate test, not a rating. Averaged over every eligible player it becomes the published result; on its own it is a single draw.",
    source_link: "docs/feasibility-report.md#temporal-stability-results",
  },
  similarity_score: {
    scope: "quantity",
    key: "similarity_score",
    term: "Similarity score",
    plain_meaning:
      "How closely two profiles point in the same direction across the 32 standardized measurements, once each measurement is scaled by the weight the model learned for it.",
    calculation_summary:
      "Each measurement's global z-score is multiplied by the square root of its fitted non-negative weight; the score is the dot product of the two scaled profiles divided by the product of their lengths.",
    scale_direction:
      "At most one. Higher means the two profiles are more alike on these measurements, and the ranking orders candidates by it from highest down.",
    interpretation_boundary:
      "Likeness of event-derived activity within one season. It is not a quality rating, a tactical-fit score or a recruitment signal, and alike numbers can come from different roles in different teams.",
    source_link: `${CONTRACT_V2}#5-weighted-retrieval-and-evidence-semantics`,
  },
  cosine_similarity: {
    scope: "quantity",
    key: "cosine_similarity",
    term: "Cosine",
    plain_meaning:
      "How closely two profiles point in the same direction across the 32 standardized measurements, with every measurement counted equally.",
    calculation_summary:
      "The cosine of the angle between the two global z-score profiles: their dot product divided by the product of their lengths.",
    scale_direction:
      "Between minus one and one. Higher means the two profiles are more alike on these measurements, and the ranking orders candidates by it from highest down.",
    interpretation_boundary:
      "Likeness of event-derived activity within one season. It is not a quality rating, a tactical-fit score or a recruitment signal, and alike numbers can come from different roles in different teams.",
    source_link: `${CONTRACT_V1}#statistical-neighbors-and-additive-evidence`,
  },
  rank_interval: {
    scope: "quantity",
    key: "rank_interval",
    term: "Median rank and rank interval",
    plain_meaning:
      "How far the self rank moves when the season's observed matches are resampled: the middle rank, and the range holding the central 95% of resampled ranks.",
    calculation_summary:
      "Whole matches are redrawn with replacement within each competition and half, the profiles and the ranking are rebuilt in every replicate, and the median and the 2.5th to 97.5th percentiles of the valid ranks are reported.",
    scale_direction:
      "Ranks, so lower is better for the identity task. A narrow interval means the rank barely depends on which matches were observed; bounds can be fractional because they are interpolated.",
    interpretation_boundary:
      "Stability to resampling this season's matches only. It is not uncertainty about data errors, tactics, injuries, future seasons or player quality.",
    source_link: `${UNCERTAINTY}#summaries-and-numeric-rules`,
  },
  resampled_recall: {
    scope: "quantity",
    key: "resampled_recall",
    term: "Recall@1, @5 and @10",
    plain_meaning:
      "How often, across the resampled seasons, the player's own profile came first, inside the top five, or inside the top ten.",
    calculation_summary:
      "The share of valid bootstrap replicates in which the self rank is at most one, five or ten.",
    scale_direction:
      "A percentage. Higher means the identity result held up in more of the resampled seasons.",
    interpretation_boundary:
      "A stability rate for one player's identity test inside this dataset, not a probability of anything outside it.",
    source_link: `${UNCERTAINTY}#contract-field-review-checklist`,
  },
  selection_stability: {
    scope: "quantity",
    key: "selection_stability",
    term: "Selection stability",
    plain_meaning:
      "How firmly a neighbour holds its place when the matches are resampled: where it ranks among the query's same-role candidates, and how often it stays in the top five.",
    calculation_summary:
      "In every bootstrap replicate the same-role candidates are re-ranked against the query. The neighbour's median rank, the 95% interval of its rank and the share of replicates with rank at most five are reported; a replicate where it is absent counts it at the bottom.",
    scale_direction:
      "For the ranks, lower means closer to the query. For the rate, higher means the neighbour was selected more consistently.",
    interpretation_boundary:
      "Stability of a statistical neighbour inside this dataset. It does not make the neighbour a comparable player, a substitute or a scouting lead.",
    source_link: `${UNCERTAINTY}#contract-field-review-checklist`,
  },
  within_role_percentile: {
    scope: "quantity",
    key: "within_role_percentile",
    term: "Within-role percentile",
    plain_meaning:
      "Where this value sits among the eligible profiles that share the player's nominal role, on a scale from 0 to 100.",
    calculation_summary:
      "An average-rank percentile over the combined period-A and period-B profiles of the same role. An unobserved value takes the population mean before ranking, so tied values share one percentile.",
    scale_direction:
      "From 0 to 100, the position among same-role profiles. High and low are both descriptive; neither end is better.",
    interpretation_boundary:
      "Display context only. The ranking compares global z-scores, so this within-role position is not what the model uses.",
    source_link: `${CONTRACT_V1}#feature-catalogjson`,
  },
  global_percentile: {
    scope: "quantity",
    key: "global_percentile",
    term: "Global percentile",
    plain_meaning:
      "Where this value sits among every eligible profile, whatever the role, on a scale from 0 to 100.",
    calculation_summary:
      "An average-rank percentile over all eligible period-A and period-B profiles. An unobserved value takes the population mean before ranking, so tied values share one percentile.",
    scale_direction:
      "From 0 to 100, the position among all profiles. High and low are both descriptive; neither end is better.",
    interpretation_boundary:
      "Display context only. Roles differ in what they do, so a low global percentile can be ordinary for the player's role.",
    source_link: `${CONTRACT_V1}#feature-catalogjson`,
  },
  model_z_score: {
    scope: "quantity",
    key: "model_z_score",
    term: "Global z-score",
    plain_meaning:
      "How far this value is from the average eligible profile, in standard deviations. It is the number the model actually compares.",
    calculation_summary:
      "The raw value minus the mean of all eligible period-A and period-B profiles, divided by their standard deviation. An unobserved value is set to the mean first, which makes its z-score exactly zero.",
    scale_direction:
      "Zero is the average, and the sign says above or below it. Neither direction is better.",
    interpretation_boundary:
      "A standardized activity level, not a grade. A large z-score means unusual, not good.",
    source_link: `${CONTRACT_V1}#feature-catalogjson`,
  },
  contribution: {
    scope: "quantity",
    key: "contribution",
    term: "Contribution",
    plain_meaning:
      "How much one measurement, or one family of measurements, adds to or takes away from the score of this pair.",
    calculation_summary:
      "Each measurement's signed term of the score: its share of the numerator divided by the score's denominator. The terms of all 32 measurements add up to the stored score, and a family's value is the sum of its measurements' terms.",
    scale_direction:
      "Signed. Positive pulls the two profiles together - two values below the average also align - negative pushes them apart, and a value that rounds to zero is neutral.",
    interpretation_boundary:
      "An exact breakdown of one similarity number. A negative value is a disagreement, not a weakness, and no contribution is evidence of playing style.",
    source_link: `${CONTRACT_V2}#5-weighted-retrieval-and-evidence-semantics`,
  },
  feature_weight: {
    scope: "quantity",
    key: "feature_weight",
    term: "Fitted weight",
    plain_meaning: "How much the ranking counts this measurement, as learned on the training split.",
    calculation_summary:
      "A non-negative weight fitted on the frozen Wyscout training split to make same-player retrieval more accurate. A measurement with no weight entry is shown as having no fitted weight, never as zero.",
    scale_direction:
      "Zero or more. A larger weight lets the measurement move the score more, and a weight of exactly zero gives it no influence on the ranking.",
    interpretation_boundary:
      "Weights describe what helped identity retrieval on the training split. They do not say which skills matter, or which player is better.",
    source_link: `${CONTRACT_V2}#5-weighted-retrieval-and-evidence-semantics`,
  },
} as const satisfies Record<string, QuantityExplanation>;

export type QuantityId = keyof typeof QUANTITY_EXPLANATIONS;

export function explainQuantity(id: string): QuantityExplanation {
  if (!Object.hasOwn(QUANTITY_EXPLANATIONS, id)) {
    throw new ExplanationNotFoundError("quantity", id, `No explanation for required quantity id: ${id}`);
  }
  return QUANTITY_EXPLANATIONS[id as QuantityId];
}

export function quantityExplanationKeys(): ReadonlyArray<QuantityId> {
  return Object.keys(QUANTITY_EXPLANATIONS) as QuantityId[];
}

/**
 * The score quantity each major publishes. v2's is weighted and may not be
 * explained as a cosine (D047); v1's is one.
 */
export function scoreQuantity(major: 1 | 2): QuantityId {
  return major === 2 ? "similarity_score" : "cosine_similarity";
}

// ---------------------------------------------------------------------------
// Feature families, evidence items and caveats.
// ---------------------------------------------------------------------------

export interface FamilyExplanation {
  key: Family;
  label: string;
  plain_meaning: string;
}

// Keyed by the generated `Family` union, so a family the contract adds is a
// type error here until it is explained - not a label guessed from its id.
const FAMILY_EXPLANATIONS: Readonly<Record<Family, FamilyExplanation>> = {
  passing: {
    key: "passing",
    label: "Passing",
    plain_meaning:
      "How often the player passes, how many passes arrive, and how many are crosses, long balls or smart passes.",
  },
  progression: {
    key: "progression",
    label: "Progression",
    plain_meaning: "How far and how often the player's passes move the ball towards the opponent's goal.",
  },
  chance_creation: {
    key: "chance_creation",
    label: "Chance Creation",
    plain_meaning: "Assists, key passes, through balls and entries into the penalty box.",
  },
  shooting: {
    key: "shooting",
    label: "Shooting",
    plain_meaning: "How often the player shoots and scores, and the share of shots on target or blocked.",
  },
  defensive: {
    key: "defensive",
    label: "Defensive",
    plain_meaning: "Interceptions, sliding tackles, clearances and the share of defensive duels won.",
  },
  spatial: {
    key: "spatial",
    label: "Spatial",
    plain_meaning: "Where on the pitch the player's events happen: average position and the share in each third.",
  },
  possession: {
    key: "possession",
    label: "Possession",
    plain_meaning: "How involved the player is on the ball: events, touches and duels, and the share of duels won.",
  },
  carrying_proxy: {
    key: "carrying_proxy",
    label: "Carrying Proxy",
    plain_meaning:
      "A stand-in for ball carrying, since the data record no carry event: the provider's acceleration events, their forward distance, and take-on success.",
  },
};

export function explainFamily(family: string): FamilyExplanation {
  if (!Object.hasOwn(FAMILY_EXPLANATIONS, family)) {
    throw new ExplanationNotFoundError("family", family, `No explanation for required feature family: ${family}`);
  }
  return FAMILY_EXPLANATIONS[family as Family];
}

export function familyExplanationKeys(): ReadonlyArray<Family> {
  return Object.keys(FAMILY_EXPLANATIONS) as Family[];
}

export interface EvidenceLabel {
  key: string;
  /** The feature's catalog label for a feature item, the family's for a family item. */
  label: string;
  family_label: string;
}

/**
 * Resolves one evidence item to the labels a reader sees.
 *
 * A feature item must name a feature the catalog defines, filed under the
 * family the catalog gives it: evidence that disagrees with the catalog it
 * claims to explain is refused, not rendered under a raw id (the contract
 * forbids inferring a label from `feature_id`).
 */
export function explainEvidence(
  features: ReadonlyArray<FeatureDefinition>,
  item: Pick<EvidenceItem, "evidence_id" | "kind" | "feature_id" | "family">,
): EvidenceLabel {
  const family = explainFamily(item.family);
  if (item.kind === "family_contribution") {
    return { key: item.evidence_id, label: family.label, family_label: family.label };
  }
  if (item.feature_id === null) {
    throw new ExplanationNotFoundError("evidence", item.evidence_id, `Feature evidence ${item.evidence_id} names no feature`);
  }
  const feature = explainFeatureFrom(features, item.feature_id);
  const filed = features.find((candidate) => candidate.feature_id === item.feature_id)?.family;
  if (filed !== item.family) {
    throw new ExplanationNotFoundError(
      "evidence",
      item.evidence_id,
      `Evidence ${item.evidence_id} files ${item.feature_id} under ${item.family}; the catalog files it under ${filed}`,
    );
  }
  return { key: item.evidence_id, label: feature.label, family_label: family.label };
}

/**
 * Resolves a caveat the surface is required to show.
 *
 * The message is the artifact's - this registry never words a caveat - but a
 * required code the payload does not carry makes the payload incompatible, so
 * it throws rather than rendering an empty paragraph where the boundary goes.
 */
export function explainCaveat<T extends Pick<Caveat, "code">>(caveats: ReadonlyArray<T>, code: string): T {
  const caveat = caveats.find((candidate) => candidate.code === code);
  if (caveat === undefined) {
    throw new ExplanationNotFoundError("caveat", code, `The payload carries no required caveat: ${code}`);
  }
  return caveat;
}
