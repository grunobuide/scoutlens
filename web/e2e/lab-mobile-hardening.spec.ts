/**
 * Lab narrow-screen hardening (`scoutlens-uze.5.1`).
 *
 * Holds the two defects `scoutlens-uze.1` measured: the 32-feature table losing
 * row identity while scrolled (F-3), and Lab-owned links below the 44 px touch
 * target.
 *
 * Both were re-measured on `main` before the fix and were unchanged three weeks
 * after the audit, so these assertions exist to stop them returning rather than
 * to document a one-off.
 *
 * Asserted from the desktop project with resizes, following `404-page.spec.ts`:
 * 320 and 768 have no standing project against the real export.
 */

import { expect, test, type Page } from "@playwright/test";

import { expectNoPageOverflow, expectNoSeriousOrCriticalViolations, waitForStablePage } from "./helpers";

const WIDTHS = [320, 360, 1280] as const;
const PROFILE = "/lab/?player=wy-8287-c-795";

async function openLab(page: Page, width: number): Promise<void> {
  await page.setViewportSize({ width, height: 900 });
  await page.goto(PROFILE);
  await waitForStablePage(page);
}

test("the feature-name column stays readable while the table is scrolled", async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Geometry is asserted once from a resizable context");

  for (const width of WIDTHS) {
    await openLab(page, width);

    const measured = await page.evaluate(() => {
      const scroller = document.querySelector(".fingerprint-table-scroll");
      const header = document.querySelector(
        ".fingerprint-value-table tbody th[scope='row']",
      );
      if (scroller === null || header === null) {
        return null;
      }
      // Scroll to the far right, where the row header is furthest from its row.
      scroller.scrollLeft = scroller.scrollWidth;
      const s = scroller.getBoundingClientRect();
      const h = header.getBoundingClientRect();
      return {
        ratio: scroller.scrollWidth / scroller.clientWidth,
        position: getComputedStyle(header).position,
        // Opaque, or the cells passing beneath show through and the header gets
        // less readable the further the table scrolls - which is the defect.
        background: getComputedStyle(header).backgroundColor,
        insideScroller: h.right > s.left && h.left < s.right,
        width: h.width,
      };
    });

    expect(measured, `no table at ${width}`).not.toBeNull();
    // The table is still wider than the viewport - that is by design. uze.1
    // judged this a usability defect and not a conformance failure, and
    // recorded "do not fix it by removing the scroller or hiding columns".
    expect(measured!.ratio, `table stopped scrolling at ${width}`).toBeGreaterThan(1);
    expect(measured!.position, `row header not sticky at ${width}`).toBe("sticky");
    expect(measured!.insideScroller, `row header scrolled away at ${width}`).toBe(true);
    expect(measured!.width, `row header collapsed at ${width}`).toBeGreaterThan(0);
    expect(measured!.background, `row header is transparent at ${width}`).not.toMatch(
      /rgba\(0, 0, 0, 0\)|transparent/,
    );
  }
});

test("the scroller keeps its region role, name and focusability", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Asserted once from a resizable context");

  // uze.1 recorded that labelling already passes. The sticky fix must not have
  // cost it: this is the part that made the table conformant in the first place.
  for (const width of WIDTHS) {
    await openLab(page, width);
    const scroller = page.locator(".fingerprint-table-scroll");
    await expect(scroller).toHaveAttribute("role", "region");
    await expect(scroller).toHaveAttribute("aria-label", "Scrollable 32-feature value table");
    await expect(scroller).toHaveAttribute("tabindex", "0");
  }
});

test("every Lab-owned control meets the 44 px target", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Geometry is asserted once from a resizable context");

  for (const width of WIDTHS) {
    await openLab(page, width);

    const undersized = await page.evaluate(() =>
      [...document.querySelectorAll("main a, main button")]
        .filter((element) => {
          // The provider boundary is rendered on more than one route and its
          // rules live in research-story.css, a different layer file. Its three
          // undersized links are tracked separately; scoping here keeps this
          // assertion about what this bead owns.
          if (element.closest(".provider-boundary") !== null) {
            return false;
          }
          const box = element.getBoundingClientRect();
          return box.width > 0 && (box.width < 44 || box.height < 44);
        })
        .map((element) => {
          const box = element.getBoundingClientRect();
          return `${Math.round(box.width)}x${Math.round(box.height)} "${(element.textContent ?? "").trim().slice(0, 40)}"`;
        }),
    );

    expect(undersized, `undersized Lab controls at ${width}`).toEqual([]);
  }
});

test("the Lab holds its overflow and axe baseline at every width", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Asserted once from a resizable context");

  // uze.1's baseline: zero page overflow and zero serious or critical axe
  // violations across every audited Lab state. The sticky column and the taller
  // links must not have cost either.
  for (const width of WIDTHS) {
    await openLab(page, width);
    await expectNoPageOverflow(page);
    await expectNoSeriousOrCriticalViolations(page);
  }
});
