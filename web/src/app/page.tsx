import Link from "next/link";

import { ProviderBoundary } from "@/components/data-provenance";
import { LandingHero } from "@/components/landing-hero";
import {
  ClaimsMatrix,
  ExperimentCard,
  FingerprintPreview,
  ProvenanceDrawer,
} from "@/components/research-story";
import { loadShowcaseStory } from "@/content/load-showcase-story";
import { eligibilityRule } from "@/content/provenance";
import { createServerShowcaseRepository } from "@/content/showcase-server";

export default async function HomePage() {
  const [story, catalog] = await Promise.all([
    loadShowcaseStory(),
    // D075: the h1's number is the catalogue's length, read at build time.
    createServerShowcaseRepository().getFeatureCatalog(),
  ]);
  const { experiments, research, manifest } = story;
  const { population, source } = manifest;
  const competitionCount = population.domestic_competition_ids.length;
  const eligible = eligibilityRule(population.minutes_threshold_per_period);

  return (
    <main id="main-content">
      <LandingHero story={story} featureCount={catalog.features.length} />

      {/*
        `scoutlens-rdz.9` (D076, narrative §7.1 item 3): facts about the
        population and the data, in place of the "100% open" strip D075 cut.
        Every value is the manifest's, read at build time. It shows no result
        value, and a fact no artifact publishes is left out rather than
        computed here: the design's provider count is one of them.
      */}
      <section className="facts-strip" aria-label="About the data">
        <ul className="facts-strip__list shell">
          <li>
            <span className="facts-strip__value">{population.profile_count.toLocaleString("en-US")}</span>{" "}
            <span className="facts-strip__label">{`profiles of ${eligible}`}</span>
          </li>
          <li>
            <span className="facts-strip__value">{competitionCount}</span>{" "}
            <span className="facts-strip__label">
              {`domestic competition${competitionCount === 1 ? "" : "s"} in the ${source.season} season`}
            </span>
          </li>
          <li>
            <span className="facts-strip__value">{population.feature_count}</span>{" "}
            <span className="facts-strip__label">measurements describe each half</span>
          </li>
          <li>
            <span className="facts-strip__value">{source.licence}</span>{" "}
            <span className="facts-strip__label">licence of the source data</span>
          </li>
          <li className="facts-strip__pin">
            <code className="facts-strip__value">{manifest.dataset_version}</code>{" "}
            <span className="facts-strip__label">dataset pin</span>
          </li>
        </ul>
      </section>

      {/*
        `scoutlens-rdz.9` (D076, narrative §7.1 item 4): the method as the
        narrative's §3 tells it, and nothing §3 does not say. The heading is
        §3's question; the three steps are its second sentence, split where
        D076 splits the method. The numbers are the manifest's.
      */}
      <section className="idea shell" aria-labelledby="idea-heading">
        <p className="eyebrow">The idea in 30 seconds</p>
        <h2 id="idea-heading">Can a player&apos;s statistical profile identify them?</h2>
        <ol className="idea__steps">
          <li>
            <h3>Split the season in two</h3>
            <p>
              {`We take public football event data from the ${source.season} season and split every player's play time into two chronological halves. Only ${eligible} count.`}
            </p>
          </li>
          <li>
            <h3>{`Describe each half with ${population.feature_count} measurements`}</h3>
            <p>
              {`Each half becomes a profile of ${population.feature_count} simple measurements of how the player acts.`}
            </p>
          </li>
          <li>
            <h3>Look for the same player again</h3>
            <p>
              {`All ${population.profile_count.toLocaleString("en-US")} second-half profiles are ranked by how similar each is to one player's first half. The test is how high that same player lands.`}
            </p>
          </li>
        </ol>
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

      {/*
        `scoutlens-rdz.12` (narrative §7.1 item 9, D075, D076): the landing's
        case-study block. It carries the case-study link only - not a third
        hero CTA, and the repository link stays in the footer and provenance
        (D076). Every line is docs/case-study.md's: §1-§5 for the trail, §6
        for the engineering, §7 for the AI boundary.
      */}
      <section className="behind shell" aria-labelledby="behind-heading">
        <div className="behind__copy">
          <p className="eyebrow">Behind the project</p>
          <h2 id="behind-heading">A question that can be wrong, and the machinery to check the answer.</h2>
          <p>
            The question was frozen before the result was read. Then came a baseline to beat, a
            control that narrowed the claim, a replication on another provider and a published null,
            and the engineering that keeps every number on this site tied to the file it came from.
          </p>
          <p className="behind__action">
            <Link className="button button--primary" href="/case-study/">
              Read the case study
            </Link>
          </p>
        </div>
        <dl className="behind__facets">
          <div>
            <dt>Data science</dt>
            <dd>A frozen question, baselines, a team control, a second provider</dd>
          </div>
          <div>
            <dt>Engineering</dt>
            <dd>Python, then immutable JSON, then a typed static site</dd>
          </div>
          <div>
            <dt>AI</dt>
            <dd>An offline explanation toolkit, kept out of this site</dd>
          </div>
          <div>
            <dt>Guardrails</dt>
            <dd>A model may only cite published evidence, and a refused output is never shown</dd>
          </div>
        </dl>
      </section>
    </main>
  );
}
