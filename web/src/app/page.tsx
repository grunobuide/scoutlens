import Link from "next/link";

import { DataVintageBadge, ProviderBoundary } from "@/components/data-provenance";
import {
  ClaimsMatrix,
  ExperimentCard,
  FingerprintPreview,
  ProvenanceDrawer,
} from "@/components/research-story";
import { loadShowcaseStory } from "@/content/load-showcase-story";
import { formatMetric, requireMetric } from "@/content/showcase-story";

export default async function HomePage() {
  const story = await loadShowcaseStory();
  const { experiments, research } = story;
  const teamControlMrr = formatMetric(requireMetric(experiments.teamControl, "baseline_c_mrr"));
  // `scoutlens-9a3.13`: the confound is only legible next to the number it beats.
  // Both come from the same 1,257-unit Wyscout population, so the comparison is
  // like for like — the bead's stop condition forbids comparing unlike ones.
  const fingerprintMrr = formatMetric(requireMetric(experiments.global, "fingerprint_mrr"));

  return (
    <main id="main-content">
      <section className="hero shell">
        <div className="hero__copy">
          <DataVintageBadge manifest={story.manifest} />
          <p className="eyebrow">Player Fingerprint Lab</p>
          {/*
            `scoutlens-9a3.14`. The h1 is the sentence a reader repeats back, and
            it used to end at "in the shape of their actions" — no time in it at
            all. Run 1's reader gave exactly that back: "an experiment showing how
            a player can be identified by their actions in the game", graded
            PARTIAL for dropping the two periods. The lede below has always
            carried them; the headline did not, and the headline is what was
            recalled.

            The opening clause is unchanged on purpose: `check-static-output.mjs`
            asserts "A player leaves a reproducible fingerprint" and that file is
            outside this bead's ownership boundary. Extending the sentence rather
            than rewriting it keeps the change inside the boundary.
          */}
          <h1>
            A player leaves a reproducible fingerprint—and it still identifies them half a
            season later.
          </h1>
          <p className="lede">
            Yumusarái Labs tests whether event-derived profiles can retrieve the same player across two chronological halves—then exposes the controls that narrow what that result means.
          </p>
          <p className="hero__boundary">
            Evidence of individual signal. Not proof of playing style. Not a recruitment recommendation.
          </p>
          <div className="actions" aria-label="Explore Yumusarái Labs">
            <Link className="button button--primary" href="/lab/">
              Explore every fingerprint
            </Link>
            <Link className="button button--secondary" href="/science/">
              Audit the science
            </Link>
          </div>
        </div>
        <aside className="hero__signal" aria-label="Supported result">
          {/*
            The dial is a circle with `overflow: hidden`, holding text at 68% of
            its width — about thirty characters a line. The old one-sentence
            confound already nearly filled it, so `scoutlens-9a3.13`'s plain-
            language rewrite clipped "Supported claim" to "…ED CLAIM" and cut the
            evidence link off at both ends. Every automated gate stayed green;
            §4.2's "read the image" is what caught it.

            So the confound moved out of the dial rather than being squeezed back
            into one line. The circle keeps the claim it was designed around, and
            the caveat gets room directly beneath it.
          */}
          <div className="signal-dial">
            <span className="signal-orbit signal-orbit--outer" aria-hidden="true" />
            <span className="signal-orbit signal-orbit--inner" aria-hidden="true" />
            <div>
              <p className="signal-label">Supported claim</p>
              <p className="signal-copy">{research.supported_claim}</p>
            </div>
          </div>
          {/*
            This previously read "a role + team + minutes control reaches
            {teamControlMrr} MRR, so same-season context can make identity
            retrieval easier" — true, and unreadable without already knowing what
            MRR is and what the fingerprint scores. Run 1's reader came away with
            "it could be biased": they took that a limit exists, but not which
            one. The shortcut is now named in plain language before any number,
            the comparison it loses is stated rather than left for the reader to
            assemble, and the evidence is one link away.
          */}
          <div className="signal-confound">
            <p className="signal-caveat">
              <strong>Critical confound:</strong> most players stayed at the same club across both
              halves, so who they played alongside is itself a clue to who they are. A control
              given only role, team and minutes—nothing about how a player acts—identifies them
              better than the fingerprint does: {teamControlMrr} against {fingerprintMrr} MRR,
              measured the same way on the same players. That narrows what the result means; it
              does not retract it.
            </p>
            <Link className="signal-evidence" href="/science/#stage-03">
              See the team-continuity control
            </Link>
          </div>
        </aside>
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
            <ExperimentCard
              emphasis="signal"
              experiment={experiments.global}
              metricIds={["baseline_a_mrr", "fingerprint_mrr", "mrr_delta"]}
              research={research}
            />
            <ExperimentCard
              emphasis="warning"
              experiment={experiments.teamControl}
              metricIds={["baseline_c_mrr", "median_rank"]}
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
            research={research}
          />
          <ExperimentCard
            experiment={experiments.shrinkage}
            metricIds={["raw_global_mrr", "shrunk_global_mrr"]}
            research={research}
          />
        </div>
      </section>

      <div className="shell landing-provenance">
        <ProviderBoundary manifest={story.manifest} research={research} />
        <ProvenanceDrawer story={story} />
      </div>
    </main>
  );
}
