import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeAll, describe, expect, it } from "vitest";

import { FingerprintProfile, LabLoadingState, LabProblemPanel } from "@/components/lab-explorer";
import type {
  FeatureCatalogArtifact,
  PlayerIndexArtifact,
  PlayerProfileArtifact,
} from "@/contracts/generated/showcase";
import { loadShowcaseLab } from "@/content/load-showcase-lab";
import {
  EMPTY_PROFILE_FILTERS,
  buildFingerprintRows,
  decodeIdentityText,
  describeLabError,
  filterProfiles,
  formatRawValue,
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

    const html = renderToStaticMarkup(<FingerprintProfile catalog={catalog} profile={profile} />);
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

    const html = renderToStaticMarkup(<FingerprintProfile catalog={catalog} profile={withNull} />);
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
});
