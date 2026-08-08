# Player Fingerprint Lab — public experience narrative and information architecture

**Specification:** 1.0.0

**Status:** frozen for implementation (product-decision record)

**Decision date:** 2026-08-06

**Tracking:** Beads `scoutlens-9a3.1` (decision); public-understanding scope of epic `scoutlens-9a3`; recorded in the decision log as D034.

## Change-control boundary

This specification is the single authority for beginner-facing product copy and
information architecture of the flagship experience until a decision-log entry
supersedes it. It constrains every later writer, frontend agent, and visual
redesign so they cannot create a second, inconsistent scientific narrative.

- **No result values in copy.** The spec quotes artifact identifiers only. Every
  headline number exists in exactly one place: the versioned showcase artifact
  fields (`public/showcase/v1/research-summary.json` experimental `metrics`,
  referenced by `metric_id`). Copy that needs a number must reference the owning
  artifact; it must never restate a constant.
- **Claims stay frozen.** A plain-language formulation must not change
  `research.supported_claim` / `research.unsupported_claims`, must not omit the
  team-context confound, and must not imply current scouting or a recruitment
  recommendation. Every claim and term below cites an existing artifact ID or
  document.
- **Stop condition.** If a formulation cannot be supported by an existing
  evidence ID, stop and request scientific review; do not resolve the conflict
  with softer or more promotional wording.

## 1. Audiences and jobs-to-be-done

### 1.1 Entry audience — the curious non-specialist

A football-analytics reader, product manager, or portfolio visitor who can read
percentiles but should not need to know MRR, cosine similarity, or the ScoutLens
codebase to understand the experience.

**Jobs-to-be-done (within 90 seconds of landing):**

1. State, in their own words, what single claim the project makes
   (answerable from `research.supported_claim`).
2. State what it does **not** claim (answerable from
   `research.unsupported_claims`).
3. Name the strongest limitation that travels with the headline (answerable
   from caveat `same_season_team_confound`).
4. Know where the data came from and that it is historic, not current
   (answerable from `manifest.source` and `manifest.dataset_version`).

The experience must not require them to read the science route first; the
landing alone must satisfy jobs 1–4 with progressive disclosure behind it.

### 1.2 Deeper-audit audience — technical hiring managers, engineers, data scientists

**Jobs-to-be-done (without reading the repository first):**

1. Audit the experimental sequence, controls, and interpretation boundary —
   `/science` stages 01–06 in frozen `narrative_steps` order.
2. Inspect the retrieval and replication method and the exact definition of
   every metric used — `/science` with links to `report_url` documents.
3. Trace the public evidence trail — provenance drawer on landing and
   `/science`: versioned manifest, research summary, feature catalog, frozen
   experiment config, result artifacts, and decision log.
4. Verify the engineering robustness claims (static export, typed contract,
   no backend/LLM dependency, quality gates) — `/science`, `web/README.md`,
   and the provenance drawer.

Both audiences share the same routes; depth is layered, not separated.

## 2. Frozen thesis

**Thesis (one plain-language sentence):**

> On the pitch, a player's actions leave a stable statistical fingerprint;
> ScoutLens shows that fingerprint can find that same player again across two
> halves of one season — and shows the limits of that evidence rather than
> hiding them.

**Boundary sentence (must always appear adjacent to the thesis, never
separated by other copy):**

> This is evidence of individual signal — not proof of playing style, not a
> recommendation, and not a prediction.

**Anchors:** `research.supported_claim`; caveat `fingerprint_not_style_proof`
("A stable event-derived fingerprint is evidence of individual signal, not
proof of playing style."); `research.unsupported_claims` (style proof;
neighbor-as-recommendation/replacement; prediction of future performance,
fitness, value, or transfer success).

**Meeting A/B wording rules.** Where a single sentence is required (opengraph,
release tagline, case-study one-liner), the thesis may be abbreviated, but the
boundary sentence must still appear within the same reading context (same
paragraph list or adjacent card). The project name is **ScoutLens**; the
experience is the **Player Fingerprint Lab**.

## 3. The 30-second explanation

Spoken-style copy usable as the landing lede, a demo script, or the case-study
opening. It follows the real experimental sequence, not a promotional one:

> ScoutLens asks one question: can a player's statistical profile identify
> them? We take public football event data from the 2017/18 season, split every
> player's play time into two chronological halves, and test whether 32 simple
> measurements of how they act can find that same player again in the second
> half. The fingerprint finds the same player far better than guessing, and the
> signal survived re-testing on an independent provider — but club continuity
> alone can make the task easier, so the controls that narrow the claim stay
> visible beside every result. The evidence ends where recommendations,
> quality ratings, or predictions would begin.

**Anchors:** `narrative_steps` (order 1–6), caveats
`same_season_team_confound` and `provider_replication_lower_magnitude`,
`unsupported_claims[2]`.

## 4. Six timed comprehension questions

Each question has a canonical answer and an evidence link. The times are targets
for a first-time reader starting from the landing hero and following in-page
progressive disclosure, matching the 90-second primary job.

| # | Time | Question | Canonical answer | Evidence |
|---|---|---|---|---|
| 1 | 10 s | What single claim is ScoutLens making? | Event-derived profiles contain a reproducible individual fingerprint that supports same-player retrieval across two chronological halves. | `research.supported_claim` |
| 2 | 15 s | What is ScoutLens **not** claiming? | It does not prove playing style, it does not treat neighbors as recommendations or replacements, and it does not predict future performance, value, fitness, or transfers. | `research.unsupported_claims` (all three) |
| 3 | 30 s | What is the strongest reason to doubt the headline? | Same-season club continuity is a strong confound: a role + team + minutes control outperforms the fingerprint on the full cohort and narrows the interpretation. | Caveat `same_season_team_confound`; experiment `wyscout_role_team_minutes`; `narrative_steps[3]` |
| 4 | 45 s | Where does the evidence come from, and how current is it? | Public Wyscout/Pappalardo 2017/18 event data, published as attributed aggregate player—competition profiles; the frozen dataset version is named by the manifest. StatsBomb contributes aggregate replication evidence only. | `manifest.source`, `manifest.dataset_version`, provenance drawer, `DATA_LICENSES.md` |
| 5 | 60 s | Was the claim reproduced independently? | Yes — an independent provider reproduced the core signal at a lower magnitude; the positive result adds confidence, the smaller size is reported, and its transfer subset is inconclusive. | `narrative_steps[5]`; experiment `statsbomb_global_replication`; caveat `provider_replication_lower_magnitude` |
| 6 | 90 s | What is a statistical neighbor, and what must it never be called? | A neighbor is the profile most similar to the selected player within a defined candidate pool — an analytical comparison, never a recommendation, replacement, or "best match". | `narrative_steps[2]` + within-role scope; caveat `fingerprint_not_style_proof`; `unsupported_claims[1]` |

The six questions double as the acceptance quiz for any redesigned landing: the
redesign is wrong if a first-time reader cannot answer all six from the landing
alone (with in-page disclosure) within 90 seconds.

## 5. Vocabulary progression (glossary)

Terms are introduced in the order below; each carries a plain definition and
forbidden shorthand. Earlier terms are assumed by later ones — a surface must
never use a term from this table before its definition has appeared in the
reading flow, on the first render of the location where the term is introduced.

| Term | Introduced at | Plain definition | Forbidden shorthand |
|---|---|---|---|
| **Fingerprint** | Landing hero + featured preview (before any metric) | A player's statistical profile that reliably reappears when the same player is re-measured later; "fingerprint" is a metaphor for consistency, not identity proof. | "style DNA"; "proof of playing style"; "unique identifier" |
| **Chronological split (period A / B)** | Landing preview + `/science` stage 01 | The season is split into two halves per player×competition unit; period A is the query (first half), period B is the candidate set (second half). | "first vs last season"; "before vs after transfer" (A/B are calendar halves, not transfer states) |
| **Candidate pool / eligible population** | Retrieval description on landing + `/lab` | The complete set of player×competition units with at least the frozen minutes threshold in both periods — the `manifest.population` count (1,257 units). A profile key names the unit (`wy-<player_id>-c-<competition_id>`), not just the human. | "shortlist"; "transfer targets"; "pool of signings"; "top prospects" |
| **Rank / reciprocal rank (MRR)** | `/science` page intro only, and only after the experiment cards | MRR measures how high the true same-player profile appears in the retrieval list on average; it is an identity-task measure, higher = better **for this task**. | "accuracy"; "success rate"; "% match"; "model win percentage" |
| **Percentile / within-role percentile** | `/lab` profile view (period A/B feature values) | Where a player's measurement sits among players of the same nominal role in the pool; a descriptive comparison, not a rating. | "FIFA-style rating"; "score out of 100"; "talent grade" |
| **Statistical neighbor** | `/lab` neighbor panel, only after the retrieval replay | The profile whose features are most similar to the selected player within the defined pool, excluding the player itself. | "best match"; "comparable signing"; "replacement"; "similar player to watch" (when implying a scouting lead) |
| **Confound** | Landing evidence band + `/science` stage 03, always beside the headline results | A factor that can make the retrieval task easier without proving the fingerprint — here club + role + minutes continuity; the experiment reports its strength so the headline stays honest. | "just noise"; "invalidates the result"; "the control beat us so there is no signal" — the true statement is "narrows the interpretation, and transferred players still show the signal with wide uncertainty" |
| **Match-resampled uncertainty** | Future uncertainty layer (`scoutlens-jtt.5`); replaces "pending" chips when available | Ranges produced by resampling whole matches inside frozen strata; they express how stable a value is under shuffled match sets. | "margin of error around a rating"; overlapping intervals must not be described as "the same" |
| **Data vintage** | First render of every surface (hero chip and provenance pin) | The exact frozen dataset and version behind every number on the page, from `manifest.dataset_version`. | bare "2017/18" without the frozen `dataset_version`; "live"; "current season" |

## 6. Route matrix and call-to-action order

Every required message has exactly one owning route and one owning surface. Any
surface that renders a headline claim must pull it from the owning artifact
field, never from a duplicated constant.

### 6.1 Navigation labels (frozen)

| Route | Label | Notes |
|---|---|---|
| `/` | **Overview** | Wordmark "ScoutLens" links here. |
| `/lab/` | **Fingerprint Lab** | Interactive evidence surface. |
| `/science` | **How it works** | URL retained; label changes from "Science" on implementation (per D034). |
| `/` (footer) | Provenance links | Audit trail lives on landing and `/science`; no separate `/about` route is added. |

### 6.2 Messages and owners

| Message | Single owner | Places it may render |
|---|---|---|
| Thesis + boundary sentence | `research.supported_claim` (+ sheltering copy in §2) | Landing hero; case study; release media |
| Claim matrix (supported / not supported) | `research.supported_claim` + `research.unsupported_claims` | Landing `ClaimsMatrix`, `/science` |
| Data vintage | `manifest.dataset_version` | Hero chip; provenance `Dataset pin` |
| Headline evidence pair | Experiments `wyscout_global_gate2` + `wyscout_role_team_minutes` | Landing evidence band, `/science` stages 02–03 |
| Confound | Caveat `same_season_team_confound` | Beside every headline evidence rendering |
| Replication + null result | `narrative_steps[5]`, `[6]` + experiments `statsbomb_global_replication`, `wyscout_ratio_shrinkage` | Landing band, `/science` stages 05–06 |
| MRR definition | Metric labels (`baseline_a_mrr`, `fingerprint_mrr`, `mrr_delta`, `median_rank`) | `/science` page intro only |
| Feature fingerprint preview | `feature-catalog.json` + featured profile | Landing `FingerprintPreview`, `/lab` profile view |
| Statistical neighbor definition | Neighbor view + caveat `fingerprint_not_style_proof` | `/lab` neighbor panel |
| Provenance chain + licences | `manifest`, `experiments[].source_artifact`, `report_url`, `DATA_LICENSES.md` | Provenance drawer (landing + `/science`) |
| Uncertainty status | `uncertainty_status` fields (future `scoutlens-jtt.5`) | `/lab` (replaces "pending" chips) |
| AI explanation | Evidence bundle per `scoutlens-jtt.6.1` | `/lab` (future, allowlisted per §8) |
| Case study | This spec §9 + future `docs/case-study.md` | Release narrative only |

### 6.3 Call-to-action order (frozen)

1. **Primary:** "Explore every fingerprint" → `/lab/` (data behavior: search).
2. **Secondary:** "How the science was checked" → `/science` ("How it works").
3. **Tertiary (footer / provenance only):** case study link when published
   (`docs/case-study.md`), licence and repository links.

The hero renders a maximum of two CTAs (primary + secondary). No CTA may imply
recruitment, comparison shopping, or "who should a club sign".

## 7. Content-order wireflows and progressive disclosure

Section order is normative per viewport; states are marked **I** = initially
visible, **E** = expandable (details/accordion), **L** = linked to the advanced
audit (`/science`, provenance, docs).

### 7.1 Landing — desktop and ≤360 px (same order, stacked on narrow)

1. **Hero** — eyebrow "Player Fingerprint Lab" · thesis (**I**) · boundary
   sentence (**I**) · data-vintage chip (**I**) · CTAs primary + secondary.
   No content above the thesis.
2. **Featured fingerprint preview** (**I**) — editorially selected profile
   (`manifest.featured_profile` with `editorial: true` and its quoted reason);
   footnote that family averages are descriptive features, not quality scores.
3. **Claim matrix** (**I**) — supported (left/top) and not supported
   (right/bottom); the unsupported list needs no expansion.
4. **Evidence band** (**I**) — headline card pair (fingerprint + team control),
   with the confound caveat chip rendered inside the cards; the "replication and
   restraint" pair below (**I**). Caveat detail is readable inline or via one
   expand step (**E**); never behind a link to another route.
5. **Provenance strip** (**I**, both cards visible) — source + licence cards;
   full audit drawer collapsed (**E**); "Dataset pin" text visible.
6. **Footer** (global) — case study link when published, repository links.

### 7.2 `/science` ("How it works") — audit surface

**I:** page intro with the MRR definition and the frozen-question block
(`narrative_steps[1]` + split definition). Stages 02–06 render in frozen order
with one experiment card grid each; every stage keeps its caveats (**I**).
Provenance drawer repeated (**E**). Any metric label on this page is the canonical
definition location for that metric (§5).

### 7.3 `/lab` — interactive evidence surface

**I:** intro heading + boundary sentence + search, role, competition, and
team-context selectors; "1,257 profiles found" status. Selected profile →
period A/B fingerprint map, retrieval replay, then statistical neighbors
(**I** after selection; direct-link friendly). Comparison drawer (**E**);
uncertainty chips are **I** on the profile header ("pending" until jtt.5.4).

### 7.4 Progressive-disclosure invariants

- The supported claim, data vintage, and the strongest limitation (confound)
  are never hidden behind an expand/link on landing or `/lab`.
- All six comprehension questions (§4) are answerable with at most in-page
  disclosure states (no route change).
- On ≤360 px: no horizontal scroll (existing gate), 44 px touch targets,
  focus travels in the order listed here, and the boundary sentence is never
  truncated.

## 8. Claims / copy matrix

The table is the allow/deny contract for every current and future copy owner.
"Anchor" names the artifact ID the copy must be consistent with.

| Topic | Allowed framing | Forbidden framing | Anchor |
|---|---|---|---|
| Benchmark | The fingerprint retrieval is compared with simple baselines and a stronger team-context control on a frozen identity-retrieval task; "higher MRR is better for this identity task". | "The model beats the baseline in general"; MRR presented as accuracy, a rating, or a betting edge. | `baseline_a_mrr`, `fingerprint_mrr`, `mrr_delta`, `wyscout_role_team_minutes` |
| Provider / licence | Wyscout/Pappalardo 2017/18 public event data, published as attributed aggregate profiles (CC BY 4.0); StatsBomb contributes aggregate replication evidence only (non-commercial, no per-player raw data). | Claiming raw StatsBomb per-player data is public; omitting attribution. | `manifest.source`, `DATA_LICENSES.md`, provenance drawer |
| Data vintage | Numbers describe only the frozen `dataset_version`; nothing is live or current. | "Live", "current season", "recent data". | `manifest.dataset_version` |
| AI explanation | Only the deterministic, evidence-bundle narration defined by `scoutlens-jtt.6.1`: every factual sentence cites evidence IDs, unknown IDs/entities are rejected, invalid output falls back to deterministic content; no repair-by-invention. | Free-form chat; AI claims without cited evidence IDs; AI restating numbers outside declared artifact formatting; AI making recommendations; AI softening caveats. | `scoutlens-jtt.6.1` evidence bundle |
| Implications (all surfaces) | Statistical similarity is evidence of individual signal with explicit limits. | Recommendation, replacement, style proof, quality/valuation, current scouting relevance, or future-performance prediction — explicitly disclaimed in `unsupported_claims` and flagship non-goals. | `unsupported_claims` (all three); caveat `fingerprint_not_style_proof`; `docs/flagship-vertical-slice.md` non-goals |
| Engineering claims | Static export, typed showcase contract, no backend, no LLM runtime dependency, deterministic contract, quality gates. | Stating engineering facts in hero copy; implying cloud/AI infrastructure exists. | `web/README.md`, provenance drawer, `docs/flagship-quality-gates.md` |

## 9. Relationship to the release case study

`docs/case-study.md` is a future release deliverable (Beads `scoutlens-jtt.7.3`).
It must consume this specification: the frozen thesis and 30-second explanation,
the glossary, and the route ownership. It may point at the same artifact
identifiers but must not introduce a second copy of any headline metric value;
numbers remain owned by artifacts, and the case study adds narrative, not data.

## 10. Dependencies for implementation

Consumers of this specification (each may start only after this spec merges):

- `scoutlens-9a3.5` — identity-challenge contract: reads §2 (thesis), §4 (six
  questions), §7 (wireflows and disclosure invariants).
- Frontend copy application (epic `scoutlens-9a3`, later child): applies the
  frozen nav label "How it works", the secondary CTA text, and the glossary
  surface rules without new CSS or results.
- `scoutlens-jtt.6` — AI narration: bounded by §8 and the `scoutlens-jtt.6.1`
  evidence-bundle contract, not by ad-hoc AI copy.
- `scoutlens-uze` children — may reuse the §7 wireflows for responsive fixtures
  but must not change narrative ownership.
- `scoutlens-jtt.7.3` — case study per §9.
