import Link from "next/link";

import { DataVintageBadge } from "@/components/data-provenance";
import { MetricGlossary, QuantityGlossary, metricTag, quantityTag } from "@/components/quantity-glossary";
import { ThesisStatement } from "@/components/thesis-statement";
import type { loadShowcaseStory } from "@/content/load-showcase-story";
import { formatMetric, requireMetric } from "@/content/showcase-story";

type LandingStory = Awaited<ReturnType<typeof loadShowcaseStory>>;

/** Where a rank sits on the 1…candidate-count strip, as a CSS offset. */
function stripPosition(rank: number, candidateCount: number): string {
  return `${((rank - 1) / Math.max(candidateCount - 1, 1)) * 100}%`;
}

/**
 * The landing hero (`scoutlens-rdz.8`, D075, D076).
 *
 * Above the thesis sit only the data-vintage chip, the eyebrow, the h1 and one
 * line naming both halves of the season (narrative §7.1 item 1). The h1 is a
 * question; the line under it keeps the two periods that `scoutlens-9a3.14`
 * put into the headline after run 1's reader dropped them.
 *
 * `featureCount` is the length of `feature-catalog.json` `features`, read when
 * the page is built (D075). It is never typed here.
 */
export function LandingHero({ story, featureCount }: { story: LandingStory; featureCount: number }) {
  const { experiments, featuredProfile, manifest, research } = story;
  const teamControl = { experiment: experiments.teamControl, metric: requireMetric(experiments.teamControl, "baseline_c_mrr") };
  const teamControlMrr = formatMetric(teamControl.metric);
  // `scoutlens-9a3.13`: the confound is only legible next to the number it beats.
  // Both come from the same 1,257-unit Wyscout population, so the comparison is
  // like for like — the bead's stop condition forbids comparing unlike ones.
  const fingerprint = { experiment: experiments.global, metric: requireMetric(experiments.global, "fingerprint_mrr") };
  const fingerprintMrr = formatMetric(fingerprint.metric);

  // D076: the card's ranks are the featured profile's, read from its artifact.
  // The profile is `manifest.featured_profile`, chosen "not based on retrieval
  // rank", and is never swapped for one that ranks better.
  const search = featuredProfile.retrieval.global;
  const guess = featuredProfile.retrieval.baseline_role_minutes;

  return (
    <section className="hero shell">
      <div className="hero__copy">
        <DataVintageBadge manifest={manifest} competitions={story.competitions} />
        <p className="eyebrow">Player Fingerprint Lab</p>
        {/*
          D075: the question the owner chose. One template string, so the
          served HTML carries the sentence as one run of text, which is what
          `check-static-output.mjs` matches.
        */}
        <h1>{`Can ${featureCount} numbers recognise a footballer?`}</h1>
        {/*
          `scoutlens-9a3.14`: run 1's reader repeated the old h1 back without
          its two periods. The question carries none, so this line, directly
          under it, names both halves (D075). The season is the manifest's.
        */}
        <p className="hero__halves">
          {`The test: given only the first half of a player's ${manifest.source.season} season, find that same player in the second half.`}
        </p>
        <ThesisStatement thesisClassName="lede" boundaryClassName="hero__boundary" />
        {/* Narrative §6.3, frozen: these two labels, in this order (D075). */}
        <div className="actions" aria-label="Explore Yumusarái Labs">
          <Link className="button button--primary" href="/lab/">
            Explore every fingerprint
          </Link>
          <Link className="button button--secondary" href="/science/">
            How the science was checked
          </Link>
        </div>
      </div>
      <aside className="hero__signal" aria-label="Supported result">
        {/*
          D076: the proof card opens the aside. One profile's rank is the most
          anecdotal number on the landing, so the supported claim and the
          confound follow it in the same aside, and its two ranks are explained
          inside the card.
        */}
        <section className="proof-card" aria-labelledby="proof-card-name" data-quantity-scope>
          <p className="proof-card__eyebrow">One real example</p>
          <h2 className="proof-card__name" id="proof-card-name">
            {story.featuredName}
          </h2>
          {/* Who and when - context, not a result (`scoutlens-9a3.32`). */}
          <p className="proof-card__context" data-context="identity">
            {story.featuredTeam} · {featuredProfile.identity.role} · {featuredProfile.identity.season}
          </p>
          <dl className="proof-card__ranks">
            <div className="proof-card__rank proof-card__rank--search">
              <dt>Fingerprint search</dt>
              <dd data-quantity={quantityTag("self_rank")}>
                <strong>{`#${search.self_rank}`}</strong>
                <span>{`out of ${search.candidate_count.toLocaleString("en-US")}`}</span>
              </dd>
            </div>
            <div className="proof-card__rank proof-card__rank--guess">
              <dt>Role-and-minutes guess</dt>
              <dd data-quantity={quantityTag("baseline_self_rank")}>
                <strong>{`#${guess.self_rank}`}</strong>
                <span>{`out of ${guess.candidate_count.toLocaleString("en-US")}`}</span>
              </dd>
            </div>
          </dl>
          {/*
            The two ranks again, as positions on one strip. Decorative: the
            ranks above are the text, and this adds no value of its own.
          */}
          <div className="proof-card__strip" aria-hidden="true">
            <span
              className="proof-card__marker proof-card__marker--guess"
              style={{ left: stripPosition(guess.self_rank, guess.candidate_count) }}
            />
            <span
              className="proof-card__marker proof-card__marker--search"
              style={{ left: stripPosition(search.self_rank, search.candidate_count) }}
            />
          </div>
          <p className="proof-card__scale" data-context="count" aria-hidden="true">
            <span>First</span>
            <span>{`All ${search.candidate_count.toLocaleString("en-US")} second-half profiles`}</span>
            <span>Last</span>
          </p>
          <p className="proof-card__reason">{manifest.featured_profile.reason}</p>
          <QuantityGlossary ids={["self_rank", "baseline_self_rank"]} />
        </section>
        <div className="hero-claim">
          <p className="signal-label">Supported claim</p>
          <p className="signal-copy" data-supported-claim>
            {research.supported_claim}
          </p>
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

          `scoutlens-9a3.32`: the hero quotes two metrics before anything on
          the page has said what MRR is - the experiment cards that explain
          them are further down. Each value carries its tag, and the two
          explanations are one disclosure away, here.
        */}
        <div className="signal-confound" data-quantity-scope>
          <p className="signal-caveat">
            <strong>Critical confound:</strong> most players stayed at the same club across both
            halves, so who they played alongside is itself a clue to who they are. A control
            given only role, team and minutes—nothing about how a player acts—identifies them
            better than the fingerprint does:{" "}
            <span data-metric={metricTag(teamControl)}>{teamControlMrr}</span> against{" "}
            <span data-metric={metricTag(fingerprint)}>{fingerprintMrr}</span> MRR, measured the
            same way on the same players. That narrows what the result means; it does not
            retract it.
          </p>
          <MetricGlossary items={[teamControl, fingerprint]} />
          <Link className="signal-evidence" href="/science/#stage-03">
            See the team-continuity control
          </Link>
        </div>
      </aside>
    </section>
  );
}
