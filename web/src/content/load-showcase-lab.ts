import type {
  AnyFeatureCatalogArtifact,
  AnyPlayerIndexItem,
  AnyPlayerProfileArtifact,
  ShowcaseMajor,
} from "@/contracts/showcase-repository";
import { describeLabError, type LabProblem } from "@/content/showcase-lab";
import { createServerShowcaseRepository } from "@/content/showcase-server";

export interface ReadyShowcaseLabData {
  status: "ready";
  datasetVersion: string;
  /** The contract major this page was built against. Presentation reads the
   * score field and the method disclosure from it rather than sniffing which
   * key happens to be present. */
  major: ShowcaseMajor;
  catalog: AnyFeatureCatalogArtifact;
  profiles: ReadonlyArray<AnyPlayerIndexItem>;
  initialProfile: AnyPlayerProfileArtifact;
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
      major: repository.major,
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
