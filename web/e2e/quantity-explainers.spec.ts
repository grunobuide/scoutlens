/**
 * Every per-profile number on /lab and in the identity challenge has its
 * explanation in reach (`scoutlens-9a3.19`).
 *
 * Each section that prints a registry quantity is a `data-quantity-scope`, each
 * element that prints one carries `data-quantity`, and the section's "What
 * these numbers mean" disclosure lists one `data-quantity-explainer` per id.
 * Three gates:
 *
 * - **Tethered.** Every printed quantity has an explainer in its own nearest
 *   scope - the drawer's numbers in the drawer, not two sections away.
 * - **Nothing untagged.** Every `<dd>` holding a digit inside a scope is a
 *   tagged quantity or declares itself context (`data-context`: minutes, a
 *   position among five shown, an identifier). A new number added without
 *   either fails here, so the tag set cannot quietly fall behind the page.
 * - **Reachable alike.** Each disclosure is a native `<summary>` that opens
 *   and closes from the keyboard, whose terms join the accessibility tree only
 *   when opened, and whose summary names every term the body defines.
 */

import { expect, test, type Page } from "@playwright/test";

import { waitForStablePage } from "./helpers";

/** What the v2 Lab and challenge print, all of it: every key except v1's score. */
const V2_QUANTITIES = [
  "self_rank",
  "baseline_self_rank",
  "reciprocal_rank",
  "similarity_score",
  "rank_interval",
  "resampled_recall",
  "selection_stability",
  "within_role_percentile",
  "global_percentile",
  "model_z_score",
  "contribution",
  "feature_weight",
];

interface Sweep {
  problems: string[];
  seen: string[];
}

async function sweep(page: Page): Promise<Sweep> {
  return page.evaluate(() => {
    const problems: string[] = [];
    const seen: string[] = [];
    const scopeName = (scope: Element) =>
      scope.getAttribute("aria-labelledby") ?? scope.className.toString().split(" ")[0] ?? scope.tagName;

    for (const element of document.querySelectorAll<HTMLElement>("[data-quantity]")) {
      const scope = element.closest("[data-quantity-scope]");
      if (scope === null) {
        problems.push(`${element.dataset.quantity} is printed outside any explained section`);
        continue;
      }
      for (const id of (element.dataset.quantity ?? "").split(" ")) {
        seen.push(id);
        const explained = [...scope.querySelectorAll(`[data-quantity-explainer="${id}"]`)].some(
          (entry) => entry.closest("[data-quantity-scope]") === scope,
        );
        if (!explained) {
          problems.push(`${id} is printed in ${scopeName(scope)} with no explainer there`);
        }
      }
    }

    for (const value of document.querySelectorAll("[data-quantity-scope] dd")) {
      if (value.closest("[data-quantity-glossary]") !== null || !/\d/.test(value.textContent ?? "")) {
        continue;
      }
      if (value.closest("[data-quantity], [data-context]") === null) {
        problems.push(`untagged number "${(value.textContent ?? "").trim().slice(0, 48)}"`);
      }
    }
    return { problems, seen };
  });
}

test.describe("every Lab and challenge quantity is explained where it is printed", () => {
  test.beforeEach(({}, testInfo) => {
    test.skip(testInfo.project.name !== "desktop", "Markup is viewport-independent; asserted once");
  });

  test("on the Lab, the drawer and all three challenge states, together covering every v2 quantity", async ({
    page,
  }) => {
    const seen = new Set<string>();
    const check = async (where: string) => {
      const result = await sweep(page);
      expect(result.problems, where).toEqual([]);
      expect(result.seen.length, `${where} printed no tagged quantity`).toBeGreaterThan(0);
      for (const id of result.seen) seen.add(id);
    };

    await page.goto("/lab/");
    await waitForStablePage(page);
    await check("Lab, within-role scale");

    // The percentile scale is a control, and the explanation must follow it.
    await page.getByRole("radio", { name: "Global" }).check();
    await check("Lab, global scale");

    await page.locator('[data-neighbor-rank="1"]').getByRole("button", { name: "Open evidence comparison" }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await check("evidence drawer");

    for (const state of ["query", "reveal", "evidence"]) {
      await page.goto(`/lab/?challenge=${state}`);
      await waitForStablePage(page);
      await expect(page.locator("[data-challenge-state]")).toHaveAttribute("data-challenge-state", state);
      await check(`challenge ${state}`);
    }

    expect([...seen].sort()).toEqual([...V2_QUANTITIES].sort());
  });

  test("each disclosure opens and closes from the keyboard and exposes the same terms it names", async ({
    page,
  }) => {
    await page.goto("/lab/");
    await waitForStablePage(page);
    const glossaries = page.locator("[data-quantity-glossary]");
    // Replay, fingerprint map, neighbours and value table on the Lab itself.
    expect(await glossaries.count()).toBeGreaterThanOrEqual(4);

    for (let index = 0; index < (await glossaries.count()); index += 1) {
      const glossary = glossaries.nth(index);
      const summary = glossary.locator("summary");
      const entries = await glossary.locator("[data-quantity-explainer]").count();
      expect(entries).toBeGreaterThan(0);

      // Closed: nothing of the body is in the accessibility tree.
      await expect(glossary.getByRole("term")).toHaveCount(0);

      await summary.focus();
      await expect(summary).toBeFocused();
      await page.keyboard.press("Enter");
      await expect(glossary).toHaveAttribute("open", "");

      const terms = await glossary.getByRole("term").allInnerTexts();
      expect(terms).toHaveLength(entries);
      const named = await summary.innerText();
      for (const term of terms) {
        expect(named, "the summary names every term the body defines").toContain(term);
      }
      await expect(glossary.getByRole("definition").first()).toBeVisible();

      await page.keyboard.press("Enter");
      await expect(glossary).not.toHaveAttribute("open", /.*/);
    }
  });

  test("the challenge names features and families by their catalog labels, never their ids", async ({ page }) => {
    await page.goto("/lab/?challenge=evidence");
    await waitForStablePage(page);
    const catalog = await page.evaluate(async () => {
      const response = await fetch("/showcase/v2/feature-catalog.json");
      return (await response.json()) as { features: Array<{ feature_id: string; label: string; family: string }> };
    });

    const labels = await page.locator(".challenge-contribution__label").allInnerTexts();
    expect(labels.length).toBeGreaterThan(0);
    const catalogLabels = new Set(catalog.features.map((feature) => feature.label));
    for (const label of labels) {
      expect(catalogLabels, `"${label}" is not a catalog label`).toContain(label.trim());
    }

    const families = [
      ...(await page.locator(".challenge-contribution__family").allInnerTexts()),
      ...(await page.locator("[data-challenge-families] li").allInnerTexts()),
    ];
    const familyIds = new Set(catalog.features.map((feature) => feature.family));
    for (const family of families) {
      expect(familyIds, `the family "${family}" is printed as its id`).not.toContain(family.trim());
      expect(family.trim()).not.toMatch(/_/);
    }
  });
});
