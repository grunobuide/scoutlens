import AxeBuilder from "@axe-core/playwright";
import { expect, type Page } from "@playwright/test";

import qualityBudgets from "../quality-budgets.json";

/** The showcase path the build actually serves; the pin decides it. */
export const SHOWCASE_BASE = `/showcase/v${process.env.NEXT_PUBLIC_SCOUTLENS_SHOWCASE_MAJOR ?? "2"}/`;

export const MESSI_PROFILE_KEY = "wy-3359-c-795";
export const INTERACTION_BUDGET_MS = qualityBudgets.lighthouse.interaction_to_next_paint_ms;

export async function expectNoSeriousOrCriticalViolations(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page }).analyze();
  const blocking = results.violations
    .filter((violation) => violation.impact === "serious" || violation.impact === "critical")
    .map((violation) => ({
      id: violation.id,
      impact: violation.impact,
      targets: violation.nodes.map((node) => node.target),
    }));
  expect(blocking, JSON.stringify(blocking, null, 2)).toEqual([]);
}

export async function expectNoPageOverflow(page: Page): Promise<void> {
  const widths = await page.evaluate(() => ({
    client: document.documentElement.clientWidth,
    document: document.documentElement.scrollWidth,
    body: document.body.scrollWidth,
  }));
  expect(widths.document).toBeLessThanOrEqual(widths.client);
  expect(widths.body).toBeLessThanOrEqual(widths.client);
}

export async function measureNextInteraction(page: Page, action: () => Promise<void>): Promise<number> {
  const eventTimingSupported = await page.evaluate(() =>
    PerformanceObserver.supportedEntryTypes.includes("event"),
  );
  expect(eventTimingSupported, "Chromium must expose the Event Timing API used by INP").toBe(true);

  await page.evaluate(() => {
    const state = window as typeof window & {
      __scoutlensInteractionDurations?: number[];
      __scoutlensInteractionObserver?: PerformanceObserver;
    };
    state.__scoutlensInteractionDurations = [];
    state.__scoutlensInteractionObserver?.disconnect();
    state.__scoutlensInteractionObserver = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        const event = entry as PerformanceEntry & { interactionId?: number };
        if ((event.interactionId ?? 0) > 0) {
          state.__scoutlensInteractionDurations?.push(event.duration);
        }
      }
    });
    const options: PerformanceObserverInit & { durationThreshold: number } = {
      type: "event",
      buffered: true,
      durationThreshold: 16,
    };
    state.__scoutlensInteractionObserver.observe(options);
  });

  await action();
  await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
  const durations = await page.evaluate(() => {
    const state = window as typeof window & { __scoutlensInteractionDurations?: number[] };
    return state.__scoutlensInteractionDurations ?? [];
  });
  expect(durations.length, "The measured action must create an Event Timing interaction").toBeGreaterThan(0);
  return Math.max(...durations);
}

export async function waitForStablePage(page: Page): Promise<void> {
  await page.waitForLoadState("networkidle");
  await page.evaluate(() => document.fonts.ready);
}

/**
 * A rendered line box, in document coordinates.
 *
 * Document rather than viewport coordinates on purpose: a viewport-relative
 * comparison between a scrolled-past element and a `position: fixed` one
 * reports an intersection that no reader can see, which is the first of the
 * three false-positive classes `scoutlens-uze.1` documented.
 */
export interface InkRect {
  left: number;
  right: number;
  top: number;
  bottom: number;
}

/** Two pieces of text that must never overlap, and a name for the failure. */
export interface TextPair {
  name: string;
  a: string;
  b: string;
}

export interface TextCollision {
  name: string;
  a: string;
  b: string;
  aRect: InkRect;
  bRect: InkRect;
  overlap: { x: number; y: number };
}

/**
 * Assert that two pieces of rendered text do not overlap
 * (`scoutlens-uze.6.1`).
 *
 * **Why line boxes and not element boxes.** `scoutlens-uze.1` found F-1 — the
 * `/science` step marker colliding with the frozen-question heading — and an
 * element-box assertion is blind to it. The marker is a stretched, clipped grid
 * item whose `getBoundingClientRect()` is innocent; what overlaps is the second
 * *line box* of the wrapped string `01 · question`, which overshoots its 40 px
 * track by 21.2 px. Only `Range.getClientRects()` sees that.
 *
 * Measuring line boxes also removes the third documented false positive for
 * free: the union box of two wrapped inline links in one paragraph is an
 * artifact of `getBoundingClientRect()`, and line boxes never produce it. That
 * class needs no exclusion rule here because the measurement cannot create it.
 *
 * The other two documented classes are excluded explicitly, each for a stated
 * reason - see `measureInk` below.
 */
export async function expectNoTextCollision(
  page: Page,
  pairs: readonly TextPair[],
  context = "",
): Promise<void> {
  const collisions = await page.evaluate((entries) => {
    const EPSILON = 0.5;

    /** Every element from `node` up to the root, inclusive. */
    const ancestry = (node: Element): Element[] => {
      const chain: Element[] = [];
      let current: Element | null = node;
      while (current !== null) {
        chain.push(current);
        current = current.parentElement;
      }
      return chain;
    };

    /**
     * Ink rectangles in document coordinates, or `null` when the element must
     * be excluded.
     *
     * Exclusion 1 - `position: fixed`. A fixed element is painted against the
     * viewport, so comparing it to content the reader has scrolled past reports
     * an overlap that never appears on screen. `.skip-link` did exactly this in
     * the audit.
     *
     * Exclusion 2 - `content-visibility: hidden` and closed `<details>`. The
     * browser keeps the last laid-out rectangles for skipped subtrees, so the
     * numbers are real but stale; they describe where the text *would* be.
     */
    const measureInk = (element: Element): DOMRect[] | null => {
      for (const node of ancestry(element)) {
        const style = getComputedStyle(node);
        if (style.position === "fixed") {
          return null;
        }
        if (style.contentVisibility === "hidden") {
          return null;
        }
        if (node instanceof HTMLDetailsElement && !node.open) {
          return null;
        }
      }
      const range = document.createRange();
      range.selectNodeContents(element);
      return [...range.getClientRects()].filter((rect) => rect.width > 0 && rect.height > 0);
    };

    const found = [];
    for (const entry of entries) {
      const a = document.querySelector(entry.a);
      const b = document.querySelector(entry.b);
      if (a === null || b === null) {
        continue;
      }
      // A pair where one element contains the other is meaningless: the
      // ancestor's range includes the descendant's text, so they always
      // "collide". That is an authoring mistake, and excluding it silently
      // would hide genuine collisions between a container and its neighbour -
      // so it is reported rather than skipped.
      if (a.contains(b) || b.contains(a)) {
        found.push({
          name: `${entry.name} [invalid pair: one element contains the other]`,
          a: entry.a,
          b: entry.b,
          aRect: { left: 0, right: 0, top: 0, bottom: 0 },
          bRect: { left: 0, right: 0, top: 0, bottom: 0 },
          overlap: { x: 0, y: 0 },
        });
        continue;
      }
      const aRects = measureInk(a);
      const bRects = measureInk(b);
      if (aRects === null || bRects === null || aRects.length === 0 || bRects.length === 0) {
        continue;
      }
      for (const ra of aRects) {
        for (const rb of bRects) {
          const x = Math.min(ra.right, rb.right) - Math.max(ra.left, rb.left);
          const y = Math.min(ra.bottom, rb.bottom) - Math.max(ra.top, rb.top);
          if (x > EPSILON && y > EPSILON) {
            const box = (r: DOMRect) => ({
              left: Math.round((r.left + window.scrollX) * 10) / 10,
              right: Math.round((r.right + window.scrollX) * 10) / 10,
              top: Math.round((r.top + window.scrollY) * 10) / 10,
              bottom: Math.round((r.bottom + window.scrollY) * 10) / 10,
            });
            found.push({
              name: entry.name,
              a: entry.a,
              b: entry.b,
              aRect: box(ra),
              bRect: box(rb),
              overlap: { x: Math.round(x * 10) / 10, y: Math.round(y * 10) / 10 },
            });
          }
        }
      }
    }
    return found;
  }, pairs as unknown as TextPair[]);

  // The message carries both locators and both measured rectangles, so a
  // failure is actionable without reproducing it by hand.
  expect(
    collisions as TextCollision[],
    `text collisions${context === "" ? "" : ` (${context})`}:
${JSON.stringify(collisions, null, 2)}`,
  ).toEqual([]);
}
