import Ajv2020, { type ValidateFunction } from "ajv/dist/2020";
import addFormats from "ajv-formats";

import schema from "@/contracts/generated/showcase.schema.json";
import type {
  FeatureCatalogArtifact,
  Manifest,
  PlayerIndexArtifact,
  PlayerIndexItem,
  PlayerProfileArtifact,
  ResearchSummaryArtifact,
  ScoutLensShowcaseArtifacts100,
} from "@/contracts/generated/showcase";

const SUPPORTED_SCHEMA_MAJOR = 1;
const DEFAULT_BASE_URL = "/showcase/v1/";

export type ShowcaseContractErrorCode =
  | "artifact_kind"
  | "byte_count_mismatch"
  | "checksum_mismatch"
  | "dataset_mismatch"
  | "http_error"
  | "invalid_json"
  | "missing_evidence"
  | "profile_mismatch"
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
  getManifest(): Promise<Manifest>;
  getFeatureCatalog(): Promise<FeatureCatalogArtifact>;
  getResearchSummary(): Promise<ResearchSummaryArtifact>;
  listProfiles(): Promise<ReadonlyArray<PlayerIndexItem>>;
  getProfile(profileKey: string): Promise<PlayerProfileArtifact>;
}

export type ShowcaseFetch = (input: string) => Promise<Response>;

interface AssetBytes {
  bytes: Uint8Array<ArrayBuffer>;
  text: string;
}

const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const validateArtifact: ValidateFunction<unknown> = ajv.compile(schema);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function assertSupportedMajor(value: unknown, artifactPath: string): void {
  if (!isRecord(value) || typeof value.schema_version !== "string") {
    return;
  }

  const major = Number.parseInt(value.schema_version.split(".")[0] ?? "", 10);
  if (!Number.isInteger(major) || major !== SUPPORTED_SCHEMA_MAJOR) {
    throw new ShowcaseContractError(
      "unsupported_schema_major",
      `Unsupported showcase schema major: ${value.schema_version}`,
      artifactPath,
    );
  }
}

function assertSchema(
  value: unknown,
  artifactPath: string,
): asserts value is ScoutLensShowcaseArtifacts100 {
  assertSupportedMajor(value, artifactPath);
  if (!validateArtifact(value)) {
    const details = ajv.errorsText(validateArtifact.errors, { separator: "; " });
    throw new ShowcaseContractError(
      "schema_validation",
      `Invalid showcase artifact ${artifactPath}: ${details}`,
      artifactPath,
    );
  }
}

function isManifest(value: ScoutLensShowcaseArtifacts100): value is Manifest {
  return "files" in value && "producer" in value;
}

function isResearchSummary(
  value: ScoutLensShowcaseArtifacts100,
): value is ResearchSummaryArtifact {
  return "experiments" in value && "supported_claim" in value;
}

function isFeatureCatalog(
  value: ScoutLensShowcaseArtifacts100,
): value is FeatureCatalogArtifact {
  return "features" in value && !('periods' in value);
}

function isPlayerIndex(value: ScoutLensShowcaseArtifacts100): value is PlayerIndexArtifact {
  return "profiles" in value;
}

function isPlayerProfile(value: ScoutLensShowcaseArtifacts100): value is PlayerProfileArtifact {
  return "profile_key" in value && "evidence_index" in value;
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
  artifact: ScoutLensShowcaseArtifacts100,
  manifest: Manifest,
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

function assertEvidence(profile: PlayerProfileArtifact, artifactPath: string): void {
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

export class StaticShowcaseRepository implements ShowcaseRepository {
  private readonly baseUrl: string;

  constructor(
    private readonly fetchAsset: ShowcaseFetch = (input) => fetch(input),
    baseUrl = DEFAULT_BASE_URL,
  ) {
    this.baseUrl = `${baseUrl.replace(/\/+$/, "")}/`;
  }

  async getManifest(): Promise<Manifest> {
    const artifactPath = "manifest.json";
    const artifact = this.parse(await this.read(artifactPath), artifactPath);
    assertSchema(artifact, artifactPath);
    if (!isManifest(artifact)) {
      throw new ShowcaseContractError("artifact_kind", "Expected a showcase manifest", artifactPath);
    }
    return artifact;
  }

  async getResearchSummary(): Promise<ResearchSummaryArtifact> {
    const manifest = await this.getManifest();
    const artifactPath = "research-summary.json";
    const artifact = await this.readVerified(artifactPath, manifest);
    if (!isResearchSummary(artifact)) {
      throw new ShowcaseContractError("artifact_kind", "Expected a research summary", artifactPath);
    }
    return artifact;
  }

  async getFeatureCatalog(): Promise<FeatureCatalogArtifact> {
    const manifest = await this.getManifest();
    const artifactPath = "feature-catalog.json";
    const artifact = await this.readVerified(artifactPath, manifest);
    if (!isFeatureCatalog(artifact)) {
      throw new ShowcaseContractError("artifact_kind", "Expected a feature catalog", artifactPath);
    }
    return artifact;
  }

  async listProfiles(): Promise<ReadonlyArray<PlayerIndexItem>> {
    const manifest = await this.getManifest();
    return (await this.getIndex(manifest)).profiles;
  }

  async getProfile(profileKey: string): Promise<PlayerProfileArtifact> {
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
    return artifact;
  }

  private async getIndex(manifest: Manifest): Promise<PlayerIndexArtifact> {
    const artifactPath = "players.index.json";
    const artifact = await this.readVerified(artifactPath, manifest);
    if (!isPlayerIndex(artifact)) {
      throw new ShowcaseContractError("artifact_kind", "Expected a player index", artifactPath);
    }
    return artifact;
  }

  private async readVerified(
    artifactPath: string,
    manifest: Manifest,
  ): Promise<ScoutLensShowcaseArtifacts100> {
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
    assertSchema(artifact, artifactPath);
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
