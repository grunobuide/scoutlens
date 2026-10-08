import type { Competition, ResearchExperiment } from "@/contracts/generated/showcase-v2";

/**
 * Presentation names for the data providers the contract can name
 * (`scoutlens-9a3.20`).
 *
 * The manifest and the research summary carry a provider *code*
 * (`wyscout_pappalardo`), never a display name, so one typed table turns codes
 * into words for every surface: the data-vintage chip at the top of each route
 * and the experiment cards. It used to be a ternary inside research-story.tsx
 * that called anything other than Wyscout "StatsBomb Open Data". Keyed by the
 * generated union, so a provider the contract adds is a type error here, and
 * an unknown code at runtime throws instead of borrowing another's name.
 */
export type ProviderCode = ResearchExperiment["provider"];

const PROVIDER_LABELS: Readonly<Record<ProviderCode, string>> = {
  wyscout_pappalardo: "Wyscout / Pappalardo",
  statsbomb_open_data: "StatsBomb Open Data",
};

export function providerLabel(provider: string): string {
  if (!Object.hasOwn(PROVIDER_LABELS, provider)) {
    throw new Error(`No display name for provider code: ${provider}`);
  }
  return PROVIDER_LABELS[provider as ProviderCode];
}

/**
 * The licence boundary in the chip's few words (`scoutlens-9a3.26`, D069).
 *
 * The full statement is the manifest's `source.redistribution_note`, which the
 * provider section prints verbatim. It cannot be copied into the chip: it names
 * the project by its repository name, and the public identity contract allows
 * that name once per page. This summary may only say what the note says -
 * web/tests/data-provenance.test.tsx fails if the note stops saying it.
 */
export const REDISTRIBUTION_SUMMARY = "aggregates only, no raw rows";

/** The competition scope, worded once; the count is the manifest's. */
export function competitionScope(count: number): string {
  return `${count.toLocaleString("en-US")} domestic competition${count === 1 ? "" : "s"}`;
}

/**
 * Which competitions the dataset covers (`scoutlens-9a3.33`, D074).
 *
 * The manifest names them by id only (`population.domestic_competition_ids`);
 * each entry of the published players index carries its competition's id,
 * name and country. This reads the distinct competitions off the index and
 * refuses to answer unless they are exactly the manifest's: an index that
 * covers a competition the manifest does not declare, or misses one it does,
 * or names one id two ways, throws rather than printing a list the artifact
 * does not support. Ordered by country, so the order is the data's, not ours.
 */
export function datasetCompetitions(
  competitionIds: ReadonlyArray<number>,
  profiles: ReadonlyArray<{ competition: Competition }>,
): ReadonlyArray<Competition> {
  const byId = new Map<number, Competition>();
  for (const { competition } of profiles) {
    const seen = byId.get(competition.id);
    if (seen !== undefined && (seen.name !== competition.name || seen.country !== competition.country)) {
      throw new Error(`Competition ${competition.id} is named two ways in the players index`);
    }
    byId.set(competition.id, competition);
  }
  const declared = [...new Set(competitionIds)].sort((a, b) => a - b);
  const indexed = [...byId.keys()].sort((a, b) => a - b);
  if (declared.join(",") !== indexed.join(",")) {
    throw new Error(
      `The players index covers competitions [${indexed.join(", ")}]; the manifest declares [${declared.join(", ")}]`,
    );
  }
  return [...byId.values()].sort((a, b) => a.country.localeCompare(b.country, "en"));
}

/**
 * The countries of the dataset's competitions, for the chip. Each country
 * once: two competitions in one country name it once, and the count before
 * the list stays the number of competitions.
 */
export function competitionCountries(competitions: ReadonlyArray<Competition>): string {
  return [...new Set(competitions.map((competition) => competition.country))].join(", ");
}

/** What the site is, in the words of the chip that opens every route. */
export const BENCHMARK_PURPOSE = "Historical reproducible benchmark";

/**
 * The population rule, worded once. The number is always the artifact's
 * (`manifest.population.minutes_threshold_per_period`, or a profile's
 * `cohort`); only the sentence around it lives here.
 */
export function eligibilityRule(minutesPerPeriod: number): string {
  return `players with at least ${minutesPerPeriod.toLocaleString("en-US")} minutes in each half`;
}
