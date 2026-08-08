import { readFile } from "node:fs/promises";
import { resolve, sep } from "node:path";

import { StaticShowcaseRepository, type ShowcaseFetch } from "@/contracts/showcase-repository";

// The published pack is the default. SCOUTLENS_SHOWCASE_ROOT is a build-time
// only override used by the delegated test-only fixture export
// (scoutlens-uze.7): with the variable unset the production `pnpm build`
// resolves the identical root and ships no fixture data or code path.
const publicAssetRoot = resolve(
  process.cwd(),
  process.env.SCOUTLENS_SHOWCASE_ROOT ?? "public/showcase/v1",
);
const publicUrlPrefix = "/showcase/v1/";

export const readPublicShowcaseAsset: ShowcaseFetch = async (input) => {
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
    return new Response(new Uint8Array(bytes).buffer, { status: 200 });
  } catch {
    return new Response(null, { status: 404 });
  }
};

export function createServerShowcaseRepository(): StaticShowcaseRepository {
  return new StaticShowcaseRepository(readPublicShowcaseAsset);
}
