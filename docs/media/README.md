# Media

Captured from the **deployed site**, not a dev server, by
`web/scripts/capture-media.mjs`:

```bash
cd web && node scripts/capture-media.mjs            # live production
cd web && node scripts/capture-media.mjs http://127.0.0.1:4173/   # a local build
```

Capturing from production is deliberate. The release audit already found one
claim — asset cache headers — where the local server and the real host disagreed,
and media is exactly the kind of artifact that quietly documents a version nobody
ships.

Deterministic by construction: fixed viewports, one named profile
(`wy-8287-c-795`), reduced motion, and a wait for the network to settle. Re-runs
differ only when the site does.

The captioned video beside the stills has its own script and provenance; see
[Walkthrough](#walkthrough).

## Provenance of the stills

| | |
|---|---|
| Source commit | `d79e3362c9e9424ec1412a2661e66a6d389e1b0e` — read from the served page, not inferred (`scoutlens-uze.20`) |
| Deployed by | `deploy` run [36475145629](https://github.com/grunobuide/scoutlens/actions/runs/36475145629), 2026-09-28, smoke 10/10 |
| Captured from | <https://grunobuide.github.io/scoutlens/> |
| Command | `node scripts/capture-media.mjs https://grunobuide.github.io/scoutlens/` |
| Profile | `wy-8287-c-795` (L. Modrić, Spanish first division, 2017/18) |
| Desktop | 1280×900 at `deviceScaleFactor: 2`; the retrieval shot uses 1280×1000 |
| Mobile | Playwright's `iPhone 13` device profile |

```
68237814b27eab04ceb455d3178122608024cb6dfad272c7332c7ef2b3050234  lab-desktop.png
9f0384b0658457ce3a2da088672f56dbeb5c6260d354419741b3dd0dc36f45f9  lab-evidence-desktop.png
eee62b579fbbc2f3a979ce659ff6c086467dd8bef988538155df481b567a5c14  lab-retrieval-desktop.png
0d21c9235206f4da346b9a1ea56ad8dd8860ec80edd908f98727050c7f68b3ef  science-desktop.png
386947bf7ce30cc97d60be27014a22e17525193310dbca7fb64bee46e5ba0eda  lab-mobile.png
```

**Four of these five are byte-identical to the previous capture.** Only
`science-desktop.png` moved, because only `/science` changed between the two
deployments. Unchanged digests here are evidence, not a failed capture: the
determinism claim above says re-runs differ only when the site does, and this is
that claim being checked rather than asserted.

The same held for the rename capture before it, where the two shots scrolled
past the site header came back identical because the wordmark was not in frame.

## Walkthrough

`lab-walkthrough.webm` is a 76-second captioned walkthrough of the Fingerprint
Lab; `lab-walkthrough.vtt` is its caption track (`scoutlens-jtt.20`). Both are
written by `web/scripts/capture-demo.mjs`, from the deployed site:

```bash
cd web && node scripts/capture-demo.mjs            # live production
cd web && node scripts/capture-demo.mjs http://127.0.0.1:4173/   # a local build
```

It needs the Chromium and the ffmpeg build Playwright installs together
(`pnpm exec playwright install chromium`). `FFMPEG=<path>` selects another
ffmpeg, which encodes the same frames but not necessarily the same bytes.

One profile, on one page: from the Lab's opening statement, through its identity
challenge, and on into the explorer below it. The cue identifiers in the caption
file are the scene names:

| Cue | Shows | On screen |
|---|---|---|
| `boundary` | caveat | The Lab's opening statement of what the fingerprint is not |
| `question` | caveat | The identity challenge's question, and its not-proof-of-style caveat |
| `query` | fingerprint | Period A's fingerprint, the name withheld |
| `reveal` | retrieval | The rank among eligible second-half profiles, beside the role-and-minutes control |
| `interval` | uncertainty | The 95% resampling interval on that rank |
| `contributions` | fingerprint | Per-measurement contributions under the learned weights |
| `replay` | retrieval, uncertainty | The stored replay: global, within role, and the context-only control |
| `map` | fingerprint | The period A/B map's header (32 features, 8 families) and its first family |
| `caveats` | caveat | The evidence boundaries |
| `neighbors` | neighbors, caveat | The first two of five nearest same-role profiles, under their boundary |
| `comparison` | neighbors | The top of one neighbor's evidence drawer |

The caption file is the transcript: plain text, reviewable in a diff, and not
burned into the pixels.

### How it is made, and what follows from that

**Assembled from screenshots, not screen-recorded.** Playwright's
`recordVideo` captures at CSS resolution whatever `deviceScaleFactor` says; a
first attempt came back as an 800×540 picture padded with grey to 1600×1080.
Every frame here is instead a 2× screenshot of the real page, in the state a
real click or scroll left it, encoded to VP8 by the ffmpeg build Playwright
ships.

**The pacing is the script's, not the site's.** Holds and scrolls are counted
in frames at 25 fps. The video shows what each state looks like, not how long
the site takes to reach it; load time is not represented at all.

**A caption cannot drift onto the wrong screen.** The caption file is written
by the same scene table that drives the capture. Before a cue starts, every
string its scene names must have a visible occurrence fully inside the frame,
or the run fails and writes nothing. Every figure a caption writes in digits
must appear, as a whole token, in a string its own scene asserts is on screen —
the video is illustration, never the source of a number — and no caption asks
for more than three words a second.

**Legible at embed size, by construction.** The page is laid out at 800×540 CSS
pixels and captured at 2×, 1600×1080. Embedded 800 pixels wide, every CSS pixel
shows at its own size — text looks exactly as large as in an 800-pixel-wide
browser window — from a source sharp enough for a 2× screen. The smallest text
any scene asserts renders at 10.9 px there, and the script refuses anything
under 10 px. A wider embed only enlarges it.

### Provenance

| | |
|---|---|
| Source commit | `a79868f49cc82cacb51969aef7a9527925e9fee1` — read from the served page by the script, and written into the caption file's header |
| Deployed by | `deploy` run [36933101622](https://github.com/grunobuide/scoutlens/actions/runs/36933101622), 2026-10-01, smoke 10/10 |
| Captured from | <https://grunobuide.github.io/scoutlens/>, 2026-10-05 |
| Command | `node scripts/capture-demo.mjs` |
| Profile | `wy-8287-c-795` (L. Modrić, Spanish first division, 2017/18) |
| Frame | 800×540 CSS px at `deviceScaleFactor: 2` = 1600×1080, 25 fps, VP8 in WebM, no audio |
| Length | 75.72 s probed back from the encoded file, not taken from the plan; 1,893 frames as written to the encoder |
| Browser | Chromium 151.0.7922.34 (`@playwright/test` 1.62.0), Windows 11 |
| Encoder | ffmpeg `n7.0.1-playwright-build-1011`, single-threaded, bit-exact, input metadata dropped |
| Size | 3.7 MiB |

```
1c9fd1f1d2aa110a64749ab12dc7b5aa3ae7c712b782701d0088b542832a03d6  lab-walkthrough.webm
3719af54858b6995635a3dfd088bd82108c95fec69243f4b09627b7b04fc2b8d  lab-walkthrough.vtt
```

**The video is byte-identical across runs — on the same toolchain.** Every pair
of captures made by the same version of the script against this deployment, on
this machine, produced the same `lab-walkthrough.webm` down to the digest; that
held for each of the three versions tried while this one was written, the
committed one included. The bytes depend on more than the site:
another OS, Chromium build or ffmpeg build rasterises or encodes the same page
differently, as this repository's separate Windows and Linux visual baselines
already show for the stills. The caption file also changes on every deploy,
because its header names the deployed commit.

So a re-capture on the same toolchain against an unchanged site stores nothing
new in git; a site change, or a capture on a different toolchain, adds a blob of
about this size.

**Why it is in the repository and not a release asset.** 3.7 MiB, against a
packed repository of about 19 MiB. The bead allowed a release asset if size
forbade a commit; nothing does yet, and keeping the video next to its caption
file keeps the pair reviewable in one place. If re-captures ever push this
directory's history past roughly 15 MiB, move the video to a release asset and
keep the caption file here.

### Embedding

```html
<video controls preload="metadata" width="800" src="lab-walkthrough.webm">
  <track kind="captions" src="lab-walkthrough.vtt" srclang="en" label="English" default>
</video>
```

GitHub does not play a video committed to the repository tree, so on GitHub it
is a link; it plays where it is embedded with the track beside it. WebM with VP8
is the only container and codec the bundled ffmpeg writes. An embed that must
reach a browser without WebM support needs a transcode, and that copy is then no
longer the one these digests describe.

### Three things in frame that are known defects

- The `comparison` drawer heads its breakdown "Where the cosine score comes
  from", and its summary says it "explains the stored additive cosine evidence"
  (further down, outside the frame, it also labels the total "stored cosine").
  The score is the weighted v2 similarity, which `D047` forbids calling cosine;
  the caption says "similarity" on purpose. Filed as `scoutlens-uze.25`.
- The `caveats` frame holds the published caveat "cosine retrieval uses globally
  standardized values" for the same weighted retrieval. It lives in the pinned
  payload rather than the page, so rewording it is a re-publication decision,
  filed as `scoutlens-jtt.23`.
- The `reveal` frame prints the candidate count as 1257, while the `replay`
  frame prints 1,257. Filed as `scoutlens-9a3.17`; the captions do not repeat
  the count.

The video records the site as deployed. When any of these is fixed and
deployed, re-run the command; the digests above will change, and that is
expected.

## Alt text

Copy these when embedding. Each describes what is *shown*, not what it means —
alt text that editorialises leaves a screen-reader user with less than a sighted
reader, not more.

### `lab-desktop.png`

> The Fingerprint Lab at desktop width. The header shows a circular `YL`
> monogram beside the wordmark "Yumusarái Labs", with navigation links Overview,
> Fingerprint Lab and How it works. A badge row reads "Historical reproducible
> benchmark", "2017/18", "CC BY 4.0" and the dataset version
> `wyscout-2017-18-v2-332766e3a822`. Above the heading, an eyebrow reads
> "Interactive evidence surface"; the heading says "Compare one player with
> himself." A highlighted note reads: "This is a statistical fingerprint—not a
> quality score, style proof, recruitment ranking, or automated verdict."

### `lab-evidence-desktop.png`

> The selected profile panel for L. Modrić, Midfielder, Spanish first division,
> 2017/18, with a "Share this profile" button. Below it, two chronological
> periods: Period A, 18 Aug 2017 to 19 Jan 2018, 1,140 minutes across 14 matches
> at Real Madrid; Period B, 20 Jan 2018 to 20 May 2018, 835 minutes across 12
> matches at Real Madrid. Above the panel, a searchable catalogue of player cards
> — A. Blin, A. Candreva, A. Caracciolo, A. Carrillo, A. Cerci, A. Christensen —
> each with role and competition, and a "Show 18 more" button.

### `lab-retrieval-desktop.png`

> The selected profile panel for L. Modrić above the stored experiment replay,
> headed "Identity retrieval, one query at a time", using representation
> `combined_scaler_diagonal_v1`. Period A is the query. Three result cards
> compare it. Global, all eligible profiles: rank 1 of 1,257, reciprocal rank
> 1.0000, similarity score 0.9069. Within role, only midfielder profiles: rank 1
> of 450, same reciprocal rank and score. Role and minutes baseline, a
> context-only control: rank 249 of 1,257, reciprocal rank 0.0040, similarity
> score not used. Each card reports uncertainty from 500 valid resamples with a
> median rank and a rank interval.

### `science-desktop.png`

> The "How it works" page at desktop width, with the same header wordmark and the
> same badge row. The heading reads "The science is the sequence, not one
> headline number." The introduction explains that the question and split were
> frozen first, and closes in bold: "This is evidence of individual signal — not
> proof of playing style, not a recommendation, and not a prediction."

### `lab-mobile.png`

> The Fingerprint Lab on a phone-width viewport. The `YL` monogram and the
> "Yumusarái Labs" wordmark sit on their own row above the navigation, and the
> badge row wraps onto two lines. The same heading, lede and fingerprint caveat
> appear in a single column.

## What is not here

**No narration and no GIF.** The walkthrough carries its explanation in the
caption track; there is no voice track, and a GIF of the same length would be
larger and could not carry captions as text.

**No measure of speed.** The walkthrough is paced by its script; see
[How it is made](#how-it-is-made-and-what-follows-from-that).

Until `scoutlens-jtt.20`, this section recorded the walkthrough itself as an
open gap: `scoutlens-jtt.7.3` AC3 asked for 60–90 seconds of captioned media
showing fingerprint, retrieval, neighbours, uncertainty and caveats, and closed
without it rather than presenting the stills as a substitute.

## One name here is not the brand

The provenance note rendered on every route still reads "ScoutLens publishes
attributed player-period aggregates only…". It comes from a content-addressed
artifact whose digest is pinned and already published, so it is not a stale
wordmark and is not being renamed. See
[`../public-identity-contract.md`](../public-identity-contract.md) §5.
