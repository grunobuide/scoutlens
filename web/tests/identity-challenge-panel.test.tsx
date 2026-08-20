/**
 * The identity challenge panel, orientation and degraded states
 * (`scoutlens-9a3.6.2`).
 *
 * Rendered with `renderToStaticMarkup`, matching the rest of the suite. That
 * is not only convention here: the panel is a server component whose whole
 * claim is that it produces complete HTML with no client JavaScript, and
 * static markup is the direct evidence for that claim.
 *
 * The copy assertions pin frozen §12 strings. They are not style checks - the
 * difference between "the fingerprint found them at rank 7" and any paraphrase
 * that sounds like a verdict is the difference between reporting a retrieval
 * rank and making a claim about a player.
 */

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { IdentityChallengePanel } from "@/components/identity-challenge-panel";
import { buildIdentityChallenge, type IdentityChallengeView } from "@/content/identity-challenge";
import type { IdentityChallengeData } from "@/content/load-identity-challenge";

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

function markup(data: IdentityChallengeData): string {
  return renderToStaticMarkup(<IdentityChallengePanel data={data} />);
}

function readyMarkup(): string {
  return markup({ status: "ready", datasetVersion: manifest.dataset_version, view: view() });
}

/** Everything inside `<noscript>` - the whole no-JavaScript experience. */
function noscriptMarkup(html: string): string {
  return [...html.matchAll(/<noscript>([\s\S]*?)<\/noscript>/g)].map((m) => m[1]).join("");
}

function text(html: string): string {
  return html
    .replace(/<[^>]+>/g, " ")
    .replace(/&#x27;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&#x2F;/g, "/")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&")
    .replace(/\s+/g, " ");
}

/**
 * Query parameters only, deliberately.
 *
 * `next/link` applies `trailingSlash: true` from `next.config.ts` at build
 * time, not in a bare `renderToStaticMarkup` call, so this render emits
 * `/lab?player=` where the export emits `/lab/?player=`. Asserting the exact
 * prefix here would pin the wrong one. The built form was verified directly in
 * `out/lab/index.html`, and the navigable URL is slice 4's E2E surface; what
 * this file owns is that the panel points at the right profile and state.
 */
function hrefQuery(html: string, marker: string): string {
  const match = new RegExp(`href="[^"]*${marker}[^"]*"`).exec(html);
  return match === null ? "" : match[0];
}

describe("the orientation state", () => {
  it("renders the frozen copy verbatim", () => {
    const body = text(readyMarkup());
    expect(body).toContain("Can a player's actions identify them?");
    expect(body).toContain(
      "We take the first half of their season as a query and test whether 32 " +
        "measurements of how they act can find that same player again in the second half.",
    );
    expect(body).toContain("See the fingerprint");
  });

  it("renders the editorial selection reason verbatim", () => {
    // §2's editorial disclosure invariant. The reason is the artifact's, and no
    // state may hide or paraphrase it - a featured profile that looks chosen by
    // rank reads as a result rather than an editorial pick.
    const html = readyMarkup();
    expect(html).toContain("data-challenge-editorial");
    expect(text(html)).toContain(manifest.featured_profile.reason);
  });

  it("shows the fingerprint boundary caveat, and hides identity and ranks", () => {
    const html = readyMarkup();
    const outside = text(html.replace(/<noscript>[\s\S]*?<\/noscript>/g, ""));

    expect(html).toContain('data-caveat="fingerprint_not_style_proof"');
    // §3.1 hides identity and every retrieval value until the reveal. Asserted
    // against the rendered sentences rather than bare digits: "7" occurs inside
    // the dataset pin and the season, so a digit scan would fail on text that
    // reveals nothing.
    expect(outside).not.toContain(profile.identity.display_name);
    expect(outside).not.toContain("was ranked");
    expect(outside).not.toContain("role-and-minutes baseline");
  });

  it("links to the URL the contract documents for the query state", () => {
    // §1's URL table. Slice 3 gives this parameter its behaviour; the link
    // points at the documented place from the start rather than at a button
    // that does nothing.
    const href = hrefQuery(readyMarkup(), "challenge=query");
    expect(href).toContain(`player=${profile.profile_key}`);
    expect(href).toContain("challenge=query");
  });
});

describe("the degraded state", () => {
  it("renders the result sentence from stored values, inside noscript", () => {
    const degraded = noscriptMarkup(readyMarkup());
    const global = profile.retrieval.global;
    const baseline = profile.retrieval.baseline_role_minutes.self_rank;

    expect(degraded).toContain("data-challenge-degraded");
    expect(text(degraded)).toContain(
      `${profile.identity.display_name}'s second-half profile was ranked ` +
        `${global.self_rank} of ${global.candidate_count} by fingerprint similarity, ` +
        `versus ${baseline} by the role-and-minutes baseline.`,
    );
  });

  it("carries every mandatory caveat the profile publishes", () => {
    // §3.5: "the boundary a reader sees without JavaScript is the same one they
    // see with it". A degraded state that drops caveats to save space would
    // publish the finding without its limits.
    const degraded = noscriptMarkup(readyMarkup());
    for (const code of [
      "fingerprint_not_style_proof",
      "same_season_team_confound",
      "similarity_not_recruitment",
      "within_role_display_differs_from_global_model",
      "uncertainty_pending",
    ]) {
      expect(degraded).toContain(`data-caveat="${code}"`);
    }
  });

  it("names both period labels and links into the full evidence", () => {
    const degraded = noscriptMarkup(readyMarkup());
    expect(text(degraded)).toContain(profile.periods.a.label);
    expect(text(degraded)).toContain(profile.periods.b.label);
    // The closing quote matters: it proves this is the plain profile link
    // (§3.5's "link to the featured profile"), not the query-state CTA, which
    // carries a further &challenge= parameter.
    expect(degraded).toContain(`player=${profile.profile_key}"`);
  });

  it("renders the uncertainty caveat the artifact declares, not an assumed one", () => {
    const degraded = noscriptMarkup(readyMarkup());
    expect(degraded).toContain('data-caveat="uncertainty_pending"');
    expect(degraded).not.toContain('data-caveat="uncertainty_sampling_only"');
  });
});

describe("forbidden language", () => {
  /**
   * Scoped to the copy the challenge authors, not to the whole rendered
   * markup - and that distinction is load-bearing.
   *
   * The artifact's mandatory caveats legitimately contain three words from the
   * forbidden lists: "not a player **quality** verdict", "not a recruitment
   * **recommend**ation", "global z-**score**s". They use those words to *deny*
   * the claim, which is the entire purpose of a caveat. A scan over the full
   * markup would flag them, and the only ways to make it pass would be to
   * weaken the caveats or delete the assertion - both worse than the problem.
   *
   * So the rule is applied where it means something: the sentences we write.
   */
  const AUTHORED_COPY_KEYS = [
    "orientationHeading",
    "orientationBody",
    "orientationCta",
    "queryHeading",
    "queryBody",
    "queryCta",
    "revealHeading",
    "revealBaseline",
    "revealCtaEvidence",
    "revealCtaLab",
    "evidenceCta",
    "degradedHeading",
    "degradedResult",
  ] as const;

  it.each([
    "guess who",
    "quiz",
    "test your knowledge",
    "accuracy",
    "% match",
    "the model got it right",
    "talent",
  ])("never uses %s in authored copy", (phrase) => {
    const copy = view().copy;
    const authored = AUTHORED_COPY_KEYS.map((key) => copy[key]).join(" ").toLowerCase();
    expect(authored).not.toContain(phrase);
  });

  it("describes a rank rather than a correct answer", () => {
    const copy = view().copy;
    const authored = AUTHORED_COPY_KEYS.map((key) => copy[key]).join(" ").toLowerCase();
    // "score" and "matched" are the two that a plausible rewrite would
    // reintroduce first, and both would turn a retrieval rank into a verdict.
    expect(authored).not.toContain("score");
    expect(authored).not.toContain("matched");
    expect(authored).not.toContain("correct");
    expect(authored).toContain("rank");
  });
});

describe("the panel fails closed", () => {
  it("renders the problem card and no artifact values", () => {
    const html = markup({
      status: "error",
      datasetVersion: manifest.dataset_version,
      problem: {
        kind: "incompatible-data",
        eyebrow: "Incompatible data",
        title: "The evidence for this profile could not be loaded",
        message: "The challenge fails closed when the published artifacts disagree.",
        canRetry: true,
      },
    });

    expect(html).toContain('data-challenge-panel="error"');
    expect(html).not.toContain('data-challenge-panel="orientation"');
    const body = text(html);
    expect(body).toContain("The evidence for this profile could not be loaded");
    // §8: fail closed, do not render partial data.
    expect(body).not.toContain(profile.identity.display_name);
    expect(body).not.toContain("was ranked");
    expect(body).not.toContain("See the fingerprint");
  });

  it("keeps the dataset pin visible on the problem card", () => {
    // §8 requires the dataset version pin to stay visible when the artifact
    // cannot be loaded: a reader needs to know which version failed.
    const html = markup({
      status: "error",
      datasetVersion: manifest.dataset_version,
      problem: {
        kind: "missing-asset",
        eyebrow: "Static asset unavailable",
        title: "The evidence for this profile could not be loaded",
        message: "No placeholder numbers are shown.",
        canRetry: true,
      },
    });
    expect(text(html)).toContain(manifest.dataset_version);
  });

  it("omits the pin when the manifest itself never loaded", () => {
    const html = markup({
      status: "error",
      datasetVersion: null,
      problem: {
        kind: "unavailable",
        eyebrow: "Lab unavailable",
        title: "The verified showcase data could not be prepared",
        message: "Retry the data load.",
        canRetry: true,
      },
    });
    expect(html).not.toContain("Dataset pin");
  });
});
