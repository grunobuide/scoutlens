import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import { ACTIVE_SHOWCASE_MAJOR } from "@/contracts/showcase-repository";

interface Manifest {
  dataset_version: string;
  population: { profile_count: number; feature_count: number; minutes_threshold_per_period: number };
  source: { licence: string; season: string };
}

describe("the landing's facts strip and 'The idea in 30 seconds' (scoutlens-rdz.9)", () => {
  it("types none of the manifest's values into the page source", async () => {
    // D076: every fact in the strip and every number in the idea block is the
    // artifact's, read at build time. A value typed into page.tsx would agree
    // with the artifact today and silently disagree with the next one.
    const manifest = JSON.parse(
      await readFile(resolve("public", "showcase", `v${ACTIVE_SHOWCASE_MAJOR}`, "manifest.json"), "utf8"),
    ) as Manifest;
    const page = await readFile(resolve("src", "app", "page.tsx"), "utf8");
    const { population, source } = manifest;

    for (const literal of [
      manifest.dataset_version,
      source.licence,
      source.season,
      population.profile_count.toLocaleString("en-US"),
    ]) {
      expect(page).not.toContain(literal);
    }
    for (const count of [population.profile_count, population.feature_count, population.minutes_threshold_per_period]) {
      expect(page).not.toMatch(new RegExp(`\\b${count}\\b`));
    }
  });
});
