# ScoutLens — Wyscout ↔ StatsBomb Feature Compatibility & Frozen Comparison Design

Beads issue `scoutlens-8mc.4`, the design gate that must clear before the
StatsBomb ingestion pipeline (`8mc.2`) is built. Written 2026-07-24,
logged as D020. Prerequisite: the StatsBomb Gate 0 audit
([`statsbomb-provenance.md`](statsbomb-provenance.md), D014) — GO for
non-commercial research replication on 2015/16 (Premier League, La Liga,
Serie A, Ligue 1; Bundesliga excluded).

Feature concepts are the 32 in [`feature-definitions.md`](feature-definitions.md).
This document decides, per feature, whether that concept can be
reproduced on StatsBomb faithfully enough for an **interpretable**
external replication, and freezes two disjoint sets: a **canonical
shared set** used for the like-for-like comparison against the Wyscout
v0.1 result, and a **provider-native secondary set** that exploits
StatsBomb's richer schema without contaminating that comparison.

Findings below were verified against a real StatsBomb 2015/16 events
file (match 3754217, Chelsea–Arsenal, Premier League) and its lineup
file — not inferred from the StatsBomb spec alone.

## Decision (summary)

**GO — with a redesigned canonical set.** 22 of 32 features map directly;
6 map by a defensible approximation; 1 is unavailable (Wyscout-
proprietary); 1 is structurally non-comparable and dropped; 2 shift
construct (proxy → native) and are kept only with an explicit flag. The
redesign is small and mechanical: normalize coordinates, re-express the
completion signal, drop `events_p90` and `smart_passes_p90` from the
canonical comparison, and quarantine StatsBomb's native richness (xG,
pressures, possession sequences, native carries) into the secondary set.
No NO-GO condition was found; the REDESIGN is bounded and specified here.

## Structural schema differences (the six required dimensions)

### 1. Event taxonomy
StatsBomb's event model is **denser and more decomposed** than Wyscout's.
The sample match has 3,732 events across 31 types; a Wyscout match has
~1,600 across ~10 `eventName` values. StatsBomb records several event
classes Wyscout has no row for at all: `Ball Receipt*` (963 in the
sample), `Carry` (814, native), `Pressure` (320), `Dribbled Past`,
`Miscontrol`, `Dispossessed`. **Consequence:** any raw *count of all
events* (`events_p90`) is not comparable between providers — the
denominators are structurally different, not just noisier. Feature
concepts tied to specific, well-defined actions (passes, shots, duels,
clearances, interceptions) survive; a concept tied to "total involvement
volume" does not.

### 2. Coordinates
StatsBomb pitch is **120 × 80**, attack-oriented on x (0 → 120 toward the
attacking goal) — same orientation convention as Wyscout, different
range (Wyscout is 100 × 100). Verified bounds in the sample: x 0.4–120.0,
y 0.1–80.0. **Normalization rule (frozen):** map every StatsBomb
coordinate to the Wyscout 0–100 × 0–100 scale via `x' = x / 120 * 100`,
`y' = y / 80 * 100`, then reuse the exact thresholds in
`feature-definitions.md` unchanged. Residual: the penalty-box x edge is
`x ≥ 84` in Wyscout units; StatsBomb's true box line (x = 102, i.e.
x' = 85.0) is ~1 normalized unit deeper. Left as-is and flagged, not
tuned — a 1-unit box-edge difference is within the approximation the box
definition already declares.

### 3. Possession
StatsBomb attaches a native `possession` id and `possession_team` to
every event, giving true possession sequences directly. Wyscout has
none — which is exactly why the sequence-involvement family was cut from
v0 (`feature-definitions.md`). **This is a provider-native capability, not
a shared one:** it enables the `4f4` sequence family on StatsBomb but
cannot be part of the canonical comparison (Wyscout has no counterpart).
Reserved for the secondary set.

### 4. Lineup & minutes
StatsBomb minutes are **cleaner to derive** than Wyscout's. Each lineup
entry carries per-position intervals with `from`/`to` timestamps,
`from_period`/`to_period`, and `start_reason`/`end_reason` (e.g.
"Starting XI" … "Final Whistle"). Substitutions are explicit
`Substitution` events (minute + `replacement`), `Starting XI` events give
the initial eleven, and `Half End` events give true per-period end
minutes (sample: 48 and 95, i.e. real stoppage-time-inclusive lengths).
Minutes-played per player is the summed duration of their on-pitch
intervals. This replaces the Wyscout `teamsData.formation` +
`substitutions` reconstruction (SLS-009); it is a re-implementation for a
new schema, not a reuse, but it is *simpler* than the original, and the
D005 stoppage-time-substitution edge case is handled natively by the
interval `to` timestamp.

### 5. Identifiers
StatsBomb `player.id` / `team.id` live in **StatsBomb's own namespace,
disjoint from Wyscout `wyId`** (e.g. Asmir Begović is StatsBomb id 3339;
there is no shared key). **Consequence, frozen into the design:** the
replication is a *within-StatsBomb* self-retrieval experiment, compared
to the Wyscout result **at the level of aggregate metrics** (MRR, median
rank, Recall@K, the Baseline A/B/C deltas) — **not** a player-level merge
across providers. No cross-provider id join is attempted; if a
player-level bridge is ever needed it would require name/DOB matching,
which is explicitly out of scope here.

### 6. Missingness encoding
StatsBomb encodes outcomes **by presence, not by tag pair.** A `Pass`
with no `outcome` sub-field is complete (sample: 863 of 1,046); failures
carry an explicit `outcome` (`Incomplete` 155, `Out` 15, `Pass Offside`
3, `Unknown` 6, `Injury Clearance` 4). This inverts the Wyscout
`accurate`[1801] / `not accurate`[1802] tag-pair convention.
**Rule (frozen):** completion % = `count(pass with no outcome) /
count(pass with a determinate outcome)`, where `Unknown` is excluded from
both numerator and denominator (indeterminate), matching the spirit of
Wyscout's "only count passes with a definite accurate/not-accurate tag."
Shots use explicit `shot.outcome` (`Goal`/`Saved`/`Off T`/`Blocked`/
`Wayward`/`Post`…), which is **cleaner** than Wyscout — the
goalkeeper-conceded-goal contamination that D-era `goals_p90` had to
exclude does not exist here, because StatsBomb attributes the shot to the
shooter only.

## 32-feature inventory

Legend: **Direct** = same construct, direct field mapping · **Approx** =
defensible approximation, construct preserved, mechanism differs ·
**Unavailable** = no faithful StatsBomb equivalent · **Non-comparable** =
computable but denominators/semantics not comparable across providers ·
**Construct-shift** = available and arguably better, but measures a
materially different thing than the Wyscout proxy did.

### Passing
| Feature | Verdict | StatsBomb realization |
|---|---|---|
| `passes_p90` | Direct | count `Pass` events |
| `pass_completion_pct` | Direct | complete = `pass.outcome` absent (see §6) |
| `crosses_p90` | Direct | `pass.cross == true` |
| `long_balls_p90` | Approx | `pass.height == "High Pass"` and `pass.length ≥` threshold; Wyscout "Launch" has no exact StatsBomb subtype |
| `smart_passes_p90` | **Unavailable** | Wyscout-proprietary creative-pass label; no StatsBomb equivalent (through-ball/cut-back overlap other features) |

### Progression
| Feature | Verdict | StatsBomb realization |
|---|---|---|
| `progressive_pass_distance_p90` | Direct | `end_location.x' − location.x'` (normalized), floored at 0 |
| `progressive_passes_p90` | Direct | normalized forward gain `≥ 15`, same threshold |

### Chance creation
| Feature | Verdict | StatsBomb realization |
|---|---|---|
| `assists_p90` | Direct | `pass.goal_assist == true` |
| `key_passes_p90` | Direct | `pass.shot_assist == true` |
| `through_balls_p90` | Direct | `pass.through_ball == true` |
| `box_entries_p90` | Direct | `pass.end_location` in normalized box (`x' ≥ 84`, `19 ≤ y' ≤ 81`) |

### Shooting
| Feature | Verdict | StatsBomb realization |
|---|---|---|
| `shots_p90` | Direct | `Shot` with `shot.type == "Open Play"` (matches the open-play-only Wyscout definition) |
| `goals_p90` | Direct | `shot.outcome == "Goal"` — no GK-conceded contamination to exclude |
| `shot_conversion_pct` | Direct | goals / shots |
| `shots_on_target_pct` | Direct | `outcome ∈ {Goal, Saved, Saved To Post, Saved Off T}` / shots |
| `blocked_shot_pct` | Direct | `outcome == "Blocked"` / shots |

### Defensive actions
| Feature | Verdict | StatsBomb realization |
|---|---|---|
| `interceptions_p90` | Direct | native `Interception` events |
| `sliding_tackles_p90` | Approx | `Duel` with `type == "Tackle"`; the "sliding" specificity is lost (StatsBomb doesn't distinguish tackle technique here) |
| `clearances_p90` | Direct | native `Clearance` events |
| `defensive_duel_win_pct` | Approx | `Tackle` outcome `∈ {Won, Success In Play, Success Out}` vs `{Lost In Play, Lost Out}`; StatsBomb's duel model differs from Wyscout's "Ground defending duel" |

### Spatial tendencies
| Feature | Verdict | StatsBomb realization |
|---|---|---|
| `mean_x` | Direct | mean `location.x'` (normalized) |
| `mean_y` | Direct | mean `location.y'` (normalized) |
| `defensive_third_share` | Direct | share `x' < 33.3` |
| `middle_third_share` | Direct | share `33.3 ≤ x' < 66.7` |
| `attacking_third_share` | Direct | share `x' ≥ 66.7` |

### Possession / on-ball involvement
| Feature | Verdict | StatsBomb realization |
|---|---|---|
| `events_p90` | **Non-comparable** | StatsBomb event density is structurally higher (Ball Receipt, Carry, Pressure) — the count means something different; **dropped from canonical** |
| `touches_p90` | Approx (weak) | no native "Touch"; approximate via `Ball Receipt*`; flagged as weak, kept only if the canonical set needs the involvement axis |
| `duels_p90` | Approx | `Duel` events, but StatsBomb splits Dribble/Dribbled Past/50-50 out of "duel", so the count is narrower |
| `duel_win_pct` | Approx | as a **ratio** it is more provider-robust than the raw count; Tackle+Aerial outcomes |

### Carrying (proxy family in Wyscout)
| Feature | Verdict | StatsBomb realization |
|---|---|---|
| `carry_proxy_p90` | **Construct-shift** | StatsBomb has a **native `Carry` event** (814 in the sample) — no longer a proxy; measures actual ball-carrying, not Wyscout's `Acceleration` stand-in |
| `carry_distance_proxy_p90` | **Construct-shift** | native `carry.end_location.x' − location.x'` — real carry distance |
| `take_on_success_pct` | Direct | `Dribble` with `dribble.outcome == "Complete"` / all `Dribble` |

**Tally:** Direct 22 · Approx 6 · Unavailable 1 · Non-comparable 1 ·
Construct-shift 2 = 32.

## Frozen canonical shared feature set (the like-for-like comparison)

The set used to test *does the v0.1 signal replicate on a different
provider and season*. **28 features:** all Direct (22) and all Approx (6),
**excluding** `smart_passes_p90` (Unavailable) and `events_p90`
(Non-comparable). The two Construct-shift carry features **are included**,
because native `Carry` is a legitimately better measure of the *same
underlying construct* (progression by carrying) — but every report
comparing the two runs must state that Wyscout measured this family by
proxy and StatsBomb natively, so an improvement there is expected and not
evidence of anything about the method. `touches_p90` is retained but
labeled weak; a sensitivity run with it dropped is part of `8mc.3`.

Normalization and eligibility for the canonical set are **frozen to match
v0.1 exactly** so the comparison is clean:
- Coordinates normalized to 0–100 (§2); all `feature-definitions.md`
  thresholds reused unchanged.
- Per-90 and ratio-null conventions identical to v0.1 (`minutes == 0`
  → `null`, ratio denominator `0` → `null`).
- Standardization: z-score, mean-impute-nulls-to-zero, fit on the
  combined A+B eligible population (D008), with the A-only-fit robustness
  check (`robustness-checks.md` Check 1) repeated.
- Eligibility: **≥ 450 minutes in both** chronological halves of the
  2015/16 season, per competition — identical bar to v0.1. Period split
  by `match_date` within each league.
- Retrieval: Baselines A (role+minutes), B (28 standardized features +
  cosine), C (role+team+minutes), plus the transferred-players follow-up
  — the full v0.1 + robustness + transfer battery, re-run.

## Frozen provider-native secondary set (StatsBomb-only enrichment)

Analyzed **separately**, never mixed into the canonical comparison:
- `statsbomb_xg` — native expected goals on every shot (Wyscout had none;
  v0.1 deliberately avoided xG modeling).
- Pressing intensity from native `Pressure` events (the physical/pressing
  axis v0.1 declared out of scope for lack of data).
- Sequence-involvement family (`4f4`) built on native `possession`
  sequences — the family cut from Wyscout v0 for lack of a break-detection
  signal.
- Ball-Receipt-based touch maps and freeze-frame-derived features (e.g.
  shot pressure) — no Wyscout counterpart.

These answer "what more can StatsBomb see?", a different question from
"does the signal replicate?", and must not silently widen the canonical
feature set.

## GO / REDESIGN / NO-GO

**GO, conditional on the redesign frozen above.** The redesign is fully
specified and bounded — normalize coordinates, invert the completion
encoding, drop 2 features from canonical, flag the carry construct-shift,
quarantine native richness. `8mc.2` (pipeline) may proceed against
StatsBomb open-data commit `b0bc9f22dd` (D014), competitions {2,7,11,12}
× season 27, implementing: StatsBomb events/lineups ingestion, the
interval-based minutes derivation (§4), the 28-feature canonical
aggregation with the normalization rules above, and the eligibility/split
rules — then `8mc.3` re-runs the retrieval battery and compares aggregate
metrics to the Wyscout v0.1 numbers.
