import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type Page } from "@playwright/test";

import {
  expectNoPageOverflow,
  MESSI_PROFILE_KEY,
  SHOWCASE_BASE,
  waitForStablePage,
} from "./helpers";

/**
 * `scoutlens-vif.4`. The display brand is Yumusarái Labs; every technical
 * identifier stays `scoutlens`.
 *
 * The assertions worth reading are the last two groups. One proves the accent
 * actually renders in the pinned font rather than silently falling back — a
 * missing glyph does not error, so nothing else would tell us. The other pins
 * the single reader-facing occurrence of the old name that this rename may not
 * touch, so that finding it on the page leads to the explanation instead of to
 * a defect report.
 */

const BRAND = "Yumusarái Labs";
const MONOGRAM = "YL";
const DESCRIPTOR = "Player Fingerprint Lab";
const RETIRED = "ScoutLens";
const PROFILE = "wy-8287-c-795";

const ROUTES = ["/", "/lab/", "/science/"] as const;

/** Widths the contract's verification matrix names. 769 is the interesting one. */
const WIDTHS = [320, 360, 769, 1280] as const;

async function wordmark(page: Page) {
  return page.getByRole("link", { name: `${BRAND} home` });
}

/**
 * Narrative §6.1's top-nav rows, read from the document: each row whose route
 * is a bare code span and whose label is bold. The footer row ("`/` (footer)")
 * is not a nav item and does not match.
 */
function frozenNavigation(): Array<{ href: string; label: string }> {
  const lines = readFileSync(
    join(__dirname, "..", "..", "docs", "public-experience-narrative.md"),
    "utf8",
  ).split(/\r?\n/);
  const start = lines.findIndex((line) => line.startsWith("### 6.1 Navigation labels"));
  expect(start, "the narrative has no section 6.1").toBeGreaterThan(-1);
  const items: Array<{ href: string; label: string }> = [];
  for (const line of lines.slice(start + 1)) {
    if (line.startsWith("### ") || line.startsWith("## ")) {
      break;
    }
    const [, href, label] = line.match(/^\| `([^`]+)` \| \*\*([^*]+)\*\* \|/) ?? [];
    if (href !== undefined && label !== undefined) {
      items.push({ href, label });
    }
  }
  expect(items.length, "section 6.1 names no nav items").toBeGreaterThan(0);
  return items;
}

const withSlash = (href: string) => (href.endsWith("/") ? href : `${href}/`);

test.describe("the brand is on every route", () => {
  for (const route of ROUTES) {
    test(`${route} shows the wordmark, the monogram and the home label`, async ({ page }) => {
      await page.goto(route);
      await waitForStablePage(page);

      const home = await wordmark(page);
      await expect(home).toBeVisible();
      await expect(home).toContainText(BRAND);
      await expect(page.locator(".wordmark__mark")).toHaveText(MONOGRAM);

      // Decoration, so the accessible name is the brand once and not twice.
      await expect(page.locator(".wordmark__mark")).toHaveAttribute("aria-hidden", "true");
    });
  }

  test("the title default and template both carry the brand", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveTitle(`${BRAND} — Player Fingerprints`);

    await page.goto("/lab/");
    await expect(page).toHaveTitle(`Fingerprint Lab — ${BRAND}`);

    await page.goto("/science/");
    await expect(page).toHaveTitle(`How it works — ${BRAND}`);
  });

  test("the shareable deep link still resolves and is branded", async ({ page }) => {
    // The query string is the point: a static host has no router, so this only
    // works because the path itself is a real file.
    await page.goto(`/lab/?player=${PROFILE}`);
    await waitForStablePage(page);

    await expect(await wordmark(page)).toContainText(BRAND);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(
      "Compare one player with himself.",
    );
  });
});

test.describe("the surfaces a rename usually breaks", () => {
  test("the wordmark is server-rendered, so it survives with scripting off", async ({
    browser,
  }) => {
    const context = await browser.newContext({ javaScriptEnabled: false });
    const page = await context.newPage();
    await page.goto("/");

    await expect(page.locator(".wordmark")).toContainText(BRAND);
    await expect(page.locator(".wordmark__mark")).toHaveText(MONOGRAM);
    await expect(page).toHaveTitle(`${BRAND} — Player Fingerprints`);

    await context.close();
  });

  test("the fail-closed integrity message carries the brand and still fails closed", async ({
    page,
  }) => {
    // A profile body that does not match the manifest's recorded digest. The
    // featured profile is baked in at prerender, so this uses one the Lab
    // actually fetches — the same profile and the same mechanism the existing
    // failure-state suite uses.
    await page.route(`**${SHOWCASE_BASE}players/${MESSI_PROFILE_KEY}.json`, (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: "{}" }),
    );

    await page.goto(`/lab/?player=${MESSI_PROFILE_KEY}`);

    const alert = page.locator(".lab-state[role='alert']");
    await expect(alert).toContainText("This profile does not match the active manifest");
    // The renamed half.
    await expect(alert).toContainText(`${BRAND} stopped before rendering any profile values.`);
    // The half the rename may not touch: nothing rendered past the failure.
    await expect(page.locator(".selected-profile")).toHaveCount(0);
  });

  for (const width of WIDTHS) {
    test(`the longer wordmark fits at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.goto("/");
      await waitForStablePage(page);

      await expectNoPageOverflow(page);

      // Clipping is the failure mode a screenshot would show and an assertion
      // usually misses: the element reports its box happily while the glyphs
      // are cut off.
      const clipped = await page.locator(".wordmark").evaluate((element) => {
        const span = element.querySelector("span:not(.wordmark__mark)");
        if (!span) return { missing: true, overflowing: false, text: "" };
        return {
          missing: false,
          overflowing: span.scrollWidth > span.clientWidth + 1,
          text: (span.textContent ?? "").trim(),
        };
      });

      expect(clipped.missing).toBe(false);
      expect(clipped.text).toBe(BRAND);
      expect(clipped.overflowing, `the wordmark is clipped at ${width}px`).toBe(false);

      // 769px is where the header is still a single row (shell.css collapses it
      // to a column at 48rem), so the wordmark and the nav items compete for
      // one line. That is the width this bead was most likely to break.
      // `scoutlens-rdz.7` put a descriptor under the wordmark, and
      // `scoutlens-rdz.13` adds a fourth nav item; both run through here.
      const header = page.locator(".site-header__inner");
      await expect(header).toBeVisible();
      const headerOverflows = await header.evaluate(
        (element) => element.scrollWidth > element.clientWidth + 1,
      );
      expect(headerOverflows, `the header overflows at ${width}px`).toBe(false);
    });
  }

  test("the tab order is unchanged and the home link answers to the new name", async ({
    page,
  }) => {
    await page.goto("/");
    await waitForStablePage(page);

    await page.keyboard.press("Tab");
    await expect(page.getByRole("link", { name: "Skip to content" })).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(page.getByRole("link", { name: `${BRAND} home` })).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(page.getByRole("link", { name: "Overview" })).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(page.getByRole("link", { name: "Fingerprint Lab" })).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(page.getByRole("link", { name: "How it works" })).toBeFocused();
  });
});

test.describe("the header the redesign gives the brand (scoutlens-rdz.7)", () => {
  test("the nav is every narrative §6.1 item whose route is built, in §6.1's order", async (
    { page, request },
    testInfo,
  ) => {
    test.skip(testInfo.project.name !== "desktop", "content assertion, run once in desktop Chromium");
    // D075 makes "Case study" §6.1's fourth item. `scoutlens-rdz.13` adds it
    // to the nav in the pull request that creates `/case-study/` (owner
    // decision, 2026-11-09), because `quality-contract.spec.ts` requires every
    // rendered link to resolve. So the expectation is §6.1 filtered by what the
    // export serves: the day the route exists, this test requires its item.
    const expected: Array<{ href: string; label: string }> = [];
    for (const item of frozenNavigation()) {
      if ((await request.get(withSlash(item.href))).ok()) {
        expected.push(item);
      }
    }
    expect(
      expected.map((item) => item.label),
      "the three frozen labels must always be in the nav",
    ).toEqual(expect.arrayContaining(["Overview", "Fingerprint Lab", "How it works"]));

    await page.goto("/");
    await waitForStablePage(page);
    const links = page.getByRole("navigation", { name: "Primary navigation" }).getByRole("link");
    await expect(links).toHaveCount(expected.length);
    for (const [index, item] of expected.entries()) {
      await expect(links.nth(index)).toHaveText(item.label);
      await expect(links.nth(index)).toHaveAttribute("href", withSlash(item.href));
    }
  });

  for (const width of WIDTHS) {
    test(`the descriptor sits under the brand name and outside the home link at ${width}px`, async ({
      page,
    }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.goto("/");
      await waitForStablePage(page);

      // D075 and public-identity-contract.md §1: "Player Fingerprint Lab",
      // not the design's "Player Fingerprints".
      const descriptor = page.locator(".site-header .site-brand__descriptor");
      await expect(descriptor).toHaveText(DESCRIPTOR);
      await expect(descriptor).toBeVisible();
      // Outside the link, so the home link's name stays the brand alone.
      await expect(page.locator(".wordmark .site-brand__descriptor")).toHaveCount(0);
      await expect(await wordmark(page)).toHaveAccessibleName(`${BRAND} home`);

      const box = await page.evaluate(() => {
        const rect = (selector: string) => document.querySelector(selector)!.getBoundingClientRect();
        const name = rect(".wordmark span:not(.wordmark__mark)");
        const mark = rect(".wordmark__mark");
        const under = rect(".site-brand__descriptor");
        return { name, mark, under };
      });
      // Under the name, beside the mark, and level with the name's first letter.
      expect(box.under.top, "the descriptor is not below the brand name").toBeGreaterThanOrEqual(
        box.name.bottom - 1,
      );
      expect(box.under.left, "the descriptor is not beside the mark").toBeGreaterThanOrEqual(box.mark.right);
      expect(Math.abs(box.under.left - box.name.left)).toBeLessThanOrEqual(1);
      // And the mark is centred on the two lines together.
      const pair = (box.name.top + box.under.bottom) / 2;
      const markCentre = (box.mark.top + box.mark.bottom) / 2;
      expect(Math.abs(pair - markCentre), "the mark is not centred on the name and descriptor").toBeLessThanOrEqual(3);
    });
  }
});

test.describe("the accent, and the old name that stays", () => {
  test("á renders in the pinned font instead of falling back silently", async ({
    page,
    browserName,
  }) => {
    test.skip(browserName !== "chromium", "CDP font reporting is Chromium-only");

    await page.goto("/");
    await waitForStablePage(page);
    await page.evaluate(() => document.fonts.ready);

    // Inter ships here as two local woff2 subsets. `á` should be in `latin`,
    // but a glyph the subset lacks does not error — it falls back to Arial and
    // the only symptom is that the wordmark looks slightly wrong. So ask the
    // renderer which font it actually used, rather than assuming the subset.
    const client = await page.context().newCDPSession(page);
    await client.send("DOM.enable");
    await client.send("CSS.enable");
    const { root } = (await client.send("DOM.getDocument")) as { root: { nodeId: number } };
    const { nodeId } = (await client.send("DOM.querySelector", {
      nodeId: root.nodeId,
      selector: ".wordmark span:not(.wordmark__mark)",
    })) as { nodeId: number };
    expect(nodeId, "the wordmark text node was not found").toBeGreaterThan(0);

    const { fonts } = (await client.send("CSS.getPlatformFontsForNode", { nodeId })) as {
      fonts: { familyName: string; glyphCount: number }[];
    };

    expect(fonts.length, "no platform font was reported for the wordmark").toBeGreaterThan(0);
    const families = fonts.map((font) => font.familyName);
    // One family for the whole string: a second one means some characters —
    // in practice the accented vowel — came from somewhere else.
    expect(
      fonts.length,
      `the wordmark rendered in more than one font: ${families.join(", ")}`,
    ).toBe(1);
    expect(families[0]).toMatch(/inter/i);

    await client.detach();
  });

  test("the only old-brand text on the page is the artifact's own provenance note", async ({
    page,
  }) => {
    await page.goto("/");
    await waitForStablePage(page);

    const pageText = (await page.locator("body").innerText()).replace(/\s+/g, " ");
    const occurrences = pageText.split(RETIRED).length - 1;

    // Not zero, and that is deliberate. `manifest.source.redistribution_note`
    // is baked into a content-addressed artifact whose digest is pinned by
    // config/showcase-payload-pack.json and belongs to an already published
    // release asset. Rewording it would change the dataset identity the case
    // study and the release manifest both quote — a cosmetic edit propagating
    // into the project's scientific identity.
    //
    // docs/public-identity-contract.md §5: the standard is not "no old brand
    // on the active surface", which was never achievable, but "no
    // *unexplained* old brand".
    const note = page.locator(".provider-boundary__card--primary");
    const noteText = (await note.innerText()).replace(/\s+/g, " ");
    const inNote = noteText.split(RETIRED).length - 1;

    expect(inNote, "the provenance note should still carry the artifact's own wording").toBe(1);
    expect(
      occurrences,
      `found ${occurrences} occurrences of "${RETIRED}" but only ${inNote} are accounted for ` +
        "by the pinned provenance note — a display surface was missed",
    ).toBe(inNote);
  });
});
