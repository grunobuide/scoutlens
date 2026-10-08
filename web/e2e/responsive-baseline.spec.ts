import { expect, test, type Page } from "@playwright/test";

import {
  expectNoPageOverflow,
  expectNoSeriousOrCriticalViolations,
  expectNoTextCollision,
  focusRingReport,
  FROZEN_WIDTHS,
  isZoom200,
  type TextPair,
  waitForStablePage,
  ZOOM_200,
} from "./helpers";

// scoutlens-uze.4 responsive regression gates for the shared shell, landing,
// and /science surfaces. These encode the audit findings from
// docs/frontend-qa-audit.md (D1, D2, D3, D5, D7) as deterministic geometry
// assertions so the repaired baseline cannot silently regress. They run on the
// desktop and mobile-360 projects against the production static export.

interface OverflowProbe {
  client: number;
  document: number;
  body: number;
}

async function probeOverflow(page: Page): Promise<OverflowProbe> {
  return page.evaluate(() => ({
    client: document.documentElement.clientWidth,
    document: document.documentElement.scrollWidth,
    body: document.body.scrollWidth,
  }));
}

async function probeEdgeCrossings(page: Page): Promise<Array<{ tag: string; cls: string }>> {
  return page.evaluate(() => {
    const bad: Array<{ tag: string; cls: string }> = [];
    for (const el of document.querySelectorAll<HTMLElement>("body *")) {
      const rect = el.getBoundingClientRect();
      if (rect.width < 2 || rect.height < 2) {
        continue;
      }
      if (rect.left < -1 || rect.right > document.documentElement.clientWidth + 1) {
        bad.push({ tag: el.tagName, cls: String(el.className).slice(0, 60) });
      }
    }
    return bad;
  });
}

async function probeUnwrappedText(page: Page): Promise<Array<{ cls: string; text: string; sw: number; cw: number }>> {
  return page.evaluate(() => {
    const bad: Array<{ cls: string; text: string; sw: number; cw: number }> = [];
    for (const el of document.querySelectorAll<HTMLElement>("body *")) {
      if (el.children.length > 0) {
        continue;
      }
      const text = el.textContent?.trim() ?? "";
      if (text.length < 25) {
        continue;
      }
      const sw = el.scrollWidth;
      const cw = el.clientWidth;
      if (sw > cw + 2 && el.getBoundingClientRect().width > 0) {
        bad.push({ cls: String(el.className).slice(0, 60), text: text.slice(0, 60), sw, cw });
      }
    }
    return bad;
  });
}

async function probeNavTargets(page: Page): Promise<Array<{ text: string; w: number; h: number }>> {
  return page.evaluate(() =>
    [...document.querySelectorAll<HTMLElement>(".site-nav a")].map((el) => {
      const rect = el.getBoundingClientRect();
      return { text: el.textContent?.trim() ?? "", w: rect.width, h: rect.height };
    }),
  );
}

/**
 * The smallest size running text may render at (`scoutlens-uze.28`).
 *
 * The stylesheets' smallest deliberate size is 0.65rem (10.4 px), on short
 * labels; on `/` and `/science/` the smallest running text measured 10.56 px
 * (the confidence-interval line and the dataset pin), the same at 320, 640 and
 * 1280 px. Nothing there scales type with the viewport except display
 * headings. So the defect this guards is text that *shrinks as the viewport
 * narrows* - a `vw` term in a body size, or a narrow-width rule that steps
 * prose down - and the floor is where that would become unreadable.
 */
const READABLE_FLOOR_PX = 10;

/** Larger than this at the widest width is display type, which may scale. */
const DISPLAY_TYPE_PX = 20;

interface TextSizeIssue {
  text: string;
  px: number;
  widePx: number;
}

/**
 * Marks every element carrying a running sentence (twenty or more characters
 * of its own text) and records its font size, so the same elements can be
 * measured again after the viewport changes.
 */
async function markRunningText(page: Page): Promise<number> {
  return page.evaluate(() => {
    let count = 0;
    for (const element of document.querySelectorAll<HTMLElement>("main *")) {
      const own = [...element.childNodes]
        .filter((node) => node.nodeType === Node.TEXT_NODE)
        .map((node) => node.textContent ?? "")
        .join("")
        .replace(/\s+/g, " ")
        .trim();
      if (own.length < 20 || element.closest("code, pre, .sr-only") !== null) {
        continue;
      }
      element.dataset.probeWidePx = getComputedStyle(element).fontSize;
      count += 1;
    }
    return count;
  });
}

async function probeTextSize(page: Page): Promise<TextSizeIssue[]> {
  return page.evaluate(
    ({ floor, display }) => {
      const issues: Array<{ text: string; px: number; widePx: number }> = [];
      for (const element of document.querySelectorAll<HTMLElement>("[data-probe-wide-px]")) {
        const rect = element.getBoundingClientRect();
        if (rect.width < 1 || rect.height < 1) {
          continue;
        }
        const px = Number.parseFloat(getComputedStyle(element).fontSize);
        const widePx = Number.parseFloat(element.dataset.probeWidePx ?? "0");
        const shrank = widePx <= display && px < widePx - 0.01;
        if (px < floor || shrank) {
          issues.push({ text: (element.textContent ?? "").trim().slice(0, 48), px, widePx });
        }
      }
      return issues;
    },
    { floor: READABLE_FLOOR_PX, display: DISPLAY_TYPE_PX },
  );
}

/**
 * Text cut off with an ellipsis or a line clamp. Neither is used on these
 * routes; the uze.4 non-goals rule both out as a way to make text fit.
 */
async function probeTruncatedText(page: Page): Promise<Array<{ text: string; how: string }>> {
  return page.evaluate(() => {
    const truncated: Array<{ text: string; how: string }> = [];
    for (const element of document.querySelectorAll<HTMLElement>("main *")) {
      const style = getComputedStyle(element);
      const clamp = style.getPropertyValue("-webkit-line-clamp");
      const text = (element.textContent ?? "").trim().slice(0, 48);
      if (style.textOverflow === "ellipsis" && element.scrollWidth > element.clientWidth + 1) {
        truncated.push({ text, how: "ellipsis" });
      } else if (clamp !== "" && clamp !== "none" && element.scrollHeight > element.clientHeight + 1) {
        truncated.push({ text, how: `line-clamp ${clamp}` });
      }
    }
    return truncated;
  });
}

async function probeProviderBoundaryTargets(page: Page): Promise<Array<{ text: string; w: number; h: number }>> {
  return page.evaluate(() =>
    [...document.querySelectorAll<HTMLElement>(".provider-boundary__card a")].map((el) => {
      const rect = el.getBoundingClientRect();
      return { text: el.textContent?.trim() ?? "", w: rect.width, h: rect.height };
    }),
  );
}

/**
 * Text pairs guarded on the routes this spec walks (`scoutlens-uze.6.2`).
 *
 * The frozen-question marker/heading pair is not here: `frozen-question.spec.ts`
 * owns it across thirteen widths with a stronger claim. These are the remaining
 * shared-shell and stage pairs.
 */
const TEXT_PAIRS: Record<string, TextPair[]> = {
  "/": [{ name: "site nav vs wordmark", a: ".site-nav", b: ".wordmark" }],
  "/science/": [
    { name: "site nav vs wordmark", a: ".site-nav", b: ".wordmark" },
    {
      name: "stage marker vs stage heading",
      a: ".research-stage > header > .research-step__marker",
      b: ".research-stage > header h2",
    },
  ],
};

/** The copy a stretched-content fixture grows (`scoutlens-uze.28`). */
const STRETCH_TARGETS = [
  "main h1",
  "main h2",
  "main h3",
  "main .lede",
  "main .data-vintage span",
  "main .signal-caveat",
  "main .claims-matrix li",
  "main .caveat",
  "main .experiment-card__conclusion",
  "main .provider-boundary__card p",
  "main .section-intro",
] as const;

async function auditRoute(page: Page, route: string): Promise<void> {
  await page.goto(route);
  await page.waitForLoadState("networkidle");
  await page.evaluate(() => document.fonts.ready);

  const width = page.viewportSize()?.width ?? 0;
  const overflow = await probeOverflow(page);
  expect(
    overflow.document,
    `${route} horizontal document overflow`,
  ).toBeLessThanOrEqual(overflow.client);
  expect(overflow.body, `${route} horizontal body overflow`).toBeLessThanOrEqual(overflow.client);

  const crossings = await probeEdgeCrossings(page);
  expect(crossings, `${route} elements crossing the viewport edge`).toEqual([]);

  const unwrapped = await probeUnwrappedText(page);
  expect(unwrapped, `${route} unwrapped long text`).toEqual([]);

  // `scoutlens-uze.28`: uze.4's AC3 also asked that text keep a readable size
  // and not be cut off, and nothing asserted either.
  expect(await probeTruncatedText(page), `${route} truncated text`).toEqual([]);

  // `scoutlens-uze.27`: 200% zoom is a touch context too - the epic's AC3 holds
  // 44 x 44 there, and this guard used to skip it because 640 > 400.
  const zoomed = isZoom200(page);
  if (width <= 400 || zoomed) {
    const targets = await probeNavTargets(page);
    for (const target of targets) {
      expect(target.h, `${route} nav target "${target.text}" hit area`).toBeGreaterThanOrEqual(44);
      // `scoutlens-uze.28`: and wide - a 44 px tall link four pixels wide is
      // not a touch target. uze.4's AC4 asked for both; only height was held.
      expect(target.w, `${route} nav target "${target.text}" hit width`).toBeGreaterThanOrEqual(44);
    }

    // `scoutlens-uze.6.5`: the three provider-boundary links measured
    // 17-20 px tall (`scoutlens-uze.5.1`) and were excluded from the Lab's own
    // 44 px sweep because the component and its rules are shared across
    // routes, not Lab-owned. This is where they are actually held.
    const providerTargets = await probeProviderBoundaryTargets(page);
    for (const target of providerTargets) {
      expect(
        target.h,
        `${route} provider-boundary target "${target.text}" hit area`,
      ).toBeGreaterThanOrEqual(44);
    }
  }

  // At 200% zoom every reachable focusable is walked, not a sample of four -
  // and the walk opens every <details> first, so the axe run below audits the
  // disclosures open. That is how `scoutlens-uze.27` found the signal card's
  // "What this means" text failing contrast: every earlier axe run saw it closed.
  const rings = await focusRingReport(page, zoomed ? undefined : width <= 400 ? 6 : 4);
  expect(
    rings.filter((ring) => !ring.visible).map((ring) => ring.label),
    `${route} focusables without a visible focus ring${zoomed ? " at 200% zoom" : ""}`,
  ).toEqual([]);

  // `scoutlens-uze.6.2`. This function already walked 320, 640x512 and 768, but
  // axe only ever ran at the project viewports (1280 and 360) in
  // quality-contract.spec.ts - so a violation that appears only when the layout
  // reflows had nothing looking for it. Reflow is exactly where they appear:
  // a heading order that changes with a wrapped grid, a control that loses its
  // accessible name when its label wraps away.
  await expectNoSeriousOrCriticalViolations(page);

  // And the line-box collision gate from `scoutlens-uze.6.1`, at the same
  // widths, for the pairs these two routes own.
  await expectNoTextCollision(page, TEXT_PAIRS[route] ?? [], `${route} at ${width}`);
}

for (const route of ["/", "/science/"]) {
  // `scoutlens-uze.26`: every width of the frozen matrix, not three of them.
  // 375, 1024 and 1440 had no standing gate on these routes; the only evidence
  // at those widths was the 2026-08-04 manual audit, which predates the Science
  // rebuild and the v2 repin.
  test(`${route} has no overflow, edge crossings, unwrapped text or undersized nav targets`, async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 800 });
    await expectNoPageOverflow(page);
    for (const width of FROZEN_WIDTHS) {
      await page.setViewportSize({ width, height: 900 });
      await auditRoute(page, route);
    }
    await page.setViewportSize(ZOOM_200);
    await auditRoute(page, route);
  });

  // `scoutlens-uze.28`, uze.4 AC3: running text keeps a readable size at every
  // width. Measured on one page load, so each element is compared with itself
  // at the widest frozen width.
  test(`${route} keeps running text at a readable size as the viewport narrows`, async ({ page }) => {
    await page.setViewportSize({ width: Math.max(...FROZEN_WIDTHS), height: 900 });
    await page.goto(route);
    await waitForStablePage(page);
    expect(await markRunningText(page), `${route} has no running text to measure`).toBeGreaterThan(20);
    for (const size of [...FROZEN_WIDTHS.map((width) => ({ width, height: 900 })), ZOOM_200]) {
      await page.setViewportSize(size);
      expect(await probeTextSize(page), `${route} at ${size.width}x${size.height}`).toEqual([]);
    }
  });

  // `scoutlens-uze.28`, uze.4 AC3: a stretched-content fixture for landing and
  // /science. The uze.7 fixtures stretch the Lab only. This stretches the copy
  // most likely to grow - caveats, sources, claims, card titles, the chip and
  // the headline - to three times its length, adds the longest published team
  // join, and asks the same reflow questions at the narrowest width and at 200%
  // zoom. It edits the rendered DOM rather than the artifacts because what is
  // under test is the layout's response to longer text, not the data.
  test(`${route} reflows stretched content without overflow or clipping`, async ({ page }) => {
    for (const size of [{ width: 320, height: 800 }, ZOOM_200]) {
      await page.setViewportSize(size);
      await page.goto(route);
      await waitForStablePage(page);
      const stretched = await page.evaluate((selectors) => {
        let count = 0;
        for (const element of document.querySelectorAll<HTMLElement>(selectors.join(", "))) {
          const text = (element.textContent ?? "").trim();
          if (text.length === 0) {
            continue;
          }
          element.append(document.createTextNode(` ${text} ${text} Saint-Étienne / Olympique Marseille`));
          count += 1;
        }
        return count;
      }, STRETCH_TARGETS);
      expect(stretched, `${route} found nothing to stretch`).toBeGreaterThan(10);

      const overflow = await probeOverflow(page);
      expect(overflow.document, `${route} stretched: document overflow`).toBeLessThanOrEqual(overflow.client);
      expect(await probeEdgeCrossings(page), `${route} stretched: edge crossings`).toEqual([]);
      expect(await probeUnwrappedText(page), `${route} stretched: unwrapped text`).toEqual([]);
      expect(await probeTruncatedText(page), `${route} stretched: truncated text`).toEqual([]);
    }
  });

  test(`${route} renders without page overflow at the project viewport`, async ({ page }) => {
    await auditRoute(page, route);
  });
}
