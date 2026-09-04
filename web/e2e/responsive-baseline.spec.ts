import { expect, test, type Page } from "@playwright/test";

import {
  expectNoPageOverflow,
  expectNoSeriousOrCriticalViolations,
  expectNoTextCollision,
  type TextPair,
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

async function probeProviderBoundaryTargets(page: Page): Promise<Array<{ text: string; w: number; h: number }>> {
  return page.evaluate(() =>
    [...document.querySelectorAll<HTMLElement>(".provider-boundary__card a")].map((el) => {
      const rect = el.getBoundingClientRect();
      return { text: el.textContent?.trim() ?? "", w: rect.width, h: rect.height };
    }),
  );
}

async function probeFocusRings(page: Page, stops: number): Promise<Array<boolean>> {
  return page.evaluate((count) => {
    const results: boolean[] = [];
    const els = [
      ...document.querySelectorAll<HTMLElement>("a, button, input, select, summary, [tabindex], [role=button]"),
    ];
    for (const el of els.slice(0, count)) {
      el.focus();
      const style = getComputedStyle(el);
      const visible =
        (style.outlineStyle !== "none" && parseFloat(style.outlineWidth) > 0) || style.boxShadow !== "none";
      results.push(visible);
    }
    return results;
  }, stops);
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

  if (width <= 400) {
    const targets = await probeNavTargets(page);
    for (const target of targets) {
      expect(target.h, `${route} nav target "${target.text}" hit area`).toBeGreaterThanOrEqual(44);
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

  const rings = await probeFocusRings(page, width <= 400 ? 6 : 4);
  expect(rings, `${route} visible focus rings`).toEqual(rings.map(() => true));

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
  test(`${route} has no overflow, edge crossings, unwrapped text or undersized nav targets`, async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 800 });
    await expectNoPageOverflow(page);
    await auditRoute(page, route);

    await page.setViewportSize({ width: 640, height: 512 });
    await auditRoute(page, route);

    await page.setViewportSize({ width: 768, height: 900 });
    await auditRoute(page, route);
  });

  test(`${route} renders without page overflow at the project viewport`, async ({ page }) => {
    await auditRoute(page, route);
  });
}
