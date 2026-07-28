# Showcase artifact contract

**Contract:** `scoutlens.showcase/1.0.0`

**Status:** normative for the first implementation

**Producer:** offline Python exporter

**Consumers:** static web application; optional later API and AI evidence layer

**Tracking:** Beads `scoutlens-jtt.3`

## Purpose

This contract is the only public data boundary between ScoutLens research code
and the flagship application. Python owns all scientific computation. The web
layer may filter, sort already-declared values, round for display, and change
visual presentation; it must not recompute features, fit scalers, choose
neighbors, estimate uncertainty, or reconstruct research claims.

The same contract can later be returned by FastAPI/DuckDB without changing UI
semantics. File reads are a deployment choice, not part of the domain model.

## Compatibility rules

- `schema_version` is semantic-versioned. Consumers accept the same major
  version and reject an unknown major.
- Adding an optional field is a minor change. Removing, renaming, changing
  meaning, or making an optional field required is a major change.
- `dataset_version` identifies one immutable export. Rebuilding different
  bytes creates a new value even when the schema is unchanged.
- JSON keys use `snake_case`; identifiers are case-sensitive ASCII strings.
- Timestamps are ISO 8601 UTC. Hashes are lowercase SHA-256 hex.
- Numbers must be finite JSON numbers. Undefined values are `null` only where
  the type permits it; `NaN`, `Infinity`, and magic sentinels are forbidden.
- Arrays with a declared ranking or catalog order are deterministically sorted.
- UI rounding never changes stored values. Default display precision lives in
  the feature catalog.

## Public file layout

```text
public/showcase/v1/
├── manifest.json
├── research-summary.json
├── feature-catalog.json
├── players.index.json
└── players/
    └── wy-<player_id>-c-<competition_id>.json
```

The manifest hashes every other file but not itself, avoiding a recursive
checksum. Files are immutable and may be cached with `immutable`; deployment
must serve `manifest.json` with a shorter cache lifetime so a client can detect
a new `dataset_version`.

## Shared vocabulary

```ts
type SchemaVersion = `${number}.${number}.${number}`;
type Sha256 = string; // ^[a-f0-9]{64}$
type PlayerKey = `wy-${number}`;
type ProfileKey = `wy-${number}-c-${number}`;
type PeriodId = "a" | "b";
type Role = "Goalkeeper" | "Defender" | "Midfielder" | "Forward";
type FeatureFamily =
  | "passing"
  | "progression"
  | "chance_creation"
  | "shooting"
  | "defensive"
  | "spatial"
  | "possession"
  | "carrying_proxy";

type CaveatCode =
  | "fingerprint_not_style_proof"
  | "similarity_not_recruitment"
  | "same_season_team_confound"
  | "small_transfer_sample"
  | "provider_replication_lower_magnitude"
  | "within_role_display_differs_from_global_model"
  | "uncertainty_pending"
  | "uncertainty_sampling_only"
  | "goalkeeper_feature_coverage_weak";

interface Caveat {
  code: CaveatCode;
  severity: "context" | "important" | "critical";
  message: string;
  evidence_refs: string[];
}
```

`Role` uses the frozen Wyscout nominal role. No finer positional taxonomy is
inferred in v1. The goalkeeper caveat is mandatory for goalkeeper profiles
because the native 32-feature catalog is outfield-oriented.

## `manifest.json`

The manifest is the discovery, licence, integrity, and compatibility entry
point.

```ts
interface ShowcaseManifest {
  contract: "scoutlens.showcase";
  schema_version: SchemaVersion;
  dataset_version: string;
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
    domestic_competition_ids: number[];
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
  inputs: Array<{
    logical_name: string;
    sha256: Sha256;
    bytes: number;
    public: false;
  }>;
  files: Array<{
    path: string;
    media_type: "application/json";
    sha256: Sha256;
    bytes: number;
    records: number;
  }>;
}
```

Normative rules:

- `profile_count` equals the number of catalog entries and player files.
- `source_sha256` uses the same path-and-byte algorithm as experiment run
  manifests.
- Raw input paths are not exposed; `logical_name` and hashes are sufficient.
- `dataset_version` should be `wyscout-2017-18-v1-<first 12 chars of the
  canonical export digest>`.
- The client verifies the requested player's file hash before accepting its
  payload. Build-time validation verifies every file hash.

## `feature-catalog.json`

Labels and descriptions exist once, outside player payloads. The catalog
contains exactly the frozen 32 Wyscout features in their declared order and
family partition.

```ts
interface FeatureCatalogArtifact {
  contract: "scoutlens.showcase";
  schema_version: SchemaVersion;
  dataset_version: string;
  features: FeatureDefinition[];
}

interface FeatureDefinition {
  feature_id: string;
  label: string;
  short_label: string;
  family: FeatureFamily;
  order: number; // unique 0..31
  description: string;
  unit: "per_90" | "ratio" | "pitch_percent" | "distance_per_90";
  display_precision: number;
  raw_null_meaning: "no_attempts" | "not_observed" | null;
  model_null_handling: "population_mean_then_z_zero";
  direction_semantics: "descriptive_not_quality";
  support_kind: "minutes" | "attempts";
  method_ref: string;
}
```

`method_ref` is a stable link or fragment into feature definitions. The web UI
must not infer labels from `feature_id` or color a higher value as better.

Percentiles are deterministic average-rank percentiles over the same combined
eligible period-A and period-B population used to fit the global scaler.
`global_percentile` uses all eligible rows; `within_role_percentile` uses the
subset with the same frozen nominal role. Null raw values inherit the scaler's
mean-imputed `z=0` before ranking, so tied nulls receive the same average
percentile. This display transform does not change the globally standardized
vectors used by cosine retrieval.

## `players.index.json`

This is the only artifact needed to populate search and filters. It must stay
within the compressed catalog budget and therefore contains no 32-feature
vectors.

```ts
interface PlayerIndexArtifact {
  contract: "scoutlens.showcase";
  schema_version: SchemaVersion;
  dataset_version: string;
  profiles: PlayerIndexItem[];
}

interface PlayerIndexItem {
  player_key: PlayerKey;
  profile_key: ProfileKey;
  display_name: string;
  role: Role;
  competition: {
    id: number;
    name: string;
    country: string;
  };
  period_contexts: {
    a: PeriodContext;
    b: PeriodContext;
  };
  total_minutes: number;
  self_rank_within_role: number;
  uncertainty_status: "pending" | "available" | "insufficient";
  artifact_path: string;
}

interface PeriodContext {
  minutes: number;
  match_count: number;
  teams: Array<{ id: number; name: string; minutes: number }>;
}
```

Sort by Unicode-normalized `display_name`, then `profile_key`. Search uses a
separate normalized client-side key constructed at build time or UI load; it
must not replace the correctly accented display name.

No birth date, nationality, market value, photograph URL, injury data, or
contract data is part of the v1 public contract.

## `players/<profile_key>.json`

One payload contains the complete selected-player flow.

```ts
interface PlayerProfileArtifact {
  contract: "scoutlens.showcase";
  schema_version: SchemaVersion;
  dataset_version: string;
  profile_key: ProfileKey;
  identity: {
    player_key: PlayerKey;
    display_name: string;
    role: Role;
    competition: { id: number; name: string; country: string };
    season: "2017/18";
    period_contexts: { a: PeriodContext; b: PeriodContext };
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
  neighbors: StatisticalNeighbor[];
  uncertainty: UncertaintyBlock;
  caveats: Caveat[];
  evidence_index: EvidenceItem[];
  provenance_ref: "manifest.json";
}

interface PeriodFingerprint {
  label: string;
  date_start: string;
  date_end: string;
  minutes: number;
  match_count: number;
  features: FeatureValue[]; // exactly 32 in feature-catalog order
}

interface FeatureValue {
  feature_id: string;
  raw_value: number | null;
  global_z_score: number;
  global_percentile: number; // 0..100
  within_role_percentile: number; // 0..100
  imputed_for_model: boolean;
  support: {
    minutes: number;
    attempts: number | null;
    successes: number | null;
  };
  uncertainty: FeatureUncertainty;
}

interface FeatureUncertainty {
  status: "pending" | "available" | "insufficient";
  valid_resamples: number | null;
  raw_ci_95: [number, number] | null;
  within_role_percentile_ci_95: [number, number] | null;
}
```

If `raw_value` is null, `imputed_for_model` must be true and
`global_z_score` must be exactly `0`. A ratio's `attempts` and `successes`
are integers when available. Per-90 fields may leave both null and use minutes
as their support.

### Identity retrieval

```ts
interface IdentityRetrieval {
  query_period: "a";
  candidate_period: "b";
  method: "combined_scaler_cosine_v1";
  global: RetrievalOutcome;
  within_role: RetrievalOutcome;
  baseline_role_minutes: RetrievalOutcome;
}

interface RetrievalOutcome {
  candidate_count: number;
  self_rank: number;
  reciprocal_rank: number;
  cosine_similarity: number | null;
  evidence_refs: string[];
  uncertainty: RankUncertainty;
}

interface RankUncertainty {
  status: "pending" | "available" | "insufficient";
  valid_resamples: number | null;
  median_rank: number | null;
  rank_ci_95: [number, number] | null;
  recall_at_1_rate: number | null;
  recall_at_5_rate: number | null;
  recall_at_10_rate: number | null;
}
```

`baseline_role_minutes.cosine_similarity` is null because that baseline does
not use cosine. Candidate counts include the true self candidate. Ties follow
the deterministic player-id rule used by the research code.

### Statistical neighbors and additive evidence

```ts
interface StatisticalNeighbor {
  rank: 1 | 2 | 3 | 4 | 5;
  player_key: PlayerKey;
  profile_key: ProfileKey;
  display_name: string;
  role: Role;
  competition: { id: number; name: string; country: string };
  teams: Array<{ id: number; name: string }>;
  candidate_period: "b";
  cosine_similarity: number;
  evidence_refs: string[];
  stability: {
    status: "pending" | "available" | "insufficient";
    valid_resamples: number | null;
    top_5_selection_rate: number | null;
    median_rank: number | null;
    rank_ci_95: [number, number] | null;
  };
}

interface EvidenceItem {
  evidence_id: string;
  subject: "self_retrieval" | `neighbor:${ProfileKey}`;
  kind: "feature_contribution" | "family_contribution";
  feature_id: string | null;
  family: FeatureFamily;
  query_global_z: number | null;
  candidate_global_z: number | null;
  contribution: number;
  interpretation: "alignment" | "disagreement" | "neutral";
}
```

For cosine evidence, feature contribution is:

```text
c_i = (z_query_i × z_candidate_i) / (||z_query|| × ||z_candidate||)
```

The sum of the 32 feature contributions equals the unrounded stored cosine
score within `1e-9`. A family contribution is the sum of its feature
contributions. Evidence ordering is descending absolute contribution, then
feature-catalog order. The query's `player_key` is forbidden in `neighbors`,
even if that human player has another competition-scoped profile.

The UI may call the largest positive contribution “strongest alignment”, but
not “shared strength”: two below-average values also align. A negative
contribution is “disagreement”, not a player weakness.

### Top-level uncertainty block

```ts
interface UncertaintyBlock {
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
```

When top-level status is `pending`, every nested uncertainty block is pending
and all interval/rate fields are null. When it is `available`, each nested
block may still be `insufficient`. The warning always explains that these are
sampling-stability estimates, not causal or future-performance uncertainty.

## `research-summary.json`

All landing and science metrics come from one artifact assembled from the five
versioned research results.

```ts
interface ResearchSummaryArtifact {
  contract: "scoutlens.showcase";
  schema_version: SchemaVersion;
  dataset_version: string;
  supported_claim: string;
  unsupported_claims: string[];
  experiments: ResearchExperiment[];
  narrative_steps: Array<{
    order: number;
    kind: "question" | "result" | "challenge" | "correction" | "replication" | "null_result";
    title: string;
    summary: string;
    experiment_ids: string[];
  }>;
  caveats: Caveat[];
}

interface ResearchExperiment {
  experiment_id: string;
  title: string;
  provider: "wyscout_pappalardo" | "statsbomb_open_data";
  population: string;
  metrics: Array<{
    metric_id: string;
    label: string;
    value: number;
    ci_95: [number, number] | null;
    unit: "mrr" | "median_rank" | "recall" | "count";
    display_precision: number;
  }>;
  conclusion: string;
  caveat_codes: CaveatCode[];
  source_artifact: string;
  report_url: string;
}
```

Required experiment coverage:

- Wyscout global and within-role Gate-2 retrieval;
- role+team+minutes robustness control;
- Wyscout transferred-player analysis;
- StatsBomb global, within-role, and transferred-player replication;
- raw-versus-shrunk ratio experiment and its null keep/drop decision.

`source_artifact` identifies one of the five checked-in result JSON files. The
exporter copies values programmatically and tests equality; it must not
redeclare headline constants.

## Mandatory cross-artifact invariants

The producer fails before writing a publishable directory unless all are true:

1. Every artifact has one identical `schema_version` and `dataset_version`.
2. Every catalog `profile_key` matches its payload and file name; there are no
   extra or missing player files.
3. Profile keys are unique player×competition units and both periods satisfy
   the frozen 450-minute eligibility threshold.
4. Every period contains each of the 32 feature IDs exactly once and in catalog
   order; feature families partition those IDs exactly.
5. Percentiles lie in `[0, 100]`, ranks are positive integers, selection rates
   lie in `[0, 1]`, and cosine values lie in `[-1, 1]` within floating-point
   tolerance.
6. A null raw value is explicitly imputed; a non-null raw value is not marked
   imputed.
7. Neighbor lists contain five distinct, same-role profiles whose `player_key`
   differs from the query and are sorted by descending cosine then ascending
   profile key.
8. Every evidence reference resolves; every contribution sum reconstructs its
   score within `1e-9`.
9. Goalkeepers carry `goalkeeper_feature_coverage_weak`; all profiles carry
   `fingerprint_not_style_proof`, `similarity_not_recruitment`, and
   `same_season_team_confound`.
10. Research-summary values equal their versioned source artifacts.
11. Every manifest checksum and byte count matches the canonical UTF-8 file
    written with sorted keys and a trailing newline.
12. StatsBomb appears only in aggregate research experiments; no StatsBomb
    profile key, player identity, team identity, or per-player feature value is
    present anywhere.

## Canonical serialization and atomic publication

The exporter writes to a new staging directory, validates every invariant,
serializes UTF-8 JSON with sorted keys and a final newline, computes file
hashes, writes the manifest last, and only then replaces the versioned public
directory. A failed build leaves the previous dataset untouched.

The reference implementation is:

```bash
uv run python -m scoutlens.showcase.export
```

It consumes `data/processed/{period_profiles,events,matches,minutes,players,
teams,competitions}.parquet`, `config/experiment.json`, and the five checked-in
research result artifacts. Ratio attempts/successes are recomputed from events
with the frozen feature code and must equal the checked period profiles before
publication.

`dataset_version` is derived without a circular self-hash: the exporter first
canonically serializes every non-manifest semantic artifact with the stable
placeholder `__DATASET_VERSION__`, hashes each sorted logical path plus
length-prefixed bytes, and uses the first 12 lowercase SHA-256 characters.
It then injects the resulting version into every artifact. `generated_at` and
producer environment fields live only in the manifest and do not change the
semantic dataset identity.

The first complete local export, `wyscout-2017-18-v1-0e48066f37cc`, contains
1,257 profiles and 1,261 JSON files including the manifest. The player payloads
measure 147,054,404 bytes uncompressed and 17,151,006 bytes as the sum of
deterministic individual gzip streams; the largest profile is 14,325 bytes
gzip and the catalog index is 69,867 bytes gzip. Both public performance
budgets pass. Because the uncompressed payload set is too noisy for code
review, Git tracks the manifest/catalog/index/research files while Beads
`scoutlens-jtt.10` owns a content-addressed immutable player pack and verified
raw-data-free hydration path.

The Git-tracked release should contain the small contract files and generated
showcase artifacts needed for a raw-data-free web build. Raw/processed provider
data remains ignored. If the complete player payload set proves noisy in code
review, it may be attached as an immutable release asset, but the manifest and
checksums remain tracked and the application build must pin the asset digest.

## Consumer behavior

- Load and validate the manifest before other artifacts.
- Reject an unsupported schema major or a profile file whose declared dataset
  version differs from the active manifest.
- Preserve raw numerical values in memory; round only at the final formatting
  boundary.
- Render declared caveats; do not synthesize weaker alternatives.
- Treat missing required evidence as an incompatible artifact, not an empty
  result.
- Keep an adapter interface such as `ShowcaseRepository` with `getManifest`,
  `getResearchSummary`, `listProfiles`, and `getProfile`. The static file
  implementation is v1; a later HTTP/API implementation must satisfy the same
  contract tests.

## AI evidence seam

The optional AI layer receives a subset of this contract, never direct data
frames or a free-form user-selected context. Its future evidence bundle will
contain profile keys, exact display values, evidence IDs, uncertainty states,
and mandatory caveat codes. Model output must reference those IDs and pass
deterministic validation. No AI field is required for the application or for
contract version 1.0.0.
