import { describe, expect, it } from "vitest";

import {
  ShowcaseContractError,
  StaticShowcaseRepository,
  type ShowcaseFetch,
} from "@/contracts/showcase-repository";

const DATASET_VERSION = "wyscout-2017-18-v1-aaaaaaaaaaaa";
const OTHER_DATASET_VERSION = "wyscout-2017-18-v1-bbbbbbbbbbbb";
const PROFILE_KEY = "wy-100-c-1";
const PROFILE_PATH = `players/${PROFILE_KEY}.json`;
const encoder = new TextEncoder();

interface FixtureOptions {
  checksumMismatch?: boolean;
  manifestSchemaVersion?: string;
  missingEvidence?: boolean;
  researchDatasetVersion?: string;
}

async function digest(text: string): Promise<string> {
  const bytes = encoder.encode(text);
  const hash = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(hash), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

function serialize(value: unknown): string {
  return `${JSON.stringify(value)}\n`;
}

function periodContext() {
  return {
    minutes: 900,
    match_count: 10,
    teams: [{ id: 1, name: "Evidence FC", minutes: 900 }],
  };
}

function caveat(code: string, evidenceRefs: ReadonlyArray<string> = []) {
  return {
    code,
    severity: "important",
    message: "This interpretation remains deliberately bounded.",
    evidence_refs: [...evidenceRefs],
  };
}

function pendingRankUncertainty() {
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

function evidenceFor(subject: string, prefix: string) {
  const items = Array.from({ length: 40 }, (_, index) => ({
    evidence_id: `${prefix}-${index}`,
    subject,
    kind: index < 32 ? "feature_contribution" : "family_contribution",
    feature_id: index < 32 ? `feature-${index}` : null,
    family: "passing",
    query_global_z: index < 32 ? 0.25 : null,
    candidate_global_z: index < 32 ? 0.5 : null,
    contribution: 0.02,
    interpretation: "alignment",
  }));
  return { items, references: items.map((item) => item.evidence_id) };
}

function buildProfile(missingEvidence: boolean) {
  const selfEvidence = evidenceFor("self_retrieval", "self");
  const neighborEvidence = Array.from({ length: 5 }, (_, index) => {
    const profileKey = `wy-${200 + index}-c-1`;
    return {
      profileKey,
      evidence: evidenceFor(`neighbor:${profileKey}`, `neighbor-${index + 1}`),
    };
  });
  const evidenceIndex = [
    ...selfEvidence.items,
    ...neighborEvidence.flatMap((entry) => entry.evidence.items),
  ];
  const featureValues = Array.from({ length: 32 }, (_, index) => ({
    feature_id: `feature-${index}`,
    raw_value: index / 10,
    global_z_score: index / 100,
    global_percentile: 50,
    within_role_percentile: 55,
    imputed_for_model: false,
    support: { minutes: 900, attempts: null, successes: null },
    uncertainty: {
      status: "pending",
      valid_resamples: null,
      raw_ci_95: null,
      within_role_percentile_ci_95: null,
    },
  }));
  const retrievalOutcome = {
    candidate_count: 10,
    self_rank: 1,
    reciprocal_rank: 1,
    cosine_similarity: 0.8,
    evidence_refs: selfEvidence.references,
    uncertainty: pendingRankUncertainty(),
  };

  return {
    contract: "scoutlens.showcase",
    schema_version: "1.0.0",
    dataset_version: DATASET_VERSION,
    profile_key: PROFILE_KEY,
    identity: {
      player_key: "wy-100",
      display_name: "Ada Midfielder",
      role: "Midfielder",
      competition: { id: 1, name: "Evidence League", country: "Testland" },
      season: "2017/18",
      period_contexts: { a: periodContext(), b: periodContext() },
    },
    cohort: {
      global_profile_count: 10,
      within_role_profile_count: 6,
      minutes_threshold_per_period: 450,
      scaler_scope: "eligible_period_a_and_b_combined",
      default_display_percentile_scope: "within_role",
    },
    periods: {
      a: {
        label: "First period",
        date_start: "2017-01-01",
        date_end: "2017-06-30",
        minutes: 900,
        match_count: 10,
        features: featureValues,
      },
      b: {
        label: "Second period",
        date_start: "2017-07-01",
        date_end: "2017-12-31",
        minutes: 900,
        match_count: 10,
        features: featureValues,
      },
    },
    retrieval: {
      query_period: "a",
      candidate_period: "b",
      method: "combined_scaler_cosine_v1",
      global: retrievalOutcome,
      within_role: retrievalOutcome,
      baseline_role_minutes: retrievalOutcome,
    },
    neighbors: neighborEvidence.map((entry, index) => ({
      rank: index + 1,
      player_key: `wy-${200 + index}`,
      profile_key: entry.profileKey,
      display_name: `Neighbor ${index + 1}`,
      role: "Midfielder",
      competition: { id: 1, name: "Evidence League", country: "Testland" },
      teams: [{ id: 2, name: "Control FC" }],
      candidate_period: "b",
      cosine_similarity: 0.7 - index / 100,
      evidence_refs: entry.evidence.references,
      stability: {
        status: "pending",
        valid_resamples: null,
        top_5_selection_rate: null,
        median_rank: null,
        rank_ci_95: null,
      },
    })),
    uncertainty: {
      status: "pending",
      design_version: null,
      seed: null,
      requested_resamples: null,
      valid_resamples: null,
      interval: null,
      resampling_unit: null,
      cohort_policy: null,
      warning: "Sampling uncertainty is not yet available.",
    },
    caveats: [
      caveat("fingerprint_not_style_proof", missingEvidence ? ["missing-evidence"] : []),
      caveat("similarity_not_recruitment"),
      caveat("same_season_team_confound"),
      caveat("within_role_display_differs_from_global_model"),
      caveat("uncertainty_pending"),
    ],
    evidence_index: evidenceIndex,
    provenance_ref: "manifest.json",
  };
}

function buildIndex() {
  return {
    contract: "scoutlens.showcase",
    schema_version: "1.0.0",
    dataset_version: DATASET_VERSION,
    profiles: [
      {
        player_key: "wy-100",
        profile_key: PROFILE_KEY,
        display_name: "Ada Midfielder",
        role: "Midfielder",
        competition: { id: 1, name: "Evidence League", country: "Testland" },
        period_contexts: { a: periodContext(), b: periodContext() },
        total_minutes: 1800,
        self_rank_within_role: 1,
        uncertainty_status: "pending",
        artifact_path: PROFILE_PATH,
      },
    ],
  };
}

function buildResearchSummary(datasetVersion: string) {
  const experiments = Array.from({ length: 8 }, (_, index) => ({
    experiment_id: `experiment-${index + 1}`,
    title: `Experiment ${index + 1}`,
    provider: "wyscout_pappalardo",
    population: "Fixture population",
    metrics: [
      {
        metric_id: `metric-${index + 1}`,
        label: "Mean reciprocal rank",
        value: 0.25,
        ci_95: null,
        unit: "mrr",
        display_precision: 4,
      },
    ],
    conclusion: "A bounded fixture conclusion.",
    caveat_codes: ["fingerprint_not_style_proof"],
    source_artifact: "artifacts/gate2_results.json",
    report_url: "docs/feasibility-report.md",
  }));
  return {
    contract: "scoutlens.showcase",
    schema_version: "1.0.0",
    dataset_version: datasetVersion,
    supported_claim: "Profiles contain a temporally stable individual signal.",
    unsupported_claims: [
      "Similarity proves style.",
      "Similarity recommends recruitment.",
      "The result predicts transfer success.",
    ],
    experiments,
    narrative_steps: Array.from({ length: 6 }, (_, index) => ({
      order: index + 1,
      kind: "result",
      title: `Step ${index + 1}`,
      summary: "A documented step in the research progression.",
      experiment_ids: [experiments[index]?.experiment_id ?? "experiment-1"],
    })),
    caveats: [
      caveat("fingerprint_not_style_proof"),
      caveat("similarity_not_recruitment"),
      caveat("same_season_team_confound"),
      caveat("uncertainty_pending"),
    ],
  };
}

async function buildFixture(options: FixtureOptions = {}) {
  const artifactValues = new Map<string, unknown>([
    ["feature-catalog.json", { fixture: true }],
    ["players.index.json", buildIndex()],
    ["research-summary.json", buildResearchSummary(options.researchDatasetVersion ?? DATASET_VERSION)],
    [PROFILE_PATH, buildProfile(options.missingEvidence ?? false)],
  ]);
  const serialized = new Map(
    [...artifactValues.entries()].map(([path, value]) => [path, serialize(value)]),
  );
  const files = await Promise.all(
    [...serialized.entries()].map(async ([path, text]) => ({
      path,
      media_type: "application/json",
      sha256:
        options.checksumMismatch === true && path === "research-summary.json"
          ? "0".repeat(64)
          : await digest(text),
      bytes: encoder.encode(text).byteLength,
      records: 1,
    })),
  );
  const manifest = {
    contract: "scoutlens.showcase",
    schema_version: options.manifestSchemaVersion ?? "1.0.0",
    dataset_version: DATASET_VERSION,
    generated_at: "2026-07-28T12:00:00Z",
    featured_profile: {
      profile_key: PROFILE_KEY,
      editorial: true,
      reason: "Selected deterministically for the repository fixture.",
    },
    source: {
      provider: "wyscout_pappalardo",
      season: "2017/18",
      title: "Fixture source",
      citation: "Fixture citation",
      source_url: "https://example.test/source",
      licence: "CC BY 4.0",
      licence_url: "https://creativecommons.org/licenses/by/4.0/",
      redistribution_note: "Derived fixture values only.",
    },
    population: {
      analytical_unit: "player_competition",
      chronological_periods: ["a", "b"],
      domestic_competition_ids: [1],
      minutes_threshold_per_period: 450,
      profile_count: 1,
      feature_count: 32,
    },
    producer: {
      git_commit: null,
      git_dirty: null,
      source_sha256: "1".repeat(64),
      config_path: "config/experiment.json",
      config_sha256: "2".repeat(64),
      python_version: "3.14.0",
      polars_version: "1.0.0",
    },
    inputs: [
      {
        logical_name: "fixture/input.json",
        sha256: "3".repeat(64),
        bytes: 1,
        public: false,
      },
    ],
    files,
  };
  serialized.set("manifest.json", serialize(manifest));

  const fetchFixture: ShowcaseFetch = async (input) => {
    const path = input.replace(/^.*\/showcase\/v1\//, "");
    const body = serialized.get(path);
    return body === undefined
      ? new Response("not found", { status: 404 })
      : new Response(body, { status: 200, headers: { "content-type": "application/json" } });
  };
  // A v1 fixture, pinned to major 1: these cases exercise the frozen cosine
  // contract, which stays supported after the site moved to major 2.
  return new StaticShowcaseRepository(fetchFixture, "/showcase/v1/", 1);
}

async function expectContractError(promise: Promise<unknown>, code: string) {
  try {
    await promise;
    throw new Error(`Expected ShowcaseContractError with code ${code}`);
  } catch (error) {
    expect(error).toBeInstanceOf(ShowcaseContractError);
    if (!(error instanceof ShowcaseContractError)) {
      throw error;
    }
    expect(error.code).toBe(code);
  }
}

describe("StaticShowcaseRepository", () => {
  it("accepts a valid fixture through every repository method", async () => {
    const repository = await buildFixture();

    await expect(repository.getManifest()).resolves.toMatchObject({ dataset_version: DATASET_VERSION });
    await expect(repository.getResearchSummary()).resolves.toMatchObject({
      supported_claim: expect.any(String),
    });
    await expect(repository.listProfiles()).resolves.toHaveLength(1);
    await expect(repository.getProfile(PROFILE_KEY)).resolves.toMatchObject({ profile_key: PROFILE_KEY });
  });

  it("rejects an unsupported schema major before schema validation", async () => {
    const repository = await buildFixture({ manifestSchemaVersion: "2.0.0" });
    await expectContractError(repository.getManifest(), "unsupported_schema_major");
  });

  it("rejects an artifact from a different dataset", async () => {
    const repository = await buildFixture({ researchDatasetVersion: OTHER_DATASET_VERSION });
    await expectContractError(repository.getResearchSummary(), "dataset_mismatch");
  });

  it("rejects unresolved profile evidence references", async () => {
    const repository = await buildFixture({ missingEvidence: true });
    await expectContractError(repository.getProfile(PROFILE_KEY), "missing_evidence");
  });

  it("rejects bytes that do not match the manifest checksum", async () => {
    const repository = await buildFixture({ checksumMismatch: true });
    await expectContractError(repository.getResearchSummary(), "checksum_mismatch");
  });
});
