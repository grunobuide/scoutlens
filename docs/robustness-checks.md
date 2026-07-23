# ScoutLens — Robustness Checks on Baseline B

Follow-up to the closed spike, per
[`feasibility-report.md`](feasibility-report.md)'s revised Recommended
Next Experiment #1: harden the current baseline before reaching for a
learned representation. Implementation:
[`src/scoutlens/evaluation/run_robustness.py`](../src/scoutlens/evaluation/run_robustness.py),
building on new reusable pieces in
[`similarity.py`](../src/scoutlens/evaluation/similarity.py)
(`fit_scaler`/`apply_scaler` split, `baseline_c_rank`, `metric` param on
`baseline_b_rank`) and
[`retrieval.py`](../src/scoutlens/evaluation/retrieval.py)
(`run_baseline_c_retrieval`). Reproduce with:

```
uv run python -m scoutlens.evaluation.run_robustness
```

Same population throughout: five domestic leagues, ≥450 min in both
periods, 1,257 eligible player×competition combinations (identical to
[`temporal-retrieval-global.md`](temporal-retrieval-global.md)).

## Check 1 — Standardization fit: A-only vs. A+B combined

D008 fits the standardization on the combined query+candidate population.
Compared against fitting on period A alone (closer to how a production
system would actually operate on a genuinely-unseen period B) and
applying that fit to both periods:

| | MRR | Median rank | Recall@10 |
|---|---|---|---|
| A+B combined fit (current default) | 0.2539 | 16 | 43.3% |
| A-only fit | 0.2543 | 16 | 43.0% |

**Reading:** no meaningful difference. D008's transductive choice is not
inflating the result.

## Check 2 — Cosine vs. Euclidean distance

| | MRR | Median rank | Recall@10 |
|---|---|---|---|
| Cosine (current default) | 0.2539 | 16 | 43.3% |
| Euclidean | 0.2535 | 15 | 44.9% |

**Reading:** essentially identical. On z-scored features, the two
metrics behave very similarly here — the choice of distance formula
isn't doing meaningful work; the standardized features themselves carry
the signal.

## Check 3 — Baseline C (role + team + minutes): the important result

A cheap, still-trivial baseline — same role **and** same primary team
first, then same role only, then same team only, then neither, minutes
proximity as the tiebreak within each tier:

| | MRR | Median rank | Recall@1 | Recall@5 | Recall@10 |
|---|---|---|---|---|---|
| Baseline A (role + minutes) | 0.0256 | 128 | 0.3% | 2.7% | 4.9% |
| **Baseline B** (32 features + cosine) | **0.2539** | **16** | **16.2%** | **34.5%** | **43.3%** |
| **Baseline C** (role + team + minutes) | **0.5893** | **2** | **36.9%** | **94.7%** | **97.9%** |

**Baseline C beats Baseline B by more than 2x on MRR, and lands the true
match in the top 5 candidates 94.7% of the time** — dramatically
outperforming the full 32-feature model this spike's headline result is
built on.

**Why:** the eligible population requires ≥450 minutes in *both*
chronological halves of the *same season*. The overwhelming majority of
such players never change clubs mid-season — transfers mostly happen
between seasons. A specific club's specific-nominal-role sub-roster is
small (often just 2–4 eligible players), so "which of this club's 2–4
eligible Defenders has the closest minutes total" already narrows the
field to almost nothing, most of the time correctly. **Team continuity
within one season is an extremely strong prior for "same player" in this
experimental design** — far stronger than event-derived statistical
style similarity turned out to be.

**What this does and doesn't change:**

- It does **not** invalidate Baseline B's result against Baseline A —
  that comparison (Gate 2's actual criterion) still shows a real,
  ~10x, confidently non-zero improvement, and [Check 4](#check-4--drop-teammates-sensitivity)
  below shows Baseline B itself isn't leaning on team membership to get
  there.
- It **does** mean the "10x better than a trivial baseline" framing
  needs an important caveat: an *even more* trivial baseline, using
  information Baseline B never sees (team membership), beats Baseline B
  by a wide margin. The charter's gating question — "is Baseline B
  worth its complexity relative to Baseline A?" — is still answered yes.
  A different, harder question this result raises — "is same-season
  same-player retrieval mostly measuring team continuity rather than
  individual stability?" — was not fully addressed by this spike's
  design, and now has direct quantitative weight behind it.
- It makes **testing transferred players** (already priority #3 in the
  revised Recommended Next Experiment) the single most important
  remaining validation: for a player who changed clubs between periods,
  Baseline C's team-based advantage disappears entirely, isolating
  exactly what Baseline B's event-derived features are worth once the
  team-continuity confound is structurally removed rather than just
  measured (Check 4) within the current team-stable population.

## Check 4 — Drop-teammates sensitivity

For each query, every period-B candidate on the query's own period-A
team is removed from Baseline B's pool *except* the true match itself
(otherwise players who stayed at their club — most of the population —
would have their own correct answer removed).

| | MRR | Median rank | Recall@10 |
|---|---|---|---|
| Full candidate pool | 0.2539 | 16 | 43.3% |
| Teammates excluded | 0.2553 | 16 | 43.3% |

**Reading:** no meaningful change (if anything, imperceptibly better
without teammates in the pool). This confirms
[`context-diagnostics.md`](context-diagnostics.md)'s corrected finding
from the other direction: Baseline B's own performance isn't propped up
by teammates cluttering the candidate pool. Baseline B is doing
something other than team-clustering — the concern Check 3 raises is
about the *experimental design's* team-continuity confound, not about
Baseline B secretly exploiting it.

## Check 5 — Per-feature-family ablation

Each of the 8 feature families ([`feature-definitions.md`](feature-definitions.md))
run alone (not combined with the others), full 32-feature model for
comparison:

| Family | # features | MRR alone | Median rank alone |
|---|---|---|---|
| Passing | 5 | 0.117 | 37 |
| Spatial tendencies | 5 | 0.095 | 31 |
| Possession involvement | 4 | 0.065 | 77 |
| Defensive actions | 4 | 0.040 | 125 |
| Chance creation | 4 | 0.033 | 186 |
| Shooting | 5 | 0.022 | 260 |
| Carrying (proxy) | 3 | 0.019 | 298 |
| Progression | 2 | 0.019 | 209 |
| **All 32 combined (Baseline B)** | 32 | **0.254** | **16** |

**Reading:** no single family comes remotely close to the combined
model — the full model's power comes from combining many weak-to-moderate
signals, not from one dominant family. Passing and spatial tendencies are
individually the strongest contributors; carrying (already flagged as a
proxy, not ground truth) and progression (only 2 features) are weakest
alone, consistent with their standing in the original catalog.

## Check 6 — Cluster-aware bootstrap on the headline MRR delta (added 2026-07-23, D018)

Limitation #12 in [`feasibility-report.md`](feasibility-report.md): the
paired bootstrap treats queries as independent draws, though teammates
share context and leagues share candidate-pool structure. This check
recomputes the same MRR(B) − MRR(A) interval resampling whole
*clusters* with replacement instead of individual queries
(`bootstrap_mrr_delta_clustered`, same seed/resample count from
`config/experiment.json`):

| Resampling unit | Δ point | 95% CI | # clusters |
|---|---|---|---|
| Independent queries (published) | 0.2283 | [0.2083, 0.2479] | 1,257 queries |
| Whole teams (period-A primary team) | 0.2283 | [0.2044, 0.2525] | 98 |
| Whole leagues | 0.2283 | [0.1952, 0.2510] | 5 |

**Reading:** within-cluster correlation is real but small — the
team-clustered CI is ~23% wider than the i.i.d. one, and even the very
coarse league-clustered interval (5 clusters is too few for a
well-calibrated bootstrap; read it as a stress test) keeps the delta
far from zero. The published i.i.d. CI should still be labeled
approximate, but Limitation #12's "likely survives a more conservative
interval" is now checked, not assumed.

## Summary

| Check | Verdict |
|---|---|
| Standardization fit (A-only vs. A+B) | Robust — no meaningful difference |
| Distance metric (cosine vs. Euclidean) | Robust — no meaningful difference |
| Role+team+minutes baseline | **Not robust to this framing** — a cheap baseline using team membership beats Baseline B by >2x. Reframes what "10x better than trivial" should be read to mean, and elevates testing transferred players from a nice-to-have to the critical next step. |
| Teammates in the candidate pool | Robust — Baseline B's own result doesn't depend on them |
| Feature family contribution | As expected — combined model >> any single family |
| Cluster-aware bootstrap CI | Robust — team-clustered CI ~23% wider, conclusion unchanged |

Four of six checks confirm robustness directly. One (Check 3) is a
genuine, important finding that should be read alongside every MRR
number in [`feasibility-report.md`](feasibility-report.md) and
[`gate-2-decision.md`](gate-2-decision.md) going forward — not a reason
to reverse Gate 2, but a reason to be more precise about what it showed.
