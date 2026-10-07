import type { ResearchExperiment } from "@/contracts/generated/showcase-v2";

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
