"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef } from "react";

import type {
  Caveat,
  EvidenceItem,
  FeatureCatalogArtifact,
  PlayerProfileArtifact,
  StatisticalNeighbor,
} from "@/contracts/generated/showcase";
import {
  familyLabel,
  formatContribution,
  formatCosine,
  formatZScore,
  type ContributionEvidence,
} from "@/content/showcase-lab";

interface NeighborComparisonDrawerProps {
  catalog: FeatureCatalogArtifact;
  profile: PlayerProfileArtifact;
  neighbor: StatisticalNeighbor;
  evidence: ContributionEvidence;
  candidateMinutes: number | null;
  onClose: () => void;
}

function caveatFor(profile: PlayerProfileArtifact, code: string): Caveat | undefined {
  return profile.caveats.find((caveat) => caveat.code === code);
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

function stabilityText(neighbor: StatisticalNeighbor): string {
  const stability = neighbor.stability;
  if (stability.status === "pending") {
    return "Pending · no resampled rank interval or top-five selection rate is available yet.";
  }
  if (stability.status === "insufficient") {
    return "Insufficient resamples · no stable interval is reported.";
  }
  const interval = stability.rank_ci_95;
  return `Available from ${stability.valid_resamples?.toLocaleString("en-US") ?? 0} valid resamples · median rank ${stability.median_rank ?? "not reported"}${interval === null ? "" : ` · rank interval ${interval[0]}–${interval[1]}`} · top-five selection rate ${stability.top_5_selection_rate === null ? "not reported" : `${(stability.top_5_selection_rate * 100).toFixed(1)}%`}.`;
}

export function NeighborComparisonDrawer({
  catalog,
  profile,
  neighbor,
  evidence,
  candidateMinutes,
  onClose,
}: NeighborComparisonDrawerProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const featureLabels = useMemo(
    () => new Map(catalog.features.map((feature) => [feature.feature_id, feature.label])),
    [catalog],
  );

  useEffect(() => {
    const dialog = dialogRef.current;
    if (dialog !== null && !dialog.open) {
      dialog.showModal();
      closeButtonRef.current?.focus();
    }
  }, []);

  const fingerprintCaveat = caveatFor(profile, "fingerprint_not_style_proof");
  const recruitmentCaveat = caveatFor(profile, "similarity_not_recruitment");

  return (
    <dialog
      ref={dialogRef}
      className="neighbor-drawer"
      aria-labelledby="neighbor-drawer-title"
      aria-describedby="neighbor-drawer-summary"
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
              The selected query remains fixed. This drawer explains the stored additive cosine
              evidence for neighbor rank {neighbor.rank}.
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
            <div><dt>Stored cosine</dt><dd>{formatCosine(neighbor.cosine_similarity)}</dd></div>
            <div><dt>Neighbor rank</dt><dd>{neighbor.rank} of five shown</dd></div>
            <div><dt>Candidate period</dt><dd>Period B</dd></div>
            <div>
              <dt>Candidate minutes</dt>
              <dd>{candidateMinutes === null ? "Unavailable" : candidateMinutes.toLocaleString("en-US")}</dd>
            </div>
          </dl>
          <p>{stabilityText(neighbor)}</p>
        </section>

        <section className="neighbor-drawer__families" aria-labelledby="family-contributions-heading">
          <header>
            <p className="eyebrow">Eight-family reconstruction</p>
            <h3 id="family-contributions-heading">Where the cosine score comes from</h3>
            <p>
              Positive values are alignment, including low-with-low agreement. Negative values are
              disagreement, not weakness.
            </p>
          </header>
          <ol>
            {evidence.families.map((item) => (
              <li key={item.evidence_id} data-family-contribution={item.family}>
                <span>{familyLabel(item.family)}</span>
                <strong className={item.contribution < 0 ? "contribution--negative" : undefined}>
                  {formatContribution(item.contribution)}
                </strong>
              </li>
            ))}
          </ol>
          <p className="neighbor-drawer__reconstruction">
            Family sum {formatContribution(evidence.familySum)} · stored cosine {formatCosine(neighbor.cosine_similarity)}
          </p>
        </section>

        <section className="neighbor-drawer__features" aria-labelledby="feature-contributions-heading">
          <header>
            <p className="eyebrow">32-feature audit</p>
            <h3 id="feature-contributions-heading">Exact additive contributions</h3>
          </header>
          <div className="neighbor-drawer__table-scroll" role="region" aria-label="Scrollable feature contribution table" tabIndex={0}>
            <table>
              <caption>
                Global z-scores used by the model and each feature contribution to the stored cosine.
              </caption>
              <thead>
                <tr>
                  <th scope="col">Feature</th>
                  <th scope="col">Query A z</th>
                  <th scope="col">Neighbor B z</th>
                  <th scope="col">Contribution</th>
                  <th scope="col">Reading</th>
                </tr>
              </thead>
              <tbody>
                {evidence.features.map((item) => (
                  <tr key={item.evidence_id} data-feature-contribution={item.feature_id ?? undefined}>
                    <th scope="row">{featureLabels.get(item.feature_id ?? "") ?? item.feature_id}</th>
                    <td>{item.query_global_z === null ? "—" : formatZScore(item.query_global_z)}</td>
                    <td>{item.candidate_global_z === null ? "—" : formatZScore(item.candidate_global_z)}</td>
                    <td className={item.contribution < 0 ? "contribution--negative" : undefined}>
                      {formatContribution(item.contribution)}
                    </td>
                    <td>{evidenceInterpretation(item)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="neighbor-drawer__reconstruction">
            Feature sum {formatContribution(evidence.featureSum)} · stored cosine {formatCosine(neighbor.cosine_similarity)}
          </p>
        </section>

        <aside className="neighbor-drawer__boundary" aria-label="Interpretation boundary">
          <p>{fingerprintCaveat?.message}</p>
          <p>{recruitmentCaveat?.message}</p>
          <Link href="/science/#stage-02">Inspect the retrieval method and aggregate evidence →</Link>
        </aside>
      </div>
    </dialog>
  );
}
