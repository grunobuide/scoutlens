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
      maxDiffPixelRatio: 0.03,
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
  ],
  projects: [
    {
      name: "desktop",
      testIgnore: /lab-fixtures\.spec\.ts/,
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1280, height: 900 },
      },
    },
    {
      name: "mobile-360",
      testIgnore: /lab-fixtures\.spec\.ts/,
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
  ],
});
