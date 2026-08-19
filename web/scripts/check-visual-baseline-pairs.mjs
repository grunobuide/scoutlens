// Pair guard for visual baselines (scoutlens-uze.11).
//
// Playwright writes one baseline per {project}-{platform}, so every logical
// snapshot exists twice: once for linux, once for win32. A contributor can only
// regenerate the platform they are running on, which makes a one-platform
// update the natural mistake rather than a careless one - and it is silent,
// because the platform you updated goes green locally while the other stays
// stale until CI runs. That failure mode cost nine red commits before anyone
// noticed (scoutlens-uze.10).
//
// This guard reads a list of changed paths and fails when a logical snapshot
// changed on one platform and not the other. It takes the paths as input rather
// than shelling out to Git, so the unit tests need no repository and no GitHub
// context; the workflow owns diff acquisition and the label/reason check.
//
// Usage:
//   node scripts/check-visual-baseline-pairs.mjs <path>...
//   node scripts/check-visual-baseline-pairs.mjs --paths-from <file>
//   node scripts/check-visual-baseline-pairs.mjs --allow-platform-specific ...
//
// Exit 0 when every changed snapshot is paired (or the override is authorised),
// 1 when an unpaired change is present, 2 on malformed input.

const SNAPSHOT_ROOT = "web/e2e/__screenshots__/";

/** Platforms Playwright produces baselines for in this repository. */
export const KNOWN_PLATFORMS = ["linux", "win32"];

export class BaselinePairError extends Error {}

/**
 * Split `desktop-linux` into `{ project: "desktop", platform: "linux" }`.
 *
 * Fails closed on a directory whose platform suffix is not one we know. An
 * unrecognised directory is more likely a new platform nobody taught this
 * guard about than a directory that is safe to ignore, and ignoring it would
 * silently exempt exactly the baselines the guard exists to pair.
 */
export function parseProjectDirectory(directory) {
  const separator = directory.lastIndexOf("-");
  if (separator <= 0) {
    throw new BaselinePairError(
      `snapshot directory "${directory}" has no {project}-{platform} form`,
    );
  }
  const project = directory.slice(0, separator);
  const platform = directory.slice(separator + 1);
  if (!KNOWN_PLATFORMS.includes(platform)) {
    throw new BaselinePairError(
      `snapshot directory "${directory}" names platform "${platform}", which this guard does not ` +
        `know about (known: ${KNOWN_PLATFORMS.join(", ")}). Teach the guard before adding baselines.`,
    );
  }
  return { project, platform };
}

/**
 * The logical identity of a snapshot: everything except which platform
 * rendered it. `desktop-linux/neighbor-cards.png` and
 * `desktop-win32/neighbor-cards.png` are one logical snapshot.
 */
export function logicalSnapshot(path) {
  const normalised = path.replaceAll("\\", "/");
  if (!normalised.startsWith(SNAPSHOT_ROOT)) {
    return null;
  }
  const remainder = normalised.slice(SNAPSHOT_ROOT.length);
  const slash = remainder.indexOf("/");
  if (slash === -1) {
    throw new BaselinePairError(`snapshot path "${path}" has no {project}-{platform} directory`);
  }
  const { project, platform } = parseProjectDirectory(remainder.slice(0, slash));
  const name = remainder.slice(slash + 1);
  if (name === "") {
    throw new BaselinePairError(`snapshot path "${path}" names no file`);
  }
  return { key: `${project}/${name}`, project, platform, name, path: normalised };
}

/**
 * Group changed paths into logical snapshots and report any missing platform.
 *
 * Paths outside the snapshot root are ignored: this guard has one job and a
 * pull request touching source and baselines together is normal.
 */
export function findUnpairedSnapshots(paths) {
  const byKey = new Map();
  for (const path of paths) {
    const snapshot = logicalSnapshot(path);
    if (snapshot === null) {
      continue;
    }
    const entry = byKey.get(snapshot.key) ?? { key: snapshot.key, platforms: new Map() };
    entry.platforms.set(snapshot.platform, snapshot.path);
    byKey.set(snapshot.key, entry);
  }

  const unpaired = [];
  for (const entry of [...byKey.values()].sort((a, b) => a.key.localeCompare(b.key, "en"))) {
    const missing = KNOWN_PLATFORMS.filter((platform) => !entry.platforms.has(platform));
    if (missing.length > 0) {
      unpaired.push({
        key: entry.key,
        changed: [...entry.platforms.values()].sort(),
        missing,
      });
    }
  }
  return { snapshotCount: byKey.size, unpaired };
}

function parseArguments(argv) {
  const paths = [];
  let allowPlatformSpecific = false;
  let pathsFrom = null;
  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];
    if (argument === "--allow-platform-specific") {
      allowPlatformSpecific = true;
    } else if (argument === "--paths-from") {
      pathsFrom = argv[index + 1];
      index += 1;
    } else {
      paths.push(argument);
    }
  }
  return { paths, allowPlatformSpecific, pathsFrom };
}

export async function main(argv) {
  const { paths, allowPlatformSpecific, pathsFrom } = parseArguments(argv);
  let candidates = paths;
  if (pathsFrom !== null) {
    const { readFile } = await import("node:fs/promises");
    const contents = await readFile(pathsFrom, "utf8");
    candidates = [...candidates, ...contents.split("\n").map((line) => line.trim()).filter(Boolean)];
  }

  let result;
  try {
    result = findUnpairedSnapshots(candidates);
  } catch (error) {
    if (error instanceof BaselinePairError) {
      console.error(`Visual baseline guard: ${error.message}`);
      return 2;
    }
    throw error;
  }

  if (result.snapshotCount === 0) {
    console.log("Visual baseline guard: no snapshot changes in this diff.");
    return 0;
  }
  if (result.unpaired.length === 0) {
    console.log(
      `Visual baseline guard: ${result.snapshotCount} logical snapshot(s) changed, every one paired across ${KNOWN_PLATFORMS.join(" and ")}.`,
    );
    return 0;
  }

  console.error(
    `Visual baseline guard: ${result.unpaired.length} of ${result.snapshotCount} changed snapshot(s) were updated on one platform only.\n`,
  );
  for (const entry of result.unpaired) {
    console.error(`  ${entry.key}`);
    for (const path of entry.changed) {
      console.error(`    changed  ${path}`);
    }
    for (const platform of entry.missing) {
      console.error(`    MISSING  ${entry.key.replace("/", `-${platform}/`)}`);
    }
  }

  if (allowPlatformSpecific) {
    console.error(
      "\nAccepted: this pull request carries the reviewed platform-specific label and a documented reason.",
    );
    return 0;
  }

  console.error(
    "\nRegenerate the missing platform's baseline before merging. A baseline updated on one\n" +
      "platform is stale on the other, and the stale side stays green locally, so nothing\n" +
      "tells you until CI runs. For the linux baselines, run the matching container:\n\n" +
      "  docker run --rm -v \"$PWD\":/repo -w /repo/web \\\n" +
      "    mcr.microsoft.com/playwright:v1.62.0-noble \\\n" +
      "    npx playwright test --project=<project> <spec> --update-snapshots\n\n" +
      "If the difference is genuinely platform-specific, a maintainer applies the\n" +
      "visual-platform-specific label and states the reason in the pull request body.",
  );
  return 1;
}

const invokedDirectly =
  process.argv[1] !== undefined && import.meta.url === new URL(`file://${process.argv[1]}`).href;
if (invokedDirectly || process.argv[1]?.endsWith("check-visual-baseline-pairs.mjs")) {
  process.exit(await main(process.argv.slice(2)));
}
