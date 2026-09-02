/**
 * Comparison-dialog geometry (`scoutlens-uze.6.2`).
 *
 * `scoutlens-uze.1` recorded why this needs its own spec rather than an entry in
 * the page-wide scans:
 *
 * > A modal `<dialog>` lives in the top layer, so a naive pairwise overlap scan
 * > reports every element behind it. Scope the scan to the dialog subtree when
 * > one is open, and measure the dialog's own geometry separately (page
 * > scrollWidth does not grow with top-layer content).
 *
 * Both halves of that matter. The first stops the scan producing noise; the
 * second stops it producing false confidence — a dialog can overflow the
 * viewport without moving `document.scrollWidth` at all, so
 * `expectNoPageOverflow` is structurally unable to see it.
 *
 * `quality-contract.spec.ts` already runs axe on the open dialog. This adds the
 * geometry that nothing was measuring.
 */

import { expect, test, type Page } from "@playwright/test";

import { expectNoTextCollision, waitForStablePage } from "./helpers";

const WIDTHS = [320, 360, 768, 1280] as const;

async function openDrawer(page: Page, width: number): Promise<void> {
  await page.setViewportSize({ width, height: 800 });
  await page.goto("/lab/");
  await waitForStablePage(page);
  await page.locator('[data-neighbor-rank="1"] button').click();
  await expect(page.getByRole("dialog")).toBeVisible();
}

test("the open dialog is contained by the viewport at every width", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Geometry is asserted once from a resizable context");

  for (const width of WIDTHS) {
    await openDrawer(page, width);

    const measured = await page.evaluate(() => {
      const dialog = document.querySelector("dialog[open]");
      if (dialog === null) {
        return null;
      }
      const box = dialog.getBoundingClientRect();
      return {
        left: Math.round(box.left * 10) / 10,
        right: Math.round(box.right * 10) / 10,
        width: Math.round(box.width * 10) / 10,
        viewport: window.innerWidth,
        // The property that makes the page-level check blind: top-layer content
        // does not extend the document's scroll width.
        documentScrollWidth: document.documentElement.scrollWidth,
        clientWidth: document.documentElement.clientWidth,
      };
    });

    expect(measured, `no open dialog at ${width}`).not.toBeNull();
    expect(measured!.left, `dialog starts left of the viewport at ${width}`).toBeGreaterThanOrEqual(-0.5);
    expect(
      measured!.right,
      `dialog extends past the viewport at ${width}`,
    ).toBeLessThanOrEqual(measured!.viewport + 0.5);

    // Recorded rather than asserted as a bug: this equality is exactly why the
    // page-level overflow helper cannot stand in for the check above.
    expect(
      measured!.documentScrollWidth,
      `the page overflow check would have masked a dialog overflow at ${width}`,
    ).toBeLessThanOrEqual(measured!.clientWidth);
  }
});

test("the dialog's own content does not overflow it", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Geometry is asserted once from a resizable context");

  for (const width of WIDTHS) {
    await openDrawer(page, width);

    const escaping = await page.evaluate(() => {
      const dialog = document.querySelector("dialog[open]");
      if (dialog === null) {
        return null;
      }
      const box = dialog.getBoundingClientRect();
      const out: string[] = [];
      for (const element of dialog.querySelectorAll("*")) {
        const style = getComputedStyle(element);
        if (style.display === "none" || style.visibility === "hidden") {
          continue;
        }
        // A declared scroller is allowed to be wider than its box - that is what
        // it is for. uze.1 made the same allowance for the 32-value table.
        const scroller = element.closest("[role='region'][aria-label], .neighbor-drawer__table-scroll");
        if (scroller !== null && scroller !== element) {
          continue;
        }
        const rect = element.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) {
          continue;
        }
        if (rect.right > box.right + 1 || rect.left < box.left - 1) {
          out.push(`${element.tagName.toLowerCase()}.${element.className.toString().split(" ")[0]}`);
        }
      }
      return out;
    });

    expect(escaping, `no open dialog at ${width}`).not.toBeNull();
    expect(escaping, `content escapes the dialog at ${width}`).toEqual([]);
  }
});

test("text inside the dialog does not collide", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Geometry is asserted once from a resizable context");

  // Scoped to the dialog subtree, which is the first half of the audit's
  // instruction. Comparing dialog text against the page behind it would report
  // a collision for every element the modal covers - by design, since that is
  // what a modal does.
  for (const width of WIDTHS) {
    await openDrawer(page, width);
    await expectNoTextCollision(
      page,
      [
        {
          name: "dialog heading vs its close control",
          a: "dialog[open] h2",
          b: "dialog[open] button",
        },
      ],
      `dialog at ${width}`,
    );
  }
});

test("closing the dialog returns focus to the control that opened it", async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Asserted once");

  // uze.1 recorded this as already correct. It is asserted here so that the
  // geometry work in this bead cannot quietly break it.
  await openDrawer(page, 360);
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toBeHidden();

  const focused = await page.evaluate(() => {
    const active = document.activeElement;
    return active === null ? null : (active.textContent ?? "").trim().slice(0, 40);
  });
  expect(focused, "focus did not return to the invoking button").toContain("Open evidence comparison");
});
