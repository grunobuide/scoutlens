/**
 * `/science/` section order (`scoutlens-9a3.11`).
 *
 * **What this guards.** Comprehension run 1 asked "what role does AI play in
 * what you are looking at?" and the first public-only reader answered
 * "describing player types" — inverting the AI boundary and the critical
 * `fingerprint_not_style_proof` caveat at once.
 *
 * The measured cause was placement, not wording: "Engineering and AI boundary"
 * sat at **block 244 of 293**, second to last before the provenance footer,
 * and the landing page never raises AI at all. A reader who covered the whole
 * site in 2:53 never reached it. `#102` moved it to **block 10 of 290**, ahead
 * of the numbered sequence, where it reads as framing.
 *
 * **That diagnosis is a hypothesis about a person, not a measurement of one.**
 * Run 1 captured no element-read trace — the field was left empty on all six
 * questions — so nothing records what R1 was actually looking at. The placement
 * evidence is strong (2:53 for the whole site; the section 83% down a long
 * page) but it is inference. This file guards the *change*, and cannot tell
 * anyone whether the change helped a reader. Under `D056` no fresh reviewer is
 * required to land it, and no comprehension improvement may be claimed from a
 * green run here.
 *
 * **Why a presence check was not enough.** `claims-consistency.spec.ts` already
 * asserts the AI boundary survives the first paint without JavaScript. That
 * assertion passed on the pre-fix build too, because the section was always
 * present — just unreachable in practice. Presence and position are different
 * properties, and only the second one was the defect.
 */

import { expect, test, type Page } from "@playwright/test";

import { waitForStablePage } from "./helpers";

/** The framing section, and the first numbered step it must precede. */
const AI_BOUNDARY = ".science-engineering";
const FIRST_STEP = ".frozen-question";

async function openScience(page: Page): Promise<void> {
  await page.goto("/science/");
  await waitForStablePage(page);
}

/** DOM position of the two sections among every element inside `main`. */
async function domOrder(page: Page): Promise<{ boundary: number; firstStep: number }> {
  return page.evaluate(
    (selectors) => {
      const all = [...document.querySelectorAll("main *")];
      const indexOf = (selector: string) => {
        const element = document.querySelector(`main ${selector}`);
        return element === null ? -1 : all.indexOf(element);
      };
      return { boundary: indexOf(selectors.boundary), firstStep: indexOf(selectors.firstStep) };
    },
    { boundary: AI_BOUNDARY, firstStep: FIRST_STEP },
  );
}

test.beforeEach(async ({}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Section order runs once in desktop Chromium");
});

test("the AI boundary precedes the numbered sequence in DOM order", async ({ page }) => {
  await openScience(page);

  const { boundary, firstStep } = await domOrder(page);

  expect(boundary, "the Engineering and AI boundary section is missing").toBeGreaterThan(-1);
  expect(firstStep, "the 01 · question section is missing").toBeGreaterThan(-1);
  expect(
    boundary,
    "the AI boundary no longer precedes 01 · question — this is the scoutlens-9a3.11 regression",
  ).toBeLessThan(firstStep);
});

test("the numbered sequence is still 01 to 06, in order and unbroken", async ({ page }) => {
  await openScience(page);

  // The stop condition on `scoutlens-9a3.11` was that the framing section may
  // sit before the sequence but must never be given a number or interleaved
  // into it. Asserting the markers are exactly 01-06 ascending catches both:
  // a seventh marker means the section was numbered, and a gap means it was
  // dropped between two steps.
  const markers = await page.evaluate(() =>
    [...document.querySelectorAll("main .research-step__marker")].map((node) =>
      (node.textContent ?? "").trim(),
    ),
  );

  const numbers = markers.map((text) => text.match(/^\d+/)?.[0] ?? null);
  expect(numbers, "a step marker does not start with a number").not.toContain(null);
  expect(numbers, "the numbered research sequence is no longer 01-06 in order").toEqual([
    "01",
    "02",
    "03",
    "04",
    "05",
    "06",
  ]);
});

test("the order is real DOM order, not CSS order", async ({ page }) => {
  await openScience(page);

  // `scoutlens-uze.5`'s stop condition, applied here: a sequence achieved with
  // CSS `order` reads correctly to the eye and wrongly to a screen reader. The
  // move in #102 was a DOM move precisely so the two cannot disagree, and this
  // is what keeps a later "fix" from reaching for the cheaper CSS route.
  const reordered = await page.evaluate(() =>
    [...document.querySelectorAll("main *")]
      .filter((element) => {
        const order = getComputedStyle(element).order;
        return order !== "" && order !== "0";
      })
      .map((element) => `${element.tagName.toLowerCase()}.${element.className}`),
  );
  expect(reordered, "an element on /science/ carries a non-default CSS order").toEqual([]);

  const geometry = await page.evaluate(
    (selectors) => {
      const top = (selector: string) => {
        const element = document.querySelector(`main ${selector}`);
        return element === null ? -1 : element.getBoundingClientRect().top + window.scrollY;
      };
      return { boundary: top(selectors.boundary), firstStep: top(selectors.firstStep) };
    },
    { boundary: AI_BOUNDARY, firstStep: FIRST_STEP },
  );

  expect(geometry.boundary, "no AI boundary to measure").toBeGreaterThan(-1);
  expect(
    geometry.boundary,
    "the AI boundary renders below 01 · question even though the DOM says otherwise",
  ).toBeLessThan(geometry.firstStep);
});

test.describe("without JavaScript", () => {
  test.use({ javaScriptEnabled: false });

  test("the AI boundary is in place on the first paint", async ({ page }) => {
    // Position, not presence. The served HTML has to carry the section *and*
    // carry it ahead of the sequence, because a reader forms their model of
    // what the system is from what the first paint shows them in the order it
    // shows it.
    await page.goto("/science/");

    const { boundary, firstStep } = await domOrder(page);
    expect(boundary, "the AI boundary needs hydration to exist").toBeGreaterThan(-1);
    expect(boundary, "the AI boundary needs hydration to reach its position").toBeLessThan(
      firstStep,
    );

    const section = page.locator(AI_BOUNDARY);
    await expect(section).toContainText("No live LLM is required for any current page");
    await expect(section).toContainText("AI never recomputes a value");
  });
});
