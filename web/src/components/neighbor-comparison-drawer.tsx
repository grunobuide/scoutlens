"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";

import type {
  Caveat,
  EvidenceItem,
} from "@/contracts/generated/showcase";
import {
  evidenceContribution,
  familyLabel,
  formatContribution,
  formatScore,
  formatZScore,
  type ContributionEvidence,
  neighborScore,
  neighborScoreLabel,
  neighborScoreQuantity,
  type AnyStatisticalNeighbor,
} from "@/content/showcase-lab";
import { explainEvidence } from "@/content/evidence-explanations";
import { QuantityGlossary, quantityTag } from "./quantity-glossary";

import { formatRank } from "./rank-format";
import type {
  AnyFeatureCatalogArtifact,
  AnyPlayerProfileArtifact,
} from "@/contracts/showcase-repository";

interface NeighborComparisonDrawerProps {
  catalog: AnyFeatureCatalogArtifact;
  profile: AnyPlayerProfileArtifact;
  neighbor: AnyStatisticalNeighbor;
  evidence: ContributionEvidence;
  candidateMinutes: number | null;
  /** Resolved by the Lab with the profile's evidence; required, never optional. */
  boundaries: { fingerprint: Caveat; recruitment: Caveat };
  onClose: () => void;
}

function evidenceInterpretation(item: EvidenceItem): string {
  if (item.interpretation === "alignment") {
    if ((item.query_global_z ?? 0) < 0 && (item.candidate_global_z ?? 0) < 0) {
      return "Alignment · both below the global mean";
    }
    return "Alignment · values point in the same direction";
  }
  if (item.interpretation === "disagreement") {
    return "Disagreement · values point in different directions";
  }
  return "Neutral contribution";
}

/**
 * The negative colour follows the sign a reader can see. A contribution below
 * display precision prints as 0.0000, and colouring it negative would say with
 * colour what the text does not (`scoutlens-uze.27`).
 */
function contributionClass(item: EvidenceItem): string | undefined {
  return formatContribution(evidenceContribution(item)).startsWith("-") ? "contribution--negative" : undefined;
}

function stabilityText(neighbor: AnyStatisticalNeighbor): string {
  const stability = neighbor.stability;
  if (stability.status === "pending") {
    return "Pending · no resampled rank interval or top-five selection rate is available yet.";
  }
  if (stability.status === "insufficient") {
    return "Insufficient resamples · no stable interval is reported.";
  }
  const interval = stability.rank_ci_95;
  const medianText = stability.median_rank === null ? "not reported" : formatRank(stability.median_rank);
  return `Available from ${stability.valid_resamples?.toLocaleString("en-US") ?? 0} valid resamples · median rank ${medianText}${interval === null ? "" : ` · rank interval ${formatRank(interval[0])}–${formatRank(interval[1])}`} · top-five selection rate ${stability.top_5_selection_rate === null ? "not reported" : `${(stability.top_5_selection_rate * 100).toFixed(1)}%`}.`;
}

export function NeighborComparisonDrawer({
  catalog,
  profile,
  neighbor,
  evidence,
  candidateMinutes,
  boundaries,
  onClose,
}: NeighborComparisonDrawerProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (dialog !== null && !dialog.open) {
      dialog.showModal();
      closeButtonRef.current?.focus();
    }
  }, []);

  // The score this drawer reconstructs, named the way its major publishes it.
  // v2's score is weighted and may not be called a cosine (D047); v1's is one.
  // Derived from the same discriminant as the value, so the two cannot drift.
  const scoreName = neighborScoreLabel(neighbor).toLowerCase();
  const scoreId = neighborScoreQuantity(neighbor);

  return (
    <dialog
      ref={dialogRef}
      className="neighbor-drawer"
      aria-labelledby="neighbor-drawer-title"
      aria-describedby="neighbor-drawer-summary"
      data-quantity-scope
      onClose={onClose}
      onKeyDown={(event) => {
        const dialog = dialogRef.current;
        if (event.key === "Tab" && dialog !== null) {
          const focusableElements = Array.from(
            dialog.querySelectorAll<HTMLElement>(
              'button:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])',
            ),
          );
          const firstElement = focusableElements[0];
          const lastElement = focusableElements.at(-1);

          if (event.shiftKey && document.activeElement === firstElement) {
            event.preventDefault();
            lastElement?.focus();
          } else if (!event.shiftKey && document.activeElement === lastElement) {
            event.preventDefault();
            firstElement?.focus();
          }
        }
        if (event.key === "Escape") {
          event.preventDefault();
          dialog?.close();
        }
      }}
    >
      <div className="neighbor-drawer__shell">
        <header className="neighbor-drawer__header">
          <div>
            <p className="eyebrow">Period A query / period B neighbor</p>
            <h2 id="neighbor-drawer-title">
              {profile.identity.display_name} / {neighbor.display_name}
            </h2>
            <p id="neighbor-drawer-summary">
              The selected query remains fixed. This drawer explains the stored additive evidence
              behind the {scoreName} for neighbor rank {neighbor.rank}.
            </p>
          </div>
          <button
            ref={closeButtonRef}
            type="button"
            className="neighbor-drawer__close"
            onClick={() => dialogRef.current?.close()}
          >
            Close comparison
          </button>
        </header>

        <section className="neighbor-drawer__score" aria-label="Stored comparison context">
          <dl>
            <div>
              <dt>{neighborScoreLabel(neighbor)}</dt>
              <dd data-quantity={quantityTag(scoreId)}>{formatScore(neighborScore(neighbor))}</dd>
            </div>
            <div><dt>Neighbor rank</dt><dd data-context="position">{neighbor.rank} of five shown</dd></div>
            <div><dt>Candidate period</dt><dd>Period B</dd></div>
            <div>
              <dt>Candidate minutes</dt>
              <dd data-context="minutes">{candidateMinutes === null ? "Unavailable" : candidateMinutes.toLocaleString("en-US")}</dd>
            </div>
          </dl>
          <p data-quantity={quantityTag("selection_stability")}>{stabilityText(neighbor)}</p>
        </section>

        <section className="neighbor-drawer__families" aria-labelledby="family-contributions-heading">
          <header>
            <p className="eyebrow">Eight-family reconstruction</p>
            <h3 id="family-contributions-heading">Where the {scoreName} comes from</h3>
            <p>
              Positive values are alignment, including low-with-low agreement. Negative values are
              disagreement, not weakness.
            </p>
          </header>
          <ol data-quantity={quantityTag("contribution")}>
            {evidence.families.map((item) => (
              <li key={item.evidence_id} data-family-contribution={item.family}>
                <span>{familyLabel(item.family)}</span>
                <strong className={contributionClass(item)}>{formatContribution(evidenceContribution(item))}</strong>
              </li>
            ))}
          </ol>
          <p className="neighbor-drawer__reconstruction">
            Family sum {formatContribution(evidence.familySum)} · stored {scoreName}{" "}
            {formatScore(neighborScore(neighbor))}
          </p>
        </section>

        <section className="neighbor-drawer__features" aria-labelledby="feature-contributions-heading">
          <header>
            <p className="eyebrow">{evidence.features.length}-feature audit</p>
            <h3 id="feature-contributions-heading">Exact additive contributions</h3>
          </header>
          <div className="neighbor-drawer__table-scroll" role="region" aria-label="Scrollable feature contribution table" tabIndex={0}>
            <table>
              <caption>
                Global z-scores used by the model and each feature contribution to the stored {scoreName}.
              </caption>
              <thead>
                <tr>
                  <th scope="col">Feature</th>
                  <th scope="col" data-quantity={quantityTag("model_z_score")}>Query A z</th>
                  <th scope="col" data-quantity={quantityTag("model_z_score")}>Neighbor B z</th>
                  <th scope="col" data-quantity={quantityTag("contribution")}>Contribution</th>
                  <th scope="col">Reading</th>
                </tr>
              </thead>
              <tbody>
                {evidence.features.map((item) => (
                  <tr key={item.evidence_id} data-feature-contribution={item.feature_id ?? undefined}>
                    <th scope="row">{explainEvidence(catalog.features, item).label}</th>
                    <td>{item.query_global_z === null ? "—" : formatZScore(item.query_global_z)}</td>
                    <td>{item.candidate_global_z === null ? "—" : formatZScore(item.candidate_global_z)}</td>
                    <td className={contributionClass(item)}>{formatContribution(evidenceContribution(item))}</td>
                    <td>{evidenceInterpretation(item)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="neighbor-drawer__reconstruction">
            Feature sum {formatContribution(evidence.featureSum)} · stored {scoreName}{" "}
            {formatScore(neighborScore(neighbor))}
          </p>
        </section>

        <QuantityGlossary ids={[scoreId, "contribution", "model_z_score", "selection_stability"]} />

        <aside className="neighbor-drawer__boundary" aria-label="Interpretation boundary">
          <p>{boundaries.fingerprint.message}</p>
          <p>{boundaries.recruitment.message}</p>
          <Link href="/science/#stage-02">Inspect the retrieval method and aggregate evidence →</Link>
        </aside>
      </div>
    </dialog>
  );
}
