/**
 * The identity challenge transitions, URL semantics and history
 * (`scoutlens-9a3.6.3`).
 *
 * These run here rather than in vitest because the project's unit environment
 * is `node` with no DOM, and what §4 specifies is a real history stack: pushed
 * entries, back and forward, and a deep link that restores a state without
 * stepping through its predecessors. Simulating that with jsdom would add a
 * dependency to approximate what this suite already does natively.
 */

import { expect, test } from "@playwright/test";

import { SHOWCASE_BASE, waitForStablePage } from "./helpers";

const PANEL = '[data-challenge-panel="orientation"]';
const STATES = "[data-challenge-state]";

async function gotoLab(page: import("@playwright/test").Page, search = ""): Promise<void> {
  await page.goto(`/lab/${search}`);
  await waitForStablePage(page);
}

test("the challenge walks orientation to evidence and back", async ({ page }) => {
  await gotoLab(page);

  await expect(page.locator(STATES)).toHaveAttribute("data-challenge-state", "orientation");
  await expect(page.getByRole("button", { name: "See the fingerprint" })).toBeVisible();
  // §3.1 hides identity until the reveal.
  await expect(page.locator("[data-challenge-identity]")).toHaveCount(0);

  await page.getByRole("button", { name: "See the fingerprint" }).click();
  await expect(page.locator(STATES)).toHaveAttribute("data-challenge-state", "query");
  await expect(page).toHaveURL(/challenge=query/);
  // §3.2 shows period A only; the period-B fingerprint is hidden.
  await expect(page.locator('[data-challenge-fingerprint="a"]')).toBeVisible();
  await expect(page.locator('[data-challenge-fingerprint="ab"]')).toHaveCount(0);
  await expect(page.locator("[data-challenge-identity]")).toHaveCount(0);

  await page.getByRole("button", { name: "Reveal the result" }).click();
  await expect(page.locator(STATES)).toHaveAttribute("data-challenge-state", "reveal");
  await expect(page).toHaveURL(/challenge=reveal/);
  await expect(page.locator("[data-challenge-identity]")).toBeVisible();
  await expect(page.locator('[data-challenge-fingerprint="ab"]')).toBeVisible();

  await page.getByRole("button", { name: "See the evidence" }).click();
  await expect(page.locator(STATES)).toHaveAttribute("data-challenge-state", "evidence");
  await expect(page).toHaveURL(/challenge=evidence/);
  await expect(page.locator("[data-challenge-contributions] li")).toHaveCount(5);

  await page.getByRole("button", { name: "Back to result" }).click();
  await expect(page.locator(STATES)).toHaveAttribute("data-challenge-state", "reveal");
});

test("each transition pushes a history entry that back and forward traverse", async ({ page }) => {
  await gotoLab(page);
  await page.getByRole("button", { name: "See the fingerprint" }).click();
  await page.getByRole("button", { name: "Reveal the result" }).click();
  await page.getByRole("button", { name: "See the evidence" }).click();

  // §4: "each state push a URL entry ... Back/forward navigates between
  // challenge states." Back must move through the states, not leave the page.
  await page.goBack();
  await expect(page.locator(STATES)).toHaveAttribute("data-challenge-state", "reveal");
  await page.goBack();
  await expect(page.locator(STATES)).toHaveAttribute("data-challenge-state", "query");
  await page.goBack();
  await expect(page.locator(STATES)).toHaveAttribute("data-challenge-state", "orientation");

  await page.goForward();
  await expect(page.locator(STATES)).toHaveAttribute("data-challenge-state", "query");
  await page.goForward();
  await expect(page.locator(STATES)).toHaveAttribute("data-challenge-state", "reveal");
});

test("a deep link restores its state without stepping through the ramps", async ({ page }) => {
  // §4: "The orientation and query states are entry ramps, not gates."
  await gotoLab(page, "?challenge=reveal");
  await expect(page.locator(STATES)).toHaveAttribute("data-challenge-state", "reveal");
  await expect(page.locator("[data-challenge-identity]")).toBeVisible();

  await page.reload();
  await waitForStablePage(page);
  await expect(page.locator(STATES)).toHaveAttribute("data-challenge-state", "reveal");
});

test("an unrecognised challenge state recovers to orientation", async ({ page }) => {
  // §8: invalid URL state returns to the documented recovery state without
  // changing the scientific query.
  await gotoLab(page, "?challenge=not-a-state");
  await expect(page.locator(STATES)).toHaveAttribute("data-challenge-state", "orientation");
  await expect(page.getByRole("button", { name: "See the fingerprint" })).toBeVisible();
});

test("the challenge is operable by keyboard, and Escape returns to orientation", async ({
  page,
}) => {
  await gotoLab(page);

  const cta = page.getByRole("button", { name: "See the fingerprint" });
  await cta.focus();
  await page.keyboard.press("Enter");
  await expect(page.locator(STATES)).toHaveAttribute("data-challenge-state", "query");

  // §6.2: entering a state moves focus to the state's heading.
  await expect(page.locator(".challenge-panel__heading")).toBeFocused();

  await page.keyboard.press("Escape");
  await expect(page.locator(STATES)).toHaveAttribute("data-challenge-state", "orientation");
  await expect(page.locator(".challenge-panel__heading")).toBeFocused();
});

test("the reveal states the method, provenance and the weighted label", async ({ page }) => {
  await gotoLab(page, "?challenge=reveal");

  await expect(page.locator("[data-challenge-method]")).toHaveText("combined_scaler_diagonal_v1");
  await expect(page.locator("[data-challenge-representation]")).toContainText("rep-");
  // §3.3, D047: the published score is weighted and must never be labelled a
  // plain cosine.
  // Scoped to the panel: the Lab's method-disclosure heading below carries the
  // same frozen label, and an unscoped query matches both.
  await expect(page.locator(PANEL).getByText("Learned weighted similarity")).toBeVisible();
  await expect(page.locator(PANEL)).not.toContainText("Cosine similarity");
});

test("the resampling interval is rounded for display, not interpolated raw", async ({ page }) => {
  await gotoLab(page, "?challenge=reveal");
  const interval = page.locator("[data-challenge-interval]");
  await expect(interval).toBeVisible();

  // D046: resampled rank bounds are legitimately fractional, and interpolating
  // one straight into a template prints its full binary expansion. The
  // published upper bound rendered as "43.524999999999998" until this was
  // routed through formatRank - caught by looking at a baseline image, not by a
  // failing assertion, which is why the assertion now exists.
  const text = (await interval.textContent()) ?? "";
  expect(text).not.toMatch(/\d\.\d{3,}/);
  expect(text).toMatch(/95% resampling interval/);
});

test("every mandatory caveat stays visible in the result states", async ({ page }) => {
  for (const state of ["reveal", "evidence"]) {
    await gotoLab(page, `?challenge=${state}`);
    for (const code of [
      "fingerprint_not_style_proof",
      "same_season_team_confound",
      "similarity_not_recruitment",
      "within_role_display_differs_from_global_model",
    ]) {
      await expect(page.locator(`[data-caveat="${code}"]`).first()).toBeVisible();
    }
  }
});

test("Explore every fingerprint reaches the Lab explorer", async ({ page }) => {
  // §5 makes this the one CTA that is a link, scrolling rather than navigating.
  await gotoLab(page, "?challenge=reveal");
  const link = page.getByRole("link", { name: "Explore every fingerprint" });
  await expect(link).toHaveAttribute("href", "#lab-explorer");
  await link.click();
  await expect(page.locator("#lab-explorer")).toBeInViewport();
});

test("the challenge prints counts the way the rest of the Lab does", async ({ page }) => {
  // `scoutlens-9a3.17`. The reveal said "rank 1 of 1257" a few hundred pixels
  // above a replay card saying "of 1,257", and the query said "1140 minutes"
  // above a period card saying "1,140 minutes". Compared against the Lab on
  // the same page rather than against literals, so the assertion follows the
  // data and fails only on a disagreement between the two surfaces.
  await gotoLab(page, "?challenge=reveal");
  const labCount = (
    await page.locator('.retrieval-outcome[data-retrieval-scope="global"] .retrieval-outcome__rank span').innerText()
  ).replace(/^of /, "");
  await expect(page.locator(".challenge-panel__heading")).toHaveText(new RegExp(`of ${labCount}\.$`));
  await expect(page.locator("[data-challenge-rank]")).toContainText(`of ${labCount}`);

  await gotoLab(page, "?challenge=query");
  const labMinutes = (await page.locator(".period-context-card").first().innerText()).match(/([\d,]+) minutes/)?.[1];
  expect(labMinutes, "the Lab's period-A card states no minutes").toBeTruthy();
  await expect(page.locator(".challenge-panel__periods")).toContainText(`${labMinutes} minutes`);
});

/**
 * `scoutlens-9a3.27`: the epic 9a3 closure audit (2026-10-07) found the reveal
 * never compared with the published profile, Escape leaking out of the
 * neighbour drawer, the challenge rewriting the explorer's `?player`, and a dead
 * button without JavaScript. D068 records the URL and profile rules.
 */
interface PublishedOutcome {
  self_rank: number;
  candidate_count: number;
  similarity_score: number | null;
  uncertainty: { status: string; rank_ci_95: readonly [number, number] | null };
}

interface PublishedProfile {
  identity: { display_name: string };
  retrieval: { global: PublishedOutcome; baseline_role_minutes: PublishedOutcome };
}

/** The published rank formatting rule, mirrored from components/rank-format.ts. */
function formatRank(value: number): string {
  const fixed = value.toFixed(1);
  return fixed.endsWith(".0") ? fixed.slice(0, -2) : fixed;
}

async function published(request: import("@playwright/test").APIRequestContext) {
  const manifest = (await (await request.get(`${SHOWCASE_BASE}manifest.json`)).json()) as {
    featured_profile: { profile_key: string; reason: string };
  };
  const profile = (await (
    await request.get(`${SHOWCASE_BASE}players/${manifest.featured_profile.profile_key}.json`)
  ).json()) as PublishedProfile;
  const index = (await (await request.get(`${SHOWCASE_BASE}players.index.json`)).json()) as {
    profiles: Array<{ profile_key: string; display_name: string }>;
  };
  const other = index.profiles.find((item) => item.profile_key !== manifest.featured_profile.profile_key);
  if (other === undefined) {
    throw new Error("the index has no profile besides the featured one");
  }
  return { manifest, profile, other };
}

test("the reveal prints the published profile's rank, interval, baseline and similarity", async ({
  page,
  request,
}) => {
  const { profile } = await published(request);
  const { global, baseline_role_minutes: baseline } = profile.retrieval;
  await gotoLab(page, "?challenge=reveal");

  await expect(page.locator("[data-challenge-rank]")).toContainText(
    `${global.self_rank} of ${global.candidate_count.toLocaleString("en-US")}`,
  );
  if (global.uncertainty.rank_ci_95 === null) {
    await expect(page.locator("[data-challenge-interval]")).toHaveCount(0);
  } else {
    const [low, high] = global.uncertainty.rank_ci_95;
    await expect(page.locator("[data-challenge-interval]")).toContainText(`${formatRank(low)}–${formatRank(high)}`);
  }
  await expect(page.locator("[data-challenge-baseline]")).toHaveText(String(baseline.self_rank));
  await expect(page.locator("[data-challenge-similarity]")).toHaveText(
    global.similarity_score === null ? "not published for this profile" : global.similarity_score.toFixed(3),
  );
  // §3.3's plain-language comparison, the §12 sentence.
  await expect(page.locator("[data-challenge-baseline-sentence]")).toHaveText(
    `A role-and-minutes baseline ranked them ${formatRank(baseline.self_rank)}.`,
  );
  // The uncertainty caveat the artifact's status calls for, with the others.
  const uncertaintyCaveat: string | undefined = (
    { available: "uncertainty_sampling_only", pending: "uncertainty_pending" } as Record<string, string>
  )[global.uncertainty.status];
  if (uncertaintyCaveat !== undefined) {
    await expect(page.locator(`${PANEL} [data-caveat="${uncertaintyCaveat}"]`)).toBeVisible();
  }
});

test("Escape returns to orientation only when the challenge owns it", async ({ page }) => {
  for (const state of ["reveal", "evidence"]) {
    await gotoLab(page, `?challenge=${state}`);

    // The neighbour drawer handles its own Escape. The challenge's listener is
    // on window and used to hear it too, resetting itself and pulling focus to
    // the top of the page while the reader was closing a dialog below.
    await page.locator('[data-neighbor-rank="1"]').getByRole("button", { name: "Open evidence comparison" }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toBeHidden();
    await expect(page.locator(STATES), `${state}: closing the drawer reset the challenge`).toHaveAttribute(
      "data-challenge-state",
      state,
    );
    await expect(page).toHaveURL(new RegExp(`challenge=${state}`));

    // Escape in the explorer's search box is the reader's, not the challenge's.
    await page.getByRole("searchbox", { name: "Search players" }).focus();
    await page.keyboard.press("Escape");
    await expect(page.locator(STATES), `${state}: Escape in search reset the challenge`).toHaveAttribute(
      "data-challenge-state",
      state,
    );

    // Inside the panel, §6.2 applies.
    await page.locator(".challenge-panel__heading").focus();
    await page.keyboard.press("Escape");
    await expect(page.locator(STATES)).toHaveAttribute("data-challenge-state", "orientation");
    await expect(page.locator(".challenge-panel__heading")).toBeFocused();
  }
});

test("the challenge leaves the explorer's ?player to the explorer (D068)", async ({ page, request }) => {
  const { profile, other } = await published(request);
  await gotoLab(page, `?player=${other.profile_key}`);
  await expect(page.locator(".selected-profile__header h2")).toHaveText(other.display_name);

  await page.getByRole("button", { name: "See the fingerprint" }).click();
  await expect(page).toHaveURL(new RegExp(`player=${other.profile_key}`));
  await expect(page).toHaveURL(/challenge=query/);
  await page.getByRole("button", { name: "Reveal the result" }).click();
  await expect(page).toHaveURL(new RegExp(`player=${other.profile_key}`));
  await expect(page).toHaveURL(/challenge=reveal/);

  // The challenge is the featured profile's and names it; the explorer keeps
  // the reader's own selection, and a reload keeps both.
  await expect(page.locator("[data-challenge-identity]")).toContainText(profile.identity.display_name);
  await expect(page.locator(".selected-profile__header h2")).toHaveText(other.display_name);
  await page.reload();
  await waitForStablePage(page);
  await expect(page.locator(STATES)).toHaveAttribute("data-challenge-state", "reveal");
  await expect(page.locator("[data-challenge-identity]")).toContainText(profile.identity.display_name);
  await expect(page.locator(".selected-profile__header h2")).toHaveText(other.display_name);
});

test.describe("without JavaScript", () => {
  test.use({ javaScriptEnabled: false });

  test("the degraded card is the experience, and no control is left that cannot work", async ({
    page,
    request,
  }) => {
    const { manifest, profile } = await published(request);
    const { global, baseline_role_minutes: baseline } = profile.retrieval;
    await page.goto("/lab/");

    const degraded = page.locator("[data-challenge-degraded]");
    await expect(degraded).toBeVisible();
    await expect(degraded.locator("[data-challenge-result]")).toHaveText(
      `${profile.identity.display_name}'s second-half profile was ranked ${global.self_rank} of ` +
        `${global.candidate_count.toLocaleString("en-US")} by fingerprint similarity, versus ` +
        `${formatRank(baseline.self_rank)} by the role-and-minutes baseline.`,
    );
    for (const code of [
      "fingerprint_not_style_proof",
      "same_season_team_confound",
      "similarity_not_recruitment",
      "within_role_display_differs_from_global_model",
    ]) {
      await expect(degraded.locator(`[data-caveat="${code}"]`)).toBeVisible();
    }
    // §2's editorial invariant holds without JavaScript too.
    await expect(page.locator(PANEL)).toContainText(manifest.featured_profile.reason);
    // The orientation's button has nothing to run here.
    await expect(page.getByRole("button", { name: "See the fingerprint" })).toBeHidden();
  });
});
