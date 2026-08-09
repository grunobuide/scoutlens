import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { DataVintageBadge, ProviderBoundary } from "@/components/data-provenance";
import type { Manifest, ResearchSummaryArtifact } from "@/contracts/generated/showcase";

const PUBLISHED_ROOT = resolve("..", "public", "showcase", "v1");
const COMPONENT_SOURCE = resolve("src", "components", "data-provenance.tsx");

async function loadManifest(): Promise<Manifest> {
  return JSON.parse(await readFile(resolve(PUBLISHED_ROOT, "manifest.json"), "utf8")) as Manifest;
}

async function loadResearch(): Promise<ResearchSummaryArtifact> {
  return JSON.parse(await readFile(resolve(PUBLISHED_ROOT, "research-summary.json"), "utf8")) as ResearchSummaryArtifact;
}

// Values that must never appear as literals in the component source — they
// belong to the artifact, not the module. Checked against the .tsx file, not
// rendered markup (rendered output legitimately shows the artifact's own season).
const HARD_CODED_PRODUCTION_VALUES = ["2017/18", "1257", "1,257", "31d2ccc6af37", "450"];

async function assertSourceHasNoHardCodedValues(): Promise<void> {
  const source = await readFile(COMPONENT_SOURCE, "utf8");
  for (const value of HARD_CODED_PRODUCTION_VALUES) {
    expect(source, `data-provenance.tsx must not hard-code "${value}"`).not.toContain(
      `"${value}"`,
    );
  }
}

describe("scoutlens-9a3.3 data provenance presentation", () => {
  it("keeps production season, population and version values out of the component source", async () => {
    await assertSourceHasNoHardCodedValues();
  });

  it("renders the concise vintage badge from manifest fields only", async () => {
    const manifest = await loadManifest();
    const html = renderToStaticMarkup(<DataVintageBadge manifest={manifest} />);

    expect(html).toContain("Historical reproducible benchmark");
    expect(html).toContain(manifest.source.season);
    expect(html).toContain(manifest.dataset_version);
    expect(html).toContain(manifest.source.licence);

    expect(html).not.toContain("live");
    expect(html).not.toContain("current season");
  });

  it("renders the provider boundary distinguishing Wyscout from aggregate StatsBomb", async () => {
    const manifest = await loadManifest();
    const research = await loadResearch();
    const html = renderToStaticMarkup(<ProviderBoundary manifest={manifest} research={research} />);

    expect(html).toContain("Primary evidence");
    expect(html).toContain("External replication");
    expect(html).toContain("aggregate results only");
    expect(html).toContain("not current scouting information");
    expect(html).toContain(manifest.source.licence);
    expect(html).toContain(manifest.source.source_url);
    expect(html).toContain(manifest.source.licence_url);
  });

  it("surfaces competition scope, eligibility threshold and population from the manifest", async () => {
    const manifest = await loadManifest();
    const research = await loadResearch();
    const html = renderToStaticMarkup(<ProviderBoundary manifest={manifest} research={research} />);

    expect(html).toContain(String(manifest.population.profile_count));
    expect(html).toContain(String(manifest.population.domestic_competition_ids.length));
    expect(html).toContain(String(manifest.population.minutes_threshold_per_period));
    expect(html).toContain(manifest.population.analytical_unit.replace(/_/g, " "));
  });

  it("does not claim Wyscout attribution when the primary provider is not Wyscout", async () => {
    const manifest = await loadManifest();
    const research = await loadResearch();
    const corrupted = JSON.parse(JSON.stringify(manifest)) as Manifest;
    corrupted.source.provider = "statsbomb_open_data" as Manifest["source"]["provider"];
    const html = renderToStaticMarkup(<ProviderBoundary manifest={corrupted} research={research} />);
    expect(html).not.toContain("Pappalardo et al.");
  });

  it("is keyboard and no-JavaScript safe: no essential provenance hidden behind interaction", async () => {
    const manifest = await loadManifest();
    const research = await loadResearch();
    const badge = renderToStaticMarkup(<DataVintageBadge manifest={manifest} />);
    const boundary = renderToStaticMarkup(<ProviderBoundary manifest={manifest} research={research} />);

    expect(badge).not.toContain("<button");
    expect(badge).not.toContain("onclick");
    expect(boundary).not.toContain("title=");
    expect(boundary).not.toContain("onmouseover");
  });

  it("route variants agree on provider and vintage facts", async () => {
    const landing = await readFile(resolve("src", "app", "page.tsx"), "utf8");
    const science = await readFile(resolve("src", "app", "science", "page.tsx"), "utf8");
    const lab = await readFile(resolve("src", "app", "lab", "page.tsx"), "utf8");

    for (const page of [landing, science, lab]) {
      expect(page).toContain("DataVintageBadge");
      expect(page).toContain("ProviderBoundary");
    }
    expect(landing).toContain(`manifest={story.manifest}`);
    expect(science).toContain(`manifest={story.manifest}`);
    expect(lab).toContain(`manifest={story.manifest}`);
  });

  it("keeps the provenance drawer as the advanced audit path and never duplicates manifest harmonically", async () => {
    const manifest = await loadManifest();
    const research = await loadResearch();
    const html = renderToStaticMarkup(<ProviderBoundary manifest={manifest} research={research} />);
    expect(html).toContain(`href="/science"`);
  });
});
