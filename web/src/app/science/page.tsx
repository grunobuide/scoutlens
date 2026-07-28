import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Science",
  description: "The result, challenge, correction, replication, and null finding behind ScoutLens.",
};

const researchArc = [
  {
    marker: "01",
    title: "Question",
    body: "Can a player’s second-period identity be retrieved from their first-period event fingerprint?",
  },
  {
    marker: "02",
    title: "Result",
    body: "The 32-feature cosine baseline substantially outperformed a role-and-minutes heuristic.",
  },
  {
    marker: "03",
    title: "Challenge",
    body: "A team-aware control exposed how much same-season context can inflate identification.",
  },
  {
    marker: "04",
    title: "Replication",
    body: "The core signal reappeared in another provider and season, at a smaller magnitude.",
  },
  {
    marker: "05",
    title: "Null result",
    body: "Ratio shrinkage improved a local pathology but did not improve retrieval, so it stayed out.",
  },
] as const;

export default function SciencePage() {
  return (
    <main id="main-content" className="shell page-shell">
      <header className="page-intro page-intro--wide">
        <p className="eyebrow">Research trail</p>
        <h1>The science is the sequence, not one headline number.</h1>
        <p className="lede">
          ScoutLens documents how the interpretation narrowed as stronger tests arrived. That
          progression is the project’s main scientific asset.
        </p>
      </header>

      <section className="research-arc" aria-label="Research progression">
        {researchArc.map((step) => (
          <article className="research-step" key={step.marker}>
            <p className="research-step__marker">{step.marker}</p>
            <div>
              <h2>{step.title}</h2>
              <p>{step.body}</p>
            </div>
          </article>
        ))}
      </section>

      <aside className="boundary-note" aria-labelledby="science-boundary-heading">
        <h2 id="science-boundary-heading">Current conclusion</h2>
        <p>
          There is a robust individual signal in these event-derived profiles. Its value as style
          evidence or recruitment support remains unproven—and the public experience will say so.
        </p>
      </aside>
    </main>
  );
}
