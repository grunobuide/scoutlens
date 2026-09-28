// Builds the static export twice and proves the two are byte-identical
// (`scoutlens-uze.20`).
//
//   node scripts/check-build-reproducible.mjs     # or: pnpm build:reproducible
//
// Why this is not a CI gate: it costs two full builds, and `quality` already
// builds once on every commit. It is the command you run when you touch
// anything that could make the output vary — the Next config, the toolchain
// pins, a script that writes into the export.
//
// The defect it exists to catch had already reached production. Next generates
// a random 21-character build ID per build and embeds it in every page's flight
// payload and in `_next/static/<buildId>/`, so two builds of an identical tree
// differed. Deploying a docs-only commit changed every served page, which meant
// a no-op deploy could not be told apart from a real one by comparing digests,
// and the served site could not say which commit produced it.
//
// `next.config.ts` now derives the build ID from SCOUTLENS_BUILD_ID, with a
// fixed literal fallback. That fallback is what makes this check work locally:
// a timestamp or a random value would have left it permanently red.

import { createHash } from "node:crypto";
import { readFile, readdir, rm } from "node:fs/promises";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";

const webRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const exportDir = join(webRoot, "out");

async function build(label) {
  process.stdout.write(`\n--- ${label} ---\n`);
  const executable = process.platform === "win32" ? "pnpm.cmd" : "pnpm";
  await new Promise((resolvePromise, reject) => {
    const child = spawn(executable, ["build"], {
      cwd: webRoot,
      // SCOUTLENS_BUILD_ID is deliberately NOT set. This checks the default
      // path — the one a contributor and a reviewer actually run.
      env: { ...process.env },
      stdio: "inherit",
      shell: process.platform === "win32",
    });
    child.on("error", reject);
    child.on("exit", (code) =>
      code === 0 ? resolvePromise() : reject(new Error(`${label} failed with exit code ${code}`)),
    );
  });
}

/** Every file under `out`, as relative path -> sha256. */
async function snapshot(root) {
  const digests = new Map();
  async function walk(directory) {
    for (const entry of await readdir(directory, { withFileTypes: true })) {
      const full = join(directory, entry.name);
      if (entry.isDirectory()) {
        await walk(full);
      } else if (entry.isFile()) {
        const bytes = await readFile(full);
        digests.set(relative(root, full).replaceAll("\\", "/"), createHash("sha256").update(bytes).digest("hex"));
      }
    }
  }
  await walk(root);
  return digests;
}

function compare(first, second) {
  const onlyFirst = [...first.keys()].filter((path) => !second.has(path));
  const onlySecond = [...second.keys()].filter((path) => !first.has(path));
  const changed = [...first.keys()].filter((path) => second.has(path) && first.get(path) !== second.get(path));
  return { onlyFirst, onlySecond, changed };
}

async function main() {
  await rm(exportDir, { recursive: true, force: true });
  await build("build 1 of 2");
  const first = await snapshot(exportDir);

  await rm(exportDir, { recursive: true, force: true });
  await build("build 2 of 2");
  const second = await snapshot(exportDir);

  const { onlyFirst, onlySecond, changed } = compare(first, second);
  const total = first.size;

  console.log(`\ncompared ${total} files from build 1 against ${second.size} from build 2`);

  if (onlyFirst.length === 0 && onlySecond.length === 0 && changed.length === 0) {
    console.log("the static export is byte-identical across two builds");
    return 0;
  }

  console.error("\nthe static export is NOT reproducible.\n");
  const report = (label, paths) => {
    if (paths.length === 0) return;
    console.error(`${label} (${paths.length}):`);
    // A build-ID regression renames a whole directory, so a full listing is
    // noise. The first few name the cause.
    for (const path of paths.slice(0, 10)) console.error(`  ${path}`);
    if (paths.length > 10) console.error(`  ... and ${paths.length - 10} more`);
    console.error("");
  };
  report("only in build 1", onlyFirst);
  report("only in build 2", onlySecond);
  report("differing content", changed);
  console.error(
    "A path present in one build and not the other usually means something in the\n" +
      "output is named after the build rather than after its content.",
  );
  return 1;
}

main().then(
  (code) => {
    process.exitCode = code;
  },
  (error) => {
    console.error(error);
    process.exitCode = 1;
  },
);
