// Capture the portfolio screenshots from the production candidate.
//
//   node scripts/capture-media.mjs [baseUrl]
//
// `scoutlens-jtt.7.3` AC4. Captured from the deployed site by default, so the
// media shows what a reader actually gets rather than what a dev server
// produces — the release audit already found one claim where those differed.
//
// Deterministic by construction: fixed viewports, fixed profile, animations
// disabled, and a wait for the network to settle. A screenshot that changes on
// every run is a diff nobody reads.

import { mkdir } from "node:fs/promises";
import path from "node:path";

import { chromium, devices } from "@playwright/test";

const BASE = process.argv[2] ?? "https://grunobuide.github.io/scoutlens/";
const OUT = path.resolve(process.cwd(), "..", "docs", "media");

// One profile, named, so the media is reproducible and the alt text can be
// specific about what is on screen.
const PROFILE = "wy-8287-c-795";

const SHOTS = [
  {
    name: "lab-desktop",
    url: `lab/?player=${PROFILE}`,
    viewport: { width: 1280, height: 900 },
    fullPage: false,
  },
  {
    // The hero is not the product. This is the evidence surface itself:
    // the retrieval outcome, the per-feature contributions, the neighbours
    // and the caveats that qualify them.
    name: "lab-evidence-desktop",
    url: `lab/?player=${PROFILE}`,
    viewport: { width: 1280, height: 900 },
    scrollTo: "Selected player",
    fullPage: false,
  },
  {
    // Where the claim is actually made and qualified: the retrieval outcome,
    // its uncertainty, and the caveats attached to it.
    name: "lab-retrieval-desktop",
    url: `lab/?player=${PROFILE}`,
    viewport: { width: 1280, height: 1000 },
    scrollTo: "STORED EXPERIMENT REPLAY",
    fullPage: false,
  },
  {
    name: "science-desktop",
    url: "science/",
    viewport: { width: 1280, height: 900 },
    fullPage: false,
  },
  {
    name: "lab-mobile",
    url: `lab/?player=${PROFILE}`,
    device: "iPhone 13",
    fullPage: false,
  },
];

async function main() {
  await mkdir(OUT, { recursive: true });
  const browser = await chromium.launch();

  for (const shot of SHOTS) {
    const contextOptions = shot.device
      ? { ...devices[shot.device] }
      : { viewport: shot.viewport, deviceScaleFactor: 2 };
    const context = await browser.newContext(contextOptions);
    const page = await context.newPage();

    // Motion would make two runs of this script differ for no reason.
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto(new URL(shot.url, BASE).toString(), { waitUntil: "networkidle" });

    if (shot.scrollTo) {
      const target = page.getByText(shot.scrollTo, { exact: false }).first();
      await target.scrollIntoViewIfNeeded();
      // Let the scroll settle; a screenshot mid-scroll is a blurry diff.
      await page.waitForTimeout(400);
    }

    const file = path.join(OUT, `${shot.name}.png`);
    await page.screenshot({ path: file, fullPage: shot.fullPage });
    console.log(`wrote ${path.relative(process.cwd(), file)}`);
    await context.close();
  }

  await browser.close();
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
