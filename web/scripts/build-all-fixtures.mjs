// Builds every fixture export the E2E gates serve, one per contract major
// (scoutlens-qop.6.5).
//
// npm scripts cannot set a per-invocation environment variable portably across
// Windows and Linux without a helper dependency, so the sequence lives here
// instead. Each major gets its own pack and its own static export; neither
// touches the production export in web/out.

import { spawn } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const webRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");

const MAJORS = [
  { major: 1, fixture: "lab-max-content" },
  { major: 2, fixture: "lab-max-content-v2" },
];

function run(script, args, env) {
  return new Promise((resolvePromise, reject) => {
    const child = spawn(process.execPath, [resolve(webRoot, "scripts", script), ...args], {
      cwd: webRoot,
      env: { ...process.env, ...env },
      stdio: "inherit",
    });
    child.on("error", reject);
    child.on("close", (code) =>
      code === 0 ? resolvePromise() : reject(new Error(`${script} exited with code ${code}`)),
    );
  });
}

for (const { major, fixture } of MAJORS) {
  const env = {
    SCOUTLENS_FIXTURE_MAJOR: String(major),
    SCOUTLENS_FIXTURE_ID: fixture,
    NEXT_PUBLIC_SCOUTLENS_SHOWCASE_MAJOR: String(major),
  };
  await run("fixture-pack.mjs", ["generate"], env);
  await run("build-fixture-export.mjs", ["--fixture", fixture], env);
}

console.log(`Built ${MAJORS.length} fixture exports: ${MAJORS.map((m) => m.fixture).join(", ")}`);
