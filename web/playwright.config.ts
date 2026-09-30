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
      // An ABSOLUTE pixel budget, not a ratio (`scoutlens-uze.19`).
      //
      // The first attempt at this used `maxDiffPixelRatio: 0.002` and CI went
      // red. The reason is the instrument, not the number. The only difference
      // this gate has to tolerate is CI rendering one monospace element with a
      // different font stack from the `v1.62.0-noble` container the frontend
      // contract pins for regenerating baselines. That artefact is roughly
      // CONSTANT IN PIXELS — about 1,052 of them — because it is one piece of
      // text. A ratio divides by image area, so the same artefact reads as
      // 0.0009 on a 1,280x900 desktop shot and 0.0037 on a 360x800 mobile one.
      // No single ratio can sit above the second and below a real change.
      //
      // Measured, all in Playwright's own arithmetic:
      //
      //   run-to-run, same machine                    0 px
      //   CI vs container, desktop, content unchanged      497 px
      //   CI vs container, mobile-360, content unchanged  1052 px   <- the floor
      //   science-stage-01, mobile-360 (wordmark + space)  3605 px
      //   landing-claims, desktop (wordmark)               6474 px
      //   landing-hero, mobile-360 (wordmark)              6825 px
      //   landing-hero, desktop (wordmark)                 6944 px
      //   science-stage-01, desktop (wordmark + space)    11099 px
      //
      // The old value was `maxDiffPixelRatio: 0.03`, which on the mobile shots
      // was a budget of 8,640 pixels — larger than any content change in that
      // list, which is how a rename of the site wordmark passed unnoticed.
      //
      // **The floor is now zero** (`scoutlens-uze.24`). `scoutlens-uze.23` moved
      // `web-quality` into the pinned image, so CI and the environment that
      // regenerates baselines are one renderer. Re-measured in CI at a budget of
      // 0: every baseline in the suite matched exactly except
      // `desktop-linux/retrieval-neighbors.png`, which was still rendered by the
      // old CI environment and differed by 497 px on the one monospace element
      // that ever differed. Re-rendering it left nothing above zero.
      //
      // So 250 is **not** a measured requirement — it is headroom for jitter
      // that has never been observed. Run-to-run on one machine is 0, and CI's
      // run and its automatic retry produced byte-identical images. It is 14x
      // below the smallest real content change ever measured here (3,605 px).
      //
      // If this ever has to move up, that is a finding about the renderer, not
      // a budget decision — record what changed before touching it.
      //
      // Only one of `maxDiffPixels` / `maxDiffPixelRatio` is set on purpose:
      // Playwright treats each as an independent limit, so setting both would
      // reintroduce the area-scaled one as a hidden second gate.
      maxDiffPixels: 250,
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
