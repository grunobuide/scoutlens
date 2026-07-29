import Link from "next/link";

import type { ResearchExperiment, ResearchSummaryArtifact } from "@/contracts/generated/showcase";
import {
  caveatsFor,
  formatMetric,
  formatMetricInterval,
  requireMetric,
  type ShowcaseStory,
} from "@/content/showcase-story";

const repositoryRoot = "https://github.com/grunobuide/scoutlens/blob/main/";

function repositoryHref(path: string): string {
  const [filePath, fragment] = path.split("#", 2);
  return `${repositoryRoot}${filePath ?? path}${fragment === undefined ? "" : `#${fragment}`}`;
}

function providerLabel(provider: ResearchExperiment["provider"]): string {
  return provider === "wyscout_pappalardo" ? "Wyscout / Pappalardo" : "StatsBomb Open Data";
}

interface ExperimentCardProps {
  experiment: ResearchExperiment;
  research: ResearchSummaryArtifact;
  metricIds?: ReadonlyArray<string>;
  emphasis?: "default" | "warning" | "signal";
}

export function ExperimentCard({
  experiment,
  research,
  metricIds,
  emphasis = "default",
}: ExperimentCardProps) {
  const metrics = metricIds?.map((metricId) => requireMetric(experiment, metricId)) ?? experiment.metrics;
  const caveats = caveatsFor(research, experiment);

  return (
    <article className={`experiment-card experiment-card--${emphasis}`}>
      <header className="experiment-card__header">
        <p className="experiment-card__provider">{providerLabel(experiment.provider)}</p>
        <h3>{experiment.title}</h3>
        <p>{experiment.population}</p>
      </header>
      <dl className="experiment-metrics">
        {metrics.map((metric) => {
          const interval = formatMetricInterval(metric);
          return (
            <div key={metric.metric_id}>
              <dt>{metric.label}</dt>
              <dd>{formatMetric(metric)}</dd>
              {interval === null ? null : <dd className="experiment-metric__interval">95% CI: {interval}</dd>}
            </div>
          );
        })}
      </dl>
      <p className="experiment-card__conclusion">{experiment.conclusion}</p>
      <div className="caveat-stack" aria-label="Interpretation boundaries">
        {caveats.map((caveat) => (
          <p className={`caveat caveat--${caveat.severity}`} key={caveat.code}>
            <span>{caveat.severity}</span>
            {caveat.message}
          </p>
        ))}
      </div>
      <p className="evidence-links">
        <a href={repositoryHref(experiment.report_url)}>Read method</a>
        <a href={repositoryHref(experiment.source_artifact)}>Inspect artifact</a>
      </p>
    </article>
  );
}

export function ClaimsMatrix({ research }: { research: ResearchSummaryArtifact }) {
  return (
    <section className="claims-matrix" aria-labelledby="claims-heading">
      <div className="claims-matrix__supported">
        <p className="eyebrow">Supported claim</p>
        <h2 id="claims-heading">What the evidence supports</h2>
        <p>{research.supported_claim}</p>
      </div>
      <div className="claims-matrix__unsupported">
        <p className="eyebrow">Not supported</p>
        <h3>Where the evidence stops</h3>
        <ul>
          {research.unsupported_claims.map((claim) => (
            <li key={claim}>{claim}</li>
          ))}
        </ul>
      </div>
    </section>
  );
}

export function FingerprintPreview({ story }: { story: ShowcaseStory }) {
  const profile = story.featuredProfile;
  const periodA = profile.periods.a;
  const periodB = profile.periods.b;

  return (
    <section className="fingerprint-section shell" aria-labelledby="fingerprint-heading">
      <div className="section-heading section-heading--fingerprint">
        <div>
          <p className="eyebrow">A real A/B fingerprint</p>
          <h2 id="fingerprint-heading">The shape persists while the matches change.</h2>
        </div>
        <div className="fingerprint-context">
          <p className="fingerprint-context__name">{story.featuredName}</p>
          <p>
            {story.featuredTeam} · {profile.identity.role} · {profile.identity.competition.name}
          </p>
          <p>
            Percentiles within {profile.cohort.within_role_profile_count.toLocaleString("en-US")} {profile.identity.role.toLowerCase()} profiles; at least {profile.cohort.minutes_threshold_per_period} minutes in each half.
          </p>
        </div>
      </div>

      <div className="fingerprint-card">
        <div className="fingerprint-legend" aria-label="Fingerprint periods">
          <span><i className="period-dot period-dot--a" />A · {periodA.label}</span>
          <span><i className="period-dot period-dot--b" />B · {periodB.label}</span>
        </div>
        <div className="fingerprint-plot">
          {story.fingerprintFeatures.map((feature) => (
            <div className="fingerprint-row" key={feature.featureId}>
              <div>
                <span>{feature.label}</span>
                <small>{feature.family}</small>
              </div>
              <div className="fingerprint-track">
                <span
                  aria-hidden="true"
                  className="fingerprint-mark fingerprint-mark--a"
                  style={{ left: `${feature.periodA}%` }}
                />
                <span
                  aria-hidden="true"
                  className="fingerprint-mark fingerprint-mark--b"
                  style={{ left: `${feature.periodB}%` }}
                />
              </div>
              <p><span>{feature.periodA.toFixed(0)}</span><span>{feature.periodB.toFixed(0)}</span></p>
            </div>
          ))}
        </div>
        <p className="fingerprint-footnote">
          Family averages across all {story.manifest.population.feature_count} descriptive features, not quality scores. Period A covers {periodA.match_count} matches; period B covers {periodB.match_count}.
        </p>
      </div>
    </section>
  );
}

export function ProvenanceDrawer({ story }: { story: ShowcaseStory }) {
  const artifactLinks = [...new Set(story.research.experiments.map((item) => item.source_artifact))];
  const reportLinks = [...new Set(story.research.experiments.map((item) => item.report_url))];

  return (
    <section className="provenance-section" aria-labelledby="sources-heading">
      <div className="source-grid">
        <article>
          <p className="source-mark">Wyscout / Pappalardo</p>
          <h2 id="sources-heading">Public event data, aggregate profiles</h2>
          <p>{story.manifest.source.citation}</p>
          <p>
            <a href={story.manifest.source.source_url}>Canonical source</a>{" · "}
            <a href={story.manifest.source.licence_url}>{story.manifest.source.licence}</a>
          </p>
        </article>
        <article>
          <p className="source-mark source-mark--statsbomb">StatsBomb</p>
          <h2>Aggregate replication only</h2>
          <p>
            StatsBomb Open Data results are published as aggregate analysis. Raw and per-player data are not redistributed; the User Agreement also restricts commercial use.
          </p>
          <p>
            <a href="https://github.com/statsbomb/open-data">Official repository</a>{" · "}
            <a href="https://github.com/statsbomb/open-data/blob/master/LICENSE.pdf">User Agreement</a>
          </p>
        </article>
      </div>

      <details className="provenance-drawer" open>
        <summary>Audit the full provenance chain</summary>
        <div className="provenance-drawer__content">
          <div>
            <h3>Published contract</h3>
            <ul>
              <li><a href="/showcase/v1/manifest.json">Versioned manifest</a></li>
              <li><a href="/showcase/v1/research-summary.json">Research summary</a></li>
              <li><a href="/showcase/v1/feature-catalog.json">Feature catalog</a></li>
              <li><a href={repositoryHref(story.manifest.producer.config_path)}>Frozen experiment config</a></li>
            </ul>
          </div>
          <div>
            <h3>Result artifacts</h3>
            <ul>
              {artifactLinks.map((path) => <li key={path}><a href={repositoryHref(path)}>{path}</a></li>)}
            </ul>
          </div>
          <div>
            <h3>Research decisions</h3>
            <ul>
              {reportLinks.map((path) => <li key={path}><a href={repositoryHref(path)}>{path}</a></li>)}
            </ul>
          </div>
        </div>
      </details>
      <p className="provenance-version">Dataset pin: <code>{story.manifest.dataset_version}</code></p>
      <p className="provenance-cta"><Link href="/lab/">Explore every fingerprint</Link></p>
    </section>
  );
}
