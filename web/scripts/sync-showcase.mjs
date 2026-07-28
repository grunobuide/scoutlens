import { cp, mkdir, readdir, rm } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const webRoot = resolve(scriptDirectory, "..");
const source = resolve(webRoot, "..", "public", "showcase", "v1");
const target = resolve(webRoot, "public", "showcase", "v1");
const required = ["feature-catalog.json", "manifest.json", "players.index.json", "research-summary.json"];

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

console.log(`Synced showcase assets to ${target}`);
