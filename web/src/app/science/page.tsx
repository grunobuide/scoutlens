import type { Metadata } from "next";

import { DataVintageBadge, ProviderBoundary } from "@/components/data-provenance";
import { ClaimsMatrix, ExperimentCard, FingerprintPreview, ProvenanceDrawer } from "@/components/research-story";
import { loadShowcaseStory } from "@/content/load-showcase-story";

export const metadata: Metadata = {
  title: "How it works",
  description: "The frozen question, controls, replication, null result, and evidence boundary behind ScoutLens.",
};

export default async function SciencePage() {
  const story = await loadShowcaseStory();
  const { experiments, research } = story;
  const narrative = [...research.narrative_steps].sort((a, b) => a.order - b.order);

  return (
    <main id="main-content" className="shell page-shell science-page">
      <header className="page-intro page-intro--wide">
        <DataVintageBadge manifest={story.manifest} />
        <p className="eyebrow">How it works</p>
        <h1>The science is the sequence, not one headline number.</h1>
        <p className="lede">
          The question and split were frozen first. Each harder test then narrowed the interpretation—from a strong retrieval result to a cross-provider individual signal with a serious team-context confound.
        </p>
        <div className="science-orientation">
          <p>
            ScoutLens asks one question: can a player&apos;s statistical profile identify them?
            We take public football event data from the {story.manifest.source.season} season,
            split every player&apos;s play time into two chronological halves, and test whether{" "}
            {story.manifest.population.feature_count} simple measurements of how they act can find
            that same player again in the second half.
          </p>
          <p className="science-orientation__boundary">
            This is evidence of individual signal — not proof of playing style, not a
            recommendation, and not a prediction.
          </p>
        </div>
      </header>

      <section className="frozen-question" aria-labelledby="frozen-question-heading">
        <p className="research-step__marker">01 · {narrative[0]?.kind}</p>
        <div>
          <h2 id="frozen-question-heading">{narrative[0]?.title}</h2>
          <p>{narrative[0]?.summary}</p>
          <dl className="split-definition">
            <div><dt>Query</dt><dd>First chronological half</dd></div>
            <div><dt>Candidate</dt><dd>Second chronological half</dd></div>
            <div><dt>Threshold</dt><dd>{story.manifest.population.minutes_threshold_per_period} minutes in each half</dd></div>
            <div><dt>Features</dt><dd>{story.manifest.population.feature_count} event-derived measurements</dd></div>
          </dl>
        </div>
      </section>

      <section className="science-mrr-intro" aria-labelledby="mrr-heading">
        <h2 id="mrr-heading">How we measure retrieval: MRR</h2>
        <p>
          Mean reciprocal rank (MRR) measures how high the true same-player profile appears in
          the retrieval list on average. A score of 1 would mean the fingerprint always finds the
          same player first; a score near 0 means it barely beats random guessing. MRR is an
          identity-task measure — higher is better <strong>for this task</strong>, never a quality
          rating.
        </p>
      </section>

      <ResearchStage marker="02" title={narrative[1]?.title ?? "Primary result"} summary={narrative[1]?.summary ?? ""}>
        <div className="experiment-grid">
          <ExperimentCard experiment={experiments.global} metricIds={["baseline_a_mrr", "fingerprint_mrr", "mrr_delta", "median_rank"]} research={research} emphasis="signal" />
          <ExperimentCard experiment={experiments.withinRole} research={research} />
        </div>
      </ResearchStage>

      <ResearchStage marker="03" title={narrative[2]?.title ?? "Team control"} summary={narrative[2]?.summary ?? ""} tone="warning">
        <ExperimentCard experiment={experiments.teamControl} research={research} emphasis="warning" />
        <p className="research-stage__confound-note">
          Same-season club continuity is a strong confound and can make identity retrieval easier
          without proving the fingerprint. This control narrows the interpretation; it does not
          invalidate the signal.
        </p>
      </ResearchStage>

      <ResearchStage marker="04" title={narrative[3]?.title ?? "Transferred-player analysis"} summary={narrative[3]?.summary ?? ""}>
        <ExperimentCard experiment={experiments.transferred} research={research} />
      </ResearchStage>

      <ResearchStage marker="05" title={narrative[4]?.title ?? "External replication"} summary={narrative[4]?.summary ?? ""}>
        <div className="experiment-grid experiment-grid--three">
          <ExperimentCard experiment={experiments.replication} research={research} />
          <ExperimentCard experiment={experiments.replicationWithinRole} research={research} />
          <ExperimentCard experiment={experiments.replicationTransferred} research={research} />
        </div>
      </ResearchStage>

      <ResearchStage marker="06" title={narrative[5]?.title ?? "Null result"} summary={narrative[5]?.summary ?? ""}>
        <ExperimentCard experiment={experiments.shrinkage} research={research} />
      </ResearchStage>

      <section className="science-worked-example" aria-labelledby="worked-example-heading">
        <div className="section-heading">
          <p className="eyebrow">A worked example</p>
          <h2 id="worked-example-heading">One player, two halves, one retrieval result</h2>
        </div>
        <p>
          {story.featuredName} ({story.featuredTeam}, {story.featuredProfile.identity.role},
          {" "}{story.featuredProfile.identity.competition.name}) is the editorially featured
          profile. The fingerprint ranked their second-half profile{" "}
          {story.featuredProfile.retrieval.global.self_rank} of{" "}
          {story.featuredProfile.retrieval.global.candidate_count} eligible profiles —
          compared to {story.featuredProfile.retrieval.baseline_role_minutes.self_rank} under
          a role-and-minutes baseline. The editorial choice is not based on retrieval rank or
          player quality.
        </p>
        <FingerprintPreview story={story} />
      </section>

      <section className="science-uncertainty" aria-labelledby="uncertainty-heading">
        <div className="section-heading">
          <p className="eyebrow">Uncertainty</p>
          <h2 id="uncertainty-heading">Every rank travels with its resampled interval</h2>
        </div>
        <p>
          Each profile&apos;s rank, median and recall rates are published with intervals
          from 500 match-bootstrap resamples (preregistered, D031) of the frozen
          population. The intervals describe sampling stability in the observed matches —
          how much a rank moves when whole matches are reshuffled — not causal effects,
          provider annotation error, or future performance. A small number of features
          that were never observed for a player (for example a conversion rate for a
          player who never shot) are marked <strong>insufficient</strong> with their valid
          resample count, never filled with a substitute value. The method is documented
          in the <a href="https://github.com/grunobuide/scoutlens/blob/main/docs/uncertainty-method.md">match-bootstrap method note</a>.
        </p>
      </section>

      <div className="science-claims">
        <ClaimsMatrix research={research} />
      </div>

      <section className="science-engineering" aria-labelledby="engineering-heading">
        <div className="section-heading">
          <p className="eyebrow">Engineering and AI boundary</p>
          <h2 id="engineering-heading">What the system is — and what it is not</h2>
        </div>
        <div className="science-engineering__grid">
          <article>
            <h3>Engineering</h3>
            <p>
              ScoutLens is a static website. Every number is computed in Python from frozen
              event data, exported as immutable JSON, and consumed by a typed TypeScript
              client. There is no backend, no live database, and no client-side computation
              of retrieval, ranks, or similarities. Quality gates enforce the build, the
              static export, and the performance budget on every change.
            </p>
          </article>
          <article>
            <h3>Governed AI</h3>
            <p>
              AI may narrate deterministic evidence in the future, but only under a fail-closed
              evidence-bundle contract: every factual sentence must cite evidence IDs, unknown
              entities are rejected, and invalid output falls back to deterministic content.
              AI never recomputes a value, invents a metric, softens a caveat, or makes a
              recommendation. No live LLM is required for any current page.
            </p>
          </article>
        </div>
      </section>

      <ProviderBoundary manifest={story.manifest} research={research} />
      <ProvenanceDrawer story={story} />
    </main>
  );
}

interface ResearchStageProps {
  marker: string;
  title: string;
  summary: string;
  tone?: "default" | "warning";
  children: React.ReactNode;
}

function ResearchStage({ marker, title, summary, tone = "default", children }: ResearchStageProps) {
  return (
    <section className={`research-stage research-stage--${tone}`} aria-labelledby={`stage-${marker}`}>
      <header>
        <p className="research-step__marker">{marker}</p>
        <div>
          <h2 id={`stage-${marker}`}>{title}</h2>
          <p>{summary}</p>
        </div>
      </header>
      {children}
    </section>
  );
}
