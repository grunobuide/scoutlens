/**
 * Forbidden copy on the surfaces the static check cannot see
 * (`scoutlens-9a3.29`).
 *
 * `scripts/check-static-output.mjs` scans the three prerendered routes. The
 * identity challenge's query, reveal and evidence states render on the client,
 * so their text is in none of them, and the explanation registry's prose
 * reaches a route only where a page happens to render it. This file holds both
 * to the same list the static check uses - imported from
 * `scripts/forbidden-copy.mjs`, not copied - with the same rule: case-
 * insensitive substring after the artifact's own `unsupported_claims` are
 * removed.
 *
 * The challenge is built from the **published pinned** artifacts, not a
 * fixture pack: the copy that ships interpolates the real featured profile and
 * the real narrative question, and a fixture's stand-in strings would prove
 * the fixture.
 *
 * The rendered states are server-rendered here by holding the state machine's
 * initial `useState` at the state under test. The vitest environment is `node`
 * with no DOM, so a deep link cannot run its effect; forcing the initial value
 * renders the same JSX branch the effect would select. The real transitions
 * are `e2e/forbidden-copy.spec.ts`'s job.
 */

import { readFile } from "node:fs/promises";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

import { renderToStaticMarkup } from "react-dom/server";
import { beforeAll, describe, expect, it, vi } from "vitest";

import {
  findForbiddenClaims,
  findForbiddenCurrentness,
  forbiddenClaims,
  forbiddenCurrentness,
  scannableText,
} from "../scripts/forbidden-copy.mjs";

import { IdentityChallengePanel } from "@/components/identity-challenge-panel";
import type { ChallengeState } from "@/components/identity-challenge-states";
import {
  explainFamily,
  explainMetric,
  explainQuantity,
  familyExplanationKeys,
  metricExplanationKeys,
  quantityExplanationKeys,
  type EvidenceExplanation,
} from "@/content/evidence-explanations";
import { buildIdentityChallenge, type IdentityChallengeView } from "@/content/identity-challenge";
import type { ReadyIdentityChallengeData } from "@/content/load-identity-challenge";
import { buildFingerprintRows } from "@/content/showcase-lab";
import {
  StaticShowcaseRepository,
  type ShowcaseFetch,
  type ShowcaseMajor,
} from "@/contracts/showcase-repository";
import type {
  Manifest,
  PlayerProfileArtifact,
  RepresentationArtifact,
  ResearchSummaryArtifact,
} from "@/contracts/generated/showcase-v2";

/**
 * The state the challenge's `useState("orientation")` starts in. Only that one
 * call is redirected; every other `useState` in the tree is untouched.
 */
const forced = vi.hoisted(() => ({ state: "orientation" as string }));

vi.mock("react", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react")>();
  return {
    ...actual,
    useState: (initial: unknown) => actual.useState(initial === "orientation" ? forced.state : initial),
  };
});

const REPO_ROOT = resolve(__dirname, "..", "..");
const PIN = JSON.parse(readFileSync(resolve(REPO_ROOT, "config", "showcase-payload-pack.json"), "utf8")) as {
  schema_version: string;
};
const PINNED_MAJOR = Number(PIN.schema_version.split(".")[0]) as ShowcaseMajor;
const PUBLISHED_ROOT = resolve(REPO_ROOT, "public", "showcase", `v${PINNED_MAJOR}`);

function publishedReader(): ShowcaseFetch {
  const prefix = `/showcase/v${PINNED_MAJOR}/`;
  return async (input: string) => {
    if (!input.startsWith(prefix)) {
      return new Response(null, { status: 404 });
    }
    try {
      const bytes = await readFile(resolve(PUBLISHED_ROOT, input.slice(prefix.length)));
      return new Response(new Uint8Array(bytes).buffer, { status: 200 });
    } catch {
      return new Response(null, { status: 404 });
    }
  };
}

let unsupportedClaims: readonly string[];
let ready: ReadyIdentityChallengeData;

beforeAll(async () => {
  // The challenge is a v2 surface; on a v1 pin there is nothing to scan, and a
  // silent pass would read as coverage.
  expect(PINNED_MAJOR, "the identity challenge exists only on the v2 contract").toBe(2);

  const repository = new StaticShowcaseRepository(publishedReader(), `/showcase/v${PINNED_MAJOR}/`, PINNED_MAJOR);
  const manifest = (await repository.getManifest()) as Manifest;
  const profilePath = resolve(PUBLISHED_ROOT, "players", `${manifest.featured_profile.profile_key}.json`);
  if (!existsSync(profilePath)) {
    throw new Error(
      `${profilePath} is not hydrated; run: uv run --frozen python -m scoutlens.showcase.payload hydrate`,
    );
  }
  const [profile, representation, research, catalog] = await Promise.all([
    repository.getProfile(manifest.featured_profile.profile_key),
    repository.getRepresentation(),
    repository.getResearchSummary(),
    repository.getFeatureCatalog(),
  ]);
  expect(representation).not.toBeNull();

  const built = buildIdentityChallenge({
    manifest,
    profile: profile as PlayerProfileArtifact,
    representation: representation as RepresentationArtifact,
    research: research as ResearchSummaryArtifact,
  });
  if (!built.available) {
    throw new Error(`The published artifacts do not build a challenge: ${built.code}`);
  }
  unsupportedClaims = (research as ResearchSummaryArtifact).unsupported_claims;
  expect(unsupportedClaims.length).toBeGreaterThan(0);
  ready = {
    status: "ready",
    datasetVersion: manifest.dataset_version,
    view: built,
    fingerprintRows: buildFingerprintRows(catalog, profile),
  };
});

/** Every forbidden entry in `text`, after the published boundaries are removed. */
function violations(text: string): string[] {
  const scannable = scannableText(text, unsupportedClaims);
  return [...findForbiddenClaims(scannable), ...findForbiddenCurrentness(scannable)];
}

function expectClean(where: string, text: string): void {
  expect(violations(text), `${where}: ${text.slice(0, 160)}`).toEqual([]);
}

/** Visible text of server markup, with React's entity escapes undone. */
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

function render(state: ChallengeState): string {
  forced.state = state;
  try {
    return renderToStaticMarkup(<IdentityChallengePanel data={ready} />);
  } finally {
    forced.state = "orientation";
  }
}

/** Every string leaf of the view, with the path it was found at. */
function stringLeaves(value: unknown, path: string): Array<[string, string]> {
  if (typeof value === "string") {
    return [[path, value]];
  }
  if (Array.isArray(value)) {
    return value.flatMap((item, index) => stringLeaves(item, `${path}[${index}]`));
  }
  if (value !== null && typeof value === "object") {
    return Object.entries(value).flatMap(([key, item]) => stringLeaves(item, `${path}.${key}`));
  }
  return [];
}

function prose(explanation: EvidenceExplanation): string {
  return [
    explanation.plain_meaning,
    explanation.calculation_summary,
    explanation.scale_direction,
    explanation.interpretation_boundary,
  ].join(" ");
}

describe("scoutlens-9a3.29 the shared forbidden-copy list", () => {
  it("is not vacuous: it catches an affirmative quality claim in each form it bans", () => {
    expect(forbiddenClaims.length).toBeGreaterThan(20);
    expect(forbiddenCurrentness.length).toBeGreaterThan(10);
    for (const planted of [
      "On this evidence he is a better player than the candidate below.",
      "The fingerprint says Messi is the best player in the league.",
      "A player rating of 8.4 out of 10.",
      "The profile earns a quality score of 91.",
      "The model gives him a talent grade of A.",
      "Of the two forwards, the first is rated as more creative.",
      "He is a top prospect for next season.",
      "He is a world-class finisher.",
    ]) {
      expect(findForbiddenClaims(scannableText(planted, [])), planted).not.toEqual([]);
    }
    expect(findForbiddenCurrentness(scannableText("Updated daily from the current season.", []))).toEqual([
      "current season",
      "updated daily",
    ]);
  });

  it("does not fire on the disclaimers the site actually writes", () => {
    // Each of these is published copy today (landing, Lab, /science, the
    // explanation registry, every feature definition). A ban that fired on
    // them would make deleting the caveat the cheapest fix.
    for (const disclaimer of [
      "Higher is better for this identity task—not a player rating.",
      "The rank is an identity-test result, not a player rating.",
      "higher is better for the identity-retrieval task only — never a quality rating.",
      "It is not a quality rating, a tactical-fit score or a recruitment signal.",
      "across all 32 descriptive features, not quality scores.",
      "a bound on the identity claim, not a position-quality score.",
      "Higher values are not interpreted as better player quality.",
      "A role, team, and minutes control outperforms the fingerprint.",
      "He is not a better player for ranking first; the rank is not a grade.",
      "The site has no live database and is not current scouting information.",
    ]) {
      expect(violations(disclaimer), disclaimer).toEqual([]);
    }
  });

  it("excepts a published claim boundary, and only that sentence", () => {
    const [boundary] = unsupportedClaims;
    expect(boundary).toBeDefined();
    expect(violations(`Where the evidence stops: ${boundary}`)).toEqual([]);
    expect(violations(`${boundary} Messi is a better player.`)).toEqual(["is a better player"]);
  });
});

describe("scoutlens-9a3.29 the identity challenge copy, from the published artifacts", () => {
  it("states no quality, recommendation or currentness claim in any string of view.copy", () => {
    const copy = Object.entries(ready.view.copy);
    expect(copy.length).toBeGreaterThan(10);
    for (const [key, value] of copy) {
      expectClean(`view.copy.${key}`, value);
    }
  });

  it("states none in any other string the view hands its states (caveats, evidence, identity, periods)", () => {
    const view: IdentityChallengeView = ready.view;
    const leaves = stringLeaves(view, "view");
    expect(leaves.some(([path]) => path.startsWith("view.caveats"))).toBe(true);
    for (const [path, value] of leaves) {
      expectClean(path, value);
    }
    for (const item of [...view.families, ...view.featureContributions]) {
      const family = explainFamily(item.family);
      expectClean(`explainFamily(${item.family})`, `${family.label} ${family.plain_meaning}`);
    }
    for (const row of ready.fingerprintRows) {
      expectClean(`fingerprint row ${row.definition.feature_id}`, stringLeaves(row.definition, "").map(([, v]) => v).join(" "));
    }
  });

  it.each([
    ["orientation", "orientationHeading"],
    ["query", "queryHeading"],
    ["reveal", "revealHeading"],
    ["evidence", "evidenceHeading"],
  ] as const)("renders the %s state with no forbidden phrase", (state, heading) => {
    const html = render(state);
    // The render is the state under test, not orientation by default.
    expect(html).toContain(`data-challenge-state="${state}"`);
    expect(text(html)).toContain(ready.view.copy[heading]);
    expectClean(`the ${state} state`, text(html));
  });

  it("renders the degraded no-JavaScript card with no forbidden phrase", () => {
    const html = render("orientation");
    const noscript = [...html.matchAll(/<noscript>([\s\S]*?)<\/noscript>/g)].map((match) => match[1]).join("");
    expect(text(noscript)).toContain(ready.view.copy.degradedResult);
    expectClean("the degraded card", text(noscript));
  });
});

describe("scoutlens-9a3.29 the explanation registry, against the same list", () => {
  it("states no forbidden phrase in any metric, quantity or family explanation", () => {
    for (const key of metricExplanationKeys()) {
      expectClean(`metric ${key}`, prose(explainMetric({ metric_id: key })));
    }
    for (const key of quantityExplanationKeys()) {
      expectClean(`quantity ${key}`, prose(explainQuantity(key)));
    }
    for (const key of familyExplanationKeys()) {
      const family = explainFamily(key);
      expectClean(`family ${key}`, `${family.label} ${family.plain_meaning}`);
    }
  });
});
