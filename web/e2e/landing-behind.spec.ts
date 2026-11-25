/**
 * The landing's case-study block (`scoutlens-rdz.12`, narrative §7.1 item 9,
 * D075, D076).
 *
 * §7.1 puts it after the provenance strip and before the footer. §6.3 item 3
 * lets it carry the case-study link and nothing else: it is not a third hero
 * CTA, and the repository link stays in the footer and provenance.
 */

import { expect, test } from "@playwright/test";

import { expectNoPageOverflow, waitForStablePage } from "./helpers";

test.describe("the landing's case-study block", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await waitForStablePage(page);
  });

  test("sits after the provenance strip, as the last section of main", async ({ page }) => {
    const order = await page.evaluate(() => {
      const main = document.querySelector("main")!;
      const behind = main.querySelector("[aria-labelledby='behind-heading']")!;
      const provenance = main.querySelector("[data-provider-boundary]")!;
      return {
        afterProvenance: Boolean(provenance.compareDocumentPosition(behind) & Node.DOCUMENT_POSITION_FOLLOWING),
        last: main.lastElementChild === behind,
      };
    });
    expect(order).toEqual({ afterProvenance: true, last: true });
  });

  test("carries the case-study link and no other, and it resolves", async ({ page, request }) => {
    const block = page.locator("[aria-labelledby='behind-heading']");
    const links = block.getByRole("link");
    await expect(links).toHaveCount(1);
    await expect(links).toHaveText("Read the case study");
    await expect(links).toHaveAttribute("href", "/case-study/");
    expect((await request.get("/case-study/")).status()).toBe(200);

    // Not a third hero CTA (§6.3): the hero still has exactly its two.
    await expect(page.locator(".hero").getByRole("link", { name: "Read the case study" })).toHaveCount(0);
  });

  test("prints no number", async ({ page }) => {
    // A result value belongs to the artifact surfaces; this block only points
    // at the case study.
    await expect(page.locator("[aria-labelledby='behind-heading']")).not.toContainText(/\d/);
  });

  test("fits the viewport", async ({ page }) => {
    await expectNoPageOverflow(page);
  });
});
