/**
 * The production export's fixture-trace scan (`scoutlens-uze.29`).
 *
 * `check-static-output.mjs` runs `findFixtureTraces` over `out/` on every
 * `pnpm build`, and therefore in `pnpm quality`. These tests build small trees
 * by hand - clean, and tampered one trace at a time in each kind of file the
 * export emits - so the scan is shown to find what it claims to find, not only
 * to pass on a clean build.
 */

import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

import { afterEach, beforeEach, describe, expect, it } from "vitest";

import {
  FIXTURE_CODE_MARKERS,
  FIXTURE_TRACE_MARKERS,
  SYNTHETIC_KEY_PATTERN,
  findFixtureTraces,
} from "../scripts/fixture-traces.mjs";
import { FIXTURE_MARKERS, SYNTHETIC_PROFILE_KEYS } from "../scripts/fixture-pack.mjs";

let root: string;

async function put(path: string, text: string): Promise<void> {
  const file = join(root, path);
  await mkdir(join(file, ".."), { recursive: true });
  await writeFile(file, text, "utf8");
}

beforeEach(async () => {
  root = await mkdtemp(join(tmpdir(), "fixture-traces-"));
  // A miniature production export: route HTML, a JS chunk, an RSC payload, a
  // stylesheet, showcase JSON with a real profile key, and a binary font.
  await put("index.html", "<main>A player leaves a reproducible fingerprint</main>");
  await put("_next/static/chunks/app.js", 'const showcase = "/showcase/v2/"; export default showcase;');
  await put("lab/__next.lab.__PAGE__.txt", '1:["$","main",null,{}]');
  await put("_next/static/css/app.css", ".lab-page{min-width:0}");
  await put("showcase/v2/players/wy-8287-c-795.json", '{"profile_key":"wy-8287-c-795"}');
  await put("_next/static/media/font.woff2", "wy-900001-c-901");
});

afterEach(async () => {
  await rm(root, { recursive: true, force: true });
});

describe("findFixtureTraces", () => {
  it("finds nothing in a clean export, and skips binary assets", async () => {
    const { traces, scanned } = await findFixtureTraces(root);
    expect(traces).toEqual([]);
    // Five text files scanned; the font, which happens to contain a fixture
    // key here, is not one of them.
    expect(scanned).toBe(5);
  });

  it("covers every identity and key the fixture pack defines, and the build switches", () => {
    for (const marker of [...FIXTURE_MARKERS, ...SYNTHETIC_PROFILE_KEYS, ...FIXTURE_CODE_MARKERS]) {
      expect(FIXTURE_TRACE_MARKERS).toContain(marker);
    }
    expect(SYNTHETIC_PROFILE_KEYS.length).toBeGreaterThanOrEqual(3);
  });

  it.each([
    ["a JS chunk", "_next/static/chunks/app.js", "SCOUTLENS_SHOWCASE_ROOT"],
    ["an RSC payload", "lab/__next.lab.__PAGE__.txt", "wy-900003-c-903"],
    ["a stylesheet", "_next/static/css/app.css", "lab-max-content"],
    ["a showcase JSON", "showcase/v2/players.index.json", "Fixture Torino"],
    ["route HTML", "science/index.html", FIXTURE_MARKERS[0] ?? "(no fixture display name)"],
  ])("finds a fixture trace planted in %s", async (_kind, path, trace) => {
    await put(path, `before ${trace} after`);
    const { traces } = await findFixtureTraces(root);
    expect(traces).toContainEqual({ file: path, trace });
  });

  it("finds a profile key on a synthetic competition even when the pack does not list it", async () => {
    await put("showcase/v2/players/wy-123456-c-907.json", '{"profile_key":"wy-123456-c-907"}');
    const { traces } = await findFixtureTraces(root);
    expect(traces).toContainEqual({ file: "showcase/v2/players/wy-123456-c-907.json", trace: "wy-123456-c-907" });
  });

  it("never mistakes a published profile key for a synthetic one", async () => {
    // Every key in the served index sits on one of the five real competitions.
    const index = JSON.parse(
      await readFile(resolve(__dirname, "..", "..", "public", "showcase", "v2", "players.index.json"), "utf8"),
    ) as { profiles: Array<{ profile_key: string }> };
    expect(index.profiles.length).toBeGreaterThan(1000);
    const flagged = index.profiles.map((profile) => profile.profile_key).filter((key) => SYNTHETIC_KEY_PATTERN.test(key));
    expect(flagged).toEqual([]);
  });
});
