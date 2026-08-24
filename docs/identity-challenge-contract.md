# Identity Challenge Contract

**Specification:** 2.1.0

**Status:** frozen for implementation (product-decision record)

**Decision date:** 2026-08-09 (1.0.0), 2026-08-18 (2.0.0), 2026-08-24 (2.1.0)

**Tracking:** Bead `scoutlens-9a3.5` (1.0.0 decision, D039);
`scoutlens-9a3.8` (2.0.0 artifact rebinding, D051); `scoutlens-9a3.6.7`
(2.1.0 keyboard-order correction, D053); identity-challenge scope of epic
`scoutlens-9a3`.

## What 2.0.0 changes, and what it does not

**The interaction is unchanged.** Routes, placement, the four-state machine,
transitions, CTAs, keyboard and touch order, screen-reader announcements, the
no-JavaScript fallback, analytics boundary and performance allocations are
exactly as `D039` froze them. 2.0.0 supersedes **only** D039's bindings to the
`scoutlens.showcase/1.0.0` artifact, because the public dataset moved to
`2.0.0` (`D047`) and a contract that names `cosine_similarity` now names a field
that does not exist.

Every delta from 1.0.0 is enumerated in §14. Nothing else moved.

The reason the concept survives a major version change is that the challenge
never computed anything: it reveals stored outputs. When the stored outputs
changed name and meaning, the bindings had to follow, and the interaction did
not.

## Change-control boundary

This contract is the single authority for the identity-challenge interaction
until a decision-log entry supersedes it. The implementation bead
(`scoutlens-9a3.6`) contains no product-design decisions: it executes the state
machine, copy, artifact bindings, focus order, and budgets defined here.

- **No client-side computation.** Every value, rank, similarity, and evidence
  decomposition comes from the versioned showcase profile artifact. The
  challenge reveals stored outputs; it never recomputes retrieval in the
  browser.
- **No gamification.** The challenge reveals the experiment; it does not score
  the user, guess football trivia, or present a quality judgment.
- **No live LLM.** The challenge is deterministic and works without
  JavaScript. Any future AI narration layer is bounded by
  `public-experience-narrative.md` §8 and `scoutlens-jtt.6.1`.
- **Stop condition.** If current showcase artifacts cannot support the frozen
  reveal, direct link, evidence decomposition, or uncertainty state without
  browser recomputation, stop and create a narrowly scoped artifact-contract
  bead before implementation.

## 1. Route and placement

**Selected placement:** a dedicated challenge panel on `/lab/`, rendered above
the full Lab explorer, using the same page route and the same client-side
JavaScript bundle. The challenge is an entry experience that transitions into
the full Lab; it is not a separate route.

**URL semantics:**

| State | URL | Behavior |
|---|---|---|
| Orientation (default) | `/lab/` | Challenge panel visible; full Lab explorer below |
| Query (period A shown) | `/lab/?player=<key>&challenge=query` | Period A fingerprint visible, identity hidden |
| Reveal | `/lab/?player=<key>&challenge=reveal` | Full identity, self-rank, baseline, evidence |
| Degraded (no JS) | `/lab/` | Static orientation card with a link to the featured profile's full evidence in the Lab explorer |

**Rejected alternatives:**

1. Separate `/challenge` route — rejected: fragments the Lab's single-route
   model, duplicates the profile-loading path, and creates a second entry point
   that competes with the primary CTA.
2. Modal overlay on landing — rejected: traps focus, hides the evidence
   surface behind a dialog, and breaks no-JavaScript reading.
3. Landing-only inline section — rejected: the landing already carries the
   thesis, claims matrix, and provenance; adding the challenge there would
   overload the first-interpretation point and delay the CTA to the Lab.

## 2. Default and featured profile policy

**Default profile:** `manifest.featured_profile.profile_key`
(`wy-8287-c-795`, L. Modrić). The editorial selection reason
(`manifest.featured_profile.reason`) is visibly disclosed in the orientation
state: the choice is editorial, not based on retrieval rank or player quality.

**Profile switching:** after the reveal, the user may search and select any
eligible profile from the full Lab explorer below. Selecting a new profile
resets the challenge to the query state for that profile. The challenge never
presents a random profile; the user always knows which player they are
inspecting after the reveal.

**Editorial disclosure invariant:** the orientation state always renders
`manifest.featured_profile.reason` verbatim. No state may hide or paraphrase
it.

## 3. State machine

Five states. Each state lists visible fields, hidden fields, the exact
artifact owner, mandatory caveats, uncertainty behavior, and forbidden
language.

### 3.1 State: orientation

**Purpose:** introduce the question before showing any data.

**Visible:**
- The frozen question from `research.narrative_steps[0].title`
- A one-sentence orientation: "Can a player's actions identify them? We take
  the first half of their season as a query and test whether 32 measurements
  of how they act can find that same player again in the second half."
- The editorial selection reason (`manifest.featured_profile.reason`)
- The data-vintage badge (`DataVintageBadge`)
- CTA button: "See the fingerprint" → transitions to query state

**Hidden:**
- Player identity (name, team, competition)
- All metric values, ranks, and retrieval results
- Neighbor list

**Artifact owner:** `research.narrative_steps`, `manifest.featured_profile`,
`manifest.source`

**Mandatory caveats:** `fingerprint_not_style_proof`

**Uncertainty:** not shown (no metric is visible yet)

**Forbidden language:** "guess who," "quiz," "test your knowledge," "score,"
"quality," "recommend," "talent"

### 3.2 State: query

**Purpose:** show the period-A fingerprint without revealing identity.

**Visible:**
- Period-A label: "First chronological half" (from `periods.a.label`)
- Period-A match count and minutes (from `identity.period_contexts.a`)
- The 32-feature fingerprint plot for period A only (same component as the
  Lab's `FingerprintPreview`, restricted to period A marks)
- A prompt: "This is one player's first-half fingerprint. Can the same
  measurements find them again in the second half?"
- CTA button: "Reveal the result" → transitions to reveal state

**Hidden:**
- Player name, team, competition, role
- Period-B fingerprint
- Self-rank, similarity score, baseline rank
- Neighbor list
- Any metric value (MRR, percentile)

**Artifact owner:** `PlayerProfileArtifact.periods.a`,
`PlayerProfileArtifact.identity.period_contexts.a`

**Mandatory caveats:** `fingerprint_not_style_proof`,
`within_role_display_differs_from_global_model`

**Uncertainty:** not shown (no retrieval metric is visible yet)

**Forbidden language:** "guess," "match," "which player is this," "identify
the player" (the challenge asks whether the *method* finds them, not whether
the *user* can)

### 3.3 State: reveal

**Purpose:** show the retrieval result and the player's identity.

**Visible (all initially visible, no expanding required):**
- Player identity: `identity.display_name`, `identity.role`,
  `identity.competition.name`
- Period-B label, match count, and minutes
- Full A/B fingerprint plot (both periods)
- Self-rank in the global pool: `retrieval.global.self_rank` of
  `retrieval.global.candidate_count`
- Baseline comparison: `retrieval.baseline_role_minutes.self_rank` (role +
  minutes baseline rank)
- Similarity: `retrieval.global.similarity_score`, labelled
  **Learned weighted similarity**. Never labelled "cosine": the published score
  is weighted, and a weighted metric must not carry a name claiming plain
  cosine (`D047`).
- Retrieval method: `retrieval.method`, which reads
  `combined_scaler_diagonal_v1`
- Representation provenance: `retrieval.global.representation_id`, shown as
  visible provenance rather than hidden model lore. The reader can see which
  representation produced the number beside it.
- A plain-language result sentence: "The fingerprint ranked this player
  [self_rank] of [candidate_count] eligible profiles — [comparison vs
  baseline]."
- The first three contributing feature families, taken from
  `retrieval.global.evidence_refs` in **published order**, filtered to
  `kind: "family_contribution"`. The artifact already emits them ranked by each
  family's contribution to the published score; the browser takes a prefix and
  never sorts, ranks or recomputes.
- CTA: "Explore every fingerprint" → scrolls to the full Lab explorer

**Hidden:**
- Neighbor list (available in the Lab explorer below, not in the challenge)
- Per-feature contribution breakdown (available in the Lab explorer)

**Artifact owner:** `PlayerProfileArtifact.identity`,
`PlayerProfileArtifact.periods`, `PlayerProfileArtifact.retrieval`

**Mandatory caveats:** `fingerprint_not_style_proof`,
`same_season_team_confound`, `similarity_not_recruitment`, and whichever
uncertainty caveat the artifact carries - `uncertainty_sampling_only` when
intervals are available, `uncertainty_pending` when they are not. The challenge
renders the codes the profile actually publishes and never asserts a state the
artifact did not declare.

**Uncertainty behavior:** driven by `retrieval.global.uncertainty.status`, not
assumed.

| `status` | Behaviour |
|---|---|
| `available` | Render the rank alongside `rank_ci_95` from the same block, and the artifact's `uncertainty_sampling_only` caveat with its full message. |
| `insufficient` | Render the rank without an interval and the artifact-provided caveat explaining why. Do not substitute a pending message. |
| `pending` | Render the rank without an interval and the `uncertainty_pending` caveat with its full message. |

Under `scoutlens.showcase/2.0.0` the published dataset reports `available` with
design `match_bootstrap_diagonal_v1`, so intervals render. **The 1.0.0 contract
hard-coded the pending case** and told the implementation to state that
intervals "are not available in this dataset version" - which would now be
false. Any state the artifact can carry must be read from the artifact.

Intervals from the v1 `match_bootstrap_v1` design are never rendered here: they
describe the sampling stability of a different metric (`D047`).

**Forbidden language:** "matched," "correct," "score," "accuracy," "% match,"
"the model got it right" — the reveal describes a retrieval rank, not a
correct/incorrect judgment

### 3.4 State: evidence

**Purpose:** show the contribution evidence that explains *why* the
fingerprint ranked the player where it did.

**Visible:**
- Everything from the reveal state
- A contribution summary: the first five feature-level contributions resolved
  from `retrieval.global.evidence_refs` in **published order**, filtered to
  `kind: "feature_contribution"`, showing feature label, family,
  alignment/disagreement, `weighted_contribution` and `feature_weight`
- A family-level contribution bar: the `kind: "family_contribution"` items from
  the same reference list, again in published order

The artifact emits both lists ranked by each item's contribution to the score
being explained. The browser resolves references and takes a prefix. It does
not sort, does not select by recomputed absolute value, and does not derive a
score.

**Which contribution is shown.** `weighted_contribution` is the number that
explains the published `similarity_score`, and it is what the summary shows.
`contribution` is retained in the artifact as the unweighted cosine audit view;
it may be surfaced only inside the advanced audit disclosure (§3.3), clearly
labelled as the baseline view, and never as the explanation of the displayed
score. A subject's `weighted_contribution` values reconstruct its
`similarity_score` within `1e-6`; the unweighted ones do not, and presenting
them as if they did would explain the number with a different number.
- Link to the full evidence in the Lab explorer's contribution panel

**Hidden:**
- Neighbor contribution evidence (available in the Lab explorer)

**Artifact owner:** `PlayerProfileArtifact.evidence_index`, resolved through
`retrieval.global.evidence_refs`; `representation_id` on each item ties the
evidence to the representation that produced it.

**Mandatory caveats:** same as reveal state

**Uncertainty:** same as reveal state

**Fitted-weight disclosure.** The fingerprint displays **32** measurements per
period; the representation fits weights for **28** of them, and the remaining
four carry no weight entry at all. Some fitted weights are exactly zero, so a
feature can be inside the fitted set and still contribute nothing - in the
published dataset three of the 28 are zero, giving seven displayed features with
no influence on the ranking. The copy must therefore say that 28 features carry
a fitted weight, not that 28 features influence the score. `feature_weight` on
each evidence item is the authority; a feature's weight is never inferred from
its position in the list.

**Forbidden language:** "most important features," "key drivers," "what makes
this player good" — contributions explain the learned weighted similarity, not
player quality

### 3.5 State: degraded (no JavaScript)

**Purpose:** provide the core finding without interaction.

**Visible (static HTML):**
- The orientation text and editorial selection reason
- The player identity, both period labels, and the self-rank vs baseline rank
  as a static sentence: "L. Modrić's second-half profile was ranked
  [self_rank] of [candidate_count] by fingerprint similarity, versus
  [baseline_rank] by the role-and-minutes baseline."
- The data-vintage badge
- The mandatory caveats as inline text
- A link to the featured profile in the Lab explorer

**Hidden:**
- The interactive fingerprint plot (replaced by the static sentence above)
- The contribution evidence (linked, not expanded)

**Artifact owner:** same as reveal state

**Mandatory caveats:** every mandatory code the profile publishes -
`fingerprint_not_style_proof`, `same_season_team_confound`,
`similarity_not_recruitment`, `within_role_display_differs_from_global_model`
and the artifact's uncertainty caveat. The degraded state is server-rendered, so
the boundary a reader sees without JavaScript is the same one they see with it.

**Forbidden language:** same as reveal state

## 4. State transitions

```
orientation ──"See the fingerprint"──→ query
query       ──"Reveal the result"───→ reveal
reveal      ──"See the evidence"────→ evidence
evidence    ──"Back to result"──────→ reveal
any state   ──profile switch────────→ query (new profile)
any state   ──"Explore every fingerprint"──→ Lab explorer (scroll)
```

**Browser history:** each state push a URL entry (`challenge=query`,
`challenge=reveal`, `challenge=evidence`). Back/forward navigates between
challenge states. Reloading a deep-linked state restores that state directly.

**Reload/share behavior:** a deep link to `/lab/?player=<key>&challenge=reveal`
loads the reveal state for that profile without requiring the user to step
through orientation and query first. The orientation and query states are
entry ramps, not gates.

## 5. Entry and exit CTAs

| CTA | From state | Action | Element |
|---|---|---|---|
| "See the fingerprint" | orientation | → query | `<button>` |
| "Reveal the result" | query | → reveal | `<button>` |
| "See the evidence" | reveal | → evidence | `<button>` |
| "Back to result" | evidence | → reveal | `<button>` |
| "Explore every fingerprint" | any | scroll to Lab explorer | `<a href="#lab-explorer">` |

No CTA uses the words "play," "quiz," "game," "score," or "test."

## 6. Keyboard, touch, and screen-reader behavior

### 6.1 Keyboard order

**Two orders, and they are not the same thing** (`D053`, 2.1.0). Specification
1.0.0 described both with the word *Tab*, which made this section contradict
itself: it required the CTA to be the first focusable element *and* required Tab
to visit 32 informational rows that precede the CTA in the DOM. Both cannot
hold.

- **Focus order** is the sequence of *interactive controls* a Tab press moves
  through. Only elements that do something belong in it.
- **Reading order** is the sequence in which *all* content, interactive or not,
  is reached by a screen reader's browse or virtual-cursor navigation. It is the
  DOM order (§6.6).

Informational content is guaranteed in reading order. Putting it in focus order
would add stops that offer a keyboard user nothing to activate, and would push
the primary action of each state behind them.

**Orientation:** the CTA is the first focusable element in the challenge panel.
Tab then moves to the next section (Lab explorer).

**Query:** the CTA is the first focusable element. The 32 fingerprint rows are
informational graphics, not controls: each is exposed with a complete accessible
name and is reached in reading order, in the artifact's published row order.
They are not Tab stops.

**Reveal:** the identity block is read first (name, role, competition), then the
rank and baseline comparison, then the caveats — all in reading order. The CTAs
are the focusable elements.

**Evidence:** the contribution list is read after the reveal content, in
published order. Each contribution row is read as: feature label, family,
alignment or disagreement, contribution value. The rows are informational; the
CTAs are the focusable elements.

**Accessible names on fingerprint rows.** Every row names its feature and the
percentile scale, plus the period values *that its state shows*:

| State | Row accessible name carries |
|---|---|
| query | feature label, period-A percentile, scale |
| reveal, evidence | feature label, period-A percentile, period-B percentile, scale |

The query state names period A only, and that is a requirement rather than an
omission: §3.2 hides the period-B fingerprint, and a row that announced period B
would hand the answer to exactly the readers who depend on announcements while
hiding it from everyone else.

### 6.2 Focus movement

- Entering a new state moves focus to the state's heading (`<h2>`).
- After the CTA action completes, focus moves to the new state's heading.
- Escape in query, reveal, or evidence returns to the orientation state and
  focuses the orientation heading.
- Profile switch from the Lab explorer resets the challenge and focuses the
  query state heading.

### 6.3 Screen-reader announcements

Each state transition triggers an `aria-live="polite"` announcement:
- → query: "Showing the first-half fingerprint. Identity hidden."
- → reveal: "Result revealed. [display_name], [role], [competition]. Ranked
  [self_rank] of [candidate_count]."
- → evidence: "Showing contribution evidence."

### 6.4 Touch targets

All CTA buttons and interactive elements are at least 44 × 44 CSS pixels.
The fingerprint plot rows are at least 44px tall on touch devices.

### 6.5 Reduced motion

No animation accompanies state transitions. The fingerprint plot marks
appear without transition. `prefers-reduced-motion` is respected by default;
there is no motion to suppress.

### 6.6 320 px reading order

1. Data-vintage badge
2. Orientation text + editorial reason
3. State-specific content (fingerprint plot / identity + rank / evidence)
4. Mandatory caveats
5. CTA button(s)
6. Lab explorer (below)

The reading order is the DOM order; no CSS `order` is used.

## 7. No-JavaScript fallback

The `<noscript>` block on `/lab/` already states that JavaScript is required
for interaction. The challenge's no-JS fallback is the degraded state (§3.5):
a static card rendered server-side in the challenge panel position, showing
the orientation text, the featured profile's result sentence, caveats, and a
link to the profile in the Lab explorer. The interactive states (query,
reveal, evidence) are not available without JavaScript; the degraded card is
the no-JS experience.

## 8. Error states

| Condition | Behavior |
|---|---|
| Unknown profile key | Challenge panel renders: "This profile was not found in the frozen dataset." with a link back to `/lab/`. Lab explorer shows the problem panel. |
| Missing artifact (fetch/load error) | Challenge panel renders: "The evidence for this profile could not be loaded." with the dataset version pin visible. Lab explorer shows the problem panel. |
| Checksum/schema mismatch | Same as missing artifact, plus the caveat that the dataset version may have changed. Fail closed; do not render partial data. |
| Uncertainty not `available` | Render the artifact's own uncertainty caveat with its full message. Rank and similarity values are still shown; the caveat explains the missing interval. The challenge never states which uncertainty state applies - it reads `uncertainty.status`. |
| Uncertainty design is not `match_bootstrap_diagonal_v1` | Fail closed. A v1 interval describes the sampling stability of a different metric and must not be shown beside a diagonal rank. |
| `representation_id` disagrees with the manifest | Fail closed before rendering any value. A profile that cannot say which representation produced it is not renderable. |
| Loading state | Show a skeleton with the state heading and a "Loading evidence…" label. Do not show stale data from a previous profile. |

All error states preserve the data-vintage badge and the mandatory caveats.

## 9. Analytics boundary

If analytics are added in the future, they must exclude:
- search text typed in the Lab explorer;
- player identity history (the sequence of profiles viewed);
- any persistent identifier linked to a player profile.

Permitted analytics: challenge state reached (orientation/query/reveal/
evidence), CTA click count, and time-to-reveal. No analytics may transmit
a `profile_key` or `display_name`.

## 10. Performance allocation

| Budget | Allocation | Current headroom |
|---|---|---|
| Initial `/lab` JavaScript (gzip) | Challenge panel adds zero new chunks; it reuses the existing Lab page chunk and `lab-explorer.tsx` client bundle | 47,215 bytes under the 204,800-byte cap (D038) |
| Lazy chunks | The challenge does not introduce lazy-loaded components; it uses the already-loaded `LabExplorer` and `FingerprintPreview` components | No new lazy chunks |
| Initial route transfer (excluding fonts) | The challenge panel is server-rendered HTML; it adds no JavaScript to the initial transfer | 263,147 gzip bytes current (D038) |

**Budget invariant:** the challenge must not increase the `/lab` initial
JavaScript gzip total beyond the frozen 204,800-byte cap. If the challenge
implementation requires a new client component, it must be lazy-loaded outside
the initial route transfer.

## 11. Allowed artifact fields

The challenge reads only from the published `scoutlens.showcase/2.0.0`
`PlayerProfileArtifact`, `Manifest` and `RepresentationArtifact`. **No new
artifact field, schema change or contract version is required** - every field
below was verified present in the published profile `wy-8287-c-795` before this
revision was frozen (§15).

| Field | Used in state |
|---|---|
| `manifest.featured_profile.profile_key` | orientation, query, reveal, evidence |
| `manifest.featured_profile.reason` | orientation |
| `manifest.source.*` | data-vintage badge (all states) |
| `manifest.population.*` | orientation (scope context) |
| `profile.identity.display_name` | reveal, evidence, degraded |
| `profile.identity.role` | reveal, evidence, degraded |
| `profile.identity.competition.name` | reveal, evidence, degraded |
| `profile.identity.period_contexts.a/b` | query, reveal, evidence, degraded |
| `profile.periods.a/b` | query (A only), reveal, evidence (A+B) |
| `profile.retrieval.global.self_rank` | reveal, evidence, degraded |
| `profile.retrieval.global.candidate_count` | reveal, evidence, degraded |
| `profile.retrieval.global.similarity_score` | reveal, evidence |
| `profile.retrieval.global.representation_id` | reveal, evidence (provenance) |
| `profile.retrieval.global.reciprocal_rank` | not shown directly (MRR is a population metric, not per-profile) |
| `profile.retrieval.baseline_role_minutes.self_rank` | reveal, evidence, degraded |
| `profile.retrieval.method` | reveal |
| `profile.retrieval.global.evidence_refs` | evidence |
| `profile.evidence_index` | evidence (resolved through `evidence_refs`, published order) |
| `evidence item .weighted_contribution` | evidence (the explanation of the shown score) |
| `evidence item .feature_weight` | evidence (fitted-weight disclosure) |
| `evidence item .contribution` | advanced audit disclosure only, labelled as the cosine baseline view |
| `evidence item .representation_id` | evidence (ties evidence to its representation) |
| `representation.json` `representation.feature_count` | evidence (the 28-of-32 disclosure) |
| `profile.caveats` | all states (filtered by mandatory set) |
| `profile.uncertainty` | reveal, evidence, degraded |

## 12. Event and copy names

All copy is frozen here; the implementation bead renders it verbatim.

| State | Element | Copy |
|---|---|---|
| orientation | heading | "Can a player's actions identify them?" |
| orientation | body | "We take the first half of their season as a query and test whether 32 measurements of how they act can find that same player again in the second half." |
| orientation | editorial | `manifest.featured_profile.reason` (rendered verbatim) |
| orientation | CTA | "See the fingerprint" |
| query | heading | "One player's first-half fingerprint" |
| query | body | "This is one player's first-half fingerprint. Can the same measurements find them again in the second half?" |
| query | CTA | "Reveal the result" |
| reveal | heading | "The fingerprint found them at rank [self_rank] of [candidate_count]." |
| reveal | identity | "[display_name] · [role] · [competition.name]" |
| reveal | baseline | "A role-and-minutes baseline ranked them [baseline_rank]." |
| reveal | CTA evidence | "See the evidence" |
| reveal | CTA lab | "Explore every fingerprint" |
| evidence | heading | "What drove the match" |
| evidence | CTA | "Back to result" |
| degraded | heading | "Can a player's actions identify them?" |
| degraded | result | "[display_name]'s second-half profile was ranked [self_rank] of [candidate_count] by fingerprint similarity, versus [baseline_rank] by the role-and-minutes baseline." |

## 13. Dependencies that unblock implementation

- `scoutlens-9a3.5` (this contract) — closed
- `scoutlens-9a3.1` (narrative spec) — closed
- `scoutlens-9a3.2` (explanation catalog) — closed
- `scoutlens-9a3.3` (data provenance component) — closed
- `scoutlens-uze.4` (responsive baseline) — closed
- `scoutlens-jtt.5.4` (render uncertainty in Lab) — closed; the published
  dataset reports `available`, so the challenge renders the interval from
  `retrieval.global.uncertainty.rank_ci_95` and the artifact's
  `uncertainty_sampling_only` caveat. The pending path remains specified in
  §3.3 because the contract reads the status rather than assuming it
- `scoutlens-jtt.14` (JavaScript headroom) — closed

## 14. Deltas from specification 1.0.0

Every change 2.0.0 makes, and nothing else. Each is forced by the move to
`scoutlens.showcase/2.0.0`; none changes the interaction.

| # | 1.0.0 | 2.0.0 | Why |
|---|---|---|---|
| 1 | `retrieval.global.cosine_similarity` | `retrieval.global.similarity_score`, labelled **Learned weighted similarity** | The field was renamed because a weighted metric must not be published under a name claiming plain cosine (`D047`). The 1.0.0 binding now names a field that does not exist. |
| 2 | `retrieval.method` shown as-is | unchanged binding; the value now reads `combined_scaler_diagonal_v1` | `D049`. The field is rendered verbatim, so the contract states the expected value. |
| 3 | no representation shown | `representation_id` visible at reveal and evidence | A ranking that cannot be traced to the metric that produced it is not auditable. Provenance, not model lore. |
| 4 | "sorted by absolute contribution, top 3 / top 5" | resolve `evidence_refs` in published order and take a prefix | The artifact already ranks by each item's contribution to the published score. Browser-side sorting would re-derive an order the producer owns, and in v2 would rank by the wrong field. |
| 5 | contributions explain "the cosine similarity" | `weighted_contribution` explains `similarity_score`; `contribution` is the audit view, advanced disclosure only | The two answer different questions. Only the weighted values reconstruct the shown score, within `1e-6`. |
| 6 | mandatory caveat list included `uncertainty_pending` | the artifact's own uncertainty caveat, whichever it publishes | `uncertainty_pending` does not exist in the published v2 profiles; requiring it would fail closed on a valid dataset. |
| 7 | "sampling-stability intervals are not available in this dataset version" | behaviour table driven by `uncertainty.status` | The 1.0.0 sentence is now false: the published dataset reports `available` with `match_bootstrap_diagonal_v1`. |
| 8 | no fitted-weight disclosure | 32 displayed measurements, 28 carrying a fitted weight | The reader is shown 32 features and told the ranking uses a learned subset; without the distinction the two counts silently disagree. |
| 9 | error table had no lineage rows | fail closed on a non-diagonal uncertainty design or a mismatched `representation_id` | Both are refusals the consumer already enforces; the contract states them so the implementation does not invent softer behaviour. |
| 10 | typo `revidence_index` | `evidence_index` | A binding nobody could implement as written. |

**Unchanged:** route and placement (§1), featured-profile policy (§2), the four
states and their purposes (§3), transitions (§4), CTAs (§5), keyboard, touch,
focus and screen-reader behaviour (§6), the no-JavaScript fallback (§7),
analytics boundary (§9), performance allocation (§10), event and copy names
(§12), the no-client-computation, no-gamification and no-live-LLM boundaries,
and every forbidden-language list.

## 15. Field audit

Run against the published dataset before freezing this revision, so the
contract binds fields that exist rather than fields that ought to.

Profile `wy-8287-c-795`, dataset `wyscout-2017-18-v2-dc398ff5661c`,
representation `rep-f018e6041ccbad10`:

| Checked | Result |
|---|---|
| `retrieval.method` | `combined_scaler_diagonal_v1` |
| `retrieval.global.similarity_score` | present; `cosine_similarity` absent |
| `retrieval.global.representation_id` | `rep-f018e6041ccbad10` |
| `retrieval.global.uncertainty.status` | `available`, `rank_ci_95` present |
| top-level `uncertainty.design_version` | `match_bootstrap_diagonal_v1` |
| `retrieval.global.evidence_refs` | resolves to 32 feature + 8 family items, all `subject: self_retrieval` |
| published order | already descending by `|weighted_contribution|`, for both lists |
| evidence item fields | `weighted_contribution`, `feature_weight`, `representation_id`, `contribution` all present |
| caveat codes | `fingerprint_not_style_proof`, `same_season_team_confound`, `similarity_not_recruitment`, `uncertainty_sampling_only`, `within_role_display_differs_from_global_model` — **no `uncertainty_pending`** |
| fingerprint features per period | 32 |
| representation `feature_count` | 28; four catalog features carry no weight entry, and three fitted weights are exactly zero |

No schema change, no artifact change and no new scientific field is required.
The one correction the audit forced is delta 6: the 1.0.0 mandatory-caveat list
named a code the published dataset does not carry.
