# Lab Mobile Content Order

**Status:** accepted for implementation

**Decision date:** 2026-08-25

**Tracking:** `scoutlens-uze.5.2`, under `scoutlens-uze.5`. Measurements from
`scoutlens-uze.1`'s audit and re-measured on `main` at `3e80a18`.

This document exists because `scoutlens-uze.5` AC1 requires the Lab to follow
"the accepted mobile narrative order" and no such order was written down. An
acceptance criterion that points at an undefined artifact can be neither met nor
refuted, so this fixes the referent.

---

## 1. Scope

The order of content on `/lab/` at 320–375 CSS pixels. Desktop is not a separate
order: one DOM serves every width, so this sequence is the reading order
everywhere and the visual order everywhere. Where desktop differs it differs by
*layout* — two columns instead of one — never by sequence.

## 2. The order

| # | Block | Why it sits here |
|---|---|---|
| 1 | Data-vintage badge, page heading, lede, interpretation boundary | The vintage and the boundary qualify everything below them, so they precede it. A reader who stops after one screen has still been told what this data is and is not. |
| 2 | Identity challenge panel | The entry experience. Frozen by `docs/identity-challenge-contract.md` §1, which places it above the explorer on the same route. |
| 3 | `<noscript>` notice | Immediately after the first interactive surface it qualifies. |
| 4 | Profile selector and results | The control that determines everything below. |
| 5 | Selected profile identity | Name, role, competition — what the reader chose. |
| 6 | Period contexts | The two halves being compared, before anything compares them. |
| 7 | **Retrieval result** — rank, baseline, similarity, provenance | **The finding.** See §3. |
| 8 | Method disclosure | Names what produced the number in 7, immediately after giving it. |
| 9 | Fingerprint plot, 32 features | The evidence behind the finding. |
| 10 | Evidence rail — uncertainty and caveats | The limits of the finding, beside the evidence for it. |
| 11 | Statistical neighbours and comparison drawer | Context: other profiles, reachable but not in the primary path. |
| 12 | All 32 measurements, value table | The equivalent value view. Last because it is the most detailed and the least narrative. |
| 13 | Provider boundary | Provenance and the replication limit, closing the page. |

## 3. Result before chart

Blocks 7 and 8 sit **above** block 9. That is the one substantive change this
document makes; everything else ratifies what the Lab already did.

Measured at 320 px on `main` at `3e80a18`, before the change:

| | |
|---|---|
| page height | 19,646 px |
| fingerprint plot | 4,156 px — the largest single block |
| retrieval result first visible at | **10,047 px** |

A reader who selected a profile had to travel more than half the page, past a
4,156 px chart, to learn that profile's rank. The chart is evidence *for* a
finding; it was being shown before the finding existed.

After the change the result appears at **4,450 px** at 320, and at **2,986 px**
at 1280. No block was added, removed, resized or hidden — the page is still
19,646 px at 320. Only the sequence moved.

The method disclosure follows the result rather than preceding it, because it
answers a question the reader now has ("what produced that number?") instead of
one they have not yet asked.

## 4. Rules that constrain any future change

1. **DOM order is the order.** No CSS `order`, no `flex-direction: *-reverse`,
   no grid placement that moves a block out of source sequence. A visual order
   achieved with `order` reads correctly to the eye and wrongly to a screen
   reader, and `scoutlens-uze.5`'s stop condition forbids it explicitly.
   Verified on `main`: zero elements in `main` carry a non-default `order`.
2. **Focus order is not this order.** Only interactive controls belong in the
   focus sequence; informational content is reached in reading order. `D053`
   settles this for the challenge and the same distinction applies here.
3. **Nothing is hidden to shorten the page.** Progressive disclosure is
   permitted where it is accessible — a `<details>` a reader can open — but no
   value, caveat, uncertainty state or text equivalent may become unreachable.
   `scoutlens-uze.5`'s non-goals are explicit.
4. **Desktop keeps its density.** Two-column layout at wide widths is a layout
   choice, not an order choice. Blocks 9 and 10 sit side by side above 48 rem
   and stack below it; both are this same sequence.
5. **The artifact's own order is untouchable.** Neighbour order, evidence order
   and feature order come from the published artifact and are never sorted in
   the browser. This document orders *sections*, never the data inside them.

## 5. What this document does not decide

The page is long — 19,646 px at 320 px, roughly 22 screens. Shortening it with
accessible disclosure on the two largest blocks (the 32-row plot and the 32-row
table, 7,814 px between them) is a real option and deliberately not taken here:
it changes what a reader sees by default, which is a larger decision than
sequence, and it deserves its own bead rather than riding along with a reorder.
