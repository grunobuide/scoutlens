declare module "*.mjs" {
  export const fixtureDirectory: () => string;
  export function generateFixturePack(fixtureDir?: string): Promise<void>;
  export function verifyFixturePack(fixtureDir?: string): Promise<{
    fixtureRoot: string;
    files: number;
    profiles: number;
  }>;
  export const FIXTURE_MARKERS: readonly string[];
  export const SYNTHETIC_PROFILE_KEYS: readonly string[];

  // scoutlens-uze.11, check-visual-baseline-pairs.mjs. The wildcard above
  // covers every .mjs import from tests, so a new script's exports have to be
  // declared here or they resolve to nothing.
  export const KNOWN_PLATFORMS: readonly string[];
  export class BaselinePairError extends Error {}
  export function parseProjectDirectory(directory: string): {
    project: string;
    platform: string;
  };
  export function logicalSnapshot(path: string): {
    key: string;
    project: string;
    platform: string;
    name: string;
    path: string;
  } | null;
  export function findUnpairedSnapshots(paths: readonly string[]): {
    snapshotCount: number;
    unpaired: Array<{ key: string; changed: string[]; missing: string[] }>;
  };
}
