import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Fingerprint Lab",
  description: "Explore period-to-period player fingerprints with evidence attached.",
};

const contractSteps = [
  "Choose a player × competition profile",
  "Compare the first and second chronological periods",
  "Inspect the nearest statistical profiles",
  "Trace each similarity back to feature evidence",
] as const;

export default function LabPage() {
  return (
    <main id="main-content" className="shell page-shell">
      <header className="page-intro">
        <p className="eyebrow">Interactive surface</p>
        <h1>Fingerprint Lab</h1>
        <p className="lede">
          The product shell is ready. Search, comparison, and visual explanation will land here
          on top of the validated static showcase contract.
        </p>
      </header>

      <section className="lab-frame" aria-labelledby="lab-contract-heading">
        <div className="lab-frame__status">
          <span className="status-dot" aria-hidden="true" />
          Static contract connected
        </div>
        <h2 id="lab-contract-heading">The interaction contract</h2>
        <ol className="step-list">
          {contractSteps.map((step, index) => (
            <li key={step}>
              <span aria-hidden="true">{String(index + 1).padStart(2, "0")}</span>
              {step}
            </li>
          ))}
        </ol>
      </section>

      <section className="boundary-note" aria-labelledby="lab-boundary-heading">
        <h2 id="lab-boundary-heading">What this Lab will not do</h2>
        <p>
          It will not calculate research results in the browser, hide caveats, or turn similarity
          into an automated scouting verdict. The interface consumes versioned, checksummed
          artifacts produced offline.
        </p>
      </section>
    </main>
  );
}
