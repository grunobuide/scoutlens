// Fixture traces in a static export (`scoutlens-uze.29`).
//
// `scoutlens-uze.7` added a test-only fixture pack and two default-off build
// switches that point the export at it. Its AC6 asks that the production export
// carry "no fixture identity and no fixture code path", and the check it shipped
// read only the three route HTML files. A fixture profile that reached a JS
// chunk, an RSC payload or `out/showcase/**` would have passed.
//
// This walks every text file the export emits and reports each fixture trace:
// the pack's identity strings, its profile keys, any profile key on a synthetic
// competition, and the names of the switches and directories that only the
// fixture build uses. Kept separate from check-static-output.mjs so a test can
// run it against a tree it builds, tampered on purpose.

import { readFile, readdir } from "node:fs/promises";
import { join, relative } from "node:path";

import { FIXTURE_MARKERS, SYNTHETIC_PROFILE_KEYS } from "./fixture-pack.mjs";

/** Strings only the fixture build path knows. */
export const FIXTURE_CODE_MARKERS = [
  "lab-max-content",
  "out-fixtures",
  "fx-max-content",
  "fx-uc-",
  "SCOUTLENS_SHOWCASE_ROOT",
  "SCOUTLENS_DIST_DIR",
];

/**
 * A profile key on a synthetic competition. The pack's competitions are 901 to
 * 903; the published dataset's are five real league ids (364 to 795), so any
 * `-c-9xx` key is a fixture whatever its player id.
 */
export const SYNTHETIC_KEY_PATTERN = /\bwy-\d+-c-9\d\d\b/;

const SCANNED = /\.(js|mjs|json|html|txt|css|map|xml|webmanifest)$/i;

export const FIXTURE_TRACE_MARKERS = [...FIXTURE_MARKERS, ...SYNTHETIC_PROFILE_KEYS, ...FIXTURE_CODE_MARKERS];

/**
 * Every fixture trace under `root`, as `{ file, trace }` with `file` relative
 * to `root`. Empty means clean. Binary assets (fonts, images) are skipped: they
 * cannot carry a profile key or a code path.
 */
export async function findFixtureTraces(root, markers = FIXTURE_TRACE_MARKERS) {
  const traces = [];
  let scanned = 0;
  async function walk(directory) {
    for (const entry of await readdir(directory, { withFileTypes: true })) {
      const path = join(directory, entry.name);
      if (entry.isDirectory()) {
        await walk(path);
        continue;
      }
      if (!SCANNED.test(entry.name)) {
        continue;
      }
      scanned += 1;
      const text = await readFile(path, "utf8");
      const file = relative(root, path).replaceAll("\\", "/");
      for (const marker of markers) {
        if (text.includes(marker)) {
          traces.push({ file, trace: marker });
        }
      }
      const key = SYNTHETIC_KEY_PATTERN.exec(text);
      if (key !== null && !markers.includes(key[0])) {
        traces.push({ file, trace: key[0] });
      }
    }
  }
  await walk(root);
  return { traces, scanned };
}
