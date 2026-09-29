import { defineConfig, devices, type Project } from "@playwright/test";

// scoutlens-uze.6 asserts responsive geometry against the delegated fixture
// export at exactly these widths (320, 360, 768 and 1280 CSS pixels).
const FIXTURE_VIEWPORTS = [
  { width: 320, height: 800 },
  { width: 360, height: 800 },
  { width: 768, height: 900 },
  { width: 1280, height: 900 },
] as const;

export default defineConfig({
  testDir: "./e2e",
  outputDir: "./test-results",
  snapshotPathTemplate: "{testDir}/__screenshots__/{projectName}-{platform}/{arg}{ext}",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  expect: {
    toHaveScreenshot: {
      animations: "disabled",
      // Set from measurement, not from a round number (`scoutlens-uze.19`).
      //
      // It was 0.03, and at 0.03 the gate did not notice the site wordmark
      // changing on every page. Every figure below is Playwright's own
      // arithmetic, taken by running the suite at `maxDiffPixelRatio: 0`:
      //
      //   run-to-run, same machine                 0.00000
      //   CI render vs pinned container, same      0.00043   <- the floor
      //     platform, content unchanged
      //   landing-claims, desktop                  0.00562
      //   landing-hero, desktop                    0.00603 / 0.00749
      //   science-stage-01, desktop                0.00964 / 0.01049
      //   science-stage-01, mobile-360             0.01252 / 0.01530
      //   landing-hero, mobile-360                 0.02370 / 0.02479
      //
      // (win32 / linux where both were measured.)
      //
      // Two things that fixes. Nothing on that list was caught, including a
      // full rename of the site. And `landing-hero` at mobile-360 had reached
      // 83% of the old budget, so the gate was also about to go red for
      // reasons nobody would have connected to a change three beads earlier.
      //
      // 0.002 is ~4.6x the measured environment floor and ~2.8x below the
      // smallest real change in the list. The floor is what the tolerance is
      // actually for: run-to-run variance on one machine is zero, so the only
      // thing it must absorb is CI rendering one monospace chip differently
      // from the container the frontend contract pins for regenerating
      // baselines (`scoutlens-uze.14`).
      //
      // May only move down (frontend contract section 5.5). If it ever has to
      // move up, that is a finding about the two environments, not a budget
      // decision.
      maxDiffPixelRatio: 0.002,
    },
  },
  use: {
    baseURL: "http://127.0.0.1:4173",
    colorScheme: "light",
    locale: "en-US",
    screenshot: "only-on-failure",
    timezoneId: "UTC",
    trace: "retain-on-failure",
    video: "retain-on-failure",
  },
  webServer: [
    {
      command: "node scripts/serve-static.mjs --port 4173",
      reuseExistingServer: false,
      timeout: 30_000,
      url: "http://127.0.0.1:4173/lab/",
    },
    // Delegated fixture export (scoutlens-uze.7): deterministic maximum-content
    // and uncertainty-state Lab fixtures served from web/out-fixtures/<fixture>.
    // Built by `pnpm build:fixtures` after `pnpm build`; never touches web/out.
    {
      command: "node scripts/serve-static.mjs --port 4174 --root out-fixtures/lab-max-content",
      reuseExistingServer: false,
      timeout: 30_000,
      url: "http://127.0.0.1:4174/lab/",
    },
    // Diagonal Lab gate (scoutlens-qop.6.5): the same delegated mechanism, one
    // major up. Served separately rather than swapped in, so the v1 fixture
    // gate keeps running unchanged and a v2 regression cannot be mistaken for
    // a v1 one.
    {
      command: "node scripts/serve-static.mjs --port 4175 --root out-fixtures/lab-max-content-v2",
      reuseExistingServer: false,
      timeout: 30_000,
      url: "http://127.0.0.1:4175/lab/",
    },
  ],
  projects: [
    {
      name: "desktop",
      testIgnore: /lab-fixtures\.spec\.ts|lab-v2-diagonal\.spec\.ts/,
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1280, height: 900 },
      },
    },
    {
      name: "mobile-360",
      testIgnore: /lab-fixtures\.spec\.ts|lab-v2-diagonal\.spec\.ts/,
      use: {
        browserName: "chromium",
        deviceScaleFactor: 1,
        hasTouch: true,
        isMobile: true,
        viewport: { width: 360, height: 800 },
      },
    },
    ...FIXTURE_VIEWPORTS.map(
      (viewport): Project => ({
        name: `fixtures-${viewport.width}`,
        testMatch: /lab-fixtures\.spec\.ts/,
        use: {
          browserName: "chromium",
          deviceScaleFactor: 1,
          hasTouch: viewport.width < 600,
          isMobile: viewport.width < 600,
          viewport: { width: viewport.width, height: viewport.height },
          baseURL: "http://127.0.0.1:4174",
        },
      }),
    ),
    ...FIXTURE_VIEWPORTS.map(
      (viewport): Project => ({
        name: `fixtures-v2-${viewport.width}`,
        testMatch: /lab-v2-diagonal\.spec\.ts/,
        use: {
          browserName: "chromium",
          deviceScaleFactor: 1,
          hasTouch: viewport.width < 600,
          isMobile: viewport.width < 600,
          viewport: { width: viewport.width, height: viewport.height },
          baseURL: "http://127.0.0.1:4175",
        },
      }),
    ),
  ],
});
