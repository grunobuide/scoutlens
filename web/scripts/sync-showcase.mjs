import { cp, mkdir, readdir, rm } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const webRoot = resolve(scriptDirectory, "..");

// Which major the build serves. Kept in step with DEPLOYED_SHOWCASE_MAJOR in
// src/contracts/showcase-repository.ts through one environment variable, so the
// bytes on disk and the schema they are validated against cannot disagree.
// scoutlens-qop.6.6 repins the payload and moves both together.
const major = Number(process.env.NEXT_PUBLIC_SCOUTLENS_SHOWCASE_MAJOR ?? "1");
if (major !== 1 && major !== 2) {
  throw new Error(`NEXT_PUBLIC_SCOUTLENS_SHOWCASE_MAJOR must be 1 or 2, got ${major}`);
}

const source = resolve(webRoot, "..", "public", "showcase", `v${major}`);
const target = resolve(webRoot, "public", "showcase", `v${major}`);
const required = [
  "feature-catalog.json",
  "manifest.json",
  "players.index.json",
  "research-summary.json",
  // v2 must ship the representation: a bundle whose rankings cannot be traced
  // to the metric that produced them is not publishable (D047).
  ...(major === 2 ? ["representation.json"] : []),
];

// Remove every other major before writing this one. The script used to clear
// only its own target, so a tree synced for v1 and then for v2 kept both and
// the static export shipped two complete player sets - roughly 380 MB for a
// site that serves one. Only the major being served may exist on disk.
const showcaseRoot = resolve(webRoot, "public", "showcase");
await mkdir(showcaseRoot, { recursive: true });
for (const entry of await readdir(showcaseRoot)) {
  if (entry !== `v${major}`) {
    await rm(resolve(showcaseRoot, entry), { recursive: true, force: true });
  }
}

await rm(target, { recursive: true, force: true });
await mkdir(target, { recursive: true });
const available = new Set(await readdir(source));
for (const filename of required) {
  if (!available.has(filename)) {
    throw new Error(`Missing versioned showcase artifact: ${filename}`);
  }
  await cp(resolve(source, filename), resolve(target, filename));
}

if (available.has("players")) {
  await cp(resolve(source, "players"), resolve(target, "players"), { recursive: true });
}

console.log(`Synced showcase v${major} assets to ${target}`);
