# Identity Challenge Contract

**Specification:** 1.0.0

**Status:** frozen for implementation (product-decision record)

**Decision date:** 2026-08-09

**Tracking:** Bead `scoutlens-9a3.5` (decision); identity-challenge scope of epic
`scoutlens-9a3`; recorded in the decision log as D039.

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
- Self-rank, cosine similarity, baseline rank
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
- Cosine similarity: `retrieval.global.cosine_similarity`
- Retrieval method: `retrieval.method`
- A plain-language result sentence: "The fingerprint ranked this player
  [self_rank] of [candidate_count] eligible profiles — [comparison vs
  baseline]."
- Top-3 contributing feature families (from `retrieval.global.evidence_refs`,
  filtered to `kind: "family_contribution"`, sorted by absolute contribution,
  top 3)
- CTA: "Explore every fingerprint" → scrolls to the full Lab explorer

**Hidden:**
- Neighbor list (available in the Lab explorer below, not in the challenge)
- Per-feature contribution breakdown (available in the Lab explorer)

**Artifact owner:** `PlayerProfileArtifact.identity`,
`PlayerProfileArtifact.periods`, `PlayerProfileArtifact.retrieval`

**Mandatory caveats:** `fingerprint_not_style_proof`,
`same_season_team_confound`, `uncertainty_pending`

**Uncertainty behavior:** the `uncertainty_pending` caveat is rendered with
its full message. The rank figure is accompanied by the text "sampling-
stability intervals are not available in this dataset version" from the
caveat message. When `uncertainty.status` changes from `"pending"` in a future
dataset version, the rank figure is accompanied by the interval from
`retrieval.global.uncertainty.rank_ci_95` instead.

**Forbidden language:** "matched," "correct," "score," "accuracy," "% match,"
"the model got it right" — the reveal describes a retrieval rank, not a
correct/incorrect judgment

### 3.4 State: evidence

**Purpose:** show the contribution evidence that explains *why* the
fingerprint ranked the player where it did.

**Visible:**
- Everything from the reveal state
- A contribution summary: top-5 feature-level contributions (from
  `revidence_index`, filtered to `kind: "feature_contribution"`, sorted by
  absolute contribution, top 5), showing feature label, family, alignment/
  disagreement, and contribution value
- A family-level contribution bar (from `evidence_index`, filtered to
  `kind: "family_contribution"`, sorted by absolute contribution)
- Link to the full evidence in the Lab explorer's contribution panel

**Hidden:**
- Neighbor contribution evidence (available in the Lab explorer)

**Artifact owner:** `PlayerProfileArtifact.evidence_index`

**Mandatory caveats:** same as reveal state

**Uncertainty:** same as reveal state

**Forbidden language:** "most important features," "key drivers," "what makes
this player good" — contributions explain the cosine similarity, not player
quality

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

**Mandatory caveats:** all four (`fingerprint_not_style_proof`,
`same_season_team_confound`, `uncertainty_pending`,
`within_role_display_differs_from_global_model`)

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

**Orientation:** CTA button is the first focusable element in the challenge
panel. Tab moves to the next section (Lab explorer).

**Query:** CTA button is the first focusable element. The fingerprint plot is
keyboard-navigable: Tab moves between feature rows, each row announces its
feature label and period-A percentile.

**Reveal:** Identity block is announced first (name, role, competition). Tab
moves to the rank/baseline comparison, then to the caveats, then to the CTA.

**Evidence:** Tab moves from the reveal content to the contribution list.
Each contribution row announces: feature label, family, alignment or
disagreement, contribution value.

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
| Pending/insufficient uncertainty | Render the `uncertainty_pending` caveat with its full message. Rank and similarity values are still shown; the caveat explains the missing interval. |
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

The challenge reads only from the existing `PlayerProfileArtifact` and
`Manifest` contracts. No new artifact field, schema change, or contract
version is required.

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
| `profile.retrieval.global.cosine_similarity` | reveal, evidence |
| `profile.retrieval.global.reciprocal_rank` | not shown directly (MRR is a population metric, not per-profile) |
| `profile.retrieval.baseline_role_minutes.self_rank` | reveal, evidence, degraded |
| `profile.retrieval.method` | reveal |
| `profile.retrieval.global.evidence_refs` | evidence |
| `profile.evidence_index` | evidence |
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
- `scoutlens-jtt.5.4` (render uncertainty in Lab) — open; the challenge must
  render the `uncertainty_pending` caveat until this closes, then render the
  interval from the artifact field
- `scoutlens-jtt.14` (JavaScript headroom) — closed
