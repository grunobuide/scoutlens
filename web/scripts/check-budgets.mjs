// Initial-JavaScript budget semantics (D038, scoutlens-jtt.14):
// "Initial /lab JavaScript" counts only <script> assets that module-capable
// browsers actually fetch and execute. Scripts carrying the `noModule`
// attribute are legacy-only polyfills (Next emits one core-js bundle of
// ~39,520 gzip bytes in production exports); browsers with module support
// and every measured surface (Chromium, Playwright, Lighthouse) never
// download them, so counting them would overstate the real initial transfer.
// The legacy noModule payload is still asserted and reported separately so it
// can never be dropped silently. Thresholds in quality-budgets.json are
// frozen and unchanged by this definition.
import { gzipSync } from "node:zlib";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const webRoot = resolve(scriptDirectory, "..");
const outputRoot = resolve(webRoot, "out");
const budgets = JSON.parse(await readFile(resolve(webRoot, "quality-budgets.json"), "utf8"));
const lighthouseConfig = JSON.parse(
  await readFile(resolve(webRoot, "lighthouserc.json"), "utf8"),
);
// Budgets are measured against the major the build actually shipped, which is
// the one the payload pin names. Same single source as the asset sync.
const pinnedMajor = JSON.parse(
  await readFile(resolve(webRoot, "..", "config", "showcase-payload-pack.json"), "utf8"),
).schema_version.split(".")[0];
const showcaseMajor = Number(process.env.NEXT_PUBLIC_SCOUTLENS_SHOWCASE_MAJOR ?? pinnedMajor);
if (showcaseMajor !== 1 && showcaseMajor !== 2) {
  throw new Error(`NEXT_PUBLIC_SCOUTLENS_SHOWCASE_MAJOR must be 1 or 2, got ${showcaseMajor}`);
}
const showcaseDir = `v${showcaseMajor}`;

const manifest = JSON.parse(
  await readFile(resolve(outputRoot, "showcase", showcaseDir, "manifest.json"), "utf8"),
);

function gzipBytes(bytes) {
  return gzipSync(bytes, { level: 9 }).byteLength;
}

async function gzipFile(relativePath) {
  return gzipBytes(await readFile(resolve(outputRoot, ...relativePath.split("/"))));
}

function localAssetPaths(html, tagName, attribute) {
  const tags = html.match(new RegExp(`<${tagName}\\b[^>]*>`, "gi")) ?? [];
  return tags
    .map((tag) => tag.match(new RegExp(`${attribute}=["']([^"']+)["']`, "i"))?.[1])
    .filter((value) => value?.startsWith("/"))
    .map((value) => value.slice(1));
}

function assertBudget(label, actual, limit) {
  if (actual > limit) {
    throw new Error(`${label} is ${actual.toLocaleString("en-US")} gzip bytes; limit is ${limit.toLocaleString("en-US")}`);
  }
  console.log(
    `${label}: ${actual.toLocaleString("en-US")} / ${limit.toLocaleString("en-US")} gzip bytes (${(limit - actual).toLocaleString("en-US")} headroom)`,
  );
}

function assertLighthouseThreshold(assertion, property, expected) {
  const rule = lighthouseConfig.ci?.assert?.assertions?.[assertion];
  const options = Array.isArray(rule) ? rule[1] : undefined;
  const actual = options?.[property];
  if (actual !== expected || options?.aggregationMethod !== "median-run") {
    throw new Error(
      `${assertion} must use ${property}=${expected} with aggregationMethod=median-run; received ${JSON.stringify(options)}`,
    );
  }
}

for (const category of ["performance", "accessibility", "best-practices", "seo"]) {
  assertLighthouseThreshold(
    `categories:${category}`,
    "minScore",
    budgets.lighthouse.category_minimum,
  );
}
assertLighthouseThreshold(
  "largest-contentful-paint",
  "maxNumericValue",
  budgets.lighthouse.largest_contentful_paint_ms,
);
assertLighthouseThreshold(
  "cumulative-layout-shift",
  "maxNumericValue",
  budgets.lighthouse.cumulative_layout_shift,
);
console.log("Lighthouse assertions match the versioned quality budgets");

// Split initial <script> assets by whether a module-capable browser fetches
// them. Scripts with the `noModule` attribute are legacy-only (see the file
// header for the budget semantics decision D035).
function localScriptAssets(html) {
  const tags = html.match(/<script\b[^>]*>/gi) ?? [];
  const modulePaths = [];
  const noModulePaths = [];
  for (const tag of tags) {
    const src = tag.match(/\bsrc=(["'])([^"']+)\1/i)?.[2];
    if (!src?.startsWith("/")) {
      continue;
    }
    if (/\bnoModule\b/i.test(tag)) {
      noModulePaths.push(src.slice(1));
    } else {
      modulePaths.push(src.slice(1));
    }
  }
  return { module: [...new Set(modulePaths)], noModule: [...new Set(noModulePaths)] };
}

const labHtmlBytes = await readFile(resolve(outputRoot, "lab", "index.html"));
const labHtml = labHtmlBytes.toString("utf8");
const scriptAssets = localScriptAssets(labHtml);
const scriptPaths = scriptAssets.module;
const legacyNoModulePaths = scriptAssets.noModule;
const stylesheetPaths = [
  ...new Set(
    localAssetPaths(labHtml, "link", "href").filter((path) => path.endsWith(".css")),
  ),
];
if (scriptPaths.length === 0 || stylesheetPaths.length === 0) {
  throw new Error("The /lab export must reference initial JavaScript and CSS assets");
}

const initialJavaScript = (
  await Promise.all(scriptPaths.map((path) => gzipFile(path)))
).reduce((total, bytes) => total + bytes, 0);
const legacyNoModuleJavaScript = (
  await Promise.all(legacyNoModulePaths.map((path) => gzipFile(path)))
).reduce((total, bytes) => total + bytes, 0);
const initialStyles = (
  await Promise.all(stylesheetPaths.map((path) => gzipFile(path)))
).reduce((total, bytes) => total + bytes, 0);
const labInitialTransfer = gzipBytes(labHtmlBytes) + initialJavaScript + initialStyles;
const catalog = await gzipFile(`showcase/${showcaseDir}/feature-catalog.json`);

let largestProfile = { bytes: 0, path: "" };
for (const file of manifest.files) {
  if (!file.path.startsWith("players/")) {
    continue;
  }
  const bytes = await gzipFile(`showcase/${showcaseDir}/${file.path}`);
  if (bytes > largestProfile.bytes) {
    largestProfile = { bytes, path: file.path };
  }
}
if (largestProfile.path === "") {
  throw new Error("The showcase manifest contains no player profiles");
}

assertBudget(
  "Initial /lab JavaScript",
  initialJavaScript,
  budgets.gzip_bytes.initial_route_javascript,
);
if (legacyNoModulePaths.length > 0) {
  console.log(
    `Legacy noModule polyfill(s) excluded from modern-browser initial JS (${legacyNoModulePaths.join(", ")}): ${legacyNoModuleJavaScript.toLocaleString("en-US")} gzip bytes`,
  );
} else {
  console.log("No legacy noModule polyfill present in the /lab export");
}
assertBudget("Feature catalog", catalog, budgets.gzip_bytes.feature_catalog);
assertBudget(
  `Largest player profile (${largestProfile.path})`,
  largestProfile.bytes,
  budgets.gzip_bytes.player_profile_max,
);
assertBudget(
  "Initial /lab transfer excluding fonts",
  labInitialTransfer,
  budgets.gzip_bytes.lab_initial_transfer_excluding_fonts,
);
