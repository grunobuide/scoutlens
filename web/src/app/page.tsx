import Link from "next/link";

import { DataVintageBadge, ProviderBoundary } from "@/components/data-provenance";
import {
  ClaimsMatrix,
  ExperimentCard,
  FingerprintPreview,
  ProvenanceDrawer,
} from "@/components/research-story";
import { loadShowcaseStory } from "@/content/load-showcase-story";
import { formatMetric, requireMetric } from "@/content/showcase-story";

export default async function HomePage() {
  const story = await loadShowcaseStory();
  const { experiments, research } = story;
  const teamControlMrr = formatMetric(requireMetric(experiments.teamControl, "baseline_c_mrr"));

  return (
    <main id="main-content">
      <section className="hero shell">
        <div className="hero__copy">
          <DataVintageBadge manifest={story.manifest} />
          <p className="eyebrow">Player Fingerprint Lab</p>
          <h1>A player leaves a reproducible fingerprint in the shape of their actions.</h1>
          <p className="lede">
            ScoutLens tests whether event-derived profiles can retrieve the same player across two chronological halves—then exposes the controls that narrow what that result means.
          </p>
          <p className="hero__boundary">
            Evidence of individual signal. Not proof of playing style. Not a recruitment recommendation.
          </p>
          <div className="actions" aria-label="Explore ScoutLens">
            <Link className="button button--primary" href="/lab/">
              Explore every fingerprint
            </Link>
            <Link className="button button--secondary" href="/science/">
              Audit the science
            </Link>
          </div>
        </div>
        <aside className="hero__signal" aria-label="Supported result">
          <span className="signal-orbit signal-orbit--outer" aria-hidden="true" />
          <span className="signal-orbit signal-orbit--inner" aria-hidden="true" />
          <div>
            <p className="signal-label">Supported claim</p>
            <p className="signal-copy">{research.supported_claim}</p>
            <p className="signal-caveat">
              Critical confound: a role + team + minutes control reaches {teamControlMrr} MRR, so same-season context can make identity retrieval easier.
            </p>
          </div>
        </aside>
      </section>

      <div className="shell initial-boundaries">
        <ClaimsMatrix research={research} />
      </div>

      <FingerprintPreview story={story} />

      <section className="proof-band" aria-labelledby="evidence-heading">
        <div className="shell">
          <div className="section-heading">
            <p className="eyebrow">Evidence at a glance</p>
            <div>
              <h2 id="evidence-heading">The headline survives, but the confound stays beside it.</h2>
              <p className="section-intro">
                Mean reciprocal rank measures how high the true same-player profile appears in the retrieval list. Higher is better for this identity task—not a player rating.
              </p>
            </div>
          </div>
          <div className="experiment-grid experiment-grid--headline">
            <ExperimentCard
              emphasis="signal"
              experiment={experiments.global}
              metricIds={["baseline_a_mrr", "fingerprint_mrr", "mrr_delta"]}
              research={research}
            />
            <ExperimentCard
              emphasis="warning"
              experiment={experiments.teamControl}
              metricIds={["baseline_c_mrr", "median_rank"]}
              research={research}
            />
          </div>
        </div>
      </section>

      <section className="replication-section shell" aria-labelledby="replication-heading">
        <div className="section-heading">
          <p className="eyebrow">Replication and restraint</p>
          <div>
            <h2 id="replication-heading">Another provider reproduced the signal. A plausible correction did not improve it.</h2>
            <p className="section-intro">
              Both outcomes matter: the lower-magnitude external replication adds confidence; the null result shows the project does not promote every promising idea.
            </p>
          </div>
        </div>
        <div className="experiment-grid">
          <ExperimentCard
            experiment={experiments.replication}
            metricIds={["baseline_a_mrr", "fingerprint_mrr", "median_rank"]}
            research={research}
          />
          <ExperimentCard
            experiment={experiments.shrinkage}
            metricIds={["raw_global_mrr", "shrunk_global_mrr"]}
            research={research}
          />
        </div>
      </section>

      <div className="shell landing-provenance">
        <ProviderBoundary manifest={story.manifest} research={research} />
        <ProvenanceDrawer story={story} />
      </div>
    </main>
  );
}
