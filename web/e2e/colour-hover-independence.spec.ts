/**
 * No analytical meaning depends on hover or on colour (`scoutlens-uze.27`).
 *
 * The uze epic's AC3 asks for it and nothing checked it. Two gates, each built
 * to hold for rules and components that do not exist yet rather than for the
 * six `:hover` rules and three colour-coded marks that exist today:
 *
 * - **Hover.** Every `:hover` rule in the stylesheets the page actually loads
 *   may change only how something looks - colour, background, border, shadow,
 *   transform, decoration - never whether it is shown or what it says. A rule
 *   that revealed a value on hover would be invisible to touch and keyboard.
 * - **Colour.** Under `forced-colors: active`, which replaces the author's
 *   palette with the system's, every colour-coded mark still carries its
 *   meaning in text: the period markers their letter, the legend its period
 *   names, every signed contribution its sign, every caveat its severity.
 */

import { expect, test, type Page } from "@playwright/test";

import { waitForStablePage } from "./helpers";

const PROFILE = "/lab/?player=wy-8287-c-795";

/** Properties a hover state may change without hiding or revealing meaning. */
const COSMETIC = /^(color|background(-.+)?|border(-.+)?-color|border-color|box-shadow|transform|translate|scale|text-decoration(-.+)?|outline(-.+)?|cursor|fill|stroke|transition(-.+)?)$/;

async function hoverRules(page: Page): Promise<Array<{ selector: string; property: string }>> {
  return page.evaluate(() => {
    const found: Array<{ selector: string; property: string }> = [];
    const walk = (rules: CSSRuleList) => {
      for (const rule of Array.from(rules)) {
        if (rule instanceof CSSStyleRule && rule.selectorText.includes(":hover")) {
          for (let i = 0; i < rule.style.length; i += 1) {
            found.push({ selector: rule.selectorText, property: rule.style.item(i) });
          }
        }
        if ("cssRules" in rule && (rule as CSSGroupingRule).cssRules) {
          walk((rule as CSSGroupingRule).cssRules);
        }
      }
    };
    for (const sheet of Array.from(document.styleSheets)) {
      walk(sheet.cssRules);
    }
    return found;
  });
}

test.describe("hover", () => {
  for (const route of ["/", "/science/", PROFILE]) {
    test(`every :hover rule on ${route} is cosmetic`, async ({ page }, testInfo) => {
      test.skip(testInfo.project.name !== "desktop", "Stylesheets are identical across projects");
      await page.goto(route);
      await waitForStablePage(page);

      const rules = await hoverRules(page);
      // Non-vacuous: the site has hover rules, so finding none means the walk
      // failed to read the stylesheets, not that the gate passed.
      expect(rules.length, "no :hover rule was found at all").toBeGreaterThan(0);
      const revealing = rules.filter(({ property }) => !COSMETIC.test(property));
      expect(revealing, "a :hover rule changes more than appearance").toEqual([]);
    });
  }
});

test.describe("colour", () => {
  test.beforeEach(async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "desktop", "Asserted once; forced colours are viewport-independent");
    await page.emulateMedia({ forcedColors: "active" });
  });

  test("the fingerprint's period marks and legend say A and B in text", async ({ page }) => {
    await page.goto(PROFILE);
    await waitForStablePage(page);

    for (const [mark, letter] of [
      [".lab-fingerprint-mark--a", "A"],
      [".lab-fingerprint-mark--b", "B"],
    ] as const) {
      const texts = await page.locator(mark).allInnerTexts();
      expect(texts.length, `no ${mark} rendered`).toBeGreaterThan(0);
      expect(new Set(texts.map((text) => text.trim())), `${mark} relies on colour`).toEqual(new Set([letter]));
    }
    const legend = page.locator(".lab-fingerprint-legend");
    await expect(legend).toContainText("Period A");
    await expect(legend).toContainText("Period B");
  });

  test("every caveat states its severity in words", async ({ page }) => {
    await page.goto(PROFILE);
    await waitForStablePage(page);

    const severities = await page.locator(".caveat > span, .lab-evidence-rail li > span").allInnerTexts();
    expect(severities.length, "no caveat severity rendered").toBeGreaterThan(0);
    for (const severity of severities) {
      expect(severity.trim().toLowerCase(), "a caveat's severity is colour only").toMatch(
        /^(critical|important|context)$/,
      );
    }
  });

  test("every signed contribution in the evidence drawer carries its sign", async ({ page }) => {
    await page.goto(PROFILE);
    await waitForStablePage(page);
    await page.locator('[data-neighbor-rank="1"]').getByRole("button", { name: "Open evidence comparison" }).click();
    const drawer = page.getByRole("dialog");
    await expect(drawer).toBeVisible();

    const negatives = await drawer.locator(".contribution--negative").allInnerTexts();
    expect(negatives.length, "the fixture has no negative contribution to check").toBeGreaterThan(0);
    for (const value of negatives) {
      expect(value.trim(), "a negative contribution is shown by colour alone").toMatch(/^[-−]\d/);
    }
    const values = await drawer.locator("[data-family-contribution] strong").allInnerTexts();
    for (const value of values) {
      expect(value.trim(), "a contribution's direction is unstated").toMatch(/^([+\-−]\d|0\.0000$)/);
    }
  });

  test("the challenge's period marks say A and B in text", async ({ page }) => {
    await page.goto("/lab/?challenge=reveal");
    await waitForStablePage(page);
    for (const [mark, letter] of [
      [".challenge-fingerprint__mark--a", "A"],
      [".challenge-fingerprint__mark--b", "B"],
    ] as const) {
      const texts = await page.locator(mark).allInnerTexts();
      expect(texts.length, `no ${mark} rendered`).toBeGreaterThan(0);
      expect(new Set(texts.map((text) => text.trim())), `${mark} relies on colour`).toEqual(new Set([letter]));
    }
  });
});
