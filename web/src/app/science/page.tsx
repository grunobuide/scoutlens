import type { Metadata } from "next";

import { ClaimsMatrix, ExperimentCard, ProvenanceDrawer } from "@/components/research-story";
import { loadShowcaseStory } from "@/content/load-showcase-story";

export const metadata: Metadata = {
  title: "Science",
  description: "The frozen question, controls, replication, null result, and evidence boundary behind ScoutLens.",
};

export default async function SciencePage() {
  const story = await loadShowcaseStory();
  const { experiments, research } = story;
  const narrative = [...research.narrative_steps].sort((a, b) => a.order - b.order);

  return (
    <main id="main-content" className="shell page-shell science-page">
      <header className="page-intro page-intro--wide">
        <p className="eyebrow">Research trail</p>
        <h1>The science is the sequence, not one headline number.</h1>
        <p className="lede">
          The question and split were frozen first. Each harder test then narrowed the interpretation—from a strong retrieval result to a cross-provider individual signal with a serious team-context confound.
        </p>
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

      <ResearchStage marker="02" title={narrative[1]?.title ?? "Primary result"} summary={narrative[1]?.summary ?? ""}>
        <div className="experiment-grid">
          <ExperimentCard experiment={experiments.global} metricIds={["baseline_a_mrr", "fingerprint_mrr", "mrr_delta", "median_rank"]} research={research} emphasis="signal" />
          <ExperimentCard experiment={experiments.withinRole} research={research} />
        </div>
      </ResearchStage>

      <ResearchStage marker="03" title={narrative[2]?.title ?? "Team control"} summary={narrative[2]?.summary ?? ""} tone="warning">
        <ExperimentCard experiment={experiments.teamControl} research={research} emphasis="warning" />
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

      <div className="science-claims">
        <ClaimsMatrix research={research} />
      </div>

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
