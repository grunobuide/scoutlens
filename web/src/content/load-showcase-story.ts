import { buildShowcaseStory } from "@/content/showcase-story";
import { createServerShowcaseRepository } from "@/content/showcase-server";

export async function loadShowcaseStory() {
  const repository = createServerShowcaseRepository();
  const [manifest, research, catalog] = await Promise.all([
    repository.getManifest(),
    repository.getResearchSummary(),
    repository.getFeatureCatalog(),
  ]);
  const featuredProfile = await repository.getProfile(manifest.featured_profile.profile_key);
  return buildShowcaseStory(manifest, research, featuredProfile, catalog);
}
