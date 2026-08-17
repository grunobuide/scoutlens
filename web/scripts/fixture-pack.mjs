// Deterministic Lab fixture pack generator and verifier (scoutlens-uze.7).
//
// Builds a complete, schema-valid showcase v1 pack under web/e2e/fixtures/
// lab-max-content that the test-only static export can be pointed at. The pack
// reuses the published catalog, research summary and real 1,257-row player
// index and appends three obviously-synthetic profiles:
//
//   wy-900001-c-901  fx-max-content      identity stretched beyond every
//                                        published maximum (selector list cell)
//   wy-900002-c-902  fx-uc-available     retrieval + neighbor stability
//                                        uncertainty "available"
//   wy-900003-c-903  fx-uc-insufficient  retrieval + neighbor stability
//                                        uncertainty "insufficient"
//
// The generator is content-stable: no timestamps, randomness, git or machine
// state. Two runs must produce byte-identical packs (determinism criterion).
// The pack is version-controlled under web/e2e/fixtures/** and is never
// reachable from the production export built by `pnpm build`.
//
// Subcommands:
//   generate          (re)write web/e2e/fixtures/lab-max-content
//   verify            validate the committed pack: canonical JSON, manifest
//                     checksums and byte counts
//
// `verify` intentionally does not depend on AJV: the JSON Schema gate for the
// pack runs in the vitest suite through the real repository contract, which is
// the authority used by the browser at runtime.

import { createHash } from "node:crypto";
import { mkdir, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const webRoot = resolve(scriptDirectory, "..");
const repoRoot = resolve(webRoot, "..");
// Which contract major this pack speaks. The published dataset for that major
// supplies the catalog, index, research summary and (for v2) the representation,
// so the fixture never hand-authors contract metadata - only the synthetic
// profiles that stress the Lab's layout.
export const FIXTURE_MAJOR = Number(process.env.SCOUTLENS_FIXTURE_MAJOR ?? "1");
if (FIXTURE_MAJOR !== 1 && FIXTURE_MAJOR !== 2) {
  throw new Error(`SCOUTLENS_FIXTURE_MAJOR must be 1 or 2, got ${FIXTURE_MAJOR}`);
}
const publishedRoot = resolve(repoRoot, "public", "showcase", `v${FIXTURE_MAJOR}`);
const fixtureId =
  process.env.SCOUTLENS_FIXTURE_ID ??
  (FIXTURE_MAJOR === 2 ? "lab-max-content-v2" : "lab-max-content");

// Assigned from the published representation before any profile is built. The
// fixture reuses the real weights so `feature_weight` matches what the
// representation publishes; a fixture that invented weights would satisfy the
// schema while failing the binding the consumer actually enforces.
let publishedRepresentation = null;

function representationId() {
  if (FIXTURE_MAJOR !== 2) {
    return null;
  }
  if (publishedRepresentation === null) {
    throw new Error("The v2 representation must be loaded before building profiles");
  }
  return publishedRepresentation.representation.id;
}

/** Adds the v2 binding to an already-built uncertainty block.
 *
 * Applied at the call site so the three builders keep one return shape each:
 * every branch of every one of them would otherwise need the same two lines,
 * which is how a branch gets missed.
 */
function bound(block) {
  return { ...block, ...v2Binding() };
}

/** Fields every ranking-bearing v2 block carries, and no v1 block has. */
function v2Binding(extra = {}) {
  return FIXTURE_MAJOR === 2 ? { representation_id: representationId(), ...extra } : {};
}

const RETRIEVAL_METHOD = {
  1: "combined_scaler_cosine_v1",
  2: "combined_scaler_diagonal_v1",
};
const UNCERTAINTY_DESIGN = {
  1: "match_bootstrap_v1",
  2: "match_bootstrap_diagonal_v1",
};

/** The score field each major publishes. v2 renamed it because a weighted
 * metric must not be published under a name claiming plain cosine (D047). */
function scoreField(value) {
  return FIXTURE_MAJOR === 2 ? { similarity_score: value } : { cosine_similarity: value };
}
const fixturesRoot = resolve(webRoot, "e2e", "fixtures");
const fixtureRoot = resolve(fixturesRoot, fixtureId);

// Stated published maximums, measured 2026-08-04 (scoutlens-uze.7 description).
export const PUBLISHED_MAX_DISPLAY_NAME = 22; // "K. Théophile Catherine" (wy-25643-c-412)
export const PUBLISHED_MAX_TEAM_JOIN = 35; // "Saint-Étienne / Olympique Marseille" (wy-25999-c-412)
export const PUBLISHED_MAX_COMPETITION = 22; // "Spanish first division"
export const PUBLISHED_MAX_TEAMS_PER_PERIOD = 2;

// Synthetic identity beyond every published maximum, kept obviously synthetic.
const FIXTURE_IDENTITY = {
  player_key: "wy-900001",
  profile_key: "wy-900001-c-901",
  display_name: "K. Théophile Catherine Saint-Michel",
  role: "Midfielder",
  competition: {
    id: 901,
    name: "Spanish first division championship",
    country: "Spain",
  },
  teams: {
    a: [{ id: 9011, name: "Saint-Étienne", minutes: 720 }],
    b: [
      { id: 9012, name: "Olympique Marseille", minutes: 300 },
      { id: 9013, name: "Athletic de Bilbao", minutes: 240 },
      { id: 9014, name: "Real Unión Irún", minutes: 180 },
    ],
  },
};

const UNCERTAINTY_PROFILES = [
  {
    id: "fx-uc-available",
    player_key: "wy-900002",
    profile_key: "wy-900002-c-902",
    display_name: "F. Fixture Avail",
    role: "Midfielder",
    competition: {
      id: 902,
      name: "French first division",
      country: "France",
    },
    teams: {
      a: [{ id: 9021, name: "Fixture Paris", minutes: 760 }],
      b: [{ id: 9021, name: "Fixture Paris", minutes: 810 }],
    },
    uncertainty: "available",
  },
  {
    id: "fx-uc-insufficient",
    player_key: "wy-900003",
    profile_key: "wy-900003-c-903",
    display_name: "F. Fixture Insuff",
    role: "Forward",
    competition: {
      id: 903,
      name: "Italian first division",
      country: "Italy",
    },
    teams: {
      a: [{ id: 9031, name: "Fixture Torino", minutes: 700 }],
      b: [{ id: 9031, name: "Fixture Torino", minutes: 655 }],
    },
    uncertainty: "insufficient",
  },
];

export const SYNTHETIC_PROFILE_KEYS = [
  FIXTURE_IDENTITY.profile_key,
  ...UNCERTAINTY_PROFILES.map((profile) => profile.profile_key),
];

// Marker strings used by the production-free-export gate (check-static-output).
export const FIXTURE_MARKERS = [
  FIXTURE_IDENTITY.display_name,
  FIXTURE_IDENTITY.competition.name,
  "Fixture Paris",
  "Fixture Torino",
];

export function fixtureDirectory() {
  return fixtureRoot;
}

export function canonicalJson(value) {
  return JSON.stringify(sortObjectKeys(value));
}

function sortObjectKeys(value) {
  if (Array.isArray(value)) {
    return value.map(sortObjectKeys);
  }
  if (value !== null && typeof value === "object") {
    return Object.fromEntries(
      Object.keys(value)
        .sort()
        .map((key) => [key, sortObjectKeys(value[key])]),
    );
  }
  return value;
}

export function sha256Of(buffer) {
  return createHash("sha256").update(buffer).digest("hex");
}

export async function readJson(path) {
  return JSON.parse(await readFile(path, "utf8"));
}

export async function writeJson(path, value) {
  await writeFile(path, canonicalJson(value), "utf8");
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function round(value, digits = 4) {
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
}

function minutesFor(period, profile) {
  return profile.teams[period].reduce((sum, team) => sum + team.minutes, 0);
}

function featureOrder(catalog, featureId) {
  return catalog.features.find((feature) => feature.feature_id === featureId)?.order
    ?? Number.MAX_SAFE_INTEGER;
}

function familyOrderOf(catalog) {
  const order = new Map();
  for (const feature of [...catalog.features].sort((a, b) => a.order - b.order)) {
    if (!order.has(feature.family)) {
      order.set(feature.family, order.size);
    }
  }
  return order;
}

// Deterministic per-feature values from catalog order and a profile seed.
function featureValueFor(index, period, seed) {
  const wave =
    period === "a"
      ? Math.sin(index * 1.7 + seed * 0.31)
      : Math.sin(index * 1.9 + seed * 0.63);
  return {
    raw: round(0.25 + wave * 0.35, 6),
    globalZ: round(clamp(wave * 1.8 + (period === "b" ? 0.12 : 0), -2.4, 2.4)),
    pct: round(clamp(50 + wave * 42 + (period === "b" ? 4 : 0), 3, 97), 2),
    rolePct: round(clamp(50 + wave * 42 + (period === "b" ? 4 : 0) + 6, 2, 98), 2),
  };
}

function featureUncertainty(status, pct) {
  if (status === "available") {
    return {
      status,
      valid_resamples: 500,
      raw_ci_95: [round(0.1, 4), round(0.2, 4)],
      within_role_percentile_ci_95: [round(Math.max(0, pct - 7), 2), round(Math.min(100, pct + 7), 2)],
      ...v2Binding(),
    };
  }
  if (status === "insufficient") {
    return {
      status,
      valid_resamples: 4,
      raw_ci_95: null,
      within_role_percentile_ci_95: null,
      ...v2Binding(),
    };
  }
  return {
    status: "pending",
    valid_resamples: null,
    raw_ci_95: null,
    within_role_percentile_ci_95: null,
    ...v2Binding(),
  };
}

function buildPeriodFingerprint(catalog, period, profile) {
  const minutes = minutesFor(period, profile);
  const features = catalog.features
    .map((feature) => {
      const values = featureValueFor(feature.order, period, profile.seed);
      return {
        feature_id: feature.feature_id,
        raw_value: values.raw,
        global_z_score: values.globalZ,
        global_percentile: values.pct,
        within_role_percentile: values.rolePct,
        imputed_for_model: false,
        support: {
          minutes,
          attempts: Math.round(minutes / 90) + feature.order,
          successes: feature.order % 3 === 0 ? Math.round(minutes / 90) : null,
        },
        uncertainty: featureUncertainty(profile.uncertainty, values.pct),
      };
    })
    .sort((left, right) => featureOrder(catalog, left.feature_id) - featureOrder(catalog, right.feature_id));

  return {
    label: period === "a" ? "First chronological half" : "Second chronological half",
    date_start: period === "a" ? "2017-08-18" : "2018-01-06",
    date_end: period === "a" ? "2017-12-17" : "2018-05-20",
    minutes,
    match_count: Math.round(minutes / 90),
    features,
  };
}

function subjectOf(subject) {
  return typeof subject === "string" && subject.startsWith("neighbor:")
    ? subject
    : "self_retrieval";
}

// Evidence contributions whose feature sum and family sum both reconstruct the
// subject cosine exactly (up to float grouping error well below 1e-9).
/** A series that sums exactly to `total`, deterministic in the profile seed. */
function additiveSeries(count, seed, total) {
  const raw = Array.from({ length: count }, (unused, index) =>
    Math.sin(index * 2.3 + count + seed) * 0.5,
  );
  const magnitude = raw.reduce((sum, value) => sum + Math.abs(value), 0);
  const scale = magnitude === 0 ? 0 : total / magnitude;
  const scaled = raw.map((value) => value * scale);
  const head = scaled.slice(0, -1).reduce((sum, value) => sum + value, 0);
  scaled[scaled.length - 1] = total - head;
  return scaled;
}

/**
 * Both decompositions, built to reconstruct independently.
 *
 * `contribution` sums to the unweighted cosine audit view and
 * `weighted_contribution` sums to the published score - the same pair of
 * identities the real producer satisfies. A fixture that reused one series for
 * both would satisfy the schema while hiding the only interesting v2 property.
 */
function buildEvidenceSet(catalog, profile, subject, score) {
  const order = familyOrderOf(catalog);
  const definitions = [...catalog.features].sort((a, b) => a.order - b.order);
  const weights =
    FIXTURE_MAJOR === 2
      ? new Map(
          publishedRepresentation.representation.weights.map((entry) => [
            entry.feature_id,
            entry.weight,
          ]),
        )
      : new Map();
  // In v2 the audit view is a different number from the published score, so the
  // fixture gives it its own series rather than reusing one.
  const cosine = FIXTURE_MAJOR === 2 ? round(score * 0.94, 6) : score;
  const scaled = additiveSeries(definitions.length, profile.seed * 0.11, cosine);
  const weighted =
    FIXTURE_MAJOR === 2 ? additiveSeries(definitions.length, profile.seed * 0.17, score) : scaled;

  const featureItems = definitions.map((feature, index) => {
    const contribution = scaled[index];
    return {
      evidence_id: `evidence-${subject}-f-${feature.feature_id}`,
      subject: subjectOf(subject),
      kind: "feature_contribution",
      feature_id: feature.feature_id,
      family: feature.family,
      query_global_z: profile.zA.get(feature.feature_id),
      candidate_global_z: profile.zB.get(feature.feature_id),
      contribution,
      interpretation:
        Math.abs(contribution) < 1e-9 ? "neutral" : contribution < 0 ? "disagreement" : "alignment",
      ...v2Binding({
        feature_weight: weights.get(feature.feature_id) ?? 0,
        weighted_contribution: weighted[index],
      }),
    };
  });

  const familyItems = [...order.keys()].map((family) => {
    const members = featureItems.filter((item) => item.family === family);
    const contribution = members.reduce((sum, item) => sum + item.contribution, 0);
    return {
      evidence_id: `evidence-${subject}-fam-${family}`,
      subject: subjectOf(subject),
      kind: "family_contribution",
      feature_id: null,
      family,
      query_global_z: null,
      candidate_global_z: null,
      contribution,
      interpretation:
        Math.abs(contribution) < 1e-9 ? "neutral" : contribution < 0 ? "disagreement" : "alignment",
      ...v2Binding({
        feature_weight: null,
        weighted_contribution: members.reduce(
          (sum, item) => sum + item.weighted_contribution,
          0,
        ),
      }),
    };
  });

  // Ordered by the contribution to the score this major publishes: ordering v2
  // evidence by the unweighted audit view would rank the explanation by a
  // number the reader is never shown.
  const magnitudeOf = (item) =>
    FIXTURE_MAJOR === 2 ? item.weighted_contribution : item.contribution;
  const compare = (left, right) =>
    Math.abs(magnitudeOf(right)) - Math.abs(magnitudeOf(left)) ||
    (left.kind === "feature_contribution"
      ? featureOrder(catalog, left.feature_id) - featureOrder(catalog, right.feature_id)
      : (order.get(left.family) ?? Number.MAX_SAFE_INTEGER)
        - (order.get(right.family) ?? Number.MAX_SAFE_INTEGER)) ||
    left.evidence_id.localeCompare(right.evidence_id, "en");

  const sortedFeatures = [...featureItems].sort(compare);
  const sortedFamilies = [...familyItems].sort(compare);
  return {
    items: [...featureItems, ...familyItems],
    references: [...sortedFeatures, ...sortedFamilies].map((item) => item.evidence_id),
  };
}

// Rank statistics are deliberately FRACTIONAL here, and the upper bound is
// deliberately a double whose shortest round-trip representation carries binary
// noise. Percentile interpolation produces exactly this shape in production
// (median 166.5, interval 1-130.2), and every fixture previously used whole
// numbers — so the raw-interpolation defect in scoutlens-jtt.16 rendered
// "rank interval 1-111.09999999999991" in the published Lab while every test
// passed against clean integers. The lower bound is a clean fractional so the
// formatter is also shown not to mangle those.
function rankUncertainty(status, median) {
  if (status === "available") {
    return {
      status,
      valid_resamples: 500,
      median_rank: median + 0.5,
      rank_ci_95: [Math.max(1, median - 3) + 0.4, 111.09999999999991],
      recall_at_1_rate: 0.86,
      recall_at_5_rate: 0.93,
      recall_at_10_rate: 0.97,
    };
  }
  if (status === "insufficient") {
    return {
      status,
      valid_resamples: 4,
      median_rank: null,
      rank_ci_95: null,
      recall_at_1_rate: null,
      recall_at_5_rate: null,
      recall_at_10_rate: null,
    };
  }
  return {
    status: "pending",
    valid_resamples: null,
    median_rank: null,
    rank_ci_95: null,
    recall_at_1_rate: null,
    recall_at_5_rate: null,
    recall_at_10_rate: null,
  };
}

function neighborStability(status) {
  if (status === "available") {
    return {
      status,
      valid_resamples: 500,
      top_5_selection_rate: 0.72,
      // Fractional for the same reason as rankUncertainty: this is the path the
      // neighbour drawer renders, and it had the identical raw-interpolation bug.
      median_rank: 6.5,
      rank_ci_95: [3.4, 91.57499999999993],
    };
  }
  if (status === "insufficient") {
    return {
      status,
      valid_resamples: 4,
      top_5_selection_rate: null,
      median_rank: null,
      rank_ci_95: null,
    };
  }
  return {
    status: "pending",
    valid_resamples: null,
    top_5_selection_rate: null,
    median_rank: null,
    rank_ci_95: null,
  };
}

function uncertaintyBlock(status) {
  if (status === "available") {
    return {
      status,
      design_version: UNCERTAINTY_DESIGN[FIXTURE_MAJOR],
      seed: 1729,
      requested_resamples: 500,
      valid_resamples: 500,
      interval: "percentile_95",
      resampling_unit: "whole_match_stratified_by_competition_and_period",
      cohort_policy: "fixed_observed_eligible_cohort",
      warning:
        "Fixture bootstrap resolved 500 valid resamples; rank and neighbor intervals are reported.",
    };
  }
  if (status === "insufficient") {
    return {
      status,
      design_version: UNCERTAINTY_DESIGN[FIXTURE_MAJOR],
      seed: 1729,
      requested_resamples: 500,
      valid_resamples: 4,
      interval: null,
      resampling_unit: null,
      cohort_policy: null,
      warning:
        "Fixture bootstrap resolved only 4 valid resamples, below the stated minimum; no interval is reported.",
    };
  }
  return {
    status: "pending",
    design_version: null,
    seed: null,
    requested_resamples: null,
    valid_resamples: null,
    interval: null,
    resampling_unit: null,
    cohort_policy: null,
    warning: "Uncertainty computation is pending for this fixture profile.",
  };
}

function buildCaveats(catalog, profile) {
  const selfSubject = "self_retrieval";
  const references = catalog.features
    .slice(0, 6)
    .map((feature) => `evidence-${selfSubject}-f-${feature.feature_id}`);
  const uncertaintyCode = profile.uncertainty === "pending"
    ? "uncertainty_pending"
    : "uncertainty_sampling_only";

  return [
    {
      code: "fingerprint_not_style_proof",
      severity: "critical",
      message: "A statistical fingerprint describes measurements, not a style proof or a player quality verdict.",
      evidence_refs: references,
    },
    {
      code: "similarity_not_recruitment",
      severity: "important",
      message: "Nearest-neighbour similarity is an identity test, not a recruitment recommendation.",
      evidence_refs: references.slice(0, 3),
    },
    {
      code: "same_season_team_confound",
      severity: "important",
      message: "Same-season comparisons keep the same club and fixture context, which is a known confound.",
      evidence_refs: references.slice(3, 6),
    },
    {
      code: "within_role_display_differs_from_global_model",
      severity: "context",
      message: "Display percentiles are within-role; the retrieval model still uses global z-scores.",
      evidence_refs: references.slice(0, 2),
    },
    {
      code: uncertaintyCode,
      severity: "context",
      message:
        profile.uncertainty === "pending"
          ? "Uncertainty intervals are not yet available for any stored profile in this dataset version."
          : "Uncertainty intervals reflect a resampling simulation and are reported with the monograph caveats.",
      evidence_refs: references.slice(1, 4),
    },
  ];
}

function buildNeighbors(catalog, profile, roleCandidates) {
  return [1, 2, 3, 4, 5].map((rank) => {
    const candidate = roleCandidates[rank - 1];
    const profileKey = candidate.profile_key;
    const cosine = round(0.92 - rank * 0.025, 6);
    const subject = `neighbor:${profileKey}`;
    const evidence = buildEvidenceSet(catalog, profile, subject, cosine);
    return {
      rank,
      player_key: candidate.player_key,
      profile_key: profileKey,
      display_name: candidate.display_name,
      role: candidate.role,
      competition: candidate.competition,
      teams: candidate.period_contexts.b.teams.map((team) => ({ id: team.id, name: team.name })),
      candidate_period: "b",
      ...scoreField(cosine),
      evidence_refs: evidence.references,
      stability: bound(neighborStability(profile.uncertainty)),
      ...v2Binding(),
    };
  });
}

function buildProfileArtifact(catalog, manifest, profile, indexProfileItems) {
  const periodA = buildPeriodFingerprint(catalog, "a", profile);
  const periodB = buildPeriodFingerprint(catalog, "b", profile);
  const zA = new Map(periodA.features.map((value) => [value.feature_id, value.global_z_score]));
  const zB = new Map(periodB.features.map((value) => [value.feature_id, value.global_z_score]));
  const withZScores = { ...profile, zA, zB };

  const selfCosine = round(0.898, 6);
  const self = buildEvidenceSet(catalog, withZScores, "self_retrieval", selfCosine);
  const neighbors = buildNeighbors(catalog, withZScores, indexProfileItems);
  const baseline = {
    candidate_count: 1,
    self_rank: 1,
    reciprocal_rank: 1,
    ...scoreField(null),
    evidence_refs: [],
    uncertainty: bound(rankUncertainty(profile.uncertainty, 1)),
    ...v2Binding(),
  };
  const retrievalGlobal = {
    candidate_count: 1257,
    self_rank: profile.selfRank,
    reciprocal_rank: round(1 / profile.selfRank, 6),
    ...scoreField(selfCosine),
    evidence_refs: self.references,
    uncertainty: bound(rankUncertainty(profile.uncertainty, profile.selfRank)),
    ...v2Binding(),
  };

  const roleCounts = { Goalkeeper: 92, Defender: 398, Midfielder: 446, Forward: 321 };
  const evidenceIndex = [
    ...self.items,
    ...neighbors.flatMap((neighbor) => {
      const evidence = buildEvidenceSet(
        catalog,
        withZScores,
        `neighbor:${neighbor.profile_key}`,
        FIXTURE_MAJOR === 2 ? neighbor.similarity_score : neighbor.cosine_similarity,
      );
      return evidence.items;
    }),
  ];

  return {
    contract: "scoutlens.showcase",
    schema_version: manifest.schema_version,
    dataset_version: manifest.dataset_version,
    profile_key: profile.profile_key,
    identity: {
      player_key: profile.player_key,
      display_name: profile.display_name,
      role: profile.role,
      competition: profile.competition,
      season: "2017/18",
      period_contexts: {
        a: {
          minutes: minutesFor("a", profile),
          match_count: periodA.match_count,
          teams: profile.teams.a,
        },
        b: {
          minutes: minutesFor("b", profile),
          match_count: periodB.match_count,
          teams: profile.teams.b,
        },
      },
    },
    cohort: {
      global_profile_count: 1257,
      within_role_profile_count: roleCounts[profile.role],
      minutes_threshold_per_period: 450,
      scaler_scope: "eligible_period_a_and_b_combined",
      default_display_percentile_scope: "within_role",
    },
    periods: { a: periodA, b: periodB },
    retrieval: {
      query_period: "a",
      candidate_period: "b",
      method: RETRIEVAL_METHOD[FIXTURE_MAJOR],
      global: retrievalGlobal,
      within_role: { ...retrievalGlobal },
      baseline_role_minutes: baseline,
    },
    neighbors,
    uncertainty: bound(uncertaintyBlock(profile.uncertainty)),
    caveats: buildCaveats(catalog, profile),
    evidence_index: evidenceIndex,
    provenance_ref: "manifest.json",
  };
}

function buildIndexItem(profile) {
  const total = minutesFor("a", profile) + minutesFor("b", profile);
  return {
    player_key: profile.player_key,
    profile_key: profile.profile_key,
    display_name: profile.display_name,
    role: profile.role,
    competition: profile.competition,
    period_contexts: {
      a: { minutes: minutesFor("a", profile), match_count: Math.round(minutesFor("a", profile) / 90), teams: profile.teams.a },
      b: { minutes: minutesFor("b", profile), match_count: Math.round(minutesFor("b", profile) / 90), teams: profile.teams.b },
    },
    total_minutes: total,
    self_rank_within_role: profile.selfRank,
    uncertainty_status: profile.uncertainty,
    artifact_path: `players/${profile.profile_key}.json`,
  };
}

function resolveProfileTemplates() {
  const base = {
    teams: FIXTURE_IDENTITY.teams,
    competition: FIXTURE_IDENTITY.competition,
    role: FIXTURE_IDENTITY.role,
    seed: 11,
    selfRank: 7,
    uncertainty: "pending",
  };
  const maxContent = {
    ...base,
    player_key: FIXTURE_IDENTITY.player_key,
    profile_key: FIXTURE_IDENTITY.profile_key,
    display_name: FIXTURE_IDENTITY.display_name,
  };
  const uncertaintyTemplates = UNCERTAINTY_PROFILES.map((template, index) => ({
    ...base,
    player_key: template.player_key,
    profile_key: template.profile_key,
    display_name: template.display_name,
    role: template.role,
    competition: template.competition,
    teams: template.teams,
    seed: 21 + index,
    selfRank: 9 + index * 3,
    uncertainty: template.uncertainty,
  }));
  return [maxContent, ...uncertaintyTemplates];
}

async function buildFixturePack() {
  const catalog = await readJson(resolve(publishedRoot, "feature-catalog.json"));
  const manifest = await readJson(resolve(publishedRoot, "manifest.json"));
  if (FIXTURE_MAJOR === 2) {
    // Real weights and a real representation id, so the fixture satisfies the
    // binding the consumer enforces rather than a shape that merely validates.
    publishedRepresentation = await readJson(resolve(publishedRoot, "representation.json"));
    if (publishedRepresentation.representation.id !== manifest.representation_id) {
      throw new Error("The published v2 manifest and representation disagree");
    }
  }
  const index = await readJson(resolve(publishedRoot, "players.index.json"));
  const researchSummary = await readJson(resolve(publishedRoot, "research-summary.json"));

  const templates = resolveProfileTemplates();
  const syntheticKeys = new Set(templates.map((template) => template.profile_key));
  const roleCandidatesByRole = new Map();
  const realIndexItems = [...index.profiles].sort((left, right) =>
    left.profile_key.localeCompare(right.profile_key, "en"),
  );
  for (const role of [...new Set(templates.map((template) => template.role))]) {
    roleCandidatesByRole.set(
      role,
      realIndexItems
        .filter((item) => item.role === role && !syntheticKeys.has(item.profile_key))
        .slice(0, 5),
    );
  }

  const profiles = new Map();
  const indexItems = [];
  for (const template of templates) {
    const artifact = buildProfileArtifact(
      catalog,
      manifest,
      template,
      roleCandidatesByRole.get(template.role) ?? [],
    );
    profiles.set(`${template.profile_key}.json`, artifact);
    indexItems.push(buildIndexItem(template));
  }

  const fixtureIndex = {
    contract: "scoutlens.showcase",
    schema_version: manifest.schema_version,
    dataset_version: manifest.dataset_version,
    profiles: [...index.profiles, ...indexItems],
  };

  const fixtureManifest = {
    ...manifest,
    generated_at: "2026-08-06T00:00:00Z",
    featured_profile: {
      profile_key: FIXTURE_IDENTITY.profile_key,
      editorial: true,
      reason:
        "Delegated test-only fixture pack: the max-content synthetic profile is featured so the static Lab export renders the stretched selector and identity cells without touching published artifacts.",
    },
  };

  const pack = new Map();
  pack.set("feature-catalog.json", catalog);
  pack.set("research-summary.json", researchSummary);
  pack.set("players.index.json", fixtureIndex);
  if (FIXTURE_MAJOR === 2) {
    pack.set("representation.json", publishedRepresentation);
  }
  for (const [filename, artifact] of profiles) {
    pack.set(`players/${filename}`, artifact);
  }

  const files = [];
  for (const [path, value] of pack) {
    const bytes = Buffer.from(canonicalJson(value), "utf8");
    files.push({
      path,
      media_type: "application/json",
      sha256: sha256Of(bytes),
      bytes: bytes.byteLength,
      records: path === "players.index.json" ? fixtureIndex.profiles.length : 1,
    });
  }
  files.sort((left, right) => left.path.localeCompare(right.path, "en"));
  fixtureManifest.files = files;
  pack.set("manifest.json", fixtureManifest);
  return pack;
}

export async function generateFixturePack(fixtureDir = fixtureRoot) {
  await rm(fixtureDir, { recursive: true, force: true });
  await mkdir(resolve(fixtureDir, "players"), { recursive: true });
  const pack = await buildFixturePack();
  for (const [path, value] of pack) {
    const target = resolve(fixtureDir, path);
    await mkdir(dirname(target), { recursive: true });
    await writeJson(target, value);
  }
}

export async function collectFiles(root) {
  const files = [];
  const walk = async (directory) => {
    for (const entry of await readdir(directory, { withFileTypes: true })) {
      const path = resolve(directory, entry.name);
      if (entry.isDirectory()) {
        await walk(path);
      } else {
        files.push(path);
      }
    }
  };
  await walk(root);
  return files.sort();
}

export async function verifyFixturePack(fixtureDir = fixtureRoot) {
  if (!fixtureDir.startsWith(fixturesRoot) || fixtureDir === fixturesRoot) {
    throw new Error(`Refusing to verify outside the fixtures root: ${fixtureDir}`);
  }
  const manifest = await readJson(resolve(fixtureDir, "manifest.json"));
  const expected = new Map(manifest.files.map((file) => [file.path, file]));
  const onDisk = await collectFiles(fixtureDir);
  // manifest.json is the verifier's entry artifact, never a member of its own files list.
  const relativePaths = new Set(
    onDisk
      .map((path) => path.replaceAll("\\", "/").slice(fixtureDir.length + 1))
      .filter((path) => path !== "manifest.json"),
  );
  if (relativePaths.size !== expected.size) {
    const missing = [...expected.keys()].filter((path) => !relativePaths.has(path));
    const extra = [...relativePaths].filter((path) => !expected.has(path));
    throw new Error(
      `Fixture pack file set differs from manifest: missing=${JSON.stringify(missing.slice(0, 3))} extra=${JSON.stringify(extra.slice(0, 3))}`,
    );
  }
  for (const [path, entry] of expected) {
    const absolute = resolve(fixtureDir, path);
    const bytes = await readFile(absolute);
    if (bytes.byteLength !== entry.bytes) {
      throw new Error(`Fixture pack ${path} byte count ${bytes.byteLength} != manifest ${entry.bytes}`);
    }
    if (sha256Of(bytes) !== entry.sha256) {
      throw new Error(`Fixture pack ${path} sha256 mismatch`);
    }
    const text = bytes.toString("utf8");
    if (canonicalJson(JSON.parse(text)) !== text) {
      throw new Error(`Fixture pack ${path} is not canonical JSON`);
    }
  }
  const index = await readJson(resolve(fixtureDir, "players.index.json"));
  return {
    fixtureRoot: fixtureDir,
    files: manifest.files.length,
    profiles: index.profiles.length,
  };
}

async function main() {
  const command = process.argv[2];
  if (command === "generate") {
    await generateFixturePack();
    const result = await verifyFixturePack();
    console.log(JSON.stringify({ command: "generate", fixtureId, ...result }, null, 2));
    return;
  }
  if (command === "verify") {
    const result = await verifyFixturePack();
    console.log(JSON.stringify({ command: "verify", fixtureId, ...result }, null, 2));
    return;
  }
  throw new Error("usage: fixture-pack.mjs generate|verify");
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  await main();
}
