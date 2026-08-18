import Ajv2020, { type ValidateFunction } from "ajv/dist/2020";
import addFormats from "ajv-formats";

import schemaV1 from "@/contracts/generated/showcase.schema.json";
import schemaV2 from "@/contracts/generated/showcase-v2.schema.json";
import type {
  FeatureCatalogArtifact,
  Manifest,
  PlayerIndexArtifact,
  PlayerIndexItem,
  PlayerProfileArtifact,
  ResearchSummaryArtifact,
  ScoutLensShowcaseArtifacts100,
} from "@/contracts/generated/showcase";
import type {
  FeatureCatalogArtifact as FeatureCatalogArtifactV2,
  Manifest as ManifestV2,
  PlayerIndexArtifact as PlayerIndexArtifactV2,
  PlayerIndexItem as PlayerIndexItemV2,
  PlayerProfileArtifact as PlayerProfileArtifactV2,
  RepresentationArtifact as RepresentationArtifactV2,
  ResearchSummaryArtifact as ResearchSummaryArtifactV2,
  ScoutLensShowcaseArtifacts200,
} from "@/contracts/generated/showcase-v2";

/** Known contract majors. An unknown major fails closed rather than falling
 * back to the newest schema: silently validating a future payload against
 * today's rules reports success for something this consumer does not
 * understand (D047). */
export const SUPPORTED_SCHEMA_MAJORS = [1, 2] as const;
export type ShowcaseMajor = (typeof SUPPORTED_SCHEMA_MAJORS)[number];

/** The major the deployed site serves.
 *
 * 2 since `scoutlens-qop.6.6.2` repinned `config/showcase-payload-pack.json` to
 * the v2 payload. The constant and the pin have to move together: a clean clone
 * hydrates whatever the pin names, so serving the other major means serving a
 * manifest whose profiles nobody can fetch. That is exactly what broke CI
 * between the repin and this flip.
 *
 * Rolling back is the same pair in reverse - restore the previous pin and set
 * this to 1. Major 1 stays fully supported either way; it is simply not the one
 * being served. */
const DEPLOYED_SHOWCASE_MAJOR: ShowcaseMajor = 2;

export function isSupportedMajor(value: number): value is ShowcaseMajor {
  return (SUPPORTED_SCHEMA_MAJORS as ReadonlyArray<number>).includes(value);
}

function resolveActiveMajor(): ShowcaseMajor {
  const raw = process.env.NEXT_PUBLIC_SCOUTLENS_SHOWCASE_MAJOR;
  if (raw === undefined || raw === "") {
    return DEPLOYED_SHOWCASE_MAJOR;
  }
  const parsed = Number.parseInt(raw, 10);
  if (!isSupportedMajor(parsed)) {
    throw new Error(
      `NEXT_PUBLIC_SCOUTLENS_SHOWCASE_MAJOR must be one of ${SUPPORTED_SCHEMA_MAJORS.join(", ")}, got ${raw}`,
    );
  }
  return parsed;
}

/** The major this build loads. Resolved once, at module load, so the served
 * assets and the validating schema can never disagree. */
export const ACTIVE_SHOWCASE_MAJOR: ShowcaseMajor = resolveActiveMajor();

export function showcaseBaseUrl(major: ShowcaseMajor = ACTIVE_SHOWCASE_MAJOR): string {
  return `/showcase/v${major}/`;
}

const DEFAULT_BASE_URL = showcaseBaseUrl();

export type ShowcaseArtifact = ScoutLensShowcaseArtifacts100 | ScoutLensShowcaseArtifacts200;
export type AnyManifest = Manifest | ManifestV2;
export type AnyFeatureCatalogArtifact = FeatureCatalogArtifact | FeatureCatalogArtifactV2;
export type AnyPlayerIndexArtifact = PlayerIndexArtifact | PlayerIndexArtifactV2;
export type AnyPlayerIndexItem = PlayerIndexItem | PlayerIndexItemV2;
export type AnyPlayerProfileArtifact = PlayerProfileArtifact | PlayerProfileArtifactV2;
export type AnyResearchSummaryArtifact = ResearchSummaryArtifact | ResearchSummaryArtifactV2;

export type ShowcaseContractErrorCode =
  | "artifact_kind"
  | "byte_count_mismatch"
  | "checksum_mismatch"
  | "dataset_mismatch"
  | "http_error"
  | "invalid_json"
  | "missing_evidence"
  | "profile_mismatch"
  | "representation_mismatch"
  | "schema_validation"
  | "unsafe_path"
  | "unsupported_schema_major";

export class ShowcaseContractError extends Error {
  constructor(
    readonly code: ShowcaseContractErrorCode,
    message: string,
    readonly artifactPath: string,
  ) {
    super(message);
    this.name = "ShowcaseContractError";
  }
}

export interface ShowcaseRepository {
  readonly major: ShowcaseMajor;
  getManifest(): Promise<AnyManifest>;
  getFeatureCatalog(): Promise<AnyFeatureCatalogArtifact>;
  getResearchSummary(): Promise<AnyResearchSummaryArtifact>;
  listProfiles(): Promise<ReadonlyArray<AnyPlayerIndexItem>>;
  getProfile(profileKey: string): Promise<AnyPlayerProfileArtifact>;
  /** The published representation, or `null` for major 1, which has none. */
  getRepresentation(): Promise<RepresentationArtifactV2 | null>;
}

export type ShowcaseFetch = (input: string) => Promise<Response>;

interface AssetBytes {
  bytes: Uint8Array<ArrayBuffer>;
  text: string;
}

const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const validatorByMajor: Record<ShowcaseMajor, ValidateFunction<unknown>> = {
  1: ajv.compile(schemaV1),
  2: ajv.compile(schemaV2),
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function assertDeclaredMajor(
  value: unknown,
  expected: ShowcaseMajor,
  artifactPath: string,
): void {
  if (!isRecord(value) || typeof value.schema_version !== "string") {
    return;
  }

  const major = Number.parseInt(value.schema_version.split(".")[0] ?? "", 10);
  if (!Number.isInteger(major) || !isSupportedMajor(major)) {
    throw new ShowcaseContractError(
      "unsupported_schema_major",
      `Unsupported showcase schema major: ${value.schema_version}`,
      artifactPath,
    );
  }
  // A known-but-different major is refused too. A dataset that mixes majors is
  // not a partially valid dataset; validating one of its artifacts against the
  // other's rules is how a diagonal payload gets read as cosine.
  if (major !== expected) {
    throw new ShowcaseContractError(
      "unsupported_schema_major",
      `${artifactPath} declares major ${major}, but this dataset is major ${expected}`,
      artifactPath,
    );
  }
}

function assertSchema(
  value: unknown,
  artifactPath: string,
  major: ShowcaseMajor,
): asserts value is ShowcaseArtifact {
  assertDeclaredMajor(value, major, artifactPath);
  const validate = validatorByMajor[major];
  if (!validate(value)) {
    const details = ajv.errorsText(validate.errors, { separator: "; " });
    throw new ShowcaseContractError(
      "schema_validation",
      `Invalid showcase artifact ${artifactPath}: ${details}`,
      artifactPath,
    );
  }
}

function isManifest(value: ShowcaseArtifact): value is AnyManifest {
  return "files" in value && "producer" in value;
}

function isResearchSummary(value: ShowcaseArtifact): value is AnyResearchSummaryArtifact {
  return "experiments" in value && "supported_claim" in value;
}

function isFeatureCatalog(value: ShowcaseArtifact): value is AnyFeatureCatalogArtifact {
  return "features" in value && !("periods" in value);
}

function isPlayerIndex(value: ShowcaseArtifact): value is AnyPlayerIndexArtifact {
  return "profiles" in value;
}

function isPlayerProfile(value: ShowcaseArtifact): value is AnyPlayerProfileArtifact {
  return "profile_key" in value && "evidence_index" in value;
}

function isRepresentation(value: ShowcaseArtifact): value is RepresentationArtifactV2 {
  return "representation" in value;
}

/** Every `representation_id` anywhere in an artifact, with the path it sat at.
 *
 * Walked rather than read from a fixed list of fields: the binding rule is
 * "every ranking-bearing block names the representation", and a rule enforced
 * only at the places someone remembered is not the rule. */
function collectRepresentationIds(
  value: unknown,
  found: Array<{ path: string; id: unknown }>,
  path = "",
): void {
  if (Array.isArray(value)) {
    value.forEach((item, index) => collectRepresentationIds(item, found, `${path}[${index}]`));
    return;
  }
  if (!isRecord(value)) {
    return;
  }
  for (const [key, child] of Object.entries(value)) {
    const childPath = path === "" ? key : `${path}.${key}`;
    if (key === "representation_id") {
      found.push({ path: childPath, id: child });
    } else {
      collectRepresentationIds(child, found, childPath);
    }
  }
}

function collectUncertaintyDesigns(value: unknown, found: Array<{ path: string; design: unknown }>, path = ""): void {
  if (Array.isArray(value)) {
    value.forEach((item, index) => collectUncertaintyDesigns(item, found, `${path}[${index}]`));
    return;
  }
  if (!isRecord(value)) {
    return;
  }
  for (const [key, child] of Object.entries(value)) {
    const childPath = path === "" ? key : `${path}.${key}`;
    if (key === "design_version") {
      found.push({ path: childPath, design: child });
    } else {
      collectUncertaintyDesigns(child, found, childPath);
    }
  }
}

function assertSafePath(path: string): void {
  const segments = path.replaceAll("\\", "/").split("/");
  if (
    path.startsWith("/") ||
    path.includes("\\") ||
    segments.some((segment) => segment === "" || segment === "." || segment === "..") ||
    !path.endsWith(".json")
  ) {
    throw new ShowcaseContractError("unsafe_path", `Unsafe showcase asset path: ${path}`, path);
  }
}

function toHex(bytes: ArrayBuffer): string {
  return Array.from(new Uint8Array(bytes), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function sha256(bytes: Uint8Array<ArrayBuffer>): Promise<string> {
  return toHex(await globalThis.crypto.subtle.digest("SHA-256", bytes));
}

function assertDatasetVersion(
  artifact: ShowcaseArtifact,
  manifest: AnyManifest,
  artifactPath: string,
): void {
  if (artifact.dataset_version !== manifest.dataset_version) {
    throw new ShowcaseContractError(
      "dataset_mismatch",
      `${artifactPath} belongs to ${artifact.dataset_version}, expected ${manifest.dataset_version}`,
      artifactPath,
    );
  }
}

function assertEvidence(profile: AnyPlayerProfileArtifact, artifactPath: string): void {
  const evidenceIds = new Set(profile.evidence_index.map((item) => item.evidence_id));
  if (evidenceIds.size !== profile.evidence_index.length) {
    throw new ShowcaseContractError(
      "missing_evidence",
      `${artifactPath} contains duplicate evidence identifiers`,
      artifactPath,
    );
  }

  const references = [
    ...profile.retrieval.global.evidence_refs,
    ...profile.retrieval.within_role.evidence_refs,
    ...profile.retrieval.baseline_role_minutes.evidence_refs,
    ...profile.neighbors.flatMap((neighbor) => neighbor.evidence_refs),
    ...profile.caveats.flatMap((caveat) => caveat.evidence_refs),
  ];
  const missing = [...new Set(references.filter((reference) => !evidenceIds.has(reference)))];
  if (missing.length > 0) {
    throw new ShowcaseContractError(
      "missing_evidence",
      `${artifactPath} has unresolved evidence references: ${missing.slice(0, 3).join(", ")}`,
      artifactPath,
    );
  }
}

export const REPRESENTATION_PATH = "representation.json";
const V2_UNCERTAINTY_DESIGN = "match_bootstrap_diagonal_v1";

export class StaticShowcaseRepository implements ShowcaseRepository {
  private readonly baseUrl: string;
  readonly major: ShowcaseMajor;

  constructor(
    private readonly fetchAsset: ShowcaseFetch = (input) => fetch(input),
    baseUrl = DEFAULT_BASE_URL,
    major: ShowcaseMajor = ACTIVE_SHOWCASE_MAJOR,
  ) {
    this.baseUrl = `${baseUrl.replace(/\/+$/, "")}/`;
    this.major = major;
  }

  async getManifest(): Promise<AnyManifest> {
    const artifactPath = "manifest.json";
    const artifact = this.parse(await this.read(artifactPath), artifactPath);
    assertSchema(artifact, artifactPath, this.major);
    if (!isManifest(artifact)) {
      throw new ShowcaseContractError("artifact_kind", "Expected a showcase manifest", artifactPath);
    }
    if (this.major === 2 && typeof (artifact as ManifestV2).representation_id !== "string") {
      throw new ShowcaseContractError(
        "representation_mismatch",
        "A v2 manifest must name the representation that produced its rankings",
        artifactPath,
      );
    }
    return artifact;
  }

  async getRepresentation(): Promise<RepresentationArtifactV2 | null> {
    if (this.major !== 2) {
      return null;
    }
    const manifest = await this.getManifest();
    const artifact = await this.readVerified(REPRESENTATION_PATH, manifest);
    if (!isRepresentation(artifact)) {
      throw new ShowcaseContractError(
        "artifact_kind",
        "Expected a representation artifact",
        REPRESENTATION_PATH,
      );
    }
    const declared = (manifest as ManifestV2).representation_id;
    if (artifact.representation.id !== declared) {
      throw new ShowcaseContractError(
        "representation_mismatch",
        `${REPRESENTATION_PATH} publishes ${artifact.representation.id}, but the manifest names ${declared}`,
        REPRESENTATION_PATH,
      );
    }
    return artifact;
  }

  async getResearchSummary(): Promise<AnyResearchSummaryArtifact> {
    const manifest = await this.getManifest();
    const artifactPath = "research-summary.json";
    const artifact = await this.readVerified(artifactPath, manifest);
    if (!isResearchSummary(artifact)) {
      throw new ShowcaseContractError("artifact_kind", "Expected a research summary", artifactPath);
    }
    return artifact;
  }

  async getFeatureCatalog(): Promise<AnyFeatureCatalogArtifact> {
    const manifest = await this.getManifest();
    const artifactPath = "feature-catalog.json";
    const artifact = await this.readVerified(artifactPath, manifest);
    if (!isFeatureCatalog(artifact)) {
      throw new ShowcaseContractError("artifact_kind", "Expected a feature catalog", artifactPath);
    }
    return artifact;
  }

  async listProfiles(): Promise<ReadonlyArray<AnyPlayerIndexItem>> {
    const manifest = await this.getManifest();
    return (await this.getIndex(manifest)).profiles;
  }

  async getProfile(profileKey: string): Promise<AnyPlayerProfileArtifact> {
    const manifest = await this.getManifest();
    const index = await this.getIndex(manifest);
    const item = index.profiles.find((candidate) => candidate.profile_key === profileKey);
    if (item === undefined) {
      throw new ShowcaseContractError(
        "profile_mismatch",
        `Profile is absent from the active index: ${profileKey}`,
        "players.index.json",
      );
    }

    assertSafePath(item.artifact_path);
    const artifact = await this.readVerified(item.artifact_path, manifest);
    if (!isPlayerProfile(artifact)) {
      throw new ShowcaseContractError(
        "artifact_kind",
        "Expected a player profile",
        item.artifact_path,
      );
    }
    if (artifact.profile_key !== profileKey || artifact.identity.player_key !== item.player_key) {
      throw new ShowcaseContractError(
        "profile_mismatch",
        `${item.artifact_path} does not match its index entry`,
        item.artifact_path,
      );
    }
    assertEvidence(artifact, item.artifact_path);
    if (this.major === 2) {
      assertRepresentationBinding(
        artifact,
        (manifest as ManifestV2).representation_id,
        item.artifact_path,
      );
    }
    return artifact;
  }

  private async getIndex(manifest: AnyManifest): Promise<AnyPlayerIndexArtifact> {
    const artifactPath = "players.index.json";
    const artifact = await this.readVerified(artifactPath, manifest);
    if (!isPlayerIndex(artifact)) {
      throw new ShowcaseContractError("artifact_kind", "Expected a player index", artifactPath);
    }
    return artifact;
  }

  private async readVerified(
    artifactPath: string,
    manifest: AnyManifest,
  ): Promise<ShowcaseArtifact> {
    assertSafePath(artifactPath);
    const expected = manifest.files.find((file) => file.path === artifactPath);
    if (expected === undefined) {
      throw new ShowcaseContractError(
        "checksum_mismatch",
        `${artifactPath} is not declared by the active manifest`,
        artifactPath,
      );
    }

    const asset = await this.read(artifactPath);
    if (asset.bytes.byteLength !== expected.bytes) {
      throw new ShowcaseContractError(
        "byte_count_mismatch",
        `${artifactPath} has ${asset.bytes.byteLength} bytes, expected ${expected.bytes}`,
        artifactPath,
      );
    }
    const digest = await sha256(asset.bytes);
    if (digest !== expected.sha256) {
      throw new ShowcaseContractError(
        "checksum_mismatch",
        `${artifactPath} checksum ${digest} does not match ${expected.sha256}`,
        artifactPath,
      );
    }

    const artifact = this.parse(asset, artifactPath);
    assertSchema(artifact, artifactPath, this.major);
    assertDatasetVersion(artifact, manifest, artifactPath);
    return artifact;
  }

  private async read(artifactPath: string): Promise<AssetBytes> {
    const response = await this.fetchAsset(`${this.baseUrl}${artifactPath}`);
    if (!response.ok) {
      throw new ShowcaseContractError(
        "http_error",
        `Unable to load ${artifactPath}: HTTP ${response.status}`,
        artifactPath,
      );
    }
    const buffer = await response.arrayBuffer();
    const bytes = new Uint8Array(buffer);
    return { bytes, text: new TextDecoder("utf-8", { fatal: true }).decode(bytes) };
  }

  private parse(asset: AssetBytes, artifactPath: string): unknown {
    try {
      return JSON.parse(asset.text);
    } catch (error) {
      throw new ShowcaseContractError(
        "invalid_json",
        `Unable to parse ${artifactPath}: ${error instanceof Error ? error.message : "invalid JSON"}`,
        artifactPath,
      );
    }
  }
}

/** Every representation reference and uncertainty design in a v2 profile must
 * agree with the dataset.
 *
 * A mismatch is refused rather than downgraded. A v1 interval attached to a
 * diagonal ranking would show a number describing the sampling stability of a
 * different metric, which is the trap D047 named explicitly; a foreign
 * representation id means the block was produced by something other than what
 * the dataset publishes. Neither is a weaker v2 payload - neither is a v2
 * payload. */
function assertRepresentationBinding(
  profile: AnyPlayerProfileArtifact,
  expected: string,
  artifactPath: string,
): void {
  const references: Array<{ path: string; id: unknown }> = [];
  collectRepresentationIds(profile, references);
  if (references.length === 0) {
    throw new ShowcaseContractError(
      "representation_mismatch",
      `${artifactPath} publishes rankings without naming a representation`,
      artifactPath,
    );
  }
  const foreign = references.find((reference) => reference.id !== expected);
  if (foreign !== undefined) {
    throw new ShowcaseContractError(
      "representation_mismatch",
      `${artifactPath}: ${foreign.path} names ${String(foreign.id)}, expected ${expected}`,
      artifactPath,
    );
  }

  const designs: Array<{ path: string; design: unknown }> = [];
  collectUncertaintyDesigns(profile, designs);
  const wrong = designs.find(
    (entry) => entry.design !== null && entry.design !== V2_UNCERTAINTY_DESIGN,
  );
  if (wrong !== undefined) {
    throw new ShowcaseContractError(
      "representation_mismatch",
      `${artifactPath}: ${wrong.path} carries uncertainty design ${String(wrong.design)}, ` +
        `expected ${V2_UNCERTAINTY_DESIGN}`,
      artifactPath,
    );
  }
}
