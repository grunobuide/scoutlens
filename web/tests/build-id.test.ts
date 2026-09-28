import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { afterEach, describe, expect, it } from "vitest";

import nextConfig from "../next.config";

/**
 * `scoutlens-uze.20`. The build ID is the one part of the static export that
 * was not derived from the source.
 *
 * Next generates a random 21-character value per build and embeds it in every
 * page's flight payload and in `_next/static/<buildId>/`, so two builds of an
 * identical tree differed. That cost two real things, both of which had already
 * bitten: a no-op deploy could not be told apart from a real one by comparing
 * digests, and the served site could not say which commit produced it —
 * `scoutlens-vif.6` had to read that off an Actions log.
 *
 * The full proof is two builds (`pnpm build:reproducible`), which is too slow
 * for this suite. What is asserted here is the mechanism: given the same input,
 * the same ID; given a commit, that commit.
 */

const ENV_VAR = "SCOUTLENS_BUILD_ID";
const LOCAL_FALLBACK = "scoutlens-local";

const original = process.env[ENV_VAR];

afterEach(() => {
  if (original === undefined) delete process.env[ENV_VAR];
  else process.env[ENV_VAR] = original;
});

async function buildId(): Promise<string> {
  const generate = nextConfig.generateBuildId;
  expect(generate, "next.config.ts must define generateBuildId").toBeTypeOf("function");
  const value = await generate!();
  expect(value, "generateBuildId must return a string, not null").toBeTypeOf("string");
  return value as string;
}

describe("the build ID identifies the build", () => {
  it("is the commit when one is supplied", async () => {
    const sha = "0045ea41d4d518e5790017a2384abf66b833d60f";
    process.env[ENV_VAR] = sha;
    expect(await buildId()).toBe(sha);
  });

  it("is stable across calls with the same input", async () => {
    process.env[ENV_VAR] = "af96be6ac0000000000000000000000000000000";
    const first = await buildId();
    const second = await buildId();
    expect(first).toBe(second);
  });

  it("falls back to a fixed literal, not to something that varies", async () => {
    // The fallback choice is the whole reason `pnpm build:reproducible` can
    // work locally. A timestamp, a random value or a `Date.now()` would leave
    // it permanently red and the check would be abandoned.
    delete process.env[ENV_VAR];
    const first = await buildId();
    const second = await buildId();
    expect(first).toBe(LOCAL_FALLBACK);
    expect(second).toBe(LOCAL_FALLBACK);
  });

  it("treats an empty or whitespace value as absent", async () => {
    // A workflow that fails to interpolate a SHA yields an empty string, not an
    // unset variable. Baking `""` in as a build ID would be worse than the
    // random value it replaced.
    for (const blank of ["", "   ", "\t"]) {
      process.env[ENV_VAR] = blank;
      expect(await buildId()).toBe(LOCAL_FALLBACK);
    }
  });

  it("trims a value that arrives with surrounding whitespace", async () => {
    process.env[ENV_VAR] = "  c79d2a0  ";
    expect(await buildId()).toBe("c79d2a0");
  });
});

describe("the deploy workflow supplies a real commit", () => {
  it("bakes the resolved SHA into the build, not the trigger's ref", async () => {
    // A `workflow_dispatch` ref may be a branch name, so the trigger's value
    // does not always name a commit. The checked-out HEAD always does.
    const workflow = await readFile(
      resolve("..", ".github", "workflows", "deploy.yml"),
      "utf8",
    );
    expect(workflow).toContain("git rev-parse HEAD");
    expect(workflow).toContain(`${ENV_VAR}: \${{ steps.commit.outputs.sha }}`);
  });

  it("still sets the Pages base path alongside it", async () => {
    const workflow = await readFile(
      resolve("..", ".github", "workflows", "deploy.yml"),
      "utf8",
    );
    expect(workflow).toContain("SCOUTLENS_BASE_PATH:");
  });
});
