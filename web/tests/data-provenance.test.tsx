import { readFileSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { DataVintageBadge, ProviderBoundary } from "@/components/data-provenance";
import { REDISTRIBUTION_SUMMARY, competitionScope, providerLabel } from "@/content/provenance";
import { ProvenanceDrawer } from "@/components/research-story";
import { loadShowcaseStory } from "@/content/load-showcase-story";
import type { Manifest, ResearchSummaryArtifact } from "@/contracts/generated/showcase-v2";

// `scoutlens-9a3.22`: the dataset the payload pin names, not v1 - this file
// read v1 while the site served v2, and its pin literal below named a v1
// dataset two re-exports old.
const PIN = JSON.parse(readFileSync(resolve("..", "config", "showcase-payload-pack.json"), "utf8")) as {
  schema_version: string;
  dataset_version: string;
};
const PUBLISHED_ROOT = resolve("..", "public", "showcase", `v${PIN.schema_version.split(".")[0]}`);
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
const HARD_CODED_PRODUCTION_VALUES = [
  "2017/18",
  "1257",
  "1,257",
  "450",
  PIN.dataset_version,
  PIN.dataset_version.split("-").at(-1) ?? PIN.dataset_version,
];

/** Rendered text, without the separators React puts between adjacent text nodes. */
function text(html: string): string {
  return html.replaceAll("<!-- -->", "");
}

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
    // `scoutlens-9a3.20`: whose data, and who counts, at the first point of
    // interpretation - not only in the provider section after every result.
    expect(html).toContain(`data-vintage__provider">${providerLabel(manifest.source.provider)}<`);
    expect(text(html)).toContain(
      `at least ${manifest.population.minutes_threshold_per_period} minutes in each half`,
    );
    // `scoutlens-9a3.26` (D069): the competition scope and the licence boundary.
    expect(text(html)).toContain(
      `data-vintage__scope">${manifest.population.domestic_competition_ids.length} domestic competitions<`,
    );
    expect(html).toContain(`data-vintage__redistribution">${REDISTRIBUTION_SUMMARY}<`);
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
    expect(text(html)).toContain("does not guarantee that historical results transfer to today&#x27;s football");
    expect(html).toContain(manifest.source.licence);
    // `scoutlens-9a3.22`: the note is the manifest's, verbatim, and a sentence
    // of its own - it was glued to the line before it ("aggregates:ScoutLens").
    expect(text(html)).toContain(`Published under ${manifest.source.licence}. ${manifest.source.redistribution_note}`);
    expect(html).toContain(manifest.source.source_url);
    expect(html).toContain(manifest.source.licence_url);
  });

  it("surfaces competition scope, eligibility threshold and population from the manifest", async () => {
    const manifest = await loadManifest();
    const research = await loadResearch();
    const html = renderToStaticMarkup(<ProviderBoundary manifest={manifest} research={research} />);

    // `scoutlens-9a3.22`: as the rest of the site prints them - a grouped count,
    // "player × competition" and "period A / B" - and with no glued or doubled
    // punctuation: the section read "et al..", "1257 player competition",
    // "period a / b" and "scouting informationand".
    const rendered = text(html);
    const { population } = manifest;
    expect(rendered).toContain(
      `Scope: ${population.profile_count.toLocaleString("en-US")} ${population.analytical_unit.replaceAll("_", " × ")} profiles` +
        ` across ${population.domestic_competition_ids.length} domestic competitions, split into period ` +
        `${population.chronological_periods.map((period) => period.toUpperCase()).join(" / ")}.`,
    );
    expect(rendered).toContain(`at least ${population.minutes_threshold_per_period} minutes per period`);
    expect(rendered).toContain("not current scouting information</strong> and does not");
    expect(rendered).not.toMatch(/[^.]\.\.(?!\.)/);
  });

  it("names a provider only from the typed table, and refuses one it does not know", () => {
    expect(providerLabel("wyscout_pappalardo")).toBe("Wyscout / Pappalardo");
    expect(providerLabel("statsbomb_open_data")).toBe("StatsBomb Open Data");
    expect(() => providerLabel("some_new_provider")).toThrow(/No display name/);
    expect(() => providerLabel("toString")).toThrow(/No display name/);
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

  it("the provider section links on to the full replication and its limits", async () => {
    // Renamed by `scoutlens-9a3.26`: this rendered ProviderBoundary under a
    // title about the provenance drawer, which no test rendered at all.
    const manifest = await loadManifest();
    const research = await loadResearch();
    const html = renderToStaticMarkup(<ProviderBoundary manifest={manifest} research={research} />);
    expect(html).toContain(`href="/science"`);
  });

  it("renders the provenance drawer from the artifacts, provider name included", async () => {
    const story = await loadShowcaseStory();
    const html = text(renderToStaticMarkup(<ProvenanceDrawer story={story} />));
    // The typed table's name, not a second spelling of it.
    expect(html).toContain(`<p class="source-mark">${providerLabel(story.manifest.source.provider)}</p>`);
    expect(html).toContain(story.manifest.source.citation.replaceAll("&", "&amp;").replaceAll("'", "&#x27;"));
    expect(html).toContain(`href="${story.manifest.source.source_url}"`);
    expect(html).toContain(`href="${story.manifest.source.licence_url}"`);
    expect(html).toContain("docs/decisions-log.md");
    expect(html).toContain(story.manifest.dataset_version);
    // Every result artifact the research summary cites is one link away.
    for (const experiment of story.research.experiments) {
      expect(html).toContain(experiment.source_artifact);
    }
  });

  it("says in the chip only what the manifest's redistribution note says (D069)", async () => {
    // The chip cannot quote the note (it names the repository; the identity
    // contract allows that once per page), so it summarises it. The summary is
    // only true while the note says both halves of it.
    const manifest = await loadManifest();
    expect(REDISTRIBUTION_SUMMARY).toBe("aggregates only, no raw rows");
    expect(manifest.source.redistribution_note).toMatch(/aggregates only/i);
    expect(manifest.source.redistribution_note).toMatch(/raw provider rows remain excluded/i);
    expect(competitionScope(1)).toBe("1 domestic competition");
    expect(competitionScope(manifest.population.domestic_competition_ids.length)).toMatch(/^\d+ domestic competitions$/);
  });
});
