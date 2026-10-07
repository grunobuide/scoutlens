import { readFile, readdir } from "node:fs/promises";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { FIXTURE_MARKERS, SYNTHETIC_PROFILE_KEYS } from "./fixture-pack.mjs";
import { findFixtureTraces } from "./fixture-traces.mjs";

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

// `scoutlens-uze.29`: the route HTML above is three of the export's files. A
// fixture identity or code path in any other - a JS chunk, an RSC payload, a
// showcase JSON - would have shipped unseen, so the whole tree is scanned.
{
  const { traces, scanned } = await findFixtureTraces(resolve(webRoot, "out"));
  if (scanned < 100) {
    throw new Error(`fixture-trace scan read only ${scanned} files; out/ is incomplete`);
  }
  if (traces.length > 0) {
    throw new Error(
      `the production export carries test-only fixture traces:\n` +
        traces.map(({ file, trace }) => `  ${file}: ${trace}`).join("\n"),
    );
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

/**
 * RSC segment-prefetch payloads must be flat files, not nested directories
 * (`scoutlens-uze.17`).
 *
 * The client router always requests the flat, dot-separated name — for example
 * `/lab/__next.lab.__PAGE__.txt`. The exporter builds that name by replacing
 * path separators with dots, but on Windows `path.relative()` returns
 * backslashes and only forward slashes are replaced. The leftover backslashes
 * are then read as directory separators, so the file lands at
 * `/lab/__next.lab/__PAGE__.txt` and every prefetch 404s.
 *
 * Upstream: vercel/next.js#85374, with #92339 closed as its duplicate. PR
 * #99058 normalises the separators; at Next 16.2.12 it is still open against
 * `canary`, so there is no fixed version to pin to.
 *
 * **Production is not affected**, because CI builds on Linux, where the
 * separator is already a forward slash. Verified against the deployed site:
 * `/lab/__next.lab.__PAGE__.txt` and `/science/__next.science.__PAGE__.txt`
 * both return 200.
 *
 * Hence the asymmetry below, which is deliberate. On Linux and macOS a nested
 * segment directory would be a real regression and fails the build. On Windows
 * it is the known upstream bug and only warns — failing there would make
 * `pnpm build` red for every Windows contributor over a defect that cannot
 * reach production and that this project cannot fix. The warning exists so a
 * developer who opens devtools finds the explanation instead of hunting a
 * phantom.
 */
async function assertSegmentPayloadsAreFlat(directory) {
  const nested = [];
  async function walk(current) {
    for (const entry of await readdir(current, { withFileTypes: true })) {
      if (!entry.isDirectory()) continue;
      const path = join(current, entry.name);
      if (entry.name.startsWith("__next.")) {
        nested.push(relative(directory, path).replaceAll("\\", "/"));
        continue;
      }
      await walk(path);
    }
  }
  await walk(directory);

  if (nested.length === 0) return;

  const detail =
    `${nested.length} RSC segment payload(s) were written as directories instead of ` +
    `flat files: ${nested.join(", ")}. The client requests the flat dot-separated ` +
    `name, so each one 404s. Upstream: vercel/next.js#85374 (PR #99058, unmerged).`;

  if (process.platform === "win32") {
    console.warn(
      `warning: ${detail}
` +
        "         This is the known Windows path bug and cannot reach production: " +
        "CI builds on Linux. Expect two console 404s when serving this build locally.",
    );
    return;
  }

  throw new Error(
    `${detail} This platform is not affected by the Windows bug, so this is a real regression.`,
  );
}

await assertStaticOnly(resolve(webRoot, "src", "app"));
await assertSegmentPayloadsAreFlat(resolve(webRoot, "out"));
console.log("Static export contains all routes and semantic landmarks");
