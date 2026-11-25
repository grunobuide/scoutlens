import type { Metadata } from "next";
import type { ReactNode } from "react";

import { DataVintageBadge, ProviderBoundary } from "@/components/data-provenance";
import { MetricGlossary, metricTag } from "@/components/quantity-glossary";
import { ThesisStatement } from "@/components/thesis-statement";
import type { ResearchExperiment, ResearchMetric } from "@/contracts/generated/showcase";
import { loadShowcaseStory } from "@/content/load-showcase-story";
import {
  caveatsFor,
  formatMetric,
  formatMetricInterval,
  requireMetric,
} from "@/content/showcase-story";

export const metadata: Metadata = {
  title: "Case study",
  description:
    "How Yumusarái Labs was built: a frozen question, a baseline to beat, a control that narrowed the claim, a replication and a published null.",
};

const repositoryRoot = "https://github.com/grunobuide/scoutlens/blob/main/";

function repositoryHref(path: string): string {
  return `${repositoryRoot}${path}`;
}

/** One metric of one experiment, the pair `metricTag` and `MetricGlossary` take. */
interface Quoted {
  experiment: ResearchExperiment;
  metric: ResearchMetric;
}

function quote(experiment: ResearchExperiment, metricId: string): Quoted {
  return { experiment, metric: requireMetric(experiment, metricId) };
}

/** A metric value in running text, tagged so a test can hold it to the artifact. */
function Value({ quoted }: { quoted: Quoted }) {
  return <span data-metric={metricTag(quoted)}>{formatMetric(quoted.metric)}</span>;
}

interface TrailStepProps {
  id: string;
  title: string;
  status: string;
  tone?: "default" | "narrowed";
  /** The step's headline number, shown beside the prose with its own label. */
  figure?: Quoted;
  /**
   * Every metric the step quotes, figure included. Its glossary lists them,
   * and the step carries the caveats of every experiment they come from.
   */
  quoted: ReadonlyArray<Quoted>;
  research: Awaited<ReturnType<typeof loadShowcaseStory>>["research"];
  doc: { href: string; label: string };
  children: ReactNode;
}

/**
 * One decision of the research trail (`scoutlens-rdz.13`, D075).
 *
 * The prose is `docs/case-study.md`'s; every number is read from the showcase
 * artifacts through `requireMetric` and printed with `formatMetric`, so its
 * rounding is the artifact's. Each step carries the caveats of the experiments
 * it quotes, derived from the quoted metrics so the two cannot drift apart,
 * inline, as every other surface that renders them does: the confound sits
 * beside the numbers it qualifies (D075).
 */
function TrailStep({ id, title, status, tone = "default", figure, quoted, research, doc, children }: TrailStepProps) {
  const caveats = [
    ...new Map(
      quoted.flatMap(({ experiment }) => caveatsFor(research, experiment)).map((caveat) => [caveat.code, caveat]),
    ).values(),
  ];
  return (
    <li className={`trail-step trail-step--${tone}`} aria-labelledby={id} data-quantity-scope>
      <div className="trail-step__body">
        <h3 id={id}>{title}</h3>
        {children}
        {caveats.length === 0 ? null : (
          <div className="caveat-stack trail-step__caveats" aria-label="Interpretation boundaries">
            {caveats.map((caveat) => (
              <p className={`caveat caveat--${caveat.severity}`} key={caveat.code}>
                <span>{caveat.severity}</span>
                {caveat.message}
              </p>
            ))}
          </div>
        )}
        {/* A document's name can carry a digit ("gate 2"); it is a name, not a value. */}
        <p className="trail-step__doc" data-context="document">
          <a href={repositoryHref(doc.href)}>{doc.label}</a>
        </p>
        {quoted.length === 0 ? null : <MetricGlossary items={quoted} />}
      </div>
      <div className="trail-step__figure">
        {figure === undefined ? null : (
          <p className="trail-step__value">
            <Value quoted={figure} />
            <span className="trail-step__value-label" data-context="label">
              {figure.metric.label}
            </span>
          </p>
        )}
        <p className="trail-step__status">{status}</p>
      </div>
    </li>
  );
}

export default async function CaseStudyPage() {
  const story = await loadShowcaseStory();
  const { experiments, research, manifest } = story;
  const { population, source } = manifest;
  const profileCount = population.profile_count.toLocaleString("en-US");

  const baseline = quote(experiments.global, "baseline_a_mrr");
  const fingerprint = quote(experiments.global, "fingerprint_mrr");
  const gain = quote(experiments.global, "mrr_delta");
  const medianRank = quote(experiments.global, "median_rank");
  const withinRole = quote(experiments.withinRole, "fingerprint_mrr");
  const withinRoleRank = quote(experiments.withinRole, "median_rank");
  const teamControl = quote(experiments.teamControl, "baseline_c_mrr");
  const teamControlRank = quote(experiments.teamControl, "median_rank");
  const transferredCount = quote(experiments.transferred, "transferred_count");
  const transferred = quote(experiments.transferred, "fingerprint_mrr");
  const replication = quote(experiments.replication, "fingerprint_mrr");
  const replicationBaseline = quote(experiments.replication, "baseline_a_mrr");
  const replicationRank = quote(experiments.replication, "median_rank");
  const replicationTransferredCount = quote(experiments.replicationTransferred, "transferred_count");
  const replicationTransferred = quote(experiments.replicationTransferred, "fingerprint_mrr");
  const shrunk = quote(experiments.shrinkage, "shrunk_global_mrr");
  const raw = quote(experiments.shrinkage, "raw_global_mrr");
  const gainInterval = formatMetricInterval(gain.metric);

  return (
    <main id="main-content" className="shell page-shell case-study">
      <header className="page-intro page-intro--wide case-study__intro">
        <DataVintageBadge manifest={manifest} competitions={story.competitions} />
        <p className="eyebrow">Case study</p>
        <h1>How I built Yumusarái Labs</h1>
        <p className="lede">
          Football analytics is full of similarity scores whose meaning is never pinned down. So
          this project asked a question that can be wrong: does an event-derived profile
          re-identify the same player across time? Re-identification has a correct answer for every
          query — the same player — so retrieval metrics mean something, and a baseline can beat
          you.
        </p>
        <div className="case-study__short">
          <p className="case-study__short-label">The short version</p>
          <ThesisStatement thesisClassName="case-study__thesis" boundaryClassName="case-study__boundary" />
        </div>
      </header>

      <section className="case-study-trail" aria-labelledby="trail-heading">
        <p className="eyebrow">The research trail</p>
        <h2 id="trail-heading">Each test made the claim smaller — and more trustworthy.</h2>
        <ol className="trail">
          <TrailStep
            id="trail-freeze"
            title="Freeze the question before seeing any result"
            status="Frozen first"
            quoted={[]}
            research={research}
            doc={{ href: "docs/chronological-split.md", label: "The chronological split" }}
          >
            {/* The frozen design's counts, from the manifest: context, not results. */}
            <p data-context="design">
              A chronological split: the first half of a season queries the second half.{" "}
              {`${profileCount} eligible player × competition units from the ${source.season} ${source.title}, each with at least ${population.minutes_threshold_per_period} minutes in each half, described by ${population.feature_count} features.`}{" "}
              The task and its thresholds were frozen before the result was read, so a result that
              contradicts the headline could not be quietly avoided.
            </p>
          </TrailStep>

          <TrailStep
            id="trail-baseline"
            title="Start with a dumb baseline"
            status="The bar to beat"
            figure={baseline}
            quoted={[baseline]}
            research={research}
            doc={{ href: "docs/feasibility-report.md", label: "The feasibility report" }}
          >
            <p>
              Same nominal role, then nearest minutes played. It knows nothing about how a player
              acts, and anything the fingerprint scores has to beat it to mean something.
            </p>
          </TrailStep>

          <TrailStep
            id="trail-fingerprint"
            title="Test the fingerprint"
            status="Signal found"
            figure={fingerprint}
            quoted={[fingerprint, gain, medianRank, withinRole, withinRoleRank]}
            research={research}
            doc={{ href: "docs/gate-2-decision.md", label: "The gate 2 decision" }}
          >
            <p>
              The <span data-context="design">{`${population.feature_count}-feature`}</span> fingerprint scores{" "}
              <Value quoted={fingerprint} /> MRR, <Value quoted={gain} /> above the baseline
              {gainInterval === null ? null : (
                <span data-metric-interval={metricTag(gain)} data-context="interval">{` (95% CI ${gainInterval})`}</span>
              )}
              , at a
              median self-rank of <Value quoted={medianRank} /> of{" "}
              <span data-context="population">{profileCount}</span>.
            </p>
            <p>
              Restricted to candidates in the same nominal role, it goes up: <Value quoted={withinRole} /> MRR,
              median self-rank <Value quoted={withinRoleRank} />. If the fingerprint were merely
              detecting &ldquo;this is a goalkeeper&rdquo;, that restriction would destroy it.
            </p>
          </TrailStep>

          <TrailStep
            id="trail-attack"
            title="Attack my own result"
            status="Claim narrowed"
            tone="narrowed"
            figure={teamControl}
            quoted={[teamControl, teamControlRank, transferredCount, transferred]}
            research={research}
            doc={{ href: "docs/robustness-checks.md", label: "The robustness checks" }}
          >
            <p>
              A baseline that knows only role, team and minutes scores <Value quoted={teamControl} /> MRR,
              at a median rank of <Value quoted={teamControlRank} /> — better than the fingerprint.
              Within a single season most players stay at one club, so knowing the club plus role and
              minutes narrows the candidates to a handful. Same-season club continuity is a stronger
              shortcut than the fingerprint itself.
            </p>
            <p>
              Players who changed club break that shortcut. There are <Value quoted={transferredCount} />,
              and the fingerprint scores <Value quoted={transferred} /> MRR on them: encouraging, and
              too few to settle it. A cross-season design would separate the two effects; it is named
              as the next experiment, not claimed as a result.
            </p>
          </TrailStep>

          <TrailStep
            id="trail-replication"
            title="Replicate on someone else's data"
            status="Weaker, same direction"
            figure={replication}
            quoted={[replication, replicationBaseline, replicationRank, replicationTransferredCount, replicationTransferred]}
            research={research}
            doc={{ href: "docs/statsbomb-replication.md", label: "The StatsBomb replication" }}
          >
            <p>
              An independent provider and a different season:{" "}
              <span data-context="population">{experiments.replication.population}</span>. The canonical
              fingerprint scores <Value quoted={replication} /> MRR against a <Value quoted={replicationBaseline} />{" "}
              baseline, at a median self-rank of <Value quoted={replicationRank} />. Positive, and lower in
              magnitude than the Wyscout result; that gap is carried as its own caveat rather than
              averaged away.
            </p>
            <p>
              Its <Value quoted={replicationTransferredCount} /> transferred players score{" "}
              <Value quoted={replicationTransferred} /> MRR, which is inconclusive and labelled as such.
            </p>
          </TrailStep>

          <TrailStep
            id="trail-null"
            title="Say no to a fix that doesn't help"
            status="Not promoted"
            figure={shrunk}
            quoted={[shrunk, raw]}
            research={research}
            doc={{ href: "docs/shrinkage-experiment.md", label: "The shrinkage experiment" }}
          >
            <p>
              Ratio features computed from few attempts are noisy, so empirical-Bayes shrinkage should
              help. It did not: <Value quoted={shrunk} /> global MRR against <Value quoted={raw} /> with raw
              ratios. Shrinkage reduced low-support extremes and slightly reduced retrieval. Raw ratios
              remain the default, and the experiment ships as a null result — a null is a result, not a
              prompt to try again differently until something works.
            </p>
          </TrailStep>
        </ol>
        <p className="case-study-trail__log">
          <a href={repositoryHref("docs/decisions-log.md")}>Every decision, in order: the decisions log</a>
        </p>
      </section>

      {/*
        `scoutlens-rdz.14` (D075): where AI fits. Every sentence is
        `docs/case-study.md` §7's or one of the agent contracts'
        (`docs/frontend-agent-contract.md`, `docs/modeling-agent-contract.md`),
        and the section opens by saying there is no AI in this site. D077
        (`scoutlens-rdz.28`): the lede's last sentence is the Lab's method
        disclosure and D056's "the project already uses ML", and `/science/`'s
        "Governed AI" carries the same sentence.
      */}
      <section className="case-study-ai" aria-labelledby="ai-heading">
        <p className="eyebrow">Where AI fits</p>
        <h2 id="ai-heading">AI helped build the project, under contract. It is not in this site.</h2>
        <p className="case-study-ai__lede">
          There is no AI in the deployed site, and none is planned. No page calls a model: every
          number on these pages is computed in Python from frozen event data and read from a
          published file. The machine learning is offline: the Fingerprint Lab ranks with one
          non-negative weight per measurement, fitted on the frozen Wyscout training split and
          published with the results.
        </p>
        <div className="case-study-ai__grid">
          <article className="case-study-ai__card">
            <h3>A governed engineering team</h3>
            <p>
              AI coding agents worked on the repository under written contracts, one for the
              frontend and one for the modeling, that bind every agent before it touches a file.
            </p>
            <ul>
              <li>One tracked issue, one branch, one pull request, with the gates the issue names run and their real output quoted.</li>
              <li>Each contract lists the files an agent may edit, the ones that need a named reviewer, and denies everything it does not list.</li>
              <li>An agent may change how a value is presented, never the value, its rounding, a caveat or the order the artifact supplies.</li>
              <li>If a contract and an issue disagree, the issue loses and the agent stops.</li>
            </ul>
            <p className="case-study-ai__links">
              <a href={repositoryHref("docs/frontend-agent-contract.md")}>Frontend agent contract</a>
              <a href={repositoryHref("docs/modeling-agent-contract.md")}>Modeling agent contract</a>
            </p>
          </article>
          <article className="case-study-ai__card">
            <h3>What a model would be allowed to say</h3>
            <p>
              Outside the site there is a local, provider-neutral explanation toolkit. It runs
              offline by default, and that is enforced, not promised: without{" "}
              <code>--online</code> the process refuses to open a socket.
            </p>
            <ul>
              <li>Every claim must cite evidence IDs from a closed set.</li>
              <li>Every number must equal the published one, compared numerically, not as a rendered string.</li>
              <li>A feature-contribution claim may only rest on weighted evidence.</li>
              <li>A refused output is never shown: the toolkit returns a typed deterministic fallback instead.</li>
            </ul>
            <p>
              No demonstration model has been evaluated. The live gate records{" "}
              <code>not_run</code>, deliberately distinct from a pass, and this project makes no
              claim about any model&apos;s behaviour.
            </p>
            <p className="case-study-ai__links">
              <a href={repositoryHref("docs/ai-explanation-contract.md")}>Explanation contract</a>
              <a href={repositoryHref("docs/ai-eval-method.md")}>Evaluation method</a>
            </p>
          </article>
        </div>
      </section>

      <section className="case-study-engineering" aria-labelledby="engineering-heading">
        <p className="eyebrow">Engineering</p>
        <h2 id="engineering-heading">No backend. Every number comes from a file you can inspect.</h2>
        <ol className="pipeline">
          <li>
            <h3>Frozen event data</h3>
            <p>
              {`${source.title}, ${source.season}, under ${source.licence}, pinned as `}
              <code>{manifest.dataset_version}</code>.
            </p>
          </li>
          <li>
            <h3>Python pipeline</h3>
            <p>Features, retrieval and the resampled intervals, computed once from the frozen data.</p>
          </li>
          <li>
            <h3>Immutable JSON</h3>
            <p>
              {"A versioned artifact contract, "}
              <code>{`${manifest.contract}/${manifest.schema_version}`}</code>, with a manifest and the
              result artifacts.
            </p>
          </li>
          <li>
            <h3>Typed static site</h3>
            <p>A TypeScript client validates the contract fail-closed and recomputes nothing.</p>
          </li>
        </ol>
        <p className="case-study-engineering__lede">
          The site is a static export: no backend, no database, no runtime model call, and no
          third-party requests. The engineering worth pointing at is not the model. It is the
          machinery that makes a claim checkable:
        </p>
        <ul className="case-study-engineering__list">
          <li>
            <strong>Content-addressed data.</strong>{" "}
            {`${profileCount} profiles are distributed as an immutable pinned archive; a clean clone reproduces the dataset exactly, and the site cannot drift from the numbers it renders.`}
          </li>
          <li>
            <strong>A claims matrix derived from the artifact</strong>, not hand-maintained. It fails
            the build if any published conclusion lacks evidence or a caveat, or if a critical caveat
            is carried by no claim.
          </li>
          <li>
            <strong>A release candidate with a computed identity</strong> — commit, contracts, dataset
            pin, config and dependency digests — which refuses to be produced from a dirty tree.
          </li>
        </ul>
        <p className="case-study-engineering__links">
          <a href={repositoryHref("docs/architecture.md")}>Architecture</a>
          <a href={repositoryHref("docs/case-study.md")}>The full case study</a>
          <a href="https://github.com/grunobuide/scoutlens">Source</a>
        </p>
      </section>

      <ProviderBoundary manifest={manifest} research={research} competitions={story.competitions} />
    </main>
  );
}
