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

## Alt text

Copy these when embedding. Each describes what is *shown*, not what it means —
alt text that editorialises leaves a screen-reader user with less than a sighted
reader, not more.

### `lab-desktop.png`

> The ScoutLens Fingerprint Lab at desktop width. A badge row reads "Historical
> reproducible benchmark", "2017/18", "CC BY 4.0" and the dataset version
> `wyscout-2017-18-v2-332766e3a822`. The heading says "Compare one player with
> himself." A highlighted note reads: "This is a statistical fingerprint—not a
> quality score, style proof, recruitment ranking, or automated verdict."

### `lab-evidence-desktop.png`

> The selected profile panel for L. Modrić, Midfielder, Spanish first division,
> 2017/18, with a "Share this profile" button. Below it, two chronological
> periods: Period A, 18 Aug 2017 to 19 Jan 2018, 1,140 minutes across 14 matches
> at Real Madrid; Period B, 20 Jan 2018 to 20 May 2018, 835 minutes across 12
> matches at Real Madrid. Above the panel, a searchable catalogue of player cards.

### `lab-retrieval-desktop.png`

> The stored experiment replay for L. Modrić, headed "Identity retrieval, one
> query at a time", using representation `combined_scaler_diagonal_v1`. Three
> result cards compare the same query. Global: rank 1 of 1,257, reciprocal rank
> 1.0000, similarity score 0.9069. Within role: rank 1 of 450, same reciprocal
> rank and score. Role and minutes baseline: rank 249 of 1,257, reciprocal rank
> 0.0040, similarity score not used. Each card reports uncertainty from 500 valid
> resamples with a median rank and a rank interval.

### `science-desktop.png`

> The "How it works" page at desktop width, presenting the method, the
> experiments and the research decision trail.

### `lab-mobile.png`

> The Fingerprint Lab on a phone-width viewport, showing the same evidence
> surface in a single column.

## What is not here

**There is no demo video or GIF.** `scoutlens-jtt.7.3` AC3 asks for 60–90 seconds
of captioned media showing fingerprint, retrieval, neighbours, uncertainty and
caveats. These stills cover that content, but they are not a video and should not
be described as one. Recorded as an open gap rather than quietly substituted.
