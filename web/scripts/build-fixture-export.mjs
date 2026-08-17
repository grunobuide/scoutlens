// Builds the delegated test-only static export for a fixture pack
// (scoutlens-uze.7). Run AFTER `pnpm build`; the production export in `web/out`
// is never touched.
//
//   node scripts/build-fixture-export.mjs --fixture lab-max-content
//
// Produces web/out-fixtures/lab-max-content:
//   1. verifies the committed fixture pack (manifest checksums + canonical JSON);
//   2. runs `next build` with SCOUTLENS_SHOWCASE_ROOT=<pack> so the server
//      components bake the synthetic selector and profile data into the export;
//   3. moves the static export out of the shared `out/` into out-fixtures/<id>;
//   4. replaces <export>/showcase/v<major> with the fixture pack, so the browser's
//      lazy manifest+profile fetches resolve natively against fixture data;
//   5. fails unless the fixture identity actually appears in the built Lab HTML.
//
// The production export built by `pnpm build` (no env override) never contains
// fixture identities or fixture code paths; check-static-output enforces that.

import { cp, mkdir, readFile, readdir, rename, rm, stat } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";

import { FIXTURE_MARKERS, fixtureDirectory, verifyFixturePack } from "./fixture-pack.mjs";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const webRoot = resolve(scriptDirectory, "..");

// The fixture export replaces the served showcase tree, so it must target
// the same major the pack was generated for.
const fixtureMajor = Number(process.env.SCOUTLENS_FIXTURE_MAJOR ?? "1");
const showcaseDir = `v${fixtureMajor}`;

function fixtureArg() {
  const index = process.argv.indexOf("--fixture");
  const value = index === -1 ? process.env.SCOUTLENS_FIXTURE_ID ?? "lab-max-content" : process.argv[index + 1];
  if (!/^[a-z0-9-]+$/.test(value)) {
    throw new Error(`Invalid fixture id: ${value}`);
  }
  return value;
}

async function exists(path) {
  try {
    await stat(path);
    return true;
  } catch {
    return false;
  }
}

async function runNextBuild(env) {
  const executable = process.platform === "win32" ? "pnpm.cmd" : "pnpm";
  await new Promise((resolvePromise, reject) => {
    const child = spawn(executable, ["exec", "next", "build"], {
      cwd: webRoot,
      env: { ...process.env, ...env },
      stdio: "inherit",
      shell: process.platform === "win32",
    });
    child.on("error", reject);
    child.on("close", (code) => {
      if (code === 0) {
        resolvePromise();
      } else {
        reject(new Error(`next build exited with code ${code}`));
      }
    });
  });
}

async function moveDirectoryTo(from, to) {
  // The isolated fixture build may place its static export inside the target
  // directory (web/out-fixtures/<id>/.next-build when Next writes to distDir),
  // so hoist the source out of the target before cleaning up the target.
  const ascent = resolve(from);
  const destination = resolve(to);
  const fromInsideTo =
    ascent === destination ||
    ascent.startsWith(`${destination}\\`) ||
    ascent.startsWith(`${destination}/`);
  if (fromInsideTo) {
    const temporary = resolve(dirname(destination), `.hoist-${Date.now()}`);
    await rename(ascent, temporary);
    await rm(destination, { recursive: true, force: true });
    await mkdir(dirname(destination), { recursive: true });
    await rename(temporary, destination);
    return;
  }
  await rm(destination, { recursive: true, force: true });
  await mkdir(dirname(destination), { recursive: true });
  await rename(ascent, destination);
}

async function replaceShowcaseAssets(exportRoot, packRoot) {
  const target = resolve(exportRoot, "showcase", showcaseDir);
  await rm(target, { recursive: true, force: true });
  await mkdir(target, { recursive: true });
  await cp(packRoot, target, { recursive: true });
}

async function listRelative(root) {
  const files = [];
  const walk = async (directory, prefix) => {
    for (const entry of await readdir(directory, { withFileTypes: true })) {
      const path = resolve(directory, entry.name);
      const relative = `${prefix}${entry.name}`;
      if (entry.isDirectory()) {
        await walk(path, `${relative}/`);
      } else {
        files.push(relative);
      }
    }
  };
  await walk(root, "");
  return files.sort();
}

async function assertFixtureIdentityInExport(exportRoot) {
  const html = await readFile(resolve(exportRoot, "lab", "index.html"), "utf8");
  const missing = FIXTURE_MARKERS.filter((marker) => !html.includes(marker));
  if (missing.length > 0) {
    throw new Error(
      `Fixture export is missing required identity markers: ${JSON.stringify(missing)}`,
    );
  }
}

async function main() {
  const fixture = fixtureArg();
  const packRoot = fixtureDirectory();
  const exportDirName = `out-fixtures/${fixture}`;
  const exportRoot = resolve(webRoot, exportDirName);
  const buildDir = resolve(webRoot, exportDirName, ".next-build");

  const summary = await verifyFixturePack();
  console.log(`Fixture pack verified: ${JSON.stringify(summary)}`);

  // Isolate the fixture build from any production compilation: the shared
  // `.next` cache must not leak production render state into the fixture
  // export. Remove it before (so the fixture build is clean) and after (so a
  // later production `pnpm build` recompiles from scratch and never serves
  // fixture-baked pages).
  const sharedNextCache = resolve(webRoot, ".next");
  await rm(sharedNextCache, { recursive: true, force: true });

  await rm(exportRoot, { recursive: true, force: true });
  await mkdir(exportRoot, { recursive: true });

  await runNextBuild({
    // The fixture root must not depend on the build worker's cwd (Turbopack
    // workers can run from a different directory on Linux). Pass an absolute
    // path using forward slashes: Windows `C:/` forms resolve fine through
    // path.resolve, while backslashes would be mangled by Next's env handling.
    SCOUTLENS_SHOWCASE_ROOT: packRoot.replaceAll("\\", "/"),
    SCOUTLENS_DIST_DIR: buildDir,
    // The consumer resolves its base URL and validating schema from this, so a
    // v2 pack built without it would be served under /showcase/v1/ and rejected
    // for declaring the wrong major - correctly, but confusingly.
    NEXT_PUBLIC_SCOUTLENS_SHOWCASE_MAJOR: String(fixtureMajor),
  });

  // With output: "export" the static files land in web/out unless the build
  // already placed them inside the isolated distDir (Next version dependent).
  // Pick the candidate that actually contains the fixture identity: a stale
  // production web/out must never be mistaken for the fixture export (it
  // exists in CI because pnpm quality builds production first).
  const candidates = [resolve(webRoot, "out"), buildDir];
  let sourceExport = null;
  for (const candidate of candidates) {
    if (!(await exists(candidate))) {
      continue;
    }
    try {
      const html = await readFile(resolve(candidate, "lab", "index.html"), "utf8");
      if (FIXTURE_MARKERS.every((marker) => html.includes(marker))) {
        sourceExport = candidate;
        break;
      }
    } catch {
      // Not a fixture export candidate; keep looking.
    }
  }
  if (sourceExport === null || !(await exists(resolve(sourceExport, "index.html")))) {
    throw new Error(`Fixture build produced no fixture-marked static export in ${JSON.stringify(candidates)}`);
  }
  await mkdir(exportRoot, { recursive: true });
  await moveDirectoryTo(sourceExport, exportRoot);

  await replaceShowcaseAssets(exportRoot, packRoot);
  if (buildDir !== sourceExport) {
    await rm(buildDir, { recursive: true, force: true });
  }
  await rm(sharedNextCache, { recursive: true, force: true });

  await assertFixtureIdentityInExport(exportRoot);
  const files = await listRelative(exportRoot);
  console.log(
    JSON.stringify(
      {
        command: "build-fixture-export",
        fixture,
        exportRoot,
        files: files.length,
        marker: "identity present in /lab HTML",
      },
      null,
      2,
    ),
  );
}

await main();
