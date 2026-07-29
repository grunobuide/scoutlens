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
const manifest = JSON.parse(
  await readFile(resolve(outputRoot, "showcase", "v1", "manifest.json"), "utf8"),
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

const labHtmlBytes = await readFile(resolve(outputRoot, "lab", "index.html"));
const labHtml = labHtmlBytes.toString("utf8");
const scriptPaths = [...new Set(localAssetPaths(labHtml, "script", "src"))];
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
const initialStyles = (
  await Promise.all(stylesheetPaths.map((path) => gzipFile(path)))
).reduce((total, bytes) => total + bytes, 0);
const labInitialTransfer = gzipBytes(labHtmlBytes) + initialJavaScript + initialStyles;
const catalog = await gzipFile("showcase/v1/feature-catalog.json");

let largestProfile = { bytes: 0, path: "" };
for (const file of manifest.files) {
  if (!file.path.startsWith("players/")) {
    continue;
  }
  const bytes = await gzipFile(`showcase/v1/${file.path}`);
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
