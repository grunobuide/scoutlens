# Goalkeeper observability — Gate 1 of `scoutlens-e87`

**Decision: GO.** The Wyscout 2017/18 event schema directly records three
distinct goalkeeper behaviours with auditable denominators, and every one is
supported for at least 97.9% of the 194 eligible goalkeeper-periods. Gate 2 —
whether the family improves goalkeeper identity retrieval — is frozen below by
hash and has not been run. Decision record: `D064`.

The recorded result is this document: the run's canonical JSON is in
[Recorded result](#recorded-result) and the support table below is rendered
from it, both written by `python -m scoutlens.goalkeeper.run_audit --write` and
reproduced exactly by `--check`. Every number here comes from that run.

## Why this exists

The frozen 32-feature catalog is outfield-oriented. The published caveat
`goalkeeper_feature_coverage_weak` says so on every goalkeeper profile, and 97 of
the 1,257 eligible units are goalkeepers. `scoutlens-e87` asks whether that can
be fixed honestly — with what the data records, not with what it could be made
to suggest.

## The rule, fixed before anything was measured

From the bead, made exact in `scoutlens.goalkeeper.observability`:

- **Directly recorded only.** A behaviour counts if an event type, subtype or
  tag records it. Inferring it from coordinates, timing or a fitted model is
  proxying, which the bead's non-goals exclude.
- **Supported.** A proportion needs at least 20 denominator events in a
  goalkeeper-period; a per-90 rate needs at least 5 events (its denominator,
  minutes, is already at least 450 by eligibility). A feature is supported when
  at least 90% of eligible goalkeeper-periods meet its minimum.
- **Distinct.** GO needs supported features in at least three concepts. Two
  features of one concept are one concept.
- **New.** A measurement the catalog already has is not a candidate.

## What the schema records

| Feature | Concept | Numerator | Denominator |
|---|---|---|---|
| `gk_save_pct` | shot-stopping | Save attempt (eventId 9) tagged accurate [1801] | Save attempt tagged accurate [1801] or not accurate [1802] |
| `gk_reflex_save_share` | shot-stopping | Save attempt of subtype Reflexes (subEventId 90) | Save attempt (eventId 9) |
| `gk_leaving_line_p90` | sweeping | Goalkeeper leaving line (eventId 4) | minutes played, per 90 |
| `gk_hand_pass_share` | distribution mode | Pass of subtype Hand pass (subEventId 81) | Pass (eventId 8) |

## Support

<!-- audit-table:begin -->
| Feature | Concept | Support basis | Minimum | Supported goalkeeper-periods | Coverage | Support p10 / median | Supported |
|---|---|---|---|---|---|---|---|
| `gk_save_pct` | shot_stopping | `saves_tagged` | 20 | 190 of 194 | 97.9% | 38 / 73 | yes |
| `gk_reflex_save_share` | shot_stopping | `save_attempts` | 20 | 190 of 194 | 97.9% | 38 / 73 | yes |
| `gk_leaving_line_p90` | sweeping | `leaving_line` | 5 | 194 of 194 | 100.0% | 12 / 24 | yes |
| `gk_hand_pass_share` | distribution_mode | `passes` | 20 | 194 of 194 | 100.0% | 174 / 315 | yes |
<!-- audit-table:end -->
Four goalkeeper-periods have fewer than 20 save attempts. Under the frozen null
rule their two shot-stopping values are null and sit at z = 0 after
imputation — "never came up", not an estimate from a handful of events.

## What the gate assumed, counted

- **Save attempts partition cleanly.** Of 13,874 save attempts by eligible
  goalkeepers, none is untagged and none carries both accurate and not
  accurate, so `gk_save_pct` divides a true partition.
- **Goal-kick accuracy is not recorded.** None of 24,736 goal kicks carries an
  accuracy tag. That is why it is listed as unavailable below rather than
  inferred from what happened next.

## Already in the catalog, so not candidates

- `long_balls_p90` — the `Launch` pass subtype, a goalkeeper's long
  distribution.
- `pass_completion_pct` — pass accuracy, including a goalkeeper's.

A family that re-counted these would re-weight existing features and call it a
new signal.

## Not observable from this schema

| Concept | Why |
|---|---|
| Positioning at the moment of a shot | Event positions locate the acting player's event only; nothing records where the goalkeeper stood. |
| Shot quality faced, post-shot xG, goals prevented | No expected-goals or shot-quality field exists; building one is a model — proxying. |
| Claiming and punching crosses, aerial command | No claim or punch event; "Goalkeeper leaving line" does not distinguish a claim, a punch, a smother or a sweep. |
| One-on-one outcomes | No field marks a one-on-one; deriving one from coordinates and timing would be inference. |
| Goal-kick accuracy | Goal kicks carry no accuracy tag (0 of 24,736 above). |
| Penalty saving | No field links a save attempt to the penalty it faced, and support would be a handful of events per goalkeeper-period. |
| Distribution under pressure, communication, organisation | Not recorded. |

## What GO does and does not mean

GO means three goalkeeper behaviours can be **measured** consistently enough to
test whether they carry identity signal. It does not mean they measure
goalkeeping quality, and nothing here ranks goalkeepers.

The confounds are real and stated in advance. `gk_save_pct` describes the
outcome of the attempts the provider recorded, and the difficulty of the shots
faced is not observed, so it mixes the goalkeeper with the defence in front of
them. `gk_leaving_line_p90` depends on how high the team plays. Both are the
same kind of same-season team context the published caveat
`same_season_team_confound` already names for the catalog, and Gate 2 reports
failure cases with that in mind.

## Gate 2, frozen and not yet run

`scoutlens.goalkeeper.protocol.PROTOCOL`, sha256
`d626385c9373a6a1296fb2d20085621a02a6674d04454fecaad7ab68bd866803`:

- **Queries and pool:** every eligible goalkeeper's period-A profile, ranked
  against all eligible goalkeepers' period-B profiles. Outfield players are
  never evidence.
- **Baseline:** the published within-role Baseline B — the 32 catalog
  features, scaled on the all-roles eligible population, cosine.
- **Candidate (one arm only):** the same 32, plus the four features above
  standardised on eligible goalkeeper-periods, cosine over 36.
- **KEEP:** ΔMRR ≥ +0.020, the 95% paired-bootstrap interval's lower bound
  above 0 (1,000 resamples over goalkeeper queries, seed 0), and no drop in
  Recall@10. Anything else is DROP, and a DROP is published.
- **One shot:** `assert_gate2_unlocked` refuses to run unless this exact hash is
  on the ledger; a second look is a new protocol version.

## Reproduce

```bash
uv run --frozen python -m scoutlens.goalkeeper.run_audit --check
uv run --frozen pytest -q tests/goalkeeper
SCOUTLENS_DRIFT=1 uv run --frozen pytest -q tests/goalkeeper   # also re-runs the audit on local data
```

## Recorded result

The canonical output of the run, from which the support table above is
rendered. `tests/goalkeeper` holds the table, the protocol hash and this block
together, and with local data re-runs the audit against it.

<!-- audit-result:begin -->
```json
{
  "already_in_catalog": [
    {
      "feature_id": "long_balls_p90",
      "measures": "Pass subtype Launch (subEventId 84) per 90 - long distribution"
    },
    {
      "feature_id": "pass_completion_pct",
      "measures": "Pass tagged accurate / accurate or not accurate - distribution accuracy"
    }
  ],
  "bead": "scoutlens-e87",
  "features": [
    {
      "concept": "shot_stopping",
      "coverage": 0.9794,
      "denominator_total": 13874.0,
      "feature_id": "gk_save_pct",
      "kind": "proportion",
      "minimum": 20,
      "numerator_total": 9792,
      "support_basis": "saves_tagged",
      "support_median": 73.0,
      "support_min": 17,
      "support_p10": 38.0,
      "supported": true,
      "unit_periods": 194,
      "unit_periods_supported": 190
    },
    {
      "concept": "shot_stopping",
      "coverage": 0.9794,
      "denominator_total": 13874.0,
      "feature_id": "gk_reflex_save_share",
      "kind": "proportion",
      "minimum": 20,
      "numerator_total": 8483,
      "support_basis": "save_attempts",
      "support_median": 73.0,
      "support_min": 17,
      "support_p10": 38.0,
      "supported": true,
      "unit_periods": 194,
      "unit_periods_supported": 190
    },
    {
      "concept": "sweeping",
      "coverage": 1.0,
      "denominator_total": 276089.0,
      "feature_id": "gk_leaving_line_p90",
      "kind": "rate_p90",
      "minimum": 5,
      "numerator_total": 4813,
      "support_basis": "leaving_line",
      "support_median": 24.0,
      "support_min": 7,
      "support_p10": 12.0,
      "supported": true,
      "unit_periods": 194,
      "unit_periods_supported": 194
    },
    {
      "concept": "distribution_mode",
      "coverage": 1.0,
      "denominator_total": 60711.0,
      "feature_id": "gk_hand_pass_share",
      "kind": "proportion",
      "minimum": 20,
      "numerator_total": 11135,
      "support_basis": "passes",
      "support_median": 315.0,
      "support_min": 61,
      "support_p10": 174.0,
      "supported": true,
      "unit_periods": 194,
      "unit_periods_supported": 194
    }
  ],
  "gate": 1,
  "gate1": {
    "decision": "GO",
    "min_distinct_concepts": 3,
    "supported_concepts": [
      "distribution_mode",
      "shot_stopping",
      "sweeping"
    ],
    "supported_features": [
      "gk_save_pct",
      "gk_reflex_save_share",
      "gk_leaving_line_p90",
      "gk_hand_pass_share"
    ]
  },
  "gate2_protocol_sha256": "d626385c9373a6a1296fb2d20085621a02a6674d04454fecaad7ab68bd866803",
  "population": {
    "competitions": [
      364,
      412,
      426,
      524,
      795
    ],
    "eligible_goalkeeper_units": 97,
    "goalkeeper_unit_periods": 194,
    "minutes_threshold_per_period": 450
  },
  "schema_checks": {
    "goal_kicks": 24736,
    "goal_kicks_tagged": 0,
    "save_attempts": 13874,
    "saves_double_tagged": 0,
    "saves_untagged": 0
  },
  "unavailable": [
    {
      "concept": "positioning at the moment of a shot",
      "why": "event positions locate the acting player's event only; nothing records where the goalkeeper stood when the shot was struck"
    },
    {
      "concept": "shot quality faced, post-shot xG, goals prevented",
      "why": "the schema has no expected-goals or shot-quality field; building one is a model, which the bead's non-goals exclude as proxying"
    },
    {
      "concept": "claiming and punching crosses, aerial command",
      "why": "there is no claim or punch event; 'Goalkeeper leaving line' does not distinguish a claim, a punch, a smother or a sweep"
    },
    {
      "concept": "one-on-one outcomes",
      "why": "no field marks a one-on-one; deriving one from attacker and goalkeeper coordinates and timing would be inference"
    },
    {
      "concept": "goal-kick accuracy",
      "why": "Goal kick (subEventId 34) carries no accurate / not-accurate tag - counted by the audit as goal_kicks_tagged"
    },
    {
      "concept": "penalty saving",
      "why": "no field links a save attempt to the penalty it faced; pairing by time would be inference, and the support per goalkeeper-period would be a handful of events"
    },
    {
      "concept": "distribution under pressure, communication, organisation",
      "why": "the schema records no pressure, no off-ball organisation and no communication"
    }
  ]
}
```
<!-- audit-result:end -->
