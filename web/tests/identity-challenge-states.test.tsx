/**
 * The identity challenge state machine (`scoutlens-9a3.6.3`).
 *
 * The vitest environment is `node` and the project carries no DOM testing
 * library, so this file proves what can be proven without a browser: the pure
 * URL mapping, the frozen §6.3 announcements, and the server-rendered default
 * state. The transitions themselves - clicking, history, focus movement - are
 * proven in `e2e/identity-challenge.spec.ts`, where there is a real browser and
 * a real history stack.
 *
 * That split is deliberate rather than a gap. Adding jsdom and a testing
 * library to assert a `pushState` that Playwright already exercises for real
 * would add a dependency to simulate what CI runs natively.
 */

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import {
  ChallengeFingerprint,
  IdentityChallengeStates,
  challengeAnnouncement,
  stateFromSearch,
  type ChallengeState,
} from "@/components/identity-challenge-states";
import { buildIdentityChallenge, type IdentityChallengeView } from "@/content/identity-challenge";
import { buildFingerprintRows } from "@/content/showcase-lab";

import catalog from "../e2e/fixtures/lab-max-content-v2/feature-catalog.json";
import manifest from "../e2e/fixtures/lab-max-content-v2/manifest.json";
import profile from "../e2e/fixtures/lab-max-content-v2/players/wy-900001-c-901.json";
import representation from "../e2e/fixtures/lab-max-content-v2/representation.json";
import research from "../e2e/fixtures/lab-max-content-v2/research-summary.json";

function view(): IdentityChallengeView {
  const built = buildIdentityChallenge({
    manifest: manifest as never,
    profile: profile as never,
    representation: representation as never,
    research: research as never,
  });
  if (!built.available) {
    throw new Error(`The fixture does not build a challenge: ${built.code}`);
  }
  return built;
}

const rows = buildFingerprintRows(catalog as never, profile as never);

function markup(): string {
  return renderToStaticMarkup(<IdentityChallengeStates view={view()} rows={rows} />);
}

describe("the URL names the state", () => {
  it.each([
    ["?challenge=query", "query"],
    ["?challenge=reveal", "reveal"],
    ["?challenge=evidence", "evidence"],
    ["?player=wy-900001-c-901&challenge=reveal", "reveal"],
  ])("reads %s as %s", (search, expected) => {
    expect(stateFromSearch(search)).toBe(expected as ChallengeState);
  });

  it.each([
    ["", "no parameter at all"],
    ["?player=wy-900001-c-901", "a profile but no challenge state"],
    ["?challenge=", "an empty value"],
    ["?challenge=REVEAL", "the right word in the wrong case"],
    ["?challenge=evidence-panel", "a value that merely starts correctly"],
    ["?challenge=../../etc", "a traversal-shaped value"],
  ])("recovers to orientation for %s (%s)", (search) => {
    // §8: "invalid URL state returns to the documented recovery state without
    // changing the scientific query". Orientation is an entry ramp, not an
    // error page, so a bad parameter costs the reader nothing.
    expect(stateFromSearch(search)).toBe("orientation");
  });
});

describe("the frozen announcements", () => {
  it("announces the query state without revealing identity", () => {
    const announcement = challengeAnnouncement(view(), "query");
    expect(announcement).toBe("Showing the first-half fingerprint. Identity hidden.");
    // The whole point of the query state is that identity is not yet known, so
    // an announcement that named the player would defeat it for exactly the
    // readers who depend on announcements.
    expect(announcement).not.toContain(profile.identity.display_name);
  });

  it("announces the reveal with identity and rank, from stored values", () => {
    const global = profile.retrieval.global;
    expect(challengeAnnouncement(view(), "reveal")).toBe(
      `Result revealed. ${profile.identity.display_name}, ${profile.identity.role}, ` +
        `${profile.identity.competition.name}. Ranked ${global.self_rank} of ` +
        `${global.candidate_count}.`,
    );
  });

  it("announces the evidence state", () => {
    expect(challengeAnnouncement(view(), "evidence")).toBe("Showing contribution evidence.");
  });

  it("announces nothing for orientation", () => {
    expect(challengeAnnouncement(view(), "orientation")).toBe("");
  });
});

describe("the server-rendered default state", () => {
  it("is orientation, and hides identity and every retrieval value", () => {
    const html = markup();
    expect(html).toContain('data-challenge-state="orientation"');
    expect(html).toContain("See the fingerprint");

    // §3.1 hides identity, all metric values and the neighbor list. This is the
    // state a search engine and a first paint see, so it is the one that must
    // not leak the answer.
    expect(html).not.toContain(profile.identity.display_name);
    expect(html).not.toContain("data-challenge-rank");
    expect(html).not.toContain("data-challenge-similarity");
    expect(html).not.toContain("data-challenge-fingerprint");
  });

  it("renders the transition CTA as a button, per section 5", () => {
    // §5 fixes the element type: every state-transition CTA is a `<button>`.
    // A link would put the state in the href and make the transition a
    // navigation, which §4 assigns to pushState instead.
    expect(markup()).toMatch(/<button[^>]*data-challenge-cta="query"/);
  });

  it("carries a polite live region that survives the state swap", () => {
    // The region is rendered outside the swapped content on purpose: replacing
    // the node a screen reader is reading from can drop the announcement.
    const html = markup();
    expect(html).toMatch(/aria-live="polite"/);
    expect(html.indexOf("aria-live")).toBeLessThan(html.indexOf('data-challenge-cta="query"'));
  });

  it("gives the heading a focus target for section 6.2", () => {
    expect(markup()).toMatch(/<h2[^>]*tabindex="-1"/);
  });
});

describe("the fingerprint plot", () => {
  it("builds one row per frozen feature", () => {
    expect(rows).toHaveLength(32);
  });

  it("never draws a period-B mark when period B is hidden", () => {
    // The Lab's own row component always draws both marks. Reusing it in the
    // query state would render exactly the period-B fingerprint §3.2 hides,
    // which is why the challenge has its own row markup. Asserted against the
    // plot itself: inferring it from a state that renders no plot would pass
    // for the wrong reason.
    const queryPlot = renderToStaticMarkup(
      <ChallengeFingerprint rows={rows} showPeriodB={false} caption="first half" />,
    );
    expect(queryPlot).toContain("challenge-fingerprint__mark--a");
    expect(queryPlot).not.toContain("challenge-fingerprint__mark--b");
    expect(queryPlot).toContain('data-challenge-fingerprint="a"');
    expect(queryPlot).not.toContain("period B");

    const revealPlot = renderToStaticMarkup(
      <ChallengeFingerprint rows={rows} showPeriodB caption="both halves" />,
    );
    expect(revealPlot).toContain("challenge-fingerprint__mark--b");
    expect(revealPlot).toContain('data-challenge-fingerprint="ab"');
    expect(revealPlot).toContain("period B");
  });
});
