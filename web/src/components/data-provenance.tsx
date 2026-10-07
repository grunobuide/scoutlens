import Link from "next/link";

import {
  BENCHMARK_PURPOSE,
  REDISTRIBUTION_SUMMARY,
  competitionScope,
  eligibilityRule,
  providerLabel,
} from "@/content/provenance";
import type {
  AnyManifest,
  AnyResearchSummaryArtifact,
} from "@/contracts/showcase-repository";


// scoutlens-9a3.3: artifact-backed data vintage, provenance and provider
// boundary presentation. Every fact is read from the versioned manifest and
// research summary at build time; no season, population or licence value is
// hard-coded in this module or in its consumers.

export interface DataVintageBadgeProps {
  manifest: AnyManifest;
}

/** Concise, no-JavaScript-safe heritage chip for the first interpretation
 *  point (landing hero and /science intro), per the frozen narrative spec
 *  (D034 §7.1: "data-vintage chip (I)").
 *
 *  `scoutlens-9a3.20` (D067): it also names the provider and the population
 *  rule. Both used to appear only in ProviderBoundary, after every result on
 *  every route, so a reader met "Rank 1 of 1,257" before learning whose data
 *  it was or who counts as eligible.
 *
 *  `scoutlens-9a3.26` (D069): and the competition scope and the licence
 *  boundary, the two remaining facts epic 9a3 AC5 places at the first point
 *  of interpretation. */
export function DataVintageBadge({ manifest }: DataVintageBadgeProps) {
  return (
    <p className="data-vintage" data-vintage-badge>
      <span className="data-vintage__label">{BENCHMARK_PURPOSE}</span>
      <span className="data-vintage__provider">{providerLabel(manifest.source.provider)}</span>
      <span className="data-vintage__season">{manifest.source.season}</span>
      <span className="data-vintage__scope">
        {competitionScope(manifest.population.domestic_competition_ids.length)}
      </span>
      <span className="data-vintage__threshold">
        {eligibilityRule(manifest.population.minutes_threshold_per_period)}
      </span>
      <span className="data-vintage__licence">{manifest.source.licence}</span>
      <span className="data-vintage__redistribution">{REDISTRIBUTION_SUMMARY}</span>
      <code className="data-vintage__pin">{manifest.dataset_version}</code>
    </p>
  );
}

export interface ProviderBoundaryProps {
  manifest: AnyManifest;
  research: AnyResearchSummaryArtifact;
}

/** Distinguishes the primary per-profile evidence (Wyscout/Pappalardo) from
 *  the aggregate-only StatsBomb replication, and states the
 *  reproducibility-vs-recency boundary explicitly. */
export function ProviderBoundary({ manifest, research }: ProviderBoundaryProps) {
  const replication = research.experiments.some(
    (experiment) => experiment.provider === "statsbomb_open_data",
  );
  const wyscout = manifest.source.provider === "wyscout_pappalardo";
  const { population } = manifest;
  const competitionCount = population.domestic_competition_ids.length;
  // `scoutlens-9a3.22`: "period A / B", as every other surface names them,
  // not the artifact's lower-case codes.
  const periodsLabel = population.chronological_periods.map((period) => period.toUpperCase()).join(" / ");

  return (
    <section className="provider-boundary" aria-labelledby="provider-boundary-heading" data-provider-boundary>
      <div className="section-heading">
        <p className="eyebrow">Data vintage and provenance</p>
        <h2 id="provider-boundary-heading">What these numbers describe — and what they do not</h2>
      </div>
      <div className="provider-boundary__grid">
        <article className="provider-boundary__card provider-boundary__card--primary">
          <h3>Primary evidence</h3>
          {/*
            `scoutlens-9a3.22`: the Wyscout branch ended "by Pappalardo et al." and
            then added its own full stop - "et al.." on every route. The second
            provider check inside it was always true there, so it is gone too.
          */}
          <p>
            {wyscout
              ? `Every player profile, rank, and neighbor on this site is derived from ${manifest.source.title} (${manifest.source.season}), a public event dataset by Pappalardo et al.`
              : `Primary evidence is derived from ${manifest.source.title} (${manifest.source.season}).`}
          </p>
          {/*
            `scoutlens-9a3.22`: this read "…player-period aggregates:" and then the
            note, on a new JSX line - which drops the space, so the page said
            "aggregates:ScoutLens publishes attributed player-period aggregates
            only", the same phrase twice and glued. The note says it; the
            sentence before it now only names the licence.
          */}
          <p>
            Published under {manifest.source.licence}.{" "}
            {manifest.source.redistribution_note}
          </p>
          <p>
            Scope: {population.profile_count.toLocaleString("en-US")}{" "}
            {population.analytical_unit.replaceAll("_", " × ")} profiles
            across {competitionCount} domestic competition{competitionCount === 1 ? "" : "s"}, split into
            period {periodsLabel}. A profile is eligible only with at least{" "}
            {population.minutes_threshold_per_period} minutes per period.
          </p>
          <p>
            <a href={manifest.source.source_url}>Canonical source</a>
            {" · "}
            <a href={manifest.source.licence_url}>{manifest.source.licence} licence</a>
          </p>
        </article>
        <article className="provider-boundary__card provider-boundary__card--replication">
          <h3>External replication — aggregate only</h3>
          <p>
            {replication
              ? "The replication evidence is drawn from a separate provider as aggregate results only. No per-player data from that provider is published or linked here."
              : "External replication evidence is reported at the aggregate level only."}
          </p>
          <p>
            The site evaluates a reproducible method on historical data. It is{" "}
            <strong>not current scouting information</strong>{" "}and does not
            guarantee that historical results transfer to today&apos;s football.
          </p>
          <p>
            <Link href="/science/">See the replication and its limitations</Link>
          </p>
        </article>
      </div>
    </section>
  );
}
