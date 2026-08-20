/**
 * The visual-baseline pair guard (`scoutlens-uze.11`).
 *
 * The failure this prevents is silent and natural rather than careless: you can
 * only regenerate the platform you are running on, and the half you updated goes
 * green locally while the other half stays stale until CI runs. It cost nine red
 * commits before anyone noticed (`scoutlens-uze.10`), and it happened again
 * during `scoutlens-qop.6.6.4`, where win32 was regenerated an hour before
 * linux.
 *
 * The synthetic paths below are deliberately not read from disk: the guard has
 * to be correct for baselines that do not exist yet, and a test that only
 * exercises today's six snapshots would pass forever without proving anything
 * about the next project someone adds.
 */

import { describe, expect, it } from "vitest";

import {
  BaselinePairError,
  KNOWN_PLATFORMS,
  findUnpairedSnapshots,
  logicalSnapshot,
  parseProjectDirectory,
} from "../scripts/check-visual-baseline-pairs.mjs";

const ROOT = "web/e2e/__screenshots__";

/** Shape returned by the guard for a snapshot missing a platform. The script is
 * plain JavaScript so the test states the contract it relies on. */
interface UnpairedSnapshot {
  key: string;
  changed: string[];
  missing: string[];
}

function pair(project: string, name: string): string[] {
  return (KNOWN_PLATFORMS as string[]).map((platform) => `${ROOT}/${project}-${platform}/${name}`);
}

describe("logical snapshot identity", () => {
  it("treats the two platforms of one snapshot as the same logical snapshot", () => {
    const [linux, win32] = pair("desktop", "neighbor-cards.png") as [string, string];
    expect(logicalSnapshot(linux)!.key).toBe(logicalSnapshot(win32)!.key);
    expect(logicalSnapshot(linux)!.key).toBe("desktop/neighbor-cards.png");
  });

  it("keeps different projects apart even with the same snapshot name", () => {
    const desktop = logicalSnapshot(`${ROOT}/desktop-linux/neighbor-cards.png`)!;
    const mobile = logicalSnapshot(`${ROOT}/mobile-360-linux/neighbor-cards.png`)!;
    expect(desktop.key).not.toBe(mobile.key);
    // A project name may itself contain a hyphen; only the last segment is the
    // platform.
    expect(mobile.project).toBe("mobile-360");
  });

  it("accepts Windows path separators", () => {
    const snapshot = logicalSnapshot(String.raw`web\e2e\__screenshots__\desktop-win32\landing-hero.png`);
    expect(snapshot!.key).toBe("desktop/landing-hero.png");
    expect(snapshot!.platform).toBe("win32");
  });

  it("ignores paths outside the snapshot root", () => {
    expect(logicalSnapshot("web/src/components/lab-explorer.tsx")).toBeNull();
    expect(logicalSnapshot("docs/frontend-agent-contract.md")).toBeNull();
  });
});

describe("malformed input fails closed", () => {
  it("refuses a platform this guard does not know", () => {
    // A new platform is more likely than a directory that is safe to skip, and
    // skipping it would exempt exactly the baselines the guard exists to pair.
    expect(() => parseProjectDirectory("desktop-darwin")).toThrow(BaselinePairError);
    expect(() => logicalSnapshot(`${ROOT}/desktop-darwin/landing-hero.png`)).toThrow(
      /does not know about/,
    );
  });

  it("refuses a directory with no platform suffix", () => {
    expect(() => parseProjectDirectory("desktop")).toThrow(BaselinePairError);
  });

  it("refuses a snapshot path with no directory or no file", () => {
    expect(() => logicalSnapshot(`${ROOT}/landing-hero.png`)).toThrow(BaselinePairError);
    expect(() => logicalSnapshot(`${ROOT}/desktop-linux/`)).toThrow(/names no file/);
  });
});

describe("pairing", () => {
  it("passes when no snapshot changed", () => {
    const result = findUnpairedSnapshots([
      "web/src/components/lab-explorer.tsx",
      "docs/decisions-log.md",
    ]);
    expect(result.snapshotCount).toBe(0);
    expect(result.unpaired).toEqual([]);
  });

  it("passes when both platforms changed together", () => {
    const result = findUnpairedSnapshots(pair("mobile-360", "neighbor-cards.png"));
    expect(result.snapshotCount).toBe(1);
    expect(result.unpaired).toEqual([]);
  });

  it("passes for several complete pairs at once", () => {
    const result = findUnpairedSnapshots([
      ...pair("desktop", "landing-hero.png"),
      ...pair("desktop", "neighbor-cards.png"),
      ...pair("mobile-360", "landing-claims.png"),
      "web/src/app/styles/lab.css",
    ]);
    expect(result.snapshotCount).toBe(3);
    expect(result.unpaired).toEqual([]);
  });

  it("fails a one-platform change and names the missing counterpart", () => {
    // This is the exact shape of the qop.6.6.4 mistake: win32 regenerated,
    // linux forgotten.
    const result = findUnpairedSnapshots([`${ROOT}/mobile-360-win32/neighbor-cards.png`]);
    expect(result.unpaired).toHaveLength(1);
    expect(result.unpaired[0]!.key).toBe("mobile-360/neighbor-cards.png");
    expect(result.unpaired[0]!.missing).toEqual(["linux"]);
  });

  it("lists every missing counterpart rather than stopping at the first", () => {
    const result = findUnpairedSnapshots([
      `${ROOT}/desktop-linux/landing-hero.png`,
      `${ROOT}/mobile-360-win32/neighbor-cards.png`,
      ...pair("desktop", "science-stage-01.png"),
    ]);
    expect(result.snapshotCount).toBe(3);
    expect(result.unpaired.map((entry: UnpairedSnapshot) => entry.key)).toEqual([
      "desktop/landing-hero.png",
      "mobile-360/neighbor-cards.png",
    ]);
    expect(result.unpaired.map((entry: UnpairedSnapshot) => entry.missing.join())).toEqual([
      "win32",
      "linux",
    ]);
  });
});

describe("the guard matches the baselines that exist today", () => {
  it("pairs every committed baseline", async () => {
    // A drift check on the repository itself: if someone adds a project or a
    // platform, the sets stop matching and this fails rather than the guard
    // quietly covering less than it appears to.
    const { readdir } = await import("node:fs/promises");
    const { resolve } = await import("node:path");
    const root = resolve(__dirname, "..", "e2e", "__screenshots__");
    const directories = await readdir(root);

    const byProject = new Map<string, Set<string>>();
    for (const directory of directories) {
      const { project, platform } = parseProjectDirectory(directory);
      const names = await readdir(resolve(root, directory));
      for (const name of names) {
        const key = `${project}/${name}`;
        byProject.set(key, (byProject.get(key) ?? new Set()).add(platform));
      }
    }

    expect(byProject.size).toBeGreaterThan(0);
    const incomplete = [...byProject.entries()]
      .filter(([, platforms]) => platforms.size !== KNOWN_PLATFORMS.length)
      .map(([key]) => key);
    expect(incomplete).toEqual([]);
  });
});
