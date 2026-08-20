import type { Metadata } from "next";

import { DataVintageBadge, ProviderBoundary } from "@/components/data-provenance";
import { IdentityChallengePanel } from "@/components/identity-challenge-panel";
import { LabExplorer, LabProblemPanel } from "@/components/lab-explorer";
import { loadIdentityChallenge } from "@/content/load-identity-challenge";
import { loadShowcaseLab } from "@/content/load-showcase-lab";
import { loadShowcaseStory } from "@/content/load-showcase-story";

export const metadata: Metadata = {
  title: "Fingerprint Lab",
  description:
    "Search 1,257 player profiles and compare 32 event-derived measurements across two chronological periods.",
};

export default async function LabPage() {
  const lab = await loadShowcaseLab();
  const story = await loadShowcaseStory();
  const challenge = await loadIdentityChallenge();

  return (
    <main id="main-content" className="shell page-shell lab-page">
      <header className="page-intro page-intro--wide lab-page-intro">
        <DataVintageBadge manifest={story.manifest} />
        <p className="eyebrow">Interactive evidence surface</p>
        <h1>Compare one player with himself.</h1>
        <p className="lede">
          Search every eligible player × competition profile, then inspect how the same 32
          event-derived measurements move between the first and second half of the season.
        </p>
        <p className="lab-page-intro__boundary">
          This is a statistical fingerprint—not a quality score, style proof, recruitment ranking,
          or automated verdict.
        </p>
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

      <ProviderBoundary manifest={story.manifest} research={story.research} />
    </main>
  );
}
