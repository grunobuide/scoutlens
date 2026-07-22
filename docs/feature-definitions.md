# ScoutLens — Feature Catalog v0 (SLS-013)

32 event-derived features across 8 families. Every definition below is
grounded in tags/subevents empirically confirmed to exist and mean what
they appear to mean — see the tag/subevent cross-reference in this
session's exploration (co-occurrence counts against `eventName`), not
assumed from field names alone. Where a definition requires a threshold
that the schema doesn't dictate (e.g. what counts as "progressive"), the
threshold is stated explicitly as a parameter, not buried in code.

**Dropped from the brief's suggested families: sequence involvement.**
`eventSec` + `matchPeriod` do give real chronological event ordering, so
this is *buildable*, but defining a "possession sequence" requires a
break-detection rule (on `Interruption`, `Foul`, team change, etc.) that
adds real complexity for a family with no single, obviously-correct
definition. Cut per the D003 scope-priority order — this is exactly the
kind of thing to drop first if time is short, not the temporal-retrieval
experiment itself. Can be revisited after Gate 2 if the simpler families
turn out insufficient.

## Conventions used throughout

- **Per-90 normalization:** `rate = (raw_count / minutes_played) * 90`,
  computed per player per temporal period (SLS-014), only for players
  meeting the period's minutes threshold. `minutes_played == 0` must
  produce `null` for every per-90 feature, not `NaN` — the aggregation
  contract guards every division explicitly rather than relying on
  callers to pre-filter perfectly.
- **Ratio features** (completion %, win %, conversion %) return `null`
  when the denominator is 0 — never fabricated as 0%. A player with zero
  shot attempts has no shot conversion rate, not a 0% one.
- **Coordinates:** `positions[0]` = origin, `positions[1]` = destination
  (when present). `x` runs 0→100 toward the *attacking* team's target
  goal (confirmed in `docs/data-dictionary.md`) — so "forward progress"
  for any event is `destination.x - origin.x`, always in the attacking
  direction regardless of which half of the pitch or which team.
- **Attribution:** every feature is attributed to `events.playerId`
  (excluding the `playerId == 0` "no player" sentinel — see
  `data-dictionary.md`).

---

## 1. Passing (5 features)

| Feature | Definition | Grounding |
|---|---|---|
| `passes_p90` | count(`eventName == "Pass"`) per 90 | 1,665,508 Pass events total |
| `pass_completion_pct` | count(Pass with tag `accurate` [1801]) / count(Pass with tag `accurate` or `not accurate` [1801 or 1802]) | 1,381,487 accurate / 284,019 not-accurate on Pass — direct completion signal, not inferred |
| `crosses_p90` | count(subEventName == "Cross") per 90 | 62,333 Cross events |
| `long_balls_p90` | count(subEventName == "Launch") per 90 | 45,738 Launch events — Wyscout's own long-ball subtype |
| `smart_passes_p90` | count(subEventName == "Smart pass") per 90 | 30,303 Smart pass events — Wyscout's own creative-pass subtype |

## 2. Progression (2 features)

| Feature | Definition | Grounding |
|---|---|---|
| `progressive_pass_distance_p90` | sum(max(0, destination.x − origin.x)) over Pass events per 90 | positions present on 1,665,506/1,665,508 Pass events (99.9999%) |
| `progressive_passes_p90` | count(Pass events where destination.x − origin.x ≥ **15**) per 90 | Threshold is a stated parameter, not schema-derived — 15 points on the 0–100 scale, revisit if Gate 2 diagnostics suggest sensitivity |

## 3. Chance creation (4 features)

| Feature | Definition | Grounding |
|---|---|---|
| `assists_p90` | count(any event with tag `assist` [301]) per 90 | 3,098 tagged events — direct signal, not a proxy |
| `key_passes_p90` | count(any event with tag `keyPass` [302]) per 90 | 12,229 tagged events — direct signal |
| `through_balls_p90` | count(Pass with tag `through` [901]) per 90 | 30,258 — appears exclusively on Pass |
| `box_entries_p90` | count(Pass where destination lands in the **penalty box** — destination.x ≥ 84 and 19 ≤ destination.y ≤ 81) per 90 | Box approximated from standard pitch proportions (16.5m box depth / ~105m pitch length ≈ 84th percentile; ~40.3m box width / ~68m pitch width ≈ 21–79 range); stated as an approximation, not a schema field |

## 4. Shooting (5 features)

| Feature | Definition | Grounding |
|---|---|---|
| `shots_p90` | count(`eventName == "Shot"`, includes open-play only — `Free kick shot` and `Penalty` are separate Free Kick subtypes, not summed in here to keep "shot" meaning open play) per 90 | 43,078 Shot events |
| `goals_p90` | count(tag `Goal` [101] on `eventName == "Shot"`, or on a Free Kick with `subEventName` in {Penalty, Free kick shot, Corner}) per 90 | Goal tag also appears on the **conceding** goalkeeper's `Save attempt` event (5,279 occurrences, 5,274 on players with role Goalkeeper — verified; marks "a goal happened during this action," not "this player scored") and must be excluded. Of the 617 Goal-tagged Free Kick events, only Penalty (477), Free kick shot (137), and Corner (3) are events a player can actually score from directly; plain `Free Kick` (indirect), `Goal kick`, and `Throw in` cannot legally produce a direct goal |
| `shot_conversion_pct` | goals (from Shot events specifically) / shots_p90's raw count | Standard definition; null if 0 shots |
| `shots_on_target_pct` | count(Shot with a goal-mouth tag, i.e. any of tags 1201–1209 [`gb`…`gtr`], or tag `Goal`) / count(Shot) | Goal-mouth zone tags observed 149–4,269 times each on Shot/Save attempt/Free Kick — see data-dictionary; on-target = reached the goal frame |
| `blocked_shot_pct` | count(Shot with tag `blocked` [2101]) / count(Shot) | 10,222 blocked-tagged Shot events |

## 5. Defensive actions (4 features)

| Feature | Definition | Grounding |
|---|---|---|
| `interceptions_p90` | count(any event with tag `interception` [1401]) per 90 | 173,909 total occurrences across Pass/Others-on-the-ball/Duel — tag marks the acting player's own action, not "this event was intercepted by someone else" (verified: interception-tagged Passes are 73% `accurate`, inconsistent with "this pass got picked off") |
| `sliding_tackles_p90` | count(any event with tag `sliding_tackle` [1601]) per 90 | 21,535 — appears exclusively on Duel |
| `clearances_p90` | count(subEventName == "Clearance") per 90 | 56,819 — note: tag `clearance` [1501] exists in the mapping but is **never actually used** in this dataset (confirmed in SLS-006); the subEventName is the real signal, not the tag |
| `defensive_duel_win_pct` | count(subEventName == "Ground defending duel" with tag `won` [703]) / count(subEventName == "Ground defending duel" with tag `won` or `lost` [703 or 701]) | 278,703 Ground defending duel events total |

## 6. Spatial tendencies (5 features)

| Feature | Definition | Grounding |
|---|---|---|
| `mean_x` | mean(origin.x) across all of the player's events | positions present on effectively all events (see data-dictionary) |
| `mean_y` | mean(origin.y) across all of the player's events | — |
| `defensive_third_share` | share of events with origin.x < 33.3 | Even thirds of the 0–100 domain |
| `middle_third_share` | share of events with origin.x in [33.3, 66.7) | — |
| `attacking_third_share` | share of events with origin.x ≥ 66.7 | — |

## 7. Possession / on-ball involvement (4 features)

Deliberately **not** called "possession time" anywhere — this measures
participation frequency, not time in possession, per the brief's own
caution (section 6).

| Feature | Definition | Grounding |
|---|---|---|
| `events_p90` | count(all events attributed to player) per 90 | Broadest involvement signal |
| `touches_p90` | count(subEventName == "Touch") per 90 | 174,535 Touch events |
| `duels_p90` | count(`eventName == "Duel"`) per 90 | 879,083 Duel events |
| `duel_win_pct` | count(Duel with tag `won` [703]) / count(Duel with tag `won` or `lost` [703 or 701]) | 338,879 won / 339,783 lost across all Duel subtypes (Air, Ground attacking/defending/loose ball) |

## 8. Carrying — explicit proxy family (3 features)

Per the brief's own warning (section 6): **no native "carry" event exists
in this dataset**, unlike modern tracking-derived datasets. Everything in
this family is a documented derived proxy, never presented as ground
truth in any report this spike produces.

| Feature | Definition | Grounding | Proxy caveat |
|---|---|---|---|
| `carry_proxy_p90` | count(subEventName == "Acceleration") per 90 | 25,886 Acceleration events — Wyscout's closest on-ball-progression-without-a-pass subtype | This is Wyscout's own label for the closest concept, not a validated carry detector |
| `carry_distance_proxy_p90` | sum(destination.x − origin.x) over Acceleration events per 90 | Positions present on Acceleration events (part of "Others on the ball", confirmed 2-position rate) | Same caveat |
| `take_on_success_pct` | count(Ground attacking duel with tag `take_on_l` or `take_on_r` [503/504] and tag `won` [703]) / count(Ground attacking duel with tag `take_on_l` or `take_on_r`) | 52,599/52,593 take_on-tagged Ground attacking duels — a real "dribble past an opponent" signal | Closer to a genuine signal than Acceleration, but still framed as "success rate at attempting to beat a defender 1v1," not literally "carrying" |

---

## Deliberately excluded from v0

- **Sequence involvement** — see above.
- **Anthropometric features** (`weight`, `height`, `foot`) — not
  event-derived, and `players.foot`/`weight`/`height` carry unresolved
  sentinel ambiguity flagged in `data-quality-report.md`. Out of scope for
  a role-signal experiment regardless.
- **xA / expected-assist modeling** — unnecessary: `assist` and `keyPass`
  tags already provide a direct, non-modeled chance-creation signal.
- **Physical/pressing-intensity features** — no data support (event data
  only, no tracking data); explicitly named as out of claim scope in the
  brief (section 11.7).

## Implementation note

This document is the specification; SLS-014 implements the aggregation in
`src/scoutlens/features/`. Per the notebook/module discipline in
`project-charter.md`, feature logic belongs in `src/`, covered by tests —
not computed ad hoc in a notebook.
