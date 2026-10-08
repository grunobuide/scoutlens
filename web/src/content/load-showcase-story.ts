import { datasetCompetitions } from "@/content/provenance";
import { buildShowcaseStory } from "@/content/showcase-story";
import { createServerShowcaseRepository } from "@/content/showcase-server";

export async function loadShowcaseStory() {
  const repository = createServerShowcaseRepository();
  const [manifest, research, catalog, profiles] = await Promise.all([
    repository.getManifest(),
    repository.getResearchSummary(),
    repository.getFeatureCatalog(),
    repository.listProfiles(),
  ]);
  const featuredProfile = await repository.getProfile(manifest.featured_profile.profile_key);
  return {
    ...buildShowcaseStory(manifest, research, featuredProfile, catalog),
    // `scoutlens-9a3.33`: which leagues, read at build time from the published
    // index. Server-side only - the pages are static, so this costs no client
    // JavaScript.
    competitions: datasetCompetitions(manifest.population.domestic_competition_ids, profiles),
  };
}
