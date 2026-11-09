import { ProviderBoundary } from "@/components/data-provenance";
import { LandingHero } from "@/components/landing-hero";
import {
  ClaimsMatrix,
  ExperimentCard,
  FingerprintPreview,
  ProvenanceDrawer,
} from "@/components/research-story";
import { loadShowcaseStory } from "@/content/load-showcase-story";
import { createServerShowcaseRepository } from "@/content/showcase-server";

export default async function HomePage() {
  const [story, catalog] = await Promise.all([
    loadShowcaseStory(),
    // D075: the h1's number is the catalogue's length, read at build time.
    createServerShowcaseRepository().getFeatureCatalog(),
  ]);
  const { experiments, research } = story;

  return (
    <main id="main-content">
      <LandingHero story={story} featureCount={catalog.features.length} />

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
            {/*
              `scoutlens-rdz.11`: the four tests share one 0–1 scale. Only
              MRR scores are drawn on it; the difference and the median rank
              stay numbers, because the artifact gives a difference the same
              unit as a score and only its id tells them apart.
            */}
            <ExperimentCard
              emphasis="signal"
              experiment={experiments.global}
              metricIds={["baseline_a_mrr", "fingerprint_mrr", "mrr_delta"]}
              scaledMetricIds={["baseline_a_mrr", "fingerprint_mrr"]}
              research={research}
            />
            <ExperimentCard
              emphasis="warning"
              experiment={experiments.teamControl}
              metricIds={["baseline_c_mrr", "median_rank"]}
              scaledMetricIds={["baseline_c_mrr"]}
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
            scaledMetricIds={["baseline_a_mrr", "fingerprint_mrr"]}
            research={research}
          />
          <ExperimentCard
            experiment={experiments.shrinkage}
            metricIds={["raw_global_mrr", "shrunk_global_mrr"]}
            scaledMetricIds={["raw_global_mrr", "shrunk_global_mrr"]}
            research={research}
          />
        </div>
      </section>

      <div className="shell landing-provenance">
        <ProviderBoundary manifest={story.manifest} research={research} competitions={story.competitions} />
        <ProvenanceDrawer story={story} />
      </div>
    </main>
  );
}
