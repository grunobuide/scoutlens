import { readFile, readdir } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { FIXTURE_MARKERS, SYNTHETIC_PROFILE_KEYS } from "./fixture-pack.mjs";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const webRoot = resolve(scriptDirectory, "..");
const routes = ["index.html", "lab/index.html", "science/index.html"];
const landmarks = ["<header", "<nav", "<main", "<footer"];
const fixtureMarkers = [...FIXTURE_MARKERS, ...SYNTHETIC_PROFILE_KEYS];
const meaningfulStaticContent = {
  "index.html": [
    "A player leaves a reproducible fingerprint",
    "Critical confound",
    "StatsBomb Open Data",
    "Not supported",
  ],
  "science/index.html": [
    "The science is the sequence",
    "First chronological half",
    "Keep a useful correction out",
    "Audit the full provenance chain",
  ],
  "lab/index.html": [
    "Compare one player with himself.",
    "Complete eligible catalog",
    "Period A / B fingerprint",
    "Identity retrieval, one query at a time",
    "Five other period-B profiles",
    "All 32 measurements",
    "uncertainty pending",
  ],
};

for (const route of routes) {
  const html = await readFile(resolve(webRoot, "out", route), "utf8");
  for (const landmark of landmarks) {
    if (!html.includes(landmark)) {
      throw new Error(`${route} is missing semantic landmark ${landmark}`);
    }
  }
  if ((html.match(/<h1[ >]/g) ?? []).length !== 1) {
    throw new Error(`${route} must contain exactly one h1`);
  }
  for (const expected of meaningfulStaticContent[route] ?? []) {
    if (!html.includes(expected)) {
      throw new Error(`${route} is missing meaningful static content: ${expected}`);
    }
  }
  for (const forbidden of [
    "% match",
    "match percentage",
    "percentage match",
    "recommended replacement",
    "recruitment target",
  ]) {
    if (html.toLowerCase().includes(forbidden)) {
      throw new Error(`${route} contains forbidden recommendation wording: ${forbidden}`);
    }
  }
  for (const marker of fixtureMarkers) {
    if (html.includes(marker)) {
      throw new Error(`${route} contains test-only fixture identity: ${marker}`);
    }
  }
}

async function assertStaticOnly(directory) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) {
      await assertStaticOnly(path);
      continue;
    }
    if (/^route\.[cm]?[jt]sx?$/.test(entry.name)) {
      throw new Error(`Runtime route handler is not allowed: ${path}`);
    }
    if (/\.[jt]sx?$/.test(entry.name)) {
      const source = await readFile(path, "utf8");
      if (/^[\t ]*["']use server["'];?/m.test(source)) {
        throw new Error(`Server action is not allowed: ${path}`);
      }
    }
  }
}

await assertStaticOnly(resolve(webRoot, "src", "app"));
console.log("Static export contains all routes and semantic landmarks");
