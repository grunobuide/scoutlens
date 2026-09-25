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

## Provenance

| | |
|---|---|
| Source commit | `0045ea41d4d518e5790017a2384abf66b833d60f` |
| Deployed by | `deploy` run [36063429790](https://github.com/grunobuide/scoutlens/actions/runs/36063429790), 2026-09-24, smoke 9/9 |
| Captured from | <https://grunobuide.github.io/scoutlens/> |
| Command | `node scripts/capture-media.mjs https://grunobuide.github.io/scoutlens/` |
| Profile | `wy-8287-c-795` (L. Modrić, Spanish first division, 2017/18) |
| Desktop | 1280×900 at `deviceScaleFactor: 2`; the retrieval shot uses 1280×1000 |
| Mobile | Playwright's `iPhone 13` device profile |

```
68237814b27eab04ceb455d3178122608024cb6dfad272c7332c7ef2b3050234  lab-desktop.png
9f0384b0658457ce3a2da088672f56dbeb5c6260d354419741b3dd0dc36f45f9  lab-evidence-desktop.png
eee62b579fbbc2f3a979ce659ff6c086467dd8bef988538155df481b567a5c14  lab-retrieval-desktop.png
0c7c2a007cfa932fbf0634d06eb7c9dcf312305c75a6dd7305970882d1bce875  science-desktop.png
386947bf7ce30cc97d60be27014a22e17525193310dbca7fb64bee46e5ba0eda  lab-mobile.png
```

**Two of these five are byte-identical to the pre-rename capture.**
`lab-evidence-desktop.png` and `lab-retrieval-desktop.png` are scrolled past the
site header, so the wordmark is not in frame and nothing in them changed. That is
not an oversight — it is the determinism claim above, checked: the only files
whose digests moved are the three where the header is visible.

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

## A known defect these images show

`science-desktop.png` renders **"2017/18season"** with no space, in the
introduction paragraph. That is `scoutlens-9a3.16`, open and unfixed. The
screenshot is not retouched and the alt text does not quietly correct it: media
shows what a reader actually gets, and a portfolio image that silently fixes a
live defect is a small lie about the product.

## What is not here

**There is no demo video or GIF.** `scoutlens-jtt.7.3` AC3 asked for 60–90
seconds of captioned media showing fingerprint, retrieval, neighbours,
uncertainty and caveats. It was not delivered, and these stills cover that
content without being a video. Tracked as `scoutlens-jtt.20`; they are recorded
as an open gap rather than quietly substituted.

## One name here is not the brand

The provenance note rendered on every route still reads "ScoutLens publishes
attributed player-period aggregates only…". It comes from a content-addressed
artifact whose digest is pinned and already published, so it is not a stale
wordmark and is not being renamed. See
[`../public-identity-contract.md`](../public-identity-contract.md) §5.
