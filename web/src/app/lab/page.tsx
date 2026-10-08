import type { Metadata } from "next";
import Link from "next/link";

import { DataVintageBadge, ProviderBoundary } from "@/components/data-provenance";
import { IdentityChallengePanel } from "@/components/identity-challenge-panel";
import { LabExplorer, LabProblemPanel } from "@/components/lab-explorer";
import { ThesisStatement } from "@/components/thesis-statement";
import { loadIdentityChallenge } from "@/content/load-identity-challenge";
import { loadShowcaseLab } from "@/content/load-showcase-lab";
import { loadShowcaseStory } from "@/content/load-showcase-story";

// `scoutlens-9a3.19`: the counts are read from the published index and
// catalog. They were retyped here, so a re-export with a different population
// would have kept describing the old one - the literal scan in
// tests/evidence-explanations.test.ts found it.
export async function generateMetadata(): Promise<Metadata> {
  const lab = await loadShowcaseLab();
  const counted =
    lab.status === "ready"
      ? `${lab.profiles.length.toLocaleString("en-US")} player profiles and compare ${lab.catalog.features.length}`
      : "player profiles and compare";
  return {
    title: "Fingerprint Lab",
    description: `Search ${counted} event-derived measurements across two chronological periods.`,
  };
}

export default async function LabPage() {
  const lab = await loadShowcaseLab();
  const story = await loadShowcaseStory();
  const challenge = await loadIdentityChallenge();

  return (
    <main id="main-content" className="shell page-shell lab-page">
      <header className="page-intro page-intro--wide lab-page-intro">
        <DataVintageBadge manifest={story.manifest} competitions={story.competitions} />
        <p className="eyebrow">Interactive evidence surface</p>
        <h1>Compare one player with himself.</h1>
        <p className="lede">
          Search every eligible player × competition profile, then inspect how the same{" "}
          {story.manifest.population.feature_count}{" "}
          event-derived measurements move between the first and second half of the season.
        </p>
        {/*
          `scoutlens-9a3.18` (D066): the same thesis and boundary as the landing
          and /science, then the artifact's supported claim and the way to the
          claims it does not support. This intro used to word a boundary of its
          own; ratings are disclaimed where they could be misread instead - the
          retrieval boundary, the neighbour caveats and the quantity explainers.
        */}
        <ThesisStatement thesisClassName="lab-page-intro__thesis" boundaryClassName="lab-page-intro__boundary" />
        <aside className="lab-page-intro__claim" aria-labelledby="lab-claim-heading">
          <p className="eyebrow" id="lab-claim-heading">Supported claim</p>
          <p data-supported-claim>{story.research.supported_claim}</p>
          <Link href="/science/#claims-heading">Where the evidence stops →</Link>
        </aside>
      </header>

      <IdentityChallengePanel data={challenge} />

      <noscript>
        <section className="lab-state lab-state--unavailable">
          <p className="eyebrow">JavaScript required for interaction</p>
          <h2>The evidence remains available</h2>
          <p>
            Enable JavaScript to search and switch profiles. The landing and scientific record
            remain fully readable without it.
          </p>
        </section>
      </noscript>

      {lab.status === "ready" ? (
        <LabExplorer
          datasetVersion={lab.datasetVersion}
          major={lab.major}
          weightedFeatureCount={lab.weightedFeatureCount}
          catalog={lab.catalog}
          profiles={lab.profiles}
          initialProfile={lab.initialProfile}
        />
      ) : (
        <LabProblemPanel problem={lab.problem} datasetVersion={lab.datasetVersion} />
      )}

      <ProviderBoundary manifest={story.manifest} research={story.research} competitions={story.competitions} />
    </main>
  );
}
