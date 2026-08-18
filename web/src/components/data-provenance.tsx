import Link from "next/link";
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
 *  (D034 §7.1: "data-vintage chip (I)"). */
export function DataVintageBadge({ manifest }: DataVintageBadgeProps) {
  return (
    <p className="data-vintage" data-vintage-badge>
      <span className="data-vintage__label">Historical reproducible benchmark</span>
      <span className="data-vintage__season">{manifest.source.season}</span>
      <span className="data-vintage__licence">{manifest.source.licence}</span>
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
  const periodsLabel = population.chronological_periods.join(" / ");

  return (
    <section className="provider-boundary" aria-labelledby="provider-boundary-heading" data-provider-boundary>
      <div className="section-heading">
        <p className="eyebrow">Data vintage and provenance</p>
        <h2 id="provider-boundary-heading">What these numbers describe — and what they do not</h2>
      </div>
      <div className="provider-boundary__grid">
        <article className="provider-boundary__card provider-boundary__card--primary">
          <h3>Primary evidence</h3>
          <p>
            {wyscout
              ? `Every player profile, rank, and neighbor on this site is derived from ${manifest.source.title} (${manifest.source.season}), a public event dataset by ${manifest.source.provider === "wyscout_pappalardo" ? "Pappalardo et al." : manifest.source.provider}.`
              : `Primary evidence is derived from ${manifest.source.title} (${manifest.source.season}).`}
          </p>
          <p>
            Published under {manifest.source.licence} as attributed player-period aggregates:
            {manifest.source.redistribution_note}
          </p>
          <p>
            Scope: {population.profile_count} {population.analytical_unit.replace(/_/g, " ")} profiles
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
            <strong>not current scouting information</strong> and does not
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
