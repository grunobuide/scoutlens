import { createHash } from "node:crypto";
import { readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import { StaticShowcaseRepository, type ShowcaseFetch } from "@/contracts/showcase-repository";

import { generateFixturePack, verifyFixturePack } from "../scripts/fixture-pack.mjs";

const fixtureRoot = resolve("e2e", "fixtures", "lab-max-content");
const publishedRoot = resolve("..", "public", "showcase", "v1");

const FIXTURE_IDS = {
  maxContent: "wy-900001-c-901",
  uncertaintyAvailable: "wy-900002-c-902",
  uncertaintyInsufficient: "wy-900003-c-903",
} as const;

const PUBLISHED_MAX_DISPLAY_NAME = 22;
const PUBLISHED_MAX_TEAM_JOIN = 35;
const PUBLISHED_MAX_COMPETITION = 22;
const PUBLISHED_MAX_TEAMS_PER_PERIOD = 2;

function fixtureFetch(): ShowcaseFetch {
  return async (input) => {
    const relative = input.replace(/^.*\/showcase\/v1\//, "");
    const bytes = await readFile(resolve(fixtureRoot, relative));
    return new Response(bytes, {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  };
}

function sha256(text: string): string {
  return createHash("sha256").update(text).digest("hex");
}

async function repositoryProfile(profileKey: string) {
  const repository = new StaticShowcaseRepository(fixtureFetch());
  return repository.getProfile(profileKey);
}

describe("scoutlens-uze.7 fixture pack", () => {
  it("passes the real repository contract for the max-content profile", async () => {
    const profile = await repositoryProfile(FIXTURE_IDS.maxContent);
    expect(`${profile.profile_key}`).toBe(FIXTURE_IDS.maxContent);
    expect(profile.identity.display_name.length).toBeGreaterThan(PUBLISHED_MAX_DISPLAY_NAME + 10);
    expect(profile.identity.competition.name.length).toBeGreaterThan(PUBLISHED_MAX_COMPETITION + 10);
    const teams = [
      ...profile.identity.period_contexts.a.teams,
      ...profile.identity.period_contexts.b.teams,
    ];
    const teamJoin = [...new Set(teams.map((team) => team.name))].join(" / ");
    expect(teamJoin.length).toBeGreaterThan(PUBLISHED_MAX_TEAM_JOIN + 30);
    expect(profile.identity.period_contexts.b.teams.length).toBeGreaterThan(
      PUBLISHED_MAX_TEAMS_PER_PERIOD,
    );
    expect(profile.neighbors).toHaveLength(5);
    expect(profile.evidence_index.length).toBeGreaterThanOrEqual(240);
  });

  it("renders a list where the synthetic profile is selectable from the same index contract", async () => {
    const repository = new StaticShowcaseRepository(fixtureFetch());
    const profiles = await repository.listProfiles();
    const item = profiles.find((candidate) => candidate.profile_key === FIXTURE_IDS.maxContent);
    expect(item).toBeDefined();
    expect(item?.display_name.length ?? 0).toBeGreaterThan(PUBLISHED_MAX_DISPLAY_NAME + 10);
    expect(item?.uncertainty_status).toBe("pending");
    expect(profiles.length).toBe(1260);
  });

  it("renders retrieval 'available' with populated interval, median, resamples and recalls", async () => {
    const profile = await repositoryProfile(FIXTURE_IDS.uncertaintyAvailable);
    for (const scope of ["global", "within_role", "baseline_role_minutes"] as const) {
      const uncertainty = profile.retrieval[scope].uncertainty;
      expect(uncertainty.status).toBe("available");
      expect(uncertainty.valid_resamples).toBe(500);
      expect(uncertainty.median_rank).not.toBeNull();
      expect(uncertainty.rank_ci_95).not.toBeNull();
      expect(uncertainty.recall_at_1_rate).not.toBeNull();
      expect(uncertainty.recall_at_5_rate).not.toBeNull();
      expect(uncertainty.recall_at_10_rate).not.toBeNull();
    }
    for (const neighbor of profile.neighbors) {
      expect(neighbor.stability.status).toBe("available");
      expect(neighbor.stability.valid_resamples).toBe(500);
      expect(neighbor.stability.median_rank).not.toBeNull();
      expect(neighbor.stability.rank_ci_95).not.toBeNull();
      expect(neighbor.stability.top_5_selection_rate).not.toBeNull();
    }
    expect(profile.uncertainty.status).toBe("available");
  });

  it("renders retrieval 'insufficient' with documented nulls and no fabricated interval", async () => {
    const profile = await repositoryProfile(FIXTURE_IDS.uncertaintyInsufficient);
    for (const scope of ["global", "within_role", "baseline_role_minutes"] as const) {
      const uncertainty = profile.retrieval[scope].uncertainty;
      expect(uncertainty.status).toBe("insufficient");
      expect(uncertainty.valid_resamples).toBe(4);
      expect(uncertainty.median_rank).toBeNull();
      expect(uncertainty.rank_ci_95).toBeNull();
      expect(uncertainty.recall_at_1_rate).toBeNull();
      expect(uncertainty.recall_at_5_rate).toBeNull();
      expect(uncertainty.recall_at_10_rate).toBeNull();
    }
    for (const neighbor of profile.neighbors) {
      expect(neighbor.stability.status).toBe("insufficient");
      expect(neighbor.stability.median_rank).toBeNull();
      expect(neighbor.stability.rank_ci_95).toBeNull();
      expect(neighbor.stability.top_5_selection_rate).toBeNull();
    }
    expect(profile.uncertainty.status).toBe("insufficient");
  });

  it("is deterministic: two fresh generations are byte-identical and match the committed pack", async () => {
    const runA = resolve(tmpdir(), `scoutlens-fixture-a-${Date.now()}`);
    const runB = resolve(tmpdir(), `scoutlens-fixture-b-${Date.now()}`);
    try {
      await generateFixturePack(runA);
      await generateFixturePack(runB);

      const digest = async (root: string) => {
        const manifest = JSON.parse(await readFile(resolve(root, "manifest.json"), "utf8"));
        const entries = manifest.files as Array<{ path: string }>;
        const hashes = await Promise.all(
          entries.map(async (entry) => sha256(await readFile(resolve(root, entry.path), "utf8"))),
        );
        return sha256(hashes.join("\u0000"));
      };

      expect(await digest(runA)).toBe(await digest(runB));
      expect(await digest(runA)).toBe(await digest(fixtureRoot));
      expect(await verifyFixturePack()).toMatchObject({ files: 6, profiles: 1260 });
    } finally {
      await rm(runA, { recursive: true, force: true });
      await rm(runB, { recursive: true, force: true });
    }
  });

  it("keeps the published shareable pack free of fixture identities", async () => {
    const index = await readFile(resolve(publishedRoot, "players.index.json"), "utf8");
    const manifest = await readFile(resolve(publishedRoot, "manifest.json"), "utf8");
    for (const marker of [
      FIXTURE_IDS.maxContent,
      FIXTURE_IDS.uncertaintyAvailable,
      FIXTURE_IDS.uncertaintyInsufficient,
    ]) {
      expect(index).not.toContain(marker);
      expect(manifest).not.toContain(marker);
    }
  });
});
