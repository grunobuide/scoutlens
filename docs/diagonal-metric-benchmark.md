# Diagonal metric benchmark — the simplest trainable alternative to cosine

`scoutlens-qop.2`, run against the preregistered protocol frozen in
[`representation-benchmark-protocol.md`](representation-benchmark-protocol.md)
(`D041`). Decision record for this run: `D042`.

**Spec hash** `47488d603e9246f45fdd3e3d0aa95835bb569e5793444b87950c34e2531aa3bd`

**Result: `CONTINUE_NEURAL`.** The diagonal metric clears the preregistered
continuation gate by a wide margin. Validation delta **+0.2174** (gate:
≥ +0.010), 95% CI [+0.1686, +0.2642] (gate: lower bound > −0.005).

---

## 1. The model

One non-negative weight per feature, and nothing else:

    s(q, c) = Σᵢ wᵢ qᵢ cᵢ / ( √(Σᵢ wᵢ qᵢ²) · √(Σᵢ wᵢ cᵢ²) )

This is exactly cosine similarity in the space scaled by `√w`. Two properties
follow, and the implementation leans on both:

1. **`w = 1` *is* the frozen Baseline B.** The learned model strictly
   generalizes the incumbent — cosine is a point in the hypothesis space, not
   a rival method. `tests/benchmark/test_diagonal.py` asserts the
   reproduction bit-for-bit.
2. **Ranking needs no new code.** Scaling standardized features by `√w` and
   calling the existing `run_baseline_b_retrieval` computes precisely this
   score, so the audited ranking path is reused untouched.

The score is invariant to a global rescaling of `w`, so weights are
normalized to mean 1. A weight is therefore directly readable as "this
feature pulls this many times as hard as it would under plain cosine".

Regularization shrinks toward `w = 1` — toward the incumbent — so the grid
interpolates between *learned* and *what we already ship*, rather than
between learned and an arbitrary zero.

## 2. Training

| | |
|---|---|
| Objective | InfoNCE over (anchor period-A, positive period-B, 32 same-role negatives) |
| Temperature | 0.05 |
| Optimizer | projected full-batch gradient descent, **proximal in the penalty** |
| Steps | 300, learning rate 0.5 |
| Init | `w = 1` (the incumbent) |
| Anchors | 753 — every training period-A row |
| Fitted on | the **train** split only; 753 players, zero overlap with the 504 held out |

Deterministic throughout: no shuffling, no adaptive optimizer state, negatives
drawn once from a seeded generator. Same inputs give bit-identical weights.

## 3. Grid and selection

Selection is on **validation within-role MRR**. Test was never consulted.
Cosine reference on validation: **0.4290**.

| λ | Validation MRR | Δ vs cosine | 95% CI | Collapsed features |
|---|---|---|---|---|
| **0.0** | **0.6464** | **+0.2174** | [+0.1686, +0.2642] | 6 |
| 0.001 | 0.6460 | +0.2171 | [+0.1686, +0.2642] | 6 |
| 0.01 | 0.6460 | +0.2170 | [+0.1686, +0.2641] | 6 |
| 0.1 | 0.6333 | +0.2043 | [+0.1572, +0.2495] | 5 |
| 1.0 | 0.5935 | +0.1645 | [+0.1220, +0.2037] | 3 |
| 10.0 | 0.4690 | +0.0400 | [+0.0205, +0.0585] | 0 |

Selected **λ = 0**. The top three arms are within 0.0004 of each other, so
selection is effectively flat across λ ≤ 0.01; the tie-break toward the larger
penalty did not bind because λ = 0 won outright.

## 4. One-time test evaluation

The selected model, evaluated **once** on the held-out test split.

| | Cosine | Diagonal | Δ | 95% CI |
|---|---|---|---|---|
| Within-role MRR | 0.4264 | **0.6532** | **+0.2268** | [+0.1835, +0.2737] |

Validation (+0.2174) and test (+0.2268) agree closely, which is the main
evidence that selecting on validation did not overfit it.

### By role

Every role improves and none degrades, on both splits.

| Role | n (test) | Cosine | Diagonal | Δ test | Δ validation |
|---|---|---|---|---|---|
| Defender | 95 | 0.3417 | 0.6106 | +0.2689 | +0.3006 |
| Midfielder | 90 | 0.5510 | 0.7528 | +0.2017 | +0.1954 |
| Forward | 48 | 0.4528 | 0.7003 | +0.2476 | +0.1721 |
| Goalkeeper | 20 | 0.2040 | 0.2938 | +0.0898 | +0.0174 |

**No role reaches the 100-query minimum, so no subgroup gates the decision** —
the inert-gate finding from `D041`, now confirmed against real numbers rather
than inferred from counts. This is what `scoutlens-qop.5` exists to resolve.
Goalkeeper is the weakest arm and the smallest (n = 19/20); its validation
gain of +0.017 would not survive any reasonable interval, and it should not be
read as evidence of anything.

## 5. Why this is not an artifact

A delta of +0.22 is large enough to deserve disbelief first. Three controls,
all run against the same pipeline:

| Control | Expectation if the gain were artifactual | Observed |
|---|---|---|
| **λ → ∞ limit** | should converge to cosine exactly | λ=10⁵ gives validation MRR **0.428984**, matching the cosine reference to six decimals |
| **Random reweighting** (5 draws) | if any reweighting helps, gains appear without training | 0.4070–0.4597, straddling cosine's 0.4290 — no systematic gain |
| **Shuffled positives** | if the optimizer manufactures gains, it would still improve | **0.3452**, materially *worse* than cosine |

The shuffled-positive control is the decisive one: destroying the same-player
correspondence while keeping everything else identical destroys the gain. The
signal comes from genuine within-player stability, not from the fitting
procedure.

Two further guards are permanent tests rather than one-off checks: training
pairs are asserted to contain no held-out player's feature vector, and the
analytic gradient is checked against a numerical one (agreement to 1e-10).

## 6. What the weights say — and what they do not

A weight describes **how much a feature helps identify the same player across
two halves of a season, in this retrieval task**. It is not a statement about
player quality, skill, or importance in football. Nothing here ranks players.

| Highest weight | | Collapsed to ≈0 | |
|---|---|---|---|
| `duels_p90` | 4.35 | `assists_p90` | 0.041 |
| `long_balls_p90` | 2.67 | `defensive_duel_win_pct` | 0.018 |
| `middle_third_share` | 2.56 | `shot_conversion_pct` | 0.002 |
| `passes_p90` | 1.59 | `blocked_shot_pct` | 0.000 |
| `duel_win_pct` | 1.58 | `shots_on_target_pct` | 0.000 |
| `pass_completion_pct` | 1.42 | `take_on_success_pct` | 0.000 |

The pattern is coherent: **the six collapsed features are all sparse
outcome-ratio features** — conversion, on-target share, block share, take-on
success, assists, defensive-duel win rate. Over half a season these are
computed from few events and swing between periods, so they carry little
information about *who* a player is. The features that survive are volume and
positional: how often someone duels, how much they play long, where on the
pitch they operate.

Read carefully, that is a statement about **measurement stability**, not about
what matters in football. A striker's conversion rate is not unimportant; it
is *unstable across half-seasons at this sample size*, which is a different
claim.

3 of 28 features are flagged **unstable** — their weight spans more than 1.0
across the regularization grid, so a single fit does not pin them down. They
are reported in `weight_stability` in the artifact and should not be quoted as
findings.

## 7. Cost

| | |
|---|---|
| Train, selected arm | 5.8 s |
| Train, full grid | 39.3 s |
| Inference, validation split | 1.7 s |
| End-to-end run incl. test | 63.8 s (budget 1,800 s) |
| Artifact | 25.9 KiB (budget 5 MiB) |

**Maintenance delta.** Baseline B has no fitted parameters and never needs
refitting. Adopting the diagonal metric adds a 28-weight vector that must be
versioned, regenerated, and kept in step with the canonical feature set, the
eligible population and the split. It must be refit whenever any of those
change. That recurring cost — not the wall clock — is what the +0.020
practical floor in `D041` exists to justify.

## 8. Decision

**`CONTINUE_NEURAL`.** Both preregistered conditions are met without
exception: validation delta +0.2174 ≥ +0.010, and CI lower bound +0.1686 >
−0.005. `scoutlens-qop.3` may run the neural contrastive arm.

Two things this does **not** decide:

- It does not adopt the diagonal metric. `scoutlens-qop.4` takes the KEEP or
  DROP decision, and it is blocked on `scoutlens-qop.5`.
- It does not change anything public. The showcase still ships Baseline B.

Worth stating plainly for whoever takes the `qop.4` decision: at this effect
size the **+0.020 practical floor is not doing any work**. The metric question
is settled by an order of magnitude. What remains is the interpretability and
maintenance trade — a 28-number weight vector between the published feature
values and the ranking, against a transparent cosine that has none. That is a
judgement about the product, not about the measurement.

## 9. Reproduction

```bash
uv run --frozen python -m scoutlens.benchmark.run_diagonal
uv run --frozen python -m scoutlens.benchmark.run_diagonal --with-test
uv run --frozen pytest tests/benchmark -q
```

Writes `artifacts/benchmark/diagonal-results.json`, carrying the spec hash,
every arm, the weight table, stability, subgroups, costs and the gate
decision.

**On reproducibility.** Every *result* in the artifact — weights, metrics,
intervals, the decision — regenerates identically. Three fields are
observations of the run rather than results and necessarily vary:
`_manifest.generated_at`, `artifact_bytes`, and the `cost` timings required by
the bead's sixth acceptance criterion. The byte-identity check in D040 §4.1 is
applied to the artifact with those excluded; the exclusion is stated here
rather than left for a reader to discover when a rerun fails to match.
