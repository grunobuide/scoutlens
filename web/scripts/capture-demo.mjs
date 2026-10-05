// Capture the captioned Fingerprint Lab walkthrough from the deployed site.
//
//   node scripts/capture-demo.mjs [baseUrl] [--out <dir>] [--frames <dir>]
//
// `scoutlens-jtt.20`: the 60-90 second demo `scoutlens-jtt.7.3` AC3 asked for
// and did not deliver. Same posture as `capture-media.mjs`: the deployed site
// by default, one named profile, reduced motion, and a wait for the network to
// settle.
//
// It is assembled from screenshots, not screen-recorded. Playwright's
// `recordVideo` captures at CSS resolution whatever `deviceScaleFactor` says,
// so a 2x recording is a 1x picture padded to 2x. Here every frame is a 2x
// screenshot of the real page in its real state, piped to the ffmpeg build
// Playwright installs beside Chromium. Two consequences, both deliberate:
//
// - The timeline is counted in frames. Holds and scrolls are paced by this
//   script, so the video says nothing about how fast the site responds.
// - With the site unchanged, a re-run should produce the same bytes, as the
//   stills do; the digests in `docs/media/README.md` are how that is checked.
//
// The caption track is written by this script, from the same scene table that
// drives the capture, so a cue cannot drift onto the wrong scene. Before a cue
// starts, every string its scene names must have a visible occurrence fully
// inside the frame, or the run fails and nothing is written.
//
// Media is illustration, never the source of a number: every figure a caption
// writes in digits must appear in a string its own scene asserts is on screen.
// That, the reading rate and the required surfaces are checked before a
// browser opens.

import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, readdirSync } from "node:fs";
import { mkdir, mkdtemp, readFile, rename, rm, writeFile } from "node:fs/promises";
import { once } from "node:events";
import { createRequire } from "node:module";
import os from "node:os";
import path from "node:path";

import { chromium } from "@playwright/test";

const args = process.argv.slice(2);
const option = (name) => {
  const index = args.indexOf(name);
  if (index === -1) return undefined;
  const [, value] = args.splice(index, 2);
  return value;
};
const OUT = path.resolve(option("--out") ?? path.join(process.cwd(), "..", "docs", "media"));
const FRAMES = option("--frames");
const BASE = args[0] ?? "https://grunobuide.github.io/scoutlens/";

const NAME = "lab-walkthrough";
const PROFILE = "wy-8287-c-795";

// Legibility is decided here, not left to the player. The page is laid out at
// the embed width itself and captured at 2x, so an EMBED_WIDTH-wide embed shows
// every CSS pixel at its own size, from a source sharp enough for a 2x screen.
const VIEWPORT = { width: 800, height: 540 };
const DEVICE_SCALE = 2;
const VIDEO = { width: VIEWPORT.width * DEVICE_SCALE, height: VIEWPORT.height * DEVICE_SCALE };
const EMBED_WIDTH = 800;
const MIN_EMBED_TEXT_PX = 10;

const FPS = 25;
const MIN_SECONDS = 60;
const MAX_SECONDS = 90;
// 180 words a minute, the fast end of what caption guidance allows.
const MAX_WORDS_PER_SECOND = 3;
const REQUIRED_SURFACES = ["fingerprint", "retrieval", "neighbors", "uncertainty", "caveat"];

// The first *visible* match, so a screen-reader-only announcer that repeats the
// same words can never stand in for what the camera sees.
const text = (root, value) => root.getByText(value, { exact: false }).filter({ visible: true }).first();

const SCENES = [
  {
    id: "boundary",
    surfaces: ["caveat"],
    hold: 6000,
    act: async ({ page }) => {
      await page.goto(new URL(`lab/?player=${PROFILE}`, BASE).toString(), { waitUntil: "networkidle" });
    },
    expect: ["Compare one player with himself.", "This is a statistical fingerprint"],
    caption: "The Fingerprint Lab opens with its limit: a statistical fingerprint, not a rating or a recommendation.",
  },
  {
    id: "question",
    surfaces: ["caveat"],
    hold: 6000,
    act: async (film) => {
      await film.glideTo(text(film.page, "Can a player's actions identify them?"));
    },
    expect: ["Can a player's actions identify them?", "32 measurements of how they act", "not proof of playing style"],
    caption: "The question: can 32 measurements from the first half-season find the same player in the second?",
  },
  {
    id: "query",
    surfaces: ["fingerprint"],
    hold: 5500,
    act: async (film) => {
      await film.press(film.page.getByRole("button", { name: "See the fingerprint" }));
      await film.glideTo(text(film.page, "One player's first-half fingerprint"));
    },
    expect: ["One player's first-half fingerprint", "First chronological half"],
    caption: "Period A is the query: one player's first-half fingerprint, without the name.",
  },
  {
    id: "reveal",
    surfaces: ["retrieval"],
    hold: 6500,
    act: async (film) => {
      await film.press(film.page.getByRole("button", { name: "Reveal the result" }));
      await film.glideTo(text(film.page, "The fingerprint found them at rank"));
    },
    expect: ["The fingerprint found them at rank 1 of", "Role-and-minutes baseline", "249"],
    caption:
      "Against every eligible second-half profile, the fingerprint ranks him first. A role-and-minutes control ranks him 249th.",
  },
  {
    id: "interval",
    surfaces: ["uncertainty"],
    hold: 6000,
    act: async () => {},
    expect: ["95% resampling interval 1–43.5"],
    caption: "The 95% resampling interval, 1–43.5: how stable that rank is across observed matches. Not a forecast.",
  },
  {
    id: "contributions",
    surfaces: ["fingerprint"],
    hold: 6000,
    act: async (film) => {
      await film.press(film.page.getByRole("button", { name: "See the evidence" }));
      await film.glideTo(text(film.page, "Weights are fitted for"), 140);
    },
    expect: ["Weights are fitted for 28 of the 32 displayed"],
    caption: "What drove the match: each measurement's contribution, under learned weights fitted for 28 of the 32.",
  },
  {
    id: "replay",
    surfaces: ["retrieval", "uncertainty"],
    hold: 6500,
    act: async (film) => {
      await film.press(film.page.getByRole("link", { name: "Explore every fingerprint" }));
      await film.glideTo(text(film.page, "Identity retrieval, one query at a time"));
    },
    expect: ["Identity retrieval, one query at a time", "Context-only control", "Available from 500 valid resamples"],
    caption: "The Lab replays the stored result for every profile, beside a context-only control, each with its interval.",
  },
  {
    id: "map",
    surfaces: ["fingerprint"],
    hold: 6000,
    act: async (film) => {
      await film.glideTo(text(film.page, "Period A / B fingerprint"));
    },
    expect: ["Period A / B fingerprint", "32 features across 8 families"],
    caption: "The full map compares period A with period B across 32 features in 8 families.",
  },
  {
    id: "caveats",
    surfaces: ["caveat"],
    hold: 6000,
    act: async (film) => {
      await film.glideTo(text(film.page, "Evidence boundaries"));
    },
    expect: ["Evidence boundaries", "Same-season club continuity is a strong confound"],
    caption: "The caveats ship with the result. The strongest: same-season club continuity can make this test easier.",
  },
  {
    id: "neighbors",
    surfaces: ["neighbors", "caveat"],
    hold: 6500,
    act: async (film) => {
      await film.glideTo(text(film.page, "Five other period-B profiles"), 56);
    },
    expect: [
      "Five other period-B profiles",
      "within the same nominal role",
      "must not be read as a recruitment recommendation",
    ],
    caption:
      "The nearest profiles in the same role, the query player excluded. Proximity is descriptive, not a recruitment recommendation.",
  },
  {
    id: "comparison",
    surfaces: ["neighbors"],
    hold: 6500,
    act: async (film) => {
      await film.press(film.page.getByRole("button", { name: "Open evidence comparison" }).first());
      await film.page.getByRole("dialog").waitFor({ state: "visible" });
    },
    within: (page) => page.getByRole("dialog"),
    expect: ["Period A query / period B neighbor", "Eight-family reconstruction"],
    caption: "Each neighbor opens its evidence: the stored similarity, rebuilt family by family.",
  },
];

// Figures written in digits, taken whole: "1–43.5", "95%", and "249" out of
// "249th". Compared as tokens, so a caption's "4" is not satisfied by the 4
// inside an on-screen "43.5".
const figures = (value) =>
  new Set((value.match(/\d[\d,.]*(?:[–/-]\d[\d,.]*)?%?/g) ?? []).map((token) => token.replace(/[.,]+$/, "")));

// Everything that can be checked without a browser, checked first.
function checkSceneTable() {
  const problems = [];
  for (const scene of SCENES) {
    const onScreen = figures(scene.expect.join(" "));
    for (const figure of figures(scene.caption)) {
      if (!onScreen.has(figure)) problems.push(`${scene.id}: caption figure "${figure}" is not asserted on screen`);
    }
    // WebVTT reads "<" and "&" as markup, and "-->" as a timing line.
    if (/[<&]|-->/.test(scene.caption)) problems.push(`${scene.id}: caption contains WebVTT markup characters`);
    const words = scene.caption.split(/\s+/).length;
    if (words / (scene.hold / 1000) > MAX_WORDS_PER_SECOND) {
      problems.push(`${scene.id}: ${words} words in ${scene.hold} ms is faster than ${MAX_WORDS_PER_SECOND} words a second`);
    }
  }
  const covered = new Set(SCENES.flatMap((scene) => scene.surfaces));
  for (const surface of REQUIRED_SURFACES) {
    if (!covered.has(surface)) problems.push(`no scene shows the ${surface} surface`);
  }
  if (problems.length > 0) throw new Error(`scene table rejected:\n  ${problems.join("\n  ")}`);
}

// Playwright installs this ffmpeg beside Chromium (`playwright install
// chromium`). `FFMPEG` overrides it; any other build encodes the same scenes
// but not necessarily the same bytes.
function findFfmpeg() {
  if (process.env.FFMPEG) return process.env.FFMPEG;
  const binary = { win32: "ffmpeg-win64.exe", linux: "ffmpeg-linux", darwin: "ffmpeg-mac" }[process.platform];
  const configured = process.env.PLAYWRIGHT_BROWSERS_PATH;
  const cache =
    configured === "0"
      ? path.join(path.dirname(createRequire(import.meta.url).resolve("playwright-core/package.json")), ".local-browsers")
      : (configured ??
        {
          win32: path.join(process.env.LOCALAPPDATA ?? "", "ms-playwright"),
          linux: path.join(os.homedir(), ".cache", "ms-playwright"),
          darwin: path.join(os.homedir(), "Library", "Caches", "ms-playwright"),
        }[process.platform]);
  const builds = existsSync(cache)
    ? readdirSync(cache)
        .filter((entry) => /^ffmpeg-\d+$/.test(entry))
        .sort((a, b) => Number(b.slice(7)) - Number(a.slice(7)))
    : [];
  for (const build of builds) {
    const candidate = path.join(cache, build, binary);
    if (existsSync(candidate)) return candidate;
  }
  throw new Error(`no Playwright ffmpeg under ${cache}: run \`pnpm exec playwright install chromium\` or set FFMPEG`);
}

// Width and height from a JPEG's start-of-frame segment.
function jpegSize(buffer) {
  let offset = 2;
  while (offset + 9 < buffer.length && buffer[offset] === 0xff) {
    const marker = buffer[offset + 1];
    if (marker >= 0xc0 && marker <= 0xcf && ![0xc4, 0xc8, 0xcc].includes(marker)) {
      return { width: buffer.readUInt16BE(offset + 7), height: buffer.readUInt16BE(offset + 5) };
    }
    offset += 2 + buffer.readUInt16BE(offset + 2);
  }
  throw new Error("screenshot is not a baseline or progressive JPEG");
}

class Film {
  constructor(page, encoder) {
    this.page = page;
    this.encoder = encoder;
    this.frames = 0;
  }

  get ms() {
    return (this.frames * 1000) / FPS;
  }

  async shoot() {
    const jpeg = await this.page.screenshot({ type: "jpeg", quality: 95 });
    const size = jpegSize(jpeg);
    if (size.width !== VIDEO.width || size.height !== VIDEO.height) {
      throw new Error(`frame is ${size.width}x${size.height}, expected ${VIDEO.width}x${VIDEO.height}`);
    }
    return jpeg;
  }

  async emit(jpeg, count) {
    for (let index = 0; index < count; index += 1) {
      if (!this.encoder.stdin.write(jpeg)) await once(this.encoder.stdin, "drain");
    }
    this.frames += count;
  }

  async hold(ms) {
    const jpeg = await this.shoot();
    await this.emit(jpeg, Math.round((ms * FPS) / 1000));
    return jpeg;
  }

  // Scroll until `locator` sits `offset` CSS pixels below the top of the
  // frame, one frame per step. Reduced motion turns the site's own smooth
  // scrolling off; this is the camera moving, not the page animating.
  async glideTo(locator, offset = 24) {
    const box = await locator.boundingBox();
    if (box === null) throw new Error("glideTo: target is not rendered");
    const distance = box.y - offset;
    const steps = Math.min(12, Math.max(6, Math.round(Math.abs(distance) / 40)));
    if (Math.abs(distance) < 1) return;
    for (let step = 1; step <= steps; step += 1) {
      await this.page.evaluate((dy) => window.scrollBy(0, dy), distance / steps);
      await this.emit(await this.shoot(), 1);
    }
  }

  // Bring a control into frame, let it be seen, then use it. The pointer is
  // parked afterwards so a hover style never lingers into the next scene.
  async press(locator) {
    const box = await locator.boundingBox();
    if (box === null) throw new Error("press: control is not rendered");
    if (box.y < 0 || box.y + box.height > VIEWPORT.height) {
      await this.glideTo(locator, Math.round(VIEWPORT.height * 0.6));
    }
    await this.hold(600);
    await locator.click();
    await this.page.mouse.move(0, 0);
  }
}

const insideViewport = (box) =>
  box !== null &&
  box.x >= 0 &&
  box.y >= 0 &&
  box.x + box.width <= VIEWPORT.width &&
  box.y + box.height <= VIEWPORT.height;

// Every named string must have a visible occurrence fully inside the frame -
// not merely somewhere on the page, since the Lab repeats its caveats in more
// than one panel - and that occurrence must be big enough to read once the
// video is shown at EMBED_WIDTH.
async function assertOnScreen(page, scene) {
  const embedScale = EMBED_WIDTH / VIEWPORT.width;
  const root = scene.within?.(page) ?? page;
  const sizes = [];
  for (const value of scene.expect) {
    await text(root, value).waitFor({ state: "visible", timeout: 15_000 });
    const boxes = [];
    let onScreen = null;
    for (const match of await root.getByText(value, { exact: false }).filter({ visible: true }).all()) {
      const box = await match.boundingBox();
      boxes.push(box);
      if (insideViewport(box)) {
        onScreen = match;
        break;
      }
    }
    if (onScreen === null) {
      throw new Error(`${scene.id}: no occurrence of "${value}" is fully inside the frame (${JSON.stringify(boxes)})`);
    }
    const fontSize = await onScreen.evaluate((element) => Number.parseFloat(getComputedStyle(element).fontSize));
    const atEmbed = fontSize * embedScale;
    if (atEmbed < MIN_EMBED_TEXT_PX) {
      throw new Error(`${scene.id}: "${value}" renders at ${atEmbed.toFixed(1)}px in an ${EMBED_WIDTH}px embed`);
    }
    sizes.push(atEmbed);
  }
  return sizes;
}

const timestamp = (ms) => {
  const total = Math.round(ms);
  const h = String(Math.floor(total / 3_600_000)).padStart(2, "0");
  const m = String(Math.floor(total / 60_000) % 60).padStart(2, "0");
  const s = String(Math.floor(total / 1000) % 60).padStart(2, "0");
  return `${h}:${m}:${s}.${String(total % 1000).padStart(3, "0")}`;
};

function webvtt(cues, buildId, smallest) {
  const lines = [
    "WEBVTT",
    "",
    "NOTE",
    `Written by web/scripts/capture-demo.mjs (scoutlens-jtt.20) from deployed commit ${buildId}.`,
    `Frame: ${VIEWPORT.width}x${VIEWPORT.height} CSS px at ${DEVICE_SCALE}x = ${VIDEO.width}x${VIDEO.height}, ${FPS} fps.`,
    `Smallest asserted text: ${smallest.toFixed(1)} px in an ${EMBED_WIDTH} px embed.`,
    "Cue identifiers name the scene. A cue starts only after its scene's on-screen text was asserted.",
    "",
  ];
  for (const cue of cues) lines.push(cue.id, `${timestamp(cue.start)} --> ${timestamp(cue.end)}`, cue.caption, "");
  return lines.join("\n");
}

// Read duration and frame size back from the encoded file, not from the plan.
async function probe(ffmpeg, file) {
  const child = spawn(ffmpeg, ["-hide_banner", "-i", file], { stdio: ["ignore", "ignore", "pipe"] });
  let stderr = "";
  child.stderr.on("data", (chunk) => (stderr += chunk));
  await once(child, "close");
  const duration = stderr.match(/Duration: (\d+):(\d+):(\d+\.\d+)/);
  const size = stderr.match(/Video: vp8\b.*?, (\d+)x(\d+)/);
  if (!duration || !size) throw new Error(`could not probe ${file}:\n${stderr}`);
  return {
    seconds: Number(duration[1]) * 3600 + Number(duration[2]) * 60 + Number(duration[3]),
    width: Number(size[1]),
    height: Number(size[2]),
  };
}

async function main() {
  checkSceneTable();
  const ffmpeg = findFfmpeg();
  const scratch = await mkdtemp(path.join(os.tmpdir(), "scoutlens-demo-"));
  const draft = path.join(scratch, `${NAME}.webm`);
  // Single-threaded, bit-exact, input metadata dropped: the encoder adds
  // nothing that varies between two runs over the same frames.
  const encoder = spawn(
    ffmpeg,
    [
      ...["-hide_banner", "-loglevel", "error"],
      ...["-f", "image2pipe", "-framerate", String(FPS), "-c:v", "mjpeg", "-i", "pipe:0"],
      ...["-an", "-c:v", "libvpx", "-pix_fmt", "yuv420p", "-deadline", "good", "-cpu-used", "0"],
      ...["-crf", "16", "-b:v", "1M", "-qmin", "0", "-qmax", "50", "-g", String(FPS * 20), "-threads", "1"],
      ...["-fflags", "+bitexact", "-flags:v", "+bitexact", "-map_metadata", "-1", "-f", "webm", "-y", draft],
    ],
    { stdio: ["pipe", "ignore", "inherit"] },
  );
  const encoded = once(encoder, "close");

  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: VIEWPORT, deviceScaleFactor: DEVICE_SCALE, reducedMotion: "reduce" });
  const page = await context.newPage();
  const film = new Film(page, encoder);
  const cues = [];
  const legibility = [];
  let buildId;
  try {
    for (const scene of SCENES) {
      await scene.act(film);
      buildId ??= (await page.content()).match(/\\?"b\\?":\\?"([0-9a-f]{40})\\?"/)?.[1];
      legibility.push(...(await assertOnScreen(page, scene)));
      const start = film.ms;
      const jpeg = await film.hold(scene.hold);
      cues.push({ id: scene.id, start, end: film.ms, caption: scene.caption });
      if (FRAMES) {
        await mkdir(FRAMES, { recursive: true });
        await writeFile(path.join(FRAMES, `${String(cues.length).padStart(2, "0")}-${scene.id}.jpg`), jpeg);
      }
    }
  } finally {
    encoder.stdin.end();
    await context.close();
    await browser.close();
  }
  const [code] = await encoded;
  if (code !== 0) throw new Error(`ffmpeg exited with ${code}`);
  if (buildId === undefined) throw new Error("the served page did not name the commit that built it");

  const video = await probe(ffmpeg, draft);
  if (video.width !== VIDEO.width || video.height !== VIDEO.height) {
    throw new Error(`encoded ${video.width}x${video.height}, expected ${VIDEO.width}x${VIDEO.height}`);
  }
  if (Math.abs(video.seconds - film.ms / 1000) > 0.1) {
    throw new Error(`encoded ${video.seconds}s, but the timeline is ${(film.ms / 1000).toFixed(2)}s`);
  }
  if (video.seconds < MIN_SECONDS || video.seconds > MAX_SECONDS) {
    throw new Error(`walkthrough is ${video.seconds}s, outside ${MIN_SECONDS}-${MAX_SECONDS}s`);
  }

  await mkdir(OUT, { recursive: true });
  const files = [path.join(OUT, `${NAME}.webm`), path.join(OUT, `${NAME}.vtt`)];
  await rename(draft, files[0]).catch(async () => writeFile(files[0], await readFile(draft)));
  await writeFile(files[1], webvtt(cues, buildId, Math.min(...legibility)));
  await rm(scratch, { recursive: true, force: true });

  console.log(`deployed commit  ${buildId}`);
  console.log(`encoded          ${video.seconds.toFixed(2)}s, ${film.frames} frames at ${FPS} fps`);
  console.log(`frame            ${video.width}x${video.height} = ${VIEWPORT.width}x${VIEWPORT.height} CSS px at ${DEVICE_SCALE}x`);
  console.log(`smallest text    ${Math.min(...legibility).toFixed(1)}px in an ${EMBED_WIDTH}px embed`);
  for (const file of files) {
    const digest = createHash("sha256").update(await readFile(file)).digest("hex");
    console.log(`${digest}  ${path.basename(file)}`);
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
