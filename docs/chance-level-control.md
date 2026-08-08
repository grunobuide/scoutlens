# ScoutLens — Chance-Level Control for Retrieval MRR (SLS-024)

Every published ScoutLens MRR answers "how well does the method find the
same player's second-half profile?" — but none of them answered "how well
*would any* method do on that question by pure design luck, before any
signal?" That is the floor this control establishes.

Implementation: [`chance_level.py`](../src/scoutlens/evaluation/chance_level.py)
+ [`run_chance_control.py`](../src/scoutlens/evaluation/run_chance_control.py).
Reproduce with:

```
uv run python -m scoutlens.evaluation.run_chance_control
```

Result: [`artifacts/chance_control_results.json`](../artifacts/chance_control_results.json).

## Method

Each retrieval baseline emits a **total ordering** of its candidate pool
(a bijection between candidates and ranks 1..N). If the same-player link
were pure noise — the target drawn uniformly from that exact pool — the
expected reciprocal rank would be

    E[1/rank] = (1/N) · (1 + 1/2 + … + 1/N) = H_N / N

which is **independent of the method** that produced the ordering. This is
the experiment design's chance level: the MRR a baseline would collect by
pool composition alone. We report:

- `chance_level_mrr` — H_N/N, pooled per-query (within-role pools vary by
  role, so the design floor is higher there than in the global pool).
- `lift` — observed MRR / chance level. 1.0 means "nothing above the
  floor"; 40x means "40 times better than uniform-target luck."
- `random_target_null` — an empirical permutation null: 10,000 seeded
  draws of a uniform target rank per query, their MRR distribution,
  a 95% central interval, and an empirical p-value for the observed MRR.

Population is bit-identical to the published artifacts: five domestic
leagues, ≥450 min/period, 1,257 player×competition units; the same 26
transferred players from `identify_transferred_players`. Observed MRRs
reproduce gate2/robustness/transfer numbers exactly.

## Results

### Global pool (N = 1,257)

| | MRR | Chance level | Lift | p (vs null) |
|---|---:|---:|---:|---:|
| Baseline A (role + minutes) | 0.0256 | 0.00614 | 4.2× | <0.0001 |
| **Baseline B** (32 features + cosine) | **0.2539** | 0.00614 | **41.4×** | **<0.0001** |
| Baseline C (role + team + minutes) | 0.5893 | 0.00614 | 96.0× | <0.0001 |

Baseline C's 96× lift is *not* a signal in its own right — it is the
team-continuity prior the experimental design accidentally rewards: most
eligible players don't change clubs mid-season, so "same club" wins.
Reading the 41× of Baseline B against the same floor shows the
event-derived signal is also an enormous, highly significant margin above
design luck.

### Within role (per-query pool = same nominal role)

| | MRR | Chance level | Lift | p |
|---|---:|---:|---:|---:|
| Baseline A (role + minutes) | 0.0256 | 0.0196 | 1.3× | 0.003 |
| **Baseline B** (features + cosine) | **0.2787** | 0.0196 | **14.2×** | **<0.0001** |

Scoping the pool to a role nearly raises the floor to Baseline A's level:
role + minutes alone is now only 1.3× above chance (p = 0.003), confirming
that once the pool stops being "1,257 anyone", the role-and-workload
baseline's power is mostly spent. Baseline B still reaches 14.2×.

### Transferred players (n = 26, pool unchanged at N = 1,257)

| | MRR | Chance level | Lift | p |
|---|---:|---:|---:|---:|
| Baseline A (role + minutes) | 0.0105 | 0.00614 | 1.7× | 0.109 |
| **Baseline B** (features + cosine) | **0.2387** | 0.00614 | **38.9×** | **<0.0001** |
| Baseline C (role + team + minutes) | 0.0101 | 0.00614 | 1.6× | 0.116 |

**This is the decisive comparison.** For players who changed clubs, the
team signal exists in the data but is wrong about the answer — and
Baseline C collapses to the design floor (1.6×, p = 0.116, statistically
indistinguishable from uniform-target luck). Baseline B, meanwhile, holds
a 38.9× lift over the same floor. The cleanup of the team-continuity
confound is now measured on the chance-level axis the transfer-analysis
could only assert on relative grounds.

## Reading

1. **Every absolute MRR should be read against its floor.** A "10× role
   baseline" claim was always relative; the chance level gives the
   absolute scale. Baseline B retains a 38–41× lift over uniform-random
   targeting in every condition examined — the same-player link is not a
   pool-composition artifact.
2. **Baseline C's strength is almost entirely team continuity.** Its lift
   is 96× in the general population and 1.6× (not significant) for
   transferred players — the cleanest expression of the
   [D010](decisions-log.md#d010--2026-07-22--team-continuity-dominates-a-trivial-roleteamminutes-baseline-reframe-dont-retract)
   reframing in the whole project.
3. **Small-n honesty:** the transferred null has only 26 queries, so its
   p-values distribute over a coarse grid (multiples of ~0.008 per draw);
   read "≈0.11" as "cannot distinguish from chance," not as a precise
   probability.
