import Link from "next/link";

const proofPoints = [
  {
    value: "1,257",
    label: "eligible player × competition profiles",
    note: "Wyscout 2017/18 public event data",
  },
  {
    value: "0.2539",
    label: "fingerprint mean reciprocal rank",
    note: "versus 0.0256 for the simple baseline",
  },
  {
    value: "2 providers",
    label: "independent event-data sources",
    note: "the signal replicated at lower magnitude",
  },
] as const;

export default function HomePage() {
  return (
    <main id="main-content">
      <section className="hero shell">
        <div className="hero__copy">
          <p className="eyebrow">Player Fingerprint Lab</p>
          <h1>Can a player be recognized by the shape of their actions?</h1>
          <p className="lede">
            ScoutLens turns a completed statistical spike into an inspectable portfolio product:
            stable event-derived fingerprints, honest controls, external replication, and evidence
            attached to every similarity.
          </p>
          <div className="actions" aria-label="Explore ScoutLens">
            <Link className="button button--primary" href="/lab/">
              Enter the Lab
            </Link>
            <Link className="button button--secondary" href="/science/">
              Read the evidence
            </Link>
          </div>
        </div>
        <aside className="hero__signal" aria-label="Project position">
          <span className="signal-orbit signal-orbit--outer" aria-hidden="true" />
          <span className="signal-orbit signal-orbit--inner" aria-hidden="true" />
          <div>
            <p className="signal-label">Supported claim</p>
            <p className="signal-copy">
              Event-derived profiles contain a temporally stable individual signal worth
              investigating.
            </p>
          </div>
        </aside>
      </section>

      <section className="proof-band" aria-labelledby="evidence-heading">
        <div className="shell">
          <div className="section-heading">
            <p className="eyebrow">Evidence at a glance</p>
            <h2 id="evidence-heading">A result that survived harder questions</h2>
          </div>
          <div className="metric-grid">
            {proofPoints.map((point) => (
              <article className="metric-card" key={point.value}>
                <p className="metric-card__value">{point.value}</p>
                <h3>{point.label}</h3>
                <p>{point.note}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="principle shell" aria-labelledby="boundary-heading">
        <div>
          <p className="eyebrow">The trust boundary</p>
          <h2 id="boundary-heading">Interesting evidence, deliberately narrow claims.</h2>
        </div>
        <p>
          Similarity is not a recruitment recommendation, and a fingerprint is not proof of
          playing style. ScoutLens keeps those distinctions visible while making the statistical
          evidence explorable.
        </p>
      </section>
    </main>
  );
}
