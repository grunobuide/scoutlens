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
}
