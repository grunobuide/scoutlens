import { readFile } from "node:fs/promises";
import { resolve, sep } from "node:path";

import { StaticShowcaseRepository, type ShowcaseFetch } from "@/contracts/showcase-repository";
import { buildShowcaseStory } from "@/content/showcase-story";

const publicAssetRoot = resolve(process.cwd(), "public", "showcase", "v1");
const publicUrlPrefix = "/showcase/v1/";

const readPublicAsset: ShowcaseFetch = async (input) => {
  if (!input.startsWith(publicUrlPrefix)) {
    return new Response(null, { status: 404 });
  }

  const relativePath = input.slice(publicUrlPrefix.length).replaceAll("/", sep);
  const assetPath = resolve(publicAssetRoot, relativePath);
  if (!assetPath.startsWith(`${publicAssetRoot}${sep}`)) {
    return new Response(null, { status: 400 });
  }

  try {
    const bytes = await readFile(assetPath);
    const body = new Uint8Array(bytes).buffer;
    return new Response(body, { status: 200 });
  } catch {
    return new Response(null, { status: 404 });
  }
};

export async function loadShowcaseStory() {
  const repository = new StaticShowcaseRepository(readPublicAsset);
  const [manifest, research, catalog] = await Promise.all([
    repository.getManifest(),
    repository.getResearchSummary(),
    repository.getFeatureCatalog(),
  ]);
  const featuredProfile = await repository.getProfile(manifest.featured_profile.profile_key);
  return buildShowcaseStory(manifest, research, featuredProfile, catalog);
}
