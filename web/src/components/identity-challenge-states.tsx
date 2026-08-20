"use client";

/**
 * The identity challenge state machine (`scoutlens-9a3.6.3`).
 *
 * The four interactive states from §3.1-§3.4 of
 * `docs/identity-challenge-contract.md`, the §4 transitions, and the §1 URL
 * semantics.
 *
 * **Why this is a client component at all**, and why it is statically
 * imported: `next.config.ts` sets `output: "export"`, so there is no
 * server-side `searchParams` and a query string is readable only in the
 * browser. §10 of the contract contradicts itself once a new client component
 * is needed - its *Lazy chunks* row forbids introducing one, its budget
 * invariant mandates lazy-loading it. `D052` resolves that: statically
 * imported, merged into the existing page chunk by the bundler, with the
 * 204,800-byte cap as the binding invariant, measured before and after.
 *
 * **Everything here is presentation.** Every value comes from
 * `IdentityChallengeView`, which slice 1 resolved from the artifacts, and from
 * `buildFingerprintRows`, the Lab's existing shared reader. Nothing in this
 * file ranks, sorts, sums or rescales.
 *
 * The degraded and problem cards deliberately live in the *server* component
 * that renders this one, so neither ships in the client bundle. A reader
 * without JavaScript never executes this file; a reader with it never needs
 * the degraded card.
 */

import { useCallback, useEffect, useRef, useState } from "react";

// D046: resampled rank bounds are legitimately fractional, and interpolating
// one straight into a template prints its full binary expansion - the published
// upper bound here renders as "43.524999999999998" without this.
import { formatRank } from "@/components/rank-format";

import type { IdentityChallengeView } from "@/content/identity-challenge";
import {
  formatPercentile,
  formatRawValue,
  percentileFor,
  type FingerprintRow,
} from "@/content/showcase-lab";
import type { Caveat, EvidenceItem } from "@/contracts/generated/showcase-v2";

/** The states §1's URL table names. `orientation` is the parameterless default. */
export type ChallengeState = "orientation" | "query" | "reveal" | "evidence";

const CHALLENGE_STATES: readonly ChallengeState[] = [
  "orientation",
  "query",
  "reveal",
  "evidence",
];

/**
 * The percentile scale the challenge shows.
 *
 * Fixed to `within_role`, the artifact's own
 * `cohort.default_display_percentile_scope`. The Lab offers a global/within-role
 * toggle; the challenge does not, because §3.2 hides "any metric value" beyond
 * the plot and a scale switch is a second thing to explain before the question
 * has been asked. The `within_role_display_differs_from_global_model` caveat is
 * mandatory in every state precisely because this display scale is not the
 * scale the model ranks on.
 */
const DISPLAY_SCOPE = "within_role" as const;

/**
 * The state a URL names, or the recovery state.
 *
 * Exported because the vitest environment is `node` and has no DOM, so the
 * transitions themselves are proven in Playwright. What can be proven here is
 * the pure mapping, including §8's rule that an unrecognised value recovers to
 * orientation rather than erroring.
 */
export function stateFromSearch(search: string): ChallengeState {
  const value = new URLSearchParams(search).get("challenge");
  // §8's "invalid URL state returns to the documented recovery state". An
  // unrecognised value is not an error page: orientation is the entry ramp, and
  // it changes nothing about the scientific query.
  return CHALLENGE_STATES.find((state) => state === value) ?? "orientation";
}

function updateChallengeUrl(profileKey: string, state: ChallengeState): void {
  const url = new URL(window.location.href);
  url.searchParams.set("player", profileKey);
  if (state === "orientation") {
    url.searchParams.delete("challenge");
  } else {
    url.searchParams.set("challenge", state);
  }
  // §4: "each state push a URL entry ... Back/forward navigates between
  // challenge states."
  window.history.pushState({}, "", url);
}

function clampedPercentile(value: number): number {
  return Math.min(100, Math.max(0, value));
}

/**
 * One fingerprint row, restricted to the periods the caller names.
 *
 * The Lab's own row component always draws both period marks, so reusing it in
 * the query state would render exactly the period-B fingerprint §3.2 hides.
 * The markup is therefore local; the *values* are not - percentile and raw
 * formatting come from the same shared readers the Lab uses, so the two
 * surfaces cannot drift apart numerically.
 */
function ChallengeFingerprintRow({
  row,
  showPeriodB,
}: {
  row: FingerprintRow;
  showPeriodB: boolean;
}) {
  const periodA = percentileFor(row.periodA, DISPLAY_SCOPE);
  const periodB = percentileFor(row.periodB, DISPLAY_SCOPE);
  const label = showPeriodB
    ? `${row.definition.label}: period A ${formatPercentile(periodA)}, period B ${formatPercentile(periodB)}, within-role percentile`
    : `${row.definition.label}: period A ${formatPercentile(periodA)}, within-role percentile`;

  return (
    <div
      className="challenge-fingerprint__row"
      // Not `data-fingerprint-row`: the Lab explorer below owns that name for its
      // own 32 rows, and sharing it makes any page-level query for "the
      // fingerprint rows" resolve to 64 elements from two different surfaces.
      data-challenge-fingerprint-row={row.definition.feature_id}
    >
      <span className="challenge-fingerprint__label">{row.definition.short_label}</span>
      <span
        className="challenge-fingerprint__track"
        style={
          {
            "--period-a-position": `${clampedPercentile(periodA)}%`,
            "--period-b-position": `${clampedPercentile(periodB)}%`,
          } as React.CSSProperties
        }
        role="img"
        aria-label={label}
      >
        <span className="challenge-fingerprint__mark challenge-fingerprint__mark--a" aria-hidden="true">
          A
        </span>
        {showPeriodB ? (
          <span
            className="challenge-fingerprint__mark challenge-fingerprint__mark--b"
            aria-hidden="true"
          >
            B
          </span>
        ) : null}
      </span>
      <span className="challenge-fingerprint__value" aria-hidden="true">
        {showPeriodB
          ? `${formatRawValue(row.periodA, row.definition as never)} → ${formatRawValue(row.periodB, row.definition as never)}`
          : formatRawValue(row.periodA, row.definition as never)}
      </span>
    </div>
  );
}

/**
 * The fingerprint plot, exported so the period-A restriction can be proven
 * directly rather than inferred from a state that happens to render no plot.
 */
export function ChallengeFingerprint({
  rows,
  showPeriodB,
  caption,
}: {
  rows: readonly FingerprintRow[];
  showPeriodB: boolean;
  caption: string;
}) {
  return (
    <div
      className="challenge-fingerprint"
      data-challenge-fingerprint={showPeriodB ? "ab" : "a"}
      aria-label={caption}
      role="group"
    >
      {rows.map((row) => (
        <ChallengeFingerprintRow
          key={row.definition.feature_id}
          row={row}
          showPeriodB={showPeriodB}
        />
      ))}
    </div>
  );
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

/** §3.3 and §3.4 carry the same mandatory set, plus the uncertainty caveat. */
function resultCaveats(view: IdentityChallengeView): readonly Caveat[] {
  return [
    ...caveatsFor(view, [
      "fingerprint_not_style_proof",
      "same_season_team_confound",
      "similarity_not_recruitment",
      "within_role_display_differs_from_global_model",
    ]),
    ...(view.retrieval.uncertainty.caveat === null ? [] : [view.retrieval.uncertainty.caveat]),
  ];
}

function ContributionRow({ item }: { item: EvidenceItem }) {
  return (
    <li className="challenge-contribution" data-evidence-id={item.evidence_id}>
      <span className="challenge-contribution__label">
        {item.feature_id ?? item.family}
      </span>
      <span className="challenge-contribution__family">{item.family}</span>
      <span className="challenge-contribution__interpretation">{item.interpretation}</span>
      <span className="challenge-contribution__value">
        {item.weighted_contribution.toFixed(3)}
      </span>
      <span className="challenge-contribution__weight">
        {/*
          §3.4: `feature_weight` is the authority, and a null weight is not a
          zero. Four of the 32 displayed features carry no weight entry at all;
          rendering that as 0.000 would state a fitted weight the representation
          never fitted.
        */}
        {item.feature_weight === null ? "no fitted weight" : item.feature_weight.toFixed(3)}
      </span>
    </li>
  );
}

/**
 * The §6.3 announcement for a state, verbatim.
 *
 * Pure and exported for the same reason as `stateFromSearch`: the announcement
 * text is contractual, and pinning it needs no browser. Orientation announces
 * nothing - it is the entry state, not a transition destination a reader needs
 * told about.
 */
export function challengeAnnouncement(
  view: IdentityChallengeView,
  state: ChallengeState,
): string {
  if (state === "query") {
    return "Showing the first-half fingerprint. Identity hidden.";
  }
  if (state === "reveal") {
    return (
      `Result revealed. ${view.identity.displayName}, ${view.identity.role}, ` +
      `${view.identity.competition}. Ranked ${view.retrieval.selfRank} of ` +
      `${view.retrieval.candidateCount}.`
    );
  }
  if (state === "evidence") {
    return "Showing contribution evidence.";
  }
  return "";
}

export interface IdentityChallengeStatesProps {
  view: IdentityChallengeView;
  rows: readonly FingerprintRow[];
}

export function IdentityChallengeStates({ view, rows }: IdentityChallengeStatesProps) {
  const [state, setState] = useState<ChallengeState>("orientation");
  const headingRef = useRef<HTMLHeadingElement>(null);
  // Focus moves only in response to a transition the reader caused. Without
  // this guard the first paint would steal focus on every page load, including
  // a deep link, which is a worse experience than the one §6.2 is protecting.
  const shouldFocus = useRef(false);
  const [announcement, setAnnouncement] = useState("");


  useEffect(() => {
    // §4: "Reloading a deep-linked state restores that state directly." The
    // same handler serves popstate, so back and forward move between states
    // rather than leaving the page.
    const syncFromUrl = () => {
      setState(stateFromSearch(window.location.search));
    };
    syncFromUrl();
    window.addEventListener("popstate", syncFromUrl);
    return () => window.removeEventListener("popstate", syncFromUrl);
  }, []);

  useEffect(() => {
    if (!shouldFocus.current) {
      return;
    }
    shouldFocus.current = false;
    headingRef.current?.focus();
  }, [state]);

  const goTo = useCallback(
    (next: ChallengeState) => {
      shouldFocus.current = true;
      updateChallengeUrl(view.profileKey, next);
      setState(next);
      setAnnouncement(challengeAnnouncement(view, next));
    },
    [view],
  );

  useEffect(() => {
    // §6.2: "Escape in query, reveal, or evidence returns to the orientation
    // state and focuses the orientation heading."
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && state !== "orientation") {
        goTo("orientation");
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [goTo, state]);

  const caveats = resultCaveats(view);
  const uncertainty = view.retrieval.uncertainty;

  return (
    <div className="challenge-states" data-challenge-state={state}>
      {/*
        §6.5: no animation accompanies a transition, so there is nothing for
        prefers-reduced-motion to suppress. The announcement region is polite
        and lives outside the swapped content, so replacing a state does not
        destroy the node the screen reader is reading from.

        Deliberately `aria-live` without `role="status"`. The role implies
        `aria-live="polite"`, so the pair is redundant - and the Lab explorer
        below already publishes a status region for its result count. Two status
        roles on one page make "the status" ambiguous to a screen-reader user
        and to any query that asks for it by role.
      */}
      <p className="sr-only" aria-live="polite" data-challenge-announcer>
        {announcement}
      </p>

      {state === "orientation" ? (
        <>
          <h2 className="challenge-panel__heading" ref={headingRef} tabIndex={-1}>
            {view.copy.orientationHeading}
          </h2>
          <p className="challenge-panel__body">{view.copy.orientationBody}</p>
          <p className="challenge-panel__editorial" data-challenge-editorial>
            {view.copy.orientationEditorial}
          </p>
          <CaveatList caveats={caveatsFor(view, ["fingerprint_not_style_proof"])} />
          <button
            type="button"
            className="button button--primary challenge-panel__cta"
            data-challenge-cta="query"
            onClick={() => goTo("query")}
          >
            {view.copy.orientationCta}
          </button>
        </>
      ) : null}

      {state === "query" ? (
        <>
          <h2 className="challenge-panel__heading" ref={headingRef} tabIndex={-1}>
            {view.copy.queryHeading}
          </h2>
          <p className="challenge-panel__periods">
            {view.periods.a.label} · {view.periods.a.matchCount} matches ·{" "}
            {view.periods.a.minutes} minutes
          </p>
          <p className="challenge-panel__body">{view.copy.queryBody}</p>
          <ChallengeFingerprint
            rows={rows}
            showPeriodB={false}
            caption="First-half fingerprint, 32 measurements, within-role percentile"
          />
          <CaveatList
            caveats={caveatsFor(view, [
              "fingerprint_not_style_proof",
              "within_role_display_differs_from_global_model",
            ])}
          />
          <button
            type="button"
            className="button button--primary challenge-panel__cta"
            data-challenge-cta="reveal"
            onClick={() => goTo("reveal")}
          >
            {view.copy.queryCta}
          </button>
        </>
      ) : null}

      {state === "reveal" || state === "evidence" ? (
        <>
          <h2 className="challenge-panel__heading" ref={headingRef} tabIndex={-1}>
            {state === "evidence" ? view.copy.evidenceHeading : view.copy.revealHeading}
          </h2>
          <p className="challenge-panel__identity" data-challenge-identity>
            {view.copy.revealIdentity}
          </p>
          <p className="challenge-panel__periods">
            {view.periods.b.label} · {view.periods.b.matchCount} matches ·{" "}
            {view.periods.b.minutes} minutes
          </p>

          <dl className="challenge-result">
            <div>
              <dt>Fingerprint rank</dt>
              <dd data-challenge-rank>
                {view.retrieval.selfRank} of {view.retrieval.candidateCount}
                {uncertainty.rankCi95 === null ? null : (
                  <span className="challenge-result__interval" data-challenge-interval>
                    {" "}
                    (95% resampling interval {formatRank(uncertainty.rankCi95[0])}–
                    {formatRank(uncertainty.rankCi95[1])})
                  </span>
                )}
              </dd>
            </div>
            <div>
              <dt>Role-and-minutes baseline</dt>
              <dd data-challenge-baseline>{view.retrieval.baselineSelfRank}</dd>
            </div>
            <div>
              {/*
                §3.3: labelled "Learned weighted similarity", never "cosine" -
                the published value is weighted, and a weighted metric must not
                carry a name claiming plain cosine (D047).
              */}
              <dt>Learned weighted similarity</dt>
              <dd data-challenge-similarity>
                {view.retrieval.similarityScore === null
                  ? "not published for this profile"
                  : view.retrieval.similarityScore.toFixed(3)}
              </dd>
            </div>
            <div>
              <dt>Retrieval method</dt>
              <dd data-challenge-method>{view.retrieval.method}</dd>
            </div>
            <div>
              <dt>Representation</dt>
              <dd data-challenge-representation>{view.retrieval.representationId}</dd>
            </div>
          </dl>

          {state === "reveal" ? (
            <>
              <ChallengeFingerprint
                rows={rows}
                showPeriodB
                caption="First and second half fingerprint, 32 measurements, within-role percentile"
              />
              <ul className="challenge-families" data-challenge-families>
                {view.revealFamilies.map((item) => (
                  <li key={item.evidence_id} data-evidence-id={item.evidence_id}>
                    {item.family}
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <>
              <p className="challenge-panel__body">
                Weights are fitted for {view.fittedFeatureCount} of the 32 displayed
                measurements. A fitted weight may be exactly zero, so a measurement can be
                inside the fitted set and carry no influence on the ranking.
              </p>
              <ol className="challenge-contributions" data-challenge-contributions>
                {view.featureContributions.map((item) => (
                  <ContributionRow key={item.evidence_id} item={item} />
                ))}
              </ol>
              <ul className="challenge-families" data-challenge-families>
                {view.families.map((item) => (
                  <li key={item.evidence_id} data-evidence-id={item.evidence_id}>
                    {item.family}
                  </li>
                ))}
              </ul>
            </>
          )}

          <CaveatList caveats={caveats} />

          <div className="challenge-panel__actions">
            {state === "reveal" ? (
              <button
                type="button"
                className="button button--primary challenge-panel__cta"
                data-challenge-cta="evidence"
                onClick={() => goTo("evidence")}
              >
                {view.copy.revealCtaEvidence}
              </button>
            ) : (
              <button
                type="button"
                className="button button--primary challenge-panel__cta"
                data-challenge-cta="back"
                onClick={() => goTo("reveal")}
              >
                {view.copy.evidenceCta}
              </button>
            )}
            {/*
              §5: this CTA is the one link among the CTAs, and it scrolls to the
              Lab explorer rather than navigating - the challenge is an entry
              ramp into the Lab on the same route, not a separate page.
            */}
            <a className="button button--secondary" href="#lab-explorer">
              {view.copy.revealCtaLab}
            </a>
          </div>
        </>
      ) : null}
    </div>
  );
}
