import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeAll, describe, expect, it } from "vitest";

import { FingerprintProfile, LabLoadingState, LabProblemPanel } from "@/components/lab-explorer";
import { NeighborComparisonDrawer } from "@/components/neighbor-comparison-drawer";
import type {
  FeatureCatalogArtifact,
  PlayerIndexArtifact,
  PlayerProfileArtifact,
} from "@/contracts/generated/showcase";
import { loadShowcaseLab } from "@/content/load-showcase-lab";
import {
  EMPTY_PROFILE_FILTERS,
  buildFingerprintRows,
  buildProfileEvidence,
  decodeIdentityText,
  describeLabError,
  filterProfiles,
  formatRawValue,
  formatCosine,
  formatSupport,
  profileHref,
} from "@/content/showcase-lab";

const FEATURED_PROFILE_PATH = "players/wy-8287-c-795.json";

let catalog: FeatureCatalogArtifact;
let index: PlayerIndexArtifact;
let profile: PlayerProfileArtifact;

beforeAll(async () => {
  [catalog, index, profile] = await Promise.all(
    ["feature-catalog.json", "players.index.json", FEATURED_PROFILE_PATH].map(async (path) =>
      JSON.parse(await readFile(resolve("public", "showcase", "v1", path), "utf8")),
    ),
  ) as [FeatureCatalogArtifact, PlayerIndexArtifact, PlayerProfileArtifact];
});

describe("searchable period fingerprint Lab", () => {
  it("loads the complete production catalog through the verified repository", async () => {
    const lab = await loadShowcaseLab();
    expect(lab.status).toBe("ready");
    if (lab.status !== "ready") {
      return;
    }
    expect(lab.profiles).toHaveLength(1257);
    expect(lab.catalog.features).toHaveLength(32);
    expect(lab.initialProfile.profile_key).toBe("wy-8287-c-795");
  });

  it("preserves displayed accents while search matches decoded names and combined filters", () => {
    expect(decodeIdentityText("L. Modri\\u0107")).toBe("L. Modrić");

    const results = filterProfiles(index.profiles, {
      query: "Á Correa",
      role: "Forward",
      competition: "Spanish first division",
      team: "Atlético Madrid",
    });

    expect(results.map((item) => item.profile_key)).toContain("wy-254408-c-795");
    expect(results.every((item) => item.role === "Forward")).toBe(true);
    expect(filterProfiles(index.profiles, EMPTY_PROFILE_FILTERS)).toHaveLength(index.profiles.length);
    expect(index.profiles[0]?.profile_key).toBe("wy-254408-c-795");
  });

  it("builds exactly the 32 catalog-ordered features and renders an equivalent table", () => {
    const rows = buildFingerprintRows(catalog, profile);
    expect(rows).toHaveLength(32);
    expect(rows.map((row) => row.definition.feature_id)).toEqual(
      [...catalog.features].sort((left, right) => left.order - right.order).map((item) => item.feature_id),
    );

    const html = renderToStaticMarkup(
      <FingerprintProfile catalog={catalog} profiles={index.profiles} profile={profile} />,
    );
    expect(html.match(/data-fingerprint-row=/g)).toHaveLength(32);
    expect(html).toContain("All 32 measurements");
    expect(html).toContain("Scrollable 32-feature value table");
    expect(html).toContain("Point estimates · uncertainty pending");
    expect(html).toContain("Within role");
    expect(html).toContain("Global");
  });

  it("keeps null raw values distinct from model imputation and formats every unit family", () => {
    const withNull = structuredClone(profile);
    const nullValue = withNull.periods.a.features[2];
    if (nullValue === undefined) {
      throw new Error("Fixture is missing its ratio feature");
    }
    nullValue.raw_value = null;
    nullValue.global_z_score = 0;
    nullValue.imputed_for_model = true;

    const html = renderToStaticMarkup(
      <FingerprintProfile catalog={catalog} profiles={index.profiles} profile={withNull} />,
    );
    expect(html).toContain("Not observed");
    expect(html).toContain("mean-imputed to z=0");

    const rows = buildFingerprintRows(catalog, profile);
    const byUnit = new Map(rows.map((row) => [row.definition.unit, row]));
    expect(formatRawValue(byUnit.get("ratio")!.periodA, byUnit.get("ratio")!.definition)).toContain("%");
    expect(formatRawValue(byUnit.get("per_90")!.periodA, byUnit.get("per_90")!.definition)).toContain("/90");
    expect(
      formatRawValue(byUnit.get("pitch_percent")!.periodA, byUnit.get("pitch_percent")!.definition),
    ).toContain("% pitch");
    expect(
      formatRawValue(
        byUnit.get("distance_per_90")!.periodA,
        byUnit.get("distance_per_90")!.definition,
      ),
    ).toContain("pitch units /90");
    expect(formatSupport(rows[2]!.periodA)).toMatch(/min; .*\/.* successes/);
  });

  it("maps loading and all required failure fixtures to explicit fail-closed states", () => {
    const loading = renderToStaticMarkup(<LabLoadingState />);
    expect(loading).toContain("Verifying selected profile");
    expect(loading).toContain("Controls are paused");

    const fixtures = [
      ["profile_mismatch", "unknown-profile"],
      ["http_error", "missing-asset"],
      ["schema_validation", "incompatible-data"],
      ["checksum_mismatch", "integrity"],
    ] as const;
    for (const [code, kind] of fixtures) {
      const problem = describeLabError({ code });
      expect(problem.kind).toBe(kind);
      const html = renderToStaticMarkup(
        <LabProblemPanel problem={problem} datasetVersion="fixture-v1" />,
      );
      expect(html).toContain("fixture-v1");
      expect(html).toContain(problem.title);
    }
  });

  it("builds a reloadable, encoded player URL", () => {
    expect(profileHref("wy-8287-c-795")).toBe("/lab/?player=wy-8287-c-795");
    expect(profileHref("unsafe key")).toBe("/lab/?player=unsafe%20key");
  });

  it("replays the stored retrieval values and preserves the five non-self neighbors in artifact order", () => {
    const html = renderToStaticMarkup(
      <FingerprintProfile catalog={catalog} profiles={index.profiles} profile={profile} />,
    );

    for (const outcome of [
      profile.retrieval.global,
      profile.retrieval.within_role,
      profile.retrieval.baseline_role_minutes,
    ]) {
      expect(html).toContain(`Rank ${outcome.self_rank}`);
      expect(html).toContain(`of ${outcome.candidate_count.toLocaleString("en-US")}`);
      expect(html).toContain(outcome.reciprocal_rank.toFixed(4));
      if (outcome.cosine_similarity !== null) {
        expect(html).toContain(formatCosine(outcome.cosine_similarity));
      }
    }
    expect(html.match(/data-retrieval-scope=/g)).toHaveLength(3);
    expect(html.match(/data-neighbor-rank=/g)).toHaveLength(5);
    let priorPosition = -1;
    for (const neighbor of profile.neighbors) {
      expect(neighbor.player_key).not.toBe(profile.identity.player_key);
      expect(neighbor.role).toBe(profile.identity.role);
      const position = html.indexOf(decodeIdentityText(neighbor.display_name));
      expect(position).toBeGreaterThan(priorPosition);
      priorPosition = position;
    }
  });

  it("resolves exact feature and family evidence and rejects a cosine reconstruction mismatch", () => {
    const evidence = buildProfileEvidence(catalog, profile);
    expect(evidence.self.features).toHaveLength(32);
    expect(evidence.self.families).toHaveLength(8);
    expect(evidence.self.featureSum).toBeCloseTo(profile.retrieval.global.cosine_similarity!, 10);
    expect(evidence.self.familySum).toBeCloseTo(profile.retrieval.global.cosine_similarity!, 10);
    expect(evidence.neighbors.map((item) => item.neighbor.profile_key)).toEqual(
      profile.neighbors.map((neighbor) => neighbor.profile_key),
    );
    for (const item of evidence.neighbors) {
      expect(item.evidence.featureSum).toBeCloseTo(item.neighbor.cosine_similarity, 10);
      expect(item.evidence.familySum).toBeCloseTo(item.neighbor.cosine_similarity, 10);
    }

    const corrupt = structuredClone(profile);
    const firstReference = corrupt.neighbors[0].evidence_refs[0];
    const contribution = corrupt.evidence_index.find((item) => item.evidence_id === firstReference);
    if (contribution === undefined) {
      throw new Error("Production fixture is missing its first neighbor contribution");
    }
    contribution.contribution += 0.01;
    expect(() => buildProfileEvidence(catalog, corrupt)).toThrow(/does not reconstruct cosine/);

    const incomplete = structuredClone(profile);
    incomplete.neighbors.pop();
    expect(() => buildProfileEvidence(catalog, incomplete)).toThrow(/exactly five neighbors/);
  });

  it("renders the focusable comparison dialog with 32 feature and eight family rows", () => {
    const selection = buildProfileEvidence(catalog, profile).neighbors[0];
    if (selection === undefined) {
      throw new Error("Production fixture is missing its first statistical neighbor");
    }
    const indexItem = index.profiles.find(
      (candidate) => candidate.profile_key === selection.neighbor.profile_key,
    );
    const html = renderToStaticMarkup(
      <NeighborComparisonDrawer
        catalog={catalog}
        profile={profile}
        neighbor={selection.neighbor}
        evidence={selection.evidence}
        candidateMinutes={indexItem?.period_contexts.b.minutes ?? null}
        onClose={() => undefined}
      />,
    );

    expect(html).toContain("<dialog");
    expect(html).toContain("Close comparison");
    expect(html.match(/data-feature-contribution=/g)).toHaveLength(32);
    expect(html.match(/data-family-contribution=/g)).toHaveLength(8);
    expect(html).toContain("both below the global mean");
    expect(html).toContain("Pending · no resampled rank interval");
  });

  it("keeps mandatory caveats adjacent and excludes shortlist or player-rating claims", async () => {
    const html = renderToStaticMarkup(
      <FingerprintProfile catalog={catalog} profiles={index.profiles} profile={profile} />,
    );
    for (const code of [
      "fingerprint_not_style_proof",
      "similarity_not_recruitment",
      "same_season_team_confound",
    ]) {
      const caveat = profile.caveats.find((item) => item.code === code);
      expect(caveat).toBeDefined();
      expect(html).toContain(caveat!.message);
    }
    expect(html).toContain("no resampled rank interval is available yet");
    expect(html).toContain("pending, no interval");

    const sources = await Promise.all(
      ["src/components/lab-explorer.tsx", "src/components/neighbor-comparison-drawer.tsx"].map(
        (path) => readFile(resolve(path), "utf8"),
      ),
    );
    const source = sources.join("\n").toLocaleLowerCase("en");
    for (const forbidden of [
      "% match",
      "match percentage",
      "recommended replacement",
      "recruitment target",
      "best player",
      "better player",
      "player quality score",
    ]) {
      expect(source).not.toContain(forbidden);
    }
  });
});
