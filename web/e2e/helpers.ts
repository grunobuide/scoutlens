import AxeBuilder from "@axe-core/playwright";
import { expect, type Page } from "@playwright/test";

import qualityBudgets from "../quality-budgets.json";

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
