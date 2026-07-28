import type {
  FeatureCatalogArtifact,
  PlayerIndexItem,
  PlayerProfileArtifact,
} from "@/contracts/generated/showcase";
import { describeLabError, type LabProblem } from "@/content/showcase-lab";
import { createServerShowcaseRepository } from "@/content/showcase-server";

export interface ReadyShowcaseLabData {
  status: "ready";
  datasetVersion: string;
  catalog: FeatureCatalogArtifact;
  profiles: ReadonlyArray<PlayerIndexItem>;
  initialProfile: PlayerProfileArtifact;
}

export interface FailedShowcaseLabData {
  status: "error";
  datasetVersion: string | null;
  problem: LabProblem;
}

export type ShowcaseLabData = ReadyShowcaseLabData | FailedShowcaseLabData;

export async function loadShowcaseLab(): Promise<ShowcaseLabData> {
  const repository = createServerShowcaseRepository();
  let datasetVersion: string | null = null;

  try {
    const manifest = await repository.getManifest();
    datasetVersion = manifest.dataset_version;
    const [catalog, profiles, initialProfile] = await Promise.all([
      repository.getFeatureCatalog(),
      repository.listProfiles(),
      repository.getProfile(manifest.featured_profile.profile_key),
    ]);
    return {
      status: "ready",
      datasetVersion,
      catalog,
      profiles,
      initialProfile,
    };
  } catch (error) {
    return {
      status: "error",
      datasetVersion,
      problem: describeLabError(error),
    };
  }
}
