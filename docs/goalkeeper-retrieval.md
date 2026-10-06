# Goalkeeper retrieval — Gate 2 of `scoutlens-e87`

**Decision: DROP.** Adding the goalkeeper family to the frozen catalog moved
goalkeeper identity retrieval the right way — MRR 0.1290 → 0.1712, Recall@10
0.309 → 0.361 — but the 95% interval on the MRR gain reaches below zero, and the
frozen rule requires it not to. The default catalog does not change, and the
published caveat `goalkeeper_feature_coverage_weak` stays. Decision record:
`D065`.

Run once against protocol sha256
`d626385c9373a6a1296fb2d20085621a02a6674d04454fecaad7ab68bd866803`, recorded in
`D064` before the run. Observability (Gate 1, GO):
[`goalkeeper-observability.md`](goalkeeper-observability.md).

## Result

<!-- gate2-table:begin -->
| Arm | Queries | MRR | Recall@1 | Recall@5 | Recall@10 | Median rank |
|---|---|---|---|---|---|---|
| Baseline B, 32 features | 97 | 0.1290 | 0.052 | 0.196 | 0.309 | 23 |
| 32 + goalkeeper family | 97 | 0.1712 | 0.072 | 0.278 | 0.361 | 23 |

ΔMRR +0.0422, 95% paired-bootstrap interval -0.0029 to +0.0850 (1000 resamples); ΔRecall@10 +0.052. **Decision: DROP.**
<!-- gate2-table:end -->


## Why DROP, read precisely

The rule has three conditions and the run met two:

| Condition | Required | Observed | |
|---|---|---|---|
| Effect size | ΔMRR ≥ +0.020 | +0.0422 | met |
| Interval | 95% lower bound > 0 | −0.0029 | **not met** |
| No Recall@10 drop | ΔRecall@10 ≥ 0 | +0.052 | met |

This is a null in the project's sense, not a negative: the point estimate is
twice the minimum effect, 65 of 97 goalkeepers rank better and 21 worse, but 97
queries cannot rule out an effect of zero. It is published as DROP rather than
re-read as a near-miss, and it is not a licence to try a variant of the family on
the same 97 goalkeepers — that would be a second look under a new name.

**What would justify revisiting:** more goalkeepers, not a different
specification — a second season or another league set under a new, separately
recorded protocol. The family's code and both gates stay in the repository for
exactly that.

## Ranks

| Self-rank | Baseline | Candidate |
|---|---|---|
| 1 | 5 | 7 |
| 2–5 | 14 | 20 |
| 6–10 | 11 | 8 |
| 11–20 | 17 | 11 |
| over 20 | 50 | 51 |

Per query: 65 improved, 11 unchanged, 21 worsened. The pool is the 97 eligible
goalkeepers' period-B profiles, so chance-level MRR is about 0.05; both arms are
above it, and most goalkeepers remain outside the top 20 in both.

**Calibration** in the probabilistic sense does not apply: retrieval produces
ranks, not probabilities. The rank distribution above is what the protocol
reports in its place.

## Failure cases

The five largest regressions — goalkeepers the family pushed down:

| Goalkeeper | Competition | Baseline rank | Candidate rank |
|---|---|---|---|
| R. Fährmann | German first division | 34 | 67 |
| Rubén Blanco | Spanish first division | 37 | 65 |
| K. Johnsson | French first division | 23 | 44 |
| L. Hradecky | German first division | 7 | 24 |
| Cuéllar | Spanish first division | 4 | 18 |

Read with Gate 1's stated confounds: save percentage and leaving-line rate move
with the defence in front of a goalkeeper and the line it holds, which can
change between halves of a season without the goalkeeper changing. None of this
is a statement about any goalkeeper's quality.

## Independent replication

Before the result was recorded, a second implementation was written from the
protocol text alone — without reading `evaluate.py`, the runner or their tests,
and with its own standardisation, cosine ranking and bootstrap. It produced the
same MRR, Recall and interval to full floating-point precision, the same
decision, and the same rank pair for **all 97** goalkeepers (0 differences). It
also checked one thing this module does not: per-period minutes from the
family's counts equal `period_profiles` minutes for all 194 goalkeeper-periods.

## Runtime and portability

The comparison takes about 1.5 s on the processed data (`run_gate2 --check`
prints it).

Portability to the StatsBomb replication: this repository's StatsBomb ingestion
keeps 46,365 `Goal Keeper` events but only their type name — not the goalkeeper
event's subtype or outcome, and not a pass's body part. The family cannot be
computed from `data/processed/statsbomb` as it stands; it would need those
fields ingested first, which is its own bead and was not part of this one.

## Reproduce

```bash
uv run --frozen python -m scoutlens.goalkeeper.run_gate2 --check
uv run --frozen pytest -q tests/goalkeeper
SCOUTLENS_DRIFT=1 uv run --frozen pytest -q tests/goalkeeper   # also re-runs both gates on local data
```

`run_gate2 --write` refuses while a result is recorded: the comparison is
one-shot, and replacing the record would be a new protocol version.

## Recorded result

<!-- gate2-result:begin -->
```json
{
  "baseline": {
    "median_rank": 23,
    "mrr": 0.12900120547319816,
    "n": 97,
    "recall_at_1": 0.05154639175257732,
    "recall_at_10": 0.30927835051546393,
    "recall_at_5": 0.1958762886597938
  },
  "bead": "scoutlens-e87",
  "candidate": {
    "median_rank": 23,
    "mrr": 0.1712475527906761,
    "n": 97,
    "recall_at_1": 0.07216494845360824,
    "recall_at_10": 0.36082474226804123,
    "recall_at_5": 0.27835051546391754
  },
  "decision": "DROP",
  "gate": 2,
  "largest_regressions": [
    {
      "competitionId": 426,
      "name": "R. Fährmann",
      "player_id": 14847,
      "pool_size": 97,
      "rank_baseline": 34,
      "rank_candidate": 67,
      "rank_change": 33
    },
    {
      "competitionId": 795,
      "name": "Rubén Blanco",
      "player_id": 3822,
      "pool_size": 97,
      "rank_baseline": 37,
      "rank_candidate": 65,
      "rank_change": 28
    },
    {
      "competitionId": 412,
      "name": "K. Johnsson",
      "player_id": 50771,
      "pool_size": 97,
      "rank_baseline": 23,
      "rank_candidate": 44,
      "rank_change": 21
    },
    {
      "competitionId": 426,
      "name": "L. Hradecky",
      "player_id": 55951,
      "pool_size": 97,
      "rank_baseline": 7,
      "rank_candidate": 24,
      "rank_change": 17
    },
    {
      "competitionId": 795,
      "name": "Cuéllar",
      "player_id": 3963,
      "pool_size": 97,
      "rank_baseline": 4,
      "rank_candidate": 18,
      "rank_change": 14
    }
  ],
  "mrr_delta": {
    "ci_high": 0.08501831273916019,
    "ci_low": -0.0028641044325523335,
    "n_queries": 97,
    "n_resamples": 1000,
    "point_estimate": 0.04224634731747795
  },
  "pool_size": [
    97
  ],
  "protocol_sha256": "d626385c9373a6a1296fb2d20085621a02a6674d04454fecaad7ab68bd866803",
  "queries": 97,
  "rank_change": {
    "improved": 65,
    "unchanged": 11,
    "worsened": 21
  },
  "rank_distribution": {
    "baseline": {
      "1": 5,
      "11-20": 17,
      "2-5": 14,
      "6-10": 11,
      ">20": 50
    },
    "candidate": {
      "1": 7,
      "11-20": 11,
      "2-5": 20,
      "6-10": 8,
      ">20": 51
    }
  },
  "recall_at_10_delta": 0.0515463917525773
}
```
<!-- gate2-result:end -->
