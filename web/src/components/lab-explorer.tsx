"use client";

import Link from "next/link";
import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
} from "react";

import type {
  Caveat,
  FeatureValue,
  PeriodContext,
} from "@/contracts/generated/showcase";
import { formatRank, formatRankBound } from "./rank-format";
import {
  EMPTY_PROFILE_FILTERS,
  buildFingerprintRows,
  buildFingerprintSummary,
  buildProfileEvidence,
  buildProfileFilterOptions,
  describeLabError,
  filterProfiles,
  formatPercentile,
  formatContribution,
  formatCosine,
  formatRawValue,
  formatSupport,
  formatZScore,
  groupFingerprintRows,
  percentileFor,
  profileHref,
  profileTeamNames,
  familyLabel,
  type FingerprintRow,
  type LabProblem,
  type NeighborEvidence,
  type PercentileScope,
  type ProfileFilters,
  neighborScore,
  retrievalScore,
  type AnyRetrievalOutcome,
} from "@/content/showcase-lab";
import type {
  AnyFeatureCatalogArtifact,
  AnyPlayerIndexItem,
  AnyPlayerProfileArtifact,
  ShowcaseMajor,
} from "@/contracts/showcase-repository";

const NeighborComparisonDrawer = lazy(() =>
  import("@/components/neighbor-comparison-drawer").then((module) => ({
    default: module.NeighborComparisonDrawer,
  })),
);

const PAGE_SIZE = 18;
const requiredCaveats = new Set([
  "fingerprint_not_style_proof",
  "same_season_team_confound",
  "within_role_display_differs_from_global_model",
  "uncertainty_pending",
  "uncertainty_sampling_only",
]);

/**
 * What the retrieval score is called, per contract major.
 *
 * v2 must not present its weighted score under a label claiming plain cosine
 * (D047). The label is chosen from the major the page was built against, not
 * from which field happens to be present on a payload, so a mislabelled score
 * is impossible rather than merely unlikely.
 */
const SCORE_LABEL_BY_MAJOR: Record<ShowcaseMajor, string> = {
  1: "Cosine",
  2: "Similarity score",
};

type ProfileLoadState =
  | { status: "ready"; profile: AnyPlayerProfileArtifact }
  | { status: "loading"; profileKey: string }
  | { status: "problem"; profileKey: string; problem: LabProblem };

interface LabExplorerProps {
  datasetVersion: string;
  /** The contract major the page was built against. Presentation reads the
   * score field and the method disclosure from it rather than sniffing which
   * key happens to be present on a payload. */
  major: ShowcaseMajor;
  catalog: AnyFeatureCatalogArtifact;
  profiles: ReadonlyArray<AnyPlayerIndexItem>;
  initialProfile: AnyPlayerProfileArtifact;
}

function updateProfileUrl(profileKey: string, mode: "push" | "replace"): void {
  const url = new URL(window.location.href);
  url.searchParams.set("player", profileKey);
  window.history[mode === "push" ? "pushState" : "replaceState"]({}, "", url);
}

function problemForUnknownProfile(profileKey: string): LabProblem {
  return {
    kind: "unknown-profile",
    eyebrow: "Profile unavailable",
    title: "That profile is not in this dataset version",
    message: `The key ${profileKey} is absent from the catalog. Choose another player and it will be replaced in the URL.`,
    canRetry: false,
  };
}

export function LabExplorer({
  datasetVersion,
  major,
  catalog,
  profiles,
  initialProfile,
}: LabExplorerProps) {
  const [filters, setFilters] = useState<ProfileFilters>(EMPTY_PROFILE_FILTERS);
  const [visibleLimit, setVisibleLimit] = useState(PAGE_SIZE);
  const [loadState, setLoadState] = useState<ProfileLoadState>({
    status: "ready",
    profile: initialProfile,
  });
  const requestSequence = useRef(0);

  const options = useMemo(() => buildProfileFilterOptions(profiles), [profiles]);
  const filteredProfiles = useMemo(() => filterProfiles(profiles, filters), [filters, profiles]);
  const visibleProfiles = filteredProfiles.slice(0, visibleLimit);
  const hasActiveFilters = Object.values(filters).some((value) => value !== "");
  const activeProfileKey =
    loadState.status === "ready" ? loadState.profile.profile_key : loadState.profileKey;
  const isLoading = loadState.status === "loading";
  const activeFilterLabels = [
    filters.query === "" ? null : `Search: “${filters.query}”`,
    filters.role === "" ? null : `Role: ${filters.role}`,
    filters.competition === "" ? null : `Competition: ${filters.competition}`,
    filters.team === "" ? null : `Team: ${filters.team}`,
  ].filter((label): label is string => label !== null);

  const loadProfile = useCallback(
    async (profileKey: string, historyMode: "push" | "replace" | "none") => {
      const request = ++requestSequence.current;
      const indexItem = profiles.find((profile) => profile.profile_key === profileKey);
      if (indexItem === undefined) {
        setLoadState({
          status: "problem",
          profileKey,
          problem: problemForUnknownProfile(profileKey),
        });
        return;
      }

      if (profileKey === initialProfile.profile_key) {
        setLoadState({ status: "ready", profile: initialProfile });
        if (historyMode !== "none") {
          updateProfileUrl(profileKey, historyMode);
        }
        return;
      }

      setLoadState({ status: "loading", profileKey });
      try {
        const { StaticShowcaseRepository } = await import("@/contracts/showcase-repository");
        const repository = new StaticShowcaseRepository();
        const profile = await repository.getProfile(profileKey);
        if (request !== requestSequence.current) {
          return;
        }
        setLoadState({ status: "ready", profile });
        if (historyMode !== "none") {
          updateProfileUrl(profileKey, historyMode);
        }
      } catch (error) {
        if (request !== requestSequence.current) {
          return;
        }
        setLoadState({ status: "problem", profileKey, problem: describeLabError(error) });
      }
    },
    [initialProfile, profiles],
  );

  useEffect(() => {
    const syncFromUrl = () => {
      const profileKey = new URLSearchParams(window.location.search).get("player");
      if (profileKey === null || profileKey === "") {
        setLoadState({ status: "ready", profile: initialProfile });
        return;
      }
      void loadProfile(profileKey, "none");
    };

    syncFromUrl();
    window.addEventListener("popstate", syncFromUrl);
    return () => window.removeEventListener("popstate", syncFromUrl);
  }, [initialProfile, loadProfile]);

  const updateFilter = (key: keyof ProfileFilters, value: string) => {
    setFilters((current) => ({ ...current, [key]: value }));
    setVisibleLimit(PAGE_SIZE);
  };

  const resetFilters = () => {
    setFilters(EMPTY_PROFILE_FILTERS);
    setVisibleLimit(PAGE_SIZE);
  };

  return (
    <>
      <section className="lab-selector" aria-labelledby="player-selector-heading">
        <header className="lab-section-heading">
          <div>
            <p className="eyebrow">Complete eligible catalog</p>
            <h2 id="player-selector-heading">Choose a player × competition profile</h2>
          </div>
          <p>
            {profiles.length.toLocaleString("en-US")} profiles · 2017/18 · at least 450 minutes in
            each chronological period
          </p>
        </header>

        <fieldset className="lab-filter-fieldset" disabled={isLoading} aria-busy={isLoading}>
          <legend className="sr-only">Search and filter player profiles</legend>
          <div className="lab-filter-grid">
            <label className="lab-control lab-control--search">
              <span>Search players</span>
              <input
                type="search"
                value={filters.query}
                placeholder="Try Modrić, midfielder, Madrid…"
                autoComplete="off"
                onChange={(event) => updateFilter("query", event.target.value)}
              />
            </label>
            <label className="lab-control">
              <span>Role</span>
              <select
                value={filters.role}
                onChange={(event) => updateFilter("role", event.target.value)}
              >
                <option value="">All roles</option>
                {options.roles.map((role) => (
                  <option key={role}>{role}</option>
                ))}
              </select>
            </label>
            <label className="lab-control">
              <span>Competition</span>
              <select
                value={filters.competition}
                onChange={(event) => updateFilter("competition", event.target.value)}
              >
                <option value="">All competitions</option>
                {options.competitions.map((competition) => (
                  <option key={competition}>{competition}</option>
                ))}
              </select>
            </label>
            <label className="lab-control">
              <span>Team context</span>
              <select
                value={filters.team}
                onChange={(event) => updateFilter("team", event.target.value)}
              >
                <option value="">All teams</option>
                {options.teams.map((team) => (
                  <option key={team}>{team}</option>
                ))}
              </select>
            </label>
          </div>
        </fieldset>

        <div className="lab-results-toolbar">
          <p role="status" aria-live="polite">
            <strong>{filteredProfiles.length.toLocaleString("en-US")}</strong>{" "}
            {filteredProfiles.length === 1 ? "profile" : "profiles"} found
          </p>
          <button type="button" className="text-button" onClick={resetFilters} disabled={!hasActiveFilters}>
            Reset filters
          </button>
        </div>

        {filteredProfiles.length === 0 ? (
          <div className="lab-empty-state">
            <p className="eyebrow">No silent broadening</p>
            <h3>No profiles match all active filters</h3>
            <p>Change one filter or reset the full selection explicitly.</p>
            <ul className="lab-active-filters" aria-label="Active filters">
              {activeFilterLabels.map((label) => <li key={label}>{label}</li>)}
            </ul>
            <button type="button" className="button button--dark" onClick={resetFilters}>
              Reset all filters
            </button>
          </div>
        ) : (
          <>
            <ul className="profile-results" aria-label="Matching player profiles">
              {visibleProfiles.map((profile) => {
                const isActive = profile.profile_key === activeProfileKey;
                return (
                  <li key={profile.profile_key}>
                    <button
                      type="button"
                      className={`profile-result${isActive ? " profile-result--active" : ""}`}
                      aria-current={isActive ? "true" : undefined}
                      onClick={() => void loadProfile(profile.profile_key, "push")}
                    >
                      <span>
                        <strong>{profile.display_name}</strong>
                        <small>
                          {profile.role} · {profile.competition.name}
                        </small>
                      </span>
                      <span>{profileTeamNames(profile).join(" / ")}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
            {visibleProfiles.length < filteredProfiles.length ? (
              <button
                type="button"
                className="button button--ghost lab-show-more"
                onClick={() => setVisibleLimit((current) => current + PAGE_SIZE)}
              >
                Show {Math.min(PAGE_SIZE, filteredProfiles.length - visibleProfiles.length)} more
              </button>
            ) : null}
          </>
        )}
      </section>

      <section className="lab-profile-region" aria-live="polite" aria-busy={isLoading}>
        {loadState.status === "loading" ? <LabLoadingState /> : null}
        {loadState.status === "problem" ? (
          <LabProblemPanel
            problem={loadState.problem}
            datasetVersion={datasetVersion}
            onRetry={
              loadState.problem.canRetry
                ? () => void loadProfile(loadState.profileKey, "none")
                : undefined
            }
          />
        ) : null}
        {loadState.status === "ready" ? (
          <FingerprintProfile
            major={major}
            key={loadState.profile.profile_key}
            catalog={catalog}
            profiles={profiles}
            profile={loadState.profile}
          />
        ) : null}
      </section>
    </>
  );
}

export function LabLoadingState() {
  return (
    <div className="lab-state lab-state--loading" role="status">
      <p className="eyebrow">Verifying selected profile</p>
      <h2>Loading checksummed evidence…</h2>
      <div className="lab-skeleton" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
      <p>Controls are paused until the profile schema and manifest checksum agree.</p>
    </div>
  );
}

interface LabProblemPanelProps {
  problem: LabProblem;
  datasetVersion: string | null;
  onRetry?: () => void;
}

export function LabProblemPanel({ problem, datasetVersion, onRetry }: LabProblemPanelProps) {
  return (
    <div className={`lab-state lab-state--${problem.kind}`} role="alert">
      <p className="eyebrow">{problem.eyebrow}</p>
      <h2>{problem.title}</h2>
      <p>{problem.message}</p>
      <p className="lab-dataset-version">
        Dataset: <code>{datasetVersion ?? "manifest unavailable"}</code>
      </p>
      <div className="button-row">
        {onRetry === undefined ? null : (
          <button type="button" className="button button--dark" onClick={onRetry}>
            Retry verified data
          </button>
        )}
        <Link className="button button--ghost" href="/science/">
          Inspect the science
        </Link>
      </div>
    </div>
  );
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${value}T00:00:00Z`));
}

function PeriodCard({ label, context, dateStart, dateEnd }: {
  label: string;
  context: PeriodContext;
  dateStart: string;
  dateEnd: string;
}) {
  return (
    <article className="period-context-card">
      <p className="period-context-card__label">{label}</p>
      <p>{formatDate(dateStart)} — {formatDate(dateEnd)}</p>
      <p>{context.minutes.toLocaleString("en-US")} minutes · {context.match_count} matches</p>
      <ul>
        {context.teams.map((team) => (
          <li key={team.id}>
            <strong>{team.name}</strong>
            <span>{team.minutes.toLocaleString("en-US")} min</span>
          </li>
        ))}
      </ul>
    </article>
  );
}

function clampedPercentile(value: number): number {
  return Math.min(100, Math.max(0, value));
}

function FingerprintMapRow({ row, scope }: { row: FingerprintRow; scope: PercentileScope }) {
  const periodA = percentileFor(row.periodA, scope);
  const periodB = percentileFor(row.periodB, scope);
  const style = {
    "--period-a-position": `${clampedPercentile(periodA)}%`,
    "--period-b-position": `${clampedPercentile(periodB)}%`,
  } as CSSProperties;
  const scale = scope === "within_role" ? "within-role" : "global";

  return (
    <div className="lab-fingerprint-row" data-fingerprint-row={row.definition.feature_id}>
      <div className="lab-fingerprint-row__label">
        <strong>{row.definition.short_label}</strong>
        <span>{formatRawValue(row.periodA, row.definition)} → {formatRawValue(row.periodB, row.definition)}</span>
      </div>
      <div
        className="lab-fingerprint-track"
        style={style}
        role="img"
        aria-label={`${row.definition.label}: period A ${formatPercentile(periodA)}, period B ${formatPercentile(periodB)}, ${scale} percentile`}
      >
        <span className="lab-fingerprint-mark lab-fingerprint-mark--a" aria-hidden="true">A</span>
        <span className="lab-fingerprint-mark lab-fingerprint-mark--b" aria-hidden="true">B</span>
      </div>
      <p className="lab-fingerprint-row__values" aria-hidden="true">
        <span>A {formatPercentile(periodA)}</span>
        <span>B {formatPercentile(periodB)}</span>
      </p>
    </div>
  );
}

function modelEvidence(value: FeatureValue): string {
  return value.imputed_for_model
    ? `${formatZScore(value.global_z_score)} · mean-imputed to z=0`
    : formatZScore(value.global_z_score);
}

function caveatFor(profile: AnyPlayerProfileArtifact, code: string): Caveat | undefined {
  return profile.caveats.find((caveat) => caveat.code === code);
}

const UNCERTAINTY_METHOD_URL =
  "https://github.com/grunobuide/scoutlens/blob/main/docs/uncertainty-method.md";

function uncertaintyHeading(status: string): string {
  if (status === "available") {
    return "Point estimates · sampling stability available";
  }
  if (status === "insufficient") {
    return "Point estimates · insufficient resamples";
  }
  return "Point estimates · uncertainty pending";
}

function featureUncertaintyCell(value: FeatureValue): string {
  const block = value.uncertainty;
  if (block.status === "pending") {
    return "Stability pending";
  }
  if (block.status === "insufficient") {
    return `Insufficient · ${block.valid_resamples} valid`;
  }
  const interval = block.raw_ci_95;
  const intervalText =
    interval === null
      ? ""
      : ` · raw CI ${interval[0].toFixed(2)}–${interval[1].toFixed(2)}`;
  return `${block.valid_resamples} valid${intervalText}`;
}

type RetrievalOutcome = AnyPlayerProfileArtifact["retrieval"]["global"];

function rankStabilityText(outcome: RetrievalOutcome): string {
  if (outcome.uncertainty.status === "pending") {
    return "Stability pending · no resampled rank interval is available yet.";
  }
  if (outcome.uncertainty.status === "insufficient") {
    return "Insufficient resamples · no stable rank interval is reported.";
  }
  const interval = outcome.uncertainty.rank_ci_95;
  const recall = [
    outcome.uncertainty.recall_at_1_rate,
    outcome.uncertainty.recall_at_5_rate,
    outcome.uncertainty.recall_at_10_rate,
  ];
  const recallText = recall.every((rate) => rate !== null)
    ? ` · recall@1 ${(recall[0]! * 100).toFixed(1)}% · recall@5 ${(recall[1]! * 100).toFixed(1)}% · recall@10 ${(recall[2]! * 100).toFixed(1)}%`
    : "";
  const medianRank = outcome.uncertainty.median_rank;
  const medianText = medianRank === null ? "not reported" : formatRank(medianRank);
  return `Available from ${outcome.uncertainty.valid_resamples?.toLocaleString("en-US") ?? 0} valid resamples · median rank ${medianText}${interval === null ? "" : ` · rank interval ${formatRank(interval[0])}–${formatRank(interval[1])}`}${recallText}.`;
}

function RetrievalOutcomeCard({
  label,
  detail,
  outcome,
  scoreLabel,
}: {
  label: string;
  detail: string;
  outcome: AnyRetrievalOutcome;
  scoreLabel: string;
}) {
  const score = retrievalScore(outcome);
  return (
    <article className="retrieval-outcome" data-retrieval-scope={label.toLowerCase().replaceAll(" ", "-")}>
      <header>
        <p>{label}</p>
        <span>{detail}</span>
      </header>
      <p className="retrieval-outcome__rank">
        Rank {outcome.self_rank}
        <span>of {outcome.candidate_count.toLocaleString("en-US")}</span>
      </p>
      <dl>
        <div><dt>Reciprocal rank</dt><dd>{outcome.reciprocal_rank.toFixed(4)}</dd></div>
        <div>
          <dt>{scoreLabel}</dt>
          <dd>{score === null ? "Not used" : formatCosine(score)}</dd>
        </div>
      </dl>
      <p className="retrieval-outcome__stability">{rankStabilityText(outcome)}</p>
    </article>
  );
}

function RetrievalReplay({ profile, scoreLabel }: { profile: AnyPlayerProfileArtifact; scoreLabel: string }) {
  const teamConfound = caveatFor(profile, "same_season_team_confound");
  return (
    <section className="retrieval-replay" aria-labelledby="retrieval-replay-heading">
      <header className="lab-narrative-heading">
        <div>
          <p className="eyebrow">Stored experiment replay</p>
          <h2 id="retrieval-replay-heading">Identity retrieval, one query at a time</h2>
        </div>
        <p>
          Period A is the query. The experiment asks where the same player × competition unit
          appears in the eligible period-B pool.
        </p>
      </header>

      <div className="retrieval-period-line" aria-label="Retrieval direction">
        <span>Query · period {profile.retrieval.query_period.toUpperCase()}</span>
        <i aria-hidden="true">→</i>
        <span>Candidate pool · period {profile.retrieval.candidate_period.toUpperCase()}</span>
        <code>{profile.retrieval.method}</code>
      </div>

      <div className="retrieval-outcome-grid">
        <RetrievalOutcomeCard
          label="Global"
          detail="All eligible profiles"
          outcome={profile.retrieval.global}
          scoreLabel={scoreLabel}
        />
        <RetrievalOutcomeCard
          label="Within role"
          detail={`Only ${profile.identity.role.toLowerCase()} profiles`}
          outcome={profile.retrieval.within_role}
          scoreLabel={scoreLabel}
        />
        <RetrievalOutcomeCard
          label="Role + minutes baseline"
          detail="Context-only control"
          outcome={profile.retrieval.baseline_role_minutes}
          scoreLabel={scoreLabel}
        />
      </div>

      <aside className="retrieval-boundary" aria-label="Identity retrieval interpretation boundary">
        <div>
          <strong>The rank is an identity-test result, not a player rating.</strong>
          <p>{teamConfound?.message}</p>
        </div>
        <Link href="/science/#stage-02">How the aggregate retrieval test was computed →</Link>
      </aside>
    </section>
  );
}

function StatisticalNeighbors({
  catalog,
  profile,
  profilesByKey,
  neighbors,
}: {
  catalog: AnyFeatureCatalogArtifact;
  profile: AnyPlayerProfileArtifact;
  profilesByKey: ReadonlyMap<string, AnyPlayerIndexItem>;
  neighbors: ReadonlyArray<NeighborEvidence>;
}) {
  const [selected, setSelected] = useState<NeighborEvidence | null>(null);
  const returnFocus = useRef<HTMLButtonElement | null>(null);
  const featureLabels = useMemo(
    () => new Map(catalog.features.map((feature) => [feature.feature_id, feature.short_label])),
    [catalog],
  );
  const fingerprintCaveat = caveatFor(profile, "fingerprint_not_style_proof");
  const recruitmentCaveat = caveatFor(profile, "similarity_not_recruitment");

  const closeComparison = () => {
    setSelected(null);
    window.setTimeout(() => returnFocus.current?.focus(), 0);
  };

  return (
    <section className="statistical-neighbors" aria-labelledby="statistical-neighbors-heading">
      <header className="lab-narrative-heading">
        <div>
          <p className="eyebrow">Self-excluded exploration</p>
          <h2 id="statistical-neighbors-heading">Five other period-B profiles</h2>
        </div>
        <p>
          These are the stored nearest profiles within the same nominal role after every profile
          belonging to the query player is excluded.
        </p>
      </header>

      <div className="neighbor-boundaries">
        <p>{fingerprintCaveat?.message}</p>
        <p>{recruitmentCaveat?.message}</p>
      </div>

      <ol className="neighbor-grid">
        {neighbors.map(({ neighbor, evidence }) => {
          const indexItem = profilesByKey.get(neighbor.profile_key);
          const alignments = evidence.families.filter((item) => item.contribution > 0).slice(0, 2);
          const disagreement = evidence.features.find((item) => item.contribution < 0);
          const titleId = `neighbor-${neighbor.rank}-title`;
          return (
            <li key={neighbor.profile_key}>
              <article className="neighbor-card" data-neighbor-rank={neighbor.rank}>
                <header>
                  <span className="neighbor-card__rank">{String(neighbor.rank).padStart(2, "0")}</span>
                  <div>
                    <h3 id={titleId}>{neighbor.display_name}</h3>
                    <p>{neighbor.role} · {neighbor.competition.name}</p>
                  </div>
                </header>
                <dl className="neighbor-card__context">
                  <div><dt>Stored cosine</dt><dd>{formatCosine(neighborScore(neighbor))}</dd></div>
                  <div>
                    <dt>Period-B minutes</dt>
                    <dd>{indexItem?.period_contexts.b.minutes.toLocaleString("en-US") ?? "Unavailable"}</dd>
                  </div>
                    <div><dt>Team context</dt><dd>{neighbor.teams.map((team) => team.name).join(" / ")}</dd></div>
                </dl>
                <div className="neighbor-card__evidence">
                  <p>Largest family alignments</p>
                  <ul>
                    {alignments.map((item) => (
                      <li key={item.evidence_id}>
                        <span>{familyLabel(item.family)}</span>
                        <strong>{formatContribution(item.contribution)}</strong>
                      </li>
                    ))}
                  </ul>
                  <p>
                    Strongest disagreement · {disagreement === undefined
                      ? "none stored"
                      : `${featureLabels.get(disagreement.feature_id ?? "") ?? disagreement.feature_id} ${formatContribution(disagreement.contribution)}`}
                  </p>
                </div>
                <p className="neighbor-card__stability">
                  Selection stability · {neighbor.stability.status === "pending" ? "pending, no interval" : neighbor.stability.status === "insufficient" ? "insufficient resamples" : `available · rank interval ${formatRankBound(neighbor.stability.rank_ci_95?.[0])}–${formatRankBound(neighbor.stability.rank_ci_95?.[1])}`}
                </p>
                <button
                  type="button"
                  aria-haspopup="dialog"
                  aria-describedby={titleId}
                  onClick={(event) => {
                    returnFocus.current = event.currentTarget;
                    setSelected({ neighbor, evidence });
                  }}
                >
                  Open evidence comparison
                </button>
              </article>
            </li>
          );
        })}
      </ol>

      {selected === null ? null : (
        <Suspense fallback={<p className="neighbor-drawer-loading" role="status">Preparing exact contribution evidence…</p>}>
          <NeighborComparisonDrawer
            catalog={catalog}
            profile={profile}
            neighbor={selected.neighbor}
            evidence={selected.evidence}
            candidateMinutes={profilesByKey.get(selected.neighbor.profile_key)?.period_contexts.b.minutes ?? null}
            onClose={closeComparison}
          />
        </Suspense>
      )}
    </section>
  );
}

export function FingerprintProfile({ catalog, profiles, profile, major }: {
  major: ShowcaseMajor;
  catalog: AnyFeatureCatalogArtifact;
  profiles: ReadonlyArray<AnyPlayerIndexItem>;
  profile: AnyPlayerProfileArtifact;
}) {
  const scoreLabel = SCORE_LABEL_BY_MAJOR[major];
  const [scope, setScope] = useState<PercentileScope>("within_role");
  const fingerprint = useMemo(() => {
    try {
      const rows = buildFingerprintRows(catalog, profile);
      const evidence = buildProfileEvidence(catalog, profile);
      const profilesByKey = new Map(profiles.map((item) => [item.profile_key, item]));
      for (const { neighbor } of evidence.neighbors) {
        const indexItem = profilesByKey.get(neighbor.profile_key);
        if (
          indexItem === undefined ||
          indexItem.player_key !== neighbor.player_key ||
          indexItem.role !== neighbor.role
        ) {
          throw new Error(`Neighbor ${neighbor.profile_key} does not resolve to the catalog`);
        }
      }
      return {
        rows,
        families: groupFingerprintRows(rows),
        evidence,
        profilesByKey,
        problem: null,
      };
    } catch (error) {
      return {
        rows: [],
        families: [],
        evidence: null,
        profilesByKey: new Map<string, AnyPlayerIndexItem>(),
        problem: describeLabError(error),
      };
    }
  }, [catalog, profile, profiles]);

  if (fingerprint.problem !== null) {
    return <LabProblemPanel problem={fingerprint.problem} datasetVersion={profile.dataset_version} />;
  }

  const visibleCaveats = profile.caveats.filter((caveat) => requiredCaveats.has(caveat.code));
  const uncertainty = caveatFor(profile, "uncertainty_pending")?.message ?? profile.uncertainty.warning;

  return (
    <article className="selected-profile" id="selected-profile">
      <header className="selected-profile__header">
        <div>
          <p className="eyebrow">Selected player × competition</p>
          <h2>{profile.identity.display_name}</h2>
          <p className="selected-profile__identity">
            {profile.identity.role} · {profile.identity.competition.name} · {profile.identity.season}
          </p>
        </div>
        <a className="profile-permalink" href={profileHref(profile.profile_key)}>
          Share this profile
        </a>
      </header>

      <div className="period-context-grid" aria-label="Chronological period contexts">
        <PeriodCard
          label={`Period A · ${profile.periods.a.label}`}
          context={profile.identity.period_contexts.a}
          dateStart={profile.periods.a.date_start}
          dateEnd={profile.periods.a.date_end}
        />
        <PeriodCard
          label={`Period B · ${profile.periods.b.label}`}
          context={profile.identity.period_contexts.b}
          dateStart={profile.periods.b.date_start}
          dateEnd={profile.periods.b.date_end}
        />
      </div>

      <div className="lab-analysis-grid">
        <section className="fingerprint-lab-card" aria-labelledby="fingerprint-map-heading">
          <header className="fingerprint-lab-card__header">
            <div>
              <p className="eyebrow">32-feature map</p>
              <h2 id="fingerprint-map-heading">Period A / B fingerprint</h2>
            </div>
            <fieldset className="percentile-toggle">
              <legend>Percentile scale</legend>
              <label>
                <input
                  type="radio"
                  name="percentile-scope"
                  value="within_role"
                  checked={scope === "within_role"}
                  onChange={() => setScope("within_role")}
                />
                Within role
              </label>
              <label>
                <input
                  type="radio"
                  name="percentile-scope"
                  value="global"
                  checked={scope === "global"}
                  onChange={() => setScope("global")}
                />
                Global
              </label>
            </fieldset>
          </header>

          <p className="fingerprint-summary">{buildFingerprintSummary(fingerprint.rows, scope)}</p>
          <div className="lab-fingerprint-legend" aria-hidden="true">
            <span><i className="legend-mark legend-mark--a" /> Period A</span>
            <span><i className="legend-mark legend-mark--b" /> Period B</span>
            <span>0 — percentile — 100</span>
          </div>

          <div className="lab-fingerprint-map">
            {fingerprint.families.map((family) => (
              <section className="lab-feature-family" key={family.family}>
                <h3>{family.label} <span>{family.rows.length} features</span></h3>
                {family.rows.map((row) => (
                  <FingerprintMapRow key={row.definition.feature_id} row={row} scope={scope} />
                ))}
              </section>
            ))}
          </div>
        </section>

        <aside className="lab-evidence-rail" aria-labelledby="evidence-rail-heading">
          <p className="eyebrow">Read before interpreting</p>
          <h2 id="evidence-rail-heading">Evidence boundaries</h2>
          <div className="uncertainty-pending">
            <strong>{uncertaintyHeading(profile.uncertainty.status)}</strong>
            <p>{uncertainty}</p>
            <a href={UNCERTAINTY_METHOD_URL}>Match-bootstrap method</a>
          </div>
          <ul>
            {visibleCaveats.map((caveat) => (
              <li key={caveat.code}>
                <span>{caveat.severity}</span>
                <p>{caveat.message}</p>
              </li>
            ))}
          </ul>
          <Link href="/science/">How the evidence was computed →</Link>
        </aside>
      </div>

      <RetrievalReplay profile={profile} scoreLabel={scoreLabel} />
      <StatisticalNeighbors
        catalog={catalog}
        profile={profile}
        profilesByKey={fingerprint.profilesByKey}
        neighbors={fingerprint.evidence!.neighbors}
      />

      <section className="fingerprint-table-section" aria-labelledby="fingerprint-table-heading">
        <header>
          <div>
            <p className="eyebrow">Equivalent value view</p>
            <h2 id="fingerprint-table-heading">All 32 measurements</h2>
          </div>
          <p>Raw values are descriptive. Global z-scores are the model inputs; percentiles are display context.</p>
        </header>
        <div className="fingerprint-table-scroll" role="region" aria-label="Scrollable 32-feature value table" tabIndex={0}>
          <table className="fingerprint-value-table">
            <caption>
              Period A and period B raw values, displayed percentiles, model z-scores, support and uncertainty.
            </caption>
            <thead>
              <tr>
                <th scope="col">Feature</th>
                <th scope="col">A raw</th>
                <th scope="col">B raw</th>
                <th scope="col">A {scope === "within_role" ? "role" : "global"} pct.</th>
                <th scope="col">B {scope === "within_role" ? "role" : "global"} pct.</th>
                <th scope="col">A global z</th>
                <th scope="col">B global z</th>
                <th scope="col">A support</th>
                <th scope="col">B support</th>
                <th scope="col">Uncertainty</th>
              </tr>
            </thead>
            {fingerprint.families.map((family) => (
              <tbody key={family.family}>
                <tr className="fingerprint-table-family">
                  <th scope="rowgroup" colSpan={10}>{family.label}</th>
                </tr>
                {family.rows.map((row) => (
                  <tr key={row.definition.feature_id}>
                    <th scope="row">
                      {row.definition.label}
                      <small>{row.definition.description}</small>
                    </th>
                    <td>{formatRawValue(row.periodA, row.definition)}</td>
                    <td>{formatRawValue(row.periodB, row.definition)}</td>
                    <td>{formatPercentile(percentileFor(row.periodA, scope))}</td>
                    <td>{formatPercentile(percentileFor(row.periodB, scope))}</td>
                    <td>{modelEvidence(row.periodA)}</td>
                    <td>{modelEvidence(row.periodB)}</td>
                    <td>{formatSupport(row.periodA)}</td>
                    <td>{formatSupport(row.periodB)}</td>
                    <td>A {featureUncertaintyCell(row.periodA)} · B {featureUncertaintyCell(row.periodB)}</td>
                  </tr>
                ))}
              </tbody>
            ))}
          </table>
        </div>
      </section>
    </article>
  );
}
