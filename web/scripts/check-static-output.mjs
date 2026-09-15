import { readFile, readdir } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { FIXTURE_MARKERS, SYNTHETIC_PROFILE_KEYS } from "./fixture-pack.mjs";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const webRoot = resolve(scriptDirectory, "..");
const routes = ["index.html", "lab/index.html", "science/index.html"];
const landmarks = ["<header", "<nav", "<main", "<footer"];
const fixtureMarkers = [...FIXTURE_MARKERS, ...SYNTHETIC_PROFILE_KEYS];
const provenanceMarkers = ["Historical reproducible benchmark", "What these numbers describe"];
const meaningfulStaticContent = {
  "index.html": [
    "A player leaves a reproducible fingerprint",
    "Critical confound",
    "StatsBomb Open Data",
    "Not supported",
  ],
  "science/index.html": [
    "The science is the sequence",
    "How we measure retrieval: MRR",
    "One player, two halves, one retrieval result",
    "Every rank travels with its resampled interval",
    "What the system is",
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
    "sampling stability available",
  ],
};

// `scoutlens-9a3.7` AC5: forbidden-copy and currentness assertions over all
// public text.
//
// The published major, resolved the same way `check-budgets.mjs` does it - the
// payload pin is the single source, overridable for fixture builds.
const pinnedMajor = JSON.parse(
  await readFile(resolve(webRoot, "..", "config", "showcase-payload-pack.json"), "utf8"),
).schema_version.split(".")[0];
const showcaseMajor = Number(process.env.NEXT_PUBLIC_SCOUTLENS_SHOWCASE_MAJOR ?? pinnedMajor);
if (showcaseMajor !== 1 && showcaseMajor !== 2) {
  throw new Error(`NEXT_PUBLIC_SCOUTLENS_SHOWCASE_MAJOR must be 1 or 2, got ${showcaseMajor}`);
}

/**
 * The three claim boundaries, read from the artifact the build shipped.
 *
 * These are the *enumerated exception* AC5 requires, and they are derived
 * rather than hardcoded on purpose. The site states each forbidden claim
 * verbatim in order to disclaim it: `ClaimsMatrix` renders "Statistical
 * similarity proves playing style." under a "Where the evidence stops" heading.
 * So a substring ban on the assertive phrasing fires on the disclaimer that
 * exists to prevent it - the check would forbid the site from saying what it
 * must say.
 *
 * Sourcing the exception from `unsupported_claims` means it cannot drift:
 * reword a boundary and the exception follows it in the same build. Hardcoding
 * the sentences here would leave a stale waiver excusing text nobody publishes.
 */
const unsupportedClaims = JSON.parse(
  await readFile(
    resolve(webRoot, "out", "showcase", `v${showcaseMajor}`, "research-summary.json"),
    "utf8",
  ),
).unsupported_claims;

if (!Array.isArray(unsupportedClaims) || unsupportedClaims.length === 0) {
  throw new Error("research-summary.json published no unsupported_claims to except");
}

/**
 * Assertive phrasings of what the project may never claim, banned outside the
 * disclaimer sentences above.
 *
 * Each is the *affirmative* form. The negated forms the site does use - "not
 * proof of playing style", "it does not measure player quality, tactical fit or
 * recruitment value", "not a scouting model" - do not contain these substrings,
 * which is why the list is phrased this way rather than banning the topic
 * words. Banning "playing style" or "recruitment" outright would flag the
 * caveats, and a check that fights the caveats teaches people to delete them.
 */
const forbiddenClaims = [
  "proves playing style",
  "proven playing style",
  "similar playing style",
  "same playing style",
  "should sign",
  "should recruit",
  "recommended signing",
  "recommended transfer",
  "ideal replacement",
  "best replacement",
  "predicts transfer success",
  "predicts future performance",
];

/**
 * Wording that would tell a reader the data is live.
 *
 * Q1 of `docs/public-understanding-check.md` blocks the gate if a reviewer
 * believes the data is current, and this is the machine-checkable half of that.
 * Every entry currently has zero occurrences across all three routes; they are
 * here to catch a future copy change, not to describe today's text. Note the
 * site legitimately writes "no live database", "no live LLM is required for any
 * current page" and "it is not current scouting information" - none of which
 * contain these phrases, which is why they are this specific.
 *
 * Matched on a trailing word boundary, not as a bare substring. The first run
 * of this check failed on `/science/` because "no live database" contains
 * "live data", and the sentence it flagged is the site correctly saying it has
 * no live database. A ban that fires on the disclaimer is worse than no ban:
 * the cheapest way to make it pass is to delete the reassurance.
 */
const forbiddenCurrentness = [
  "real-time",
  "real time data",
  "live data",
  "up to date",
  "up-to-date",
  "current season",
  "this season's",
  "latest data",
  "latest season",
  "continuously updated",
  "updated daily",
  "updated weekly",
  "updated automatically",
];

/** The positive half: every public route must say the data is historical. */
const currentnessDisclaimers = ["not current scouting information"];

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
  for (const marker of provenanceMarkers) {
    if (!html.includes(marker)) {
      throw new Error(`${route} is missing provenance presentation: ${marker}`);
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

  // Everything below scans the route with the published claim boundaries
  // removed, so the disclaimers cannot satisfy - or trip - a ban on the thing
  // they disclaim. Removal is by exact string: the boundaries render inside a
  // single element, so they survive as contiguous text in the HTML.
  let scannable = html;
  for (const claim of unsupportedClaims) {
    scannable = scannable.split(claim).join(" ");
  }
  scannable = scannable.toLowerCase();

  for (const forbidden of forbiddenClaims) {
    if (scannable.includes(forbidden)) {
      throw new Error(
        `${route} asserts a claim the project does not support: ${forbidden}. ` +
          `If this is inside a published claim boundary, it belongs in ` +
          `research-summary.json's unsupported_claims, not in template copy.`,
      );
    }
  }

  for (const forbidden of forbiddenCurrentness) {
    const pattern = new RegExp(`${forbidden.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`);
    if (pattern.test(scannable)) {
      throw new Error(
        `${route} implies the data is current: ${forbidden}. ` +
          `The dataset is a frozen historical season; see docs/public-understanding-check.md Q1.`,
      );
    }
  }

  for (const disclaimer of currentnessDisclaimers) {
    if (!html.toLowerCase().includes(disclaimer)) {
      throw new Error(`${route} is missing its currentness disclaimer: ${disclaimer}`);
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
