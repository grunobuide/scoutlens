/**
 * The identity challenge panel, orientation and degraded states
 * (`scoutlens-9a3.6.2`).
 *
 * This is a **server component on purpose**, and the purpose is a budget. §10
 * of `docs/identity-challenge-contract.md` allocates the challenge *zero* new
 * initial JavaScript: it may reuse the Lab's existing client bundle, but it may
 * not add one. Orientation and degraded are pure presentation over values the
 * selector already resolved, so they cost nothing at runtime - and building
 * them first means the explanatory content and the no-JavaScript backbone exist
 * before any interactivity does, rather than being retrofitted onto it.
 *
 * Nothing here reads an artifact. Every value arrives through
 * `IdentityChallengeView`, and every sentence that is not a value is frozen
 * copy from §12, rendered verbatim.
 *
 * The interactive states (query, reveal, evidence) arrive in
 * `scoutlens-9a3.6.3`. Until then the orientation CTA is a plain link to the
 * URL §1 documents for the query state; it navigates, and slice 3 gives that
 * URL its meaning. It is deliberately a real `<a>` rather than a button that
 * does nothing: a link that goes to the documented place is honest at every
 * stage of the build, and it is what keeps the flow reachable without
 * JavaScript once slice 3 reads the parameter.
 */

import Link from "next/link";

import type { IdentityChallengeData } from "@/content/load-identity-challenge";
import type { IdentityChallengeView } from "@/content/identity-challenge";
import type { Caveat } from "@/contracts/generated/showcase-v2";
import { profileHref } from "@/content/showcase-lab";

/**
 * Caveats the degraded state must show, in the order §3.5 lists them.
 *
 * The uncertainty caveat is appended from the view rather than named here,
 * because which one applies is the artifact's statement, not ours.
 */
const DEGRADED_CAVEAT_ORDER = [
  "fingerprint_not_style_proof",
  "same_season_team_confound",
  "similarity_not_recruitment",
  "within_role_display_differs_from_global_model",
] as const;

function caveatsFor(view: IdentityChallengeView, codes: readonly string[]): readonly Caveat[] {
  const byCode = new Map<string, Caveat>(view.caveats.map((caveat) => [caveat.code, caveat]));
  const selected: Caveat[] = [];
  for (const code of codes) {
    const caveat = byCode.get(code);
    if (caveat !== undefined) {
      selected.push(caveat);
    }
  }
  return selected;
}

function CaveatList({ caveats }: { caveats: readonly Caveat[] }) {
  return (
    <ul className="challenge-panel__caveats">
      {caveats.map((caveat) => (
        <li key={caveat.code} data-caveat={caveat.code}>
          {caveat.message}
        </li>
      ))}
    </ul>
  );
}

/**
 * The no-JavaScript experience (§3.5, §7).
 *
 * Server-rendered inside `<noscript>`, so a reader without JavaScript gets the
 * finding itself - identity, both period labels, the result sentence, every
 * mandatory caveat, and a link into the full evidence - rather than an
 * invitation to enable JavaScript. §3.5 is explicit that the boundary a reader
 * sees without JavaScript is the same one they see with it, which is why the
 * caveats are repeated here in full rather than summarised.
 */
function DegradedCard({ view }: { view: IdentityChallengeView }) {
  const caveats = [
    ...caveatsFor(view, DEGRADED_CAVEAT_ORDER),
    ...(view.retrieval.uncertainty.caveat === null ? [] : [view.retrieval.uncertainty.caveat]),
  ];

  return (
    <div className="challenge-panel__degraded" data-challenge-degraded>
      <h3>{view.copy.degradedHeading}</h3>
      <p className="challenge-panel__identity">{view.copy.revealIdentity}</p>
      <p className="challenge-panel__periods">
        <span>{view.periods.a.label}</span>
        <span aria-hidden="true"> · </span>
        <span>{view.periods.b.label}</span>
      </p>
      <p className="challenge-panel__result" data-challenge-result>
        {view.copy.degradedResult}
      </p>
      <CaveatList caveats={caveats} />
      <Link className="button button--secondary" href={profileHref(view.profileKey)}>
        {view.copy.revealCtaLab}
      </Link>
    </div>
  );
}

function ProblemCard({ data }: { data: Extract<IdentityChallengeData, { status: "error" }> }) {
  return (
    <section
      className="challenge-panel challenge-panel--problem"
      aria-labelledby="challenge-problem-heading"
      data-challenge-panel="error"
    >
      <p className="eyebrow">{data.problem.eyebrow}</p>
      <h2 id="challenge-problem-heading">{data.problem.title}</h2>
      <p>{data.problem.message}</p>
      {data.datasetVersion === null ? null : (
        <p className="challenge-panel__pin">
          Dataset pin: <code>{data.datasetVersion}</code>
        </p>
      )}
    </section>
  );
}

export interface IdentityChallengePanelProps {
  data: IdentityChallengeData;
}

export function IdentityChallengePanel({ data }: IdentityChallengePanelProps) {
  if (data.status === "error") {
    return <ProblemCard data={data} />;
  }

  const { view } = data;
  const orientationCaveats = caveatsFor(view, ["fingerprint_not_style_proof"]);

  return (
    <section
      className="challenge-panel"
      aria-labelledby="challenge-heading"
      data-challenge-panel="orientation"
    >
      <p className="eyebrow">{view.copy.orientationQuestion}</p>
      <h2 id="challenge-heading">{view.copy.orientationHeading}</h2>
      <p className="challenge-panel__body">{view.copy.orientationBody}</p>

      {/*
        §2's editorial disclosure invariant: this reason is always rendered
        verbatim, never hidden or paraphrased. The featured profile is an
        editorial choice, and a reader is entitled to know that before they see
        a rank - otherwise the selection reads as a result.
      */}
      <p className="challenge-panel__editorial" data-challenge-editorial>
        {view.copy.orientationEditorial}
      </p>

      <CaveatList caveats={orientationCaveats} />

      <Link
        className="button button--primary challenge-panel__cta"
        href={`${profileHref(view.profileKey)}&challenge=query`}
        data-challenge-cta="query"
      >
        {view.copy.orientationCta}
      </Link>

      <noscript>
        <DegradedCard view={view} />
      </noscript>
    </section>
  );
}
