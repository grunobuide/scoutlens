# Neural contrastive benchmark — a null result

`scoutlens-qop.3`, the conditional arm. Ran because `scoutlens-qop.2`
recorded `CONTINUE_NEURAL` (`D042`). Decision record for this run: `D043`.

**Spec hash** `39d4e4098e3c6b55f540702de5cee0b3146c94d22b89e1ff5ebc7cd669e62f84`
**Protocol hash** `886ba315b587a91d0fa9ab5c7387f172f8957cf2cfde8a39a65216cb4ff31f1d` (D041)

**Result: the neural projection does not earn its place.** It beats plain
cosine comfortably, and it **loses to the interpretable diagonal metric** —
on test by −0.0419 with a 95% interval entirely below zero.

| Method | Validation MRR | Test MRR |
|---|---|---|
| Baseline B cosine | 0.4290 | 0.4264 |
| Diagonal (qop.2) | **0.6464** | **0.6532** |
| Neural projection | 0.6112 | 0.6113 |

| Comparison | Validation Δ | 95% CI | Test Δ | 95% CI |
|---|---|---|---|---|
| Neural − cosine | +0.1822 | [+0.1367, +0.2288] | — | — |
| Neural − diagonal | −0.0352 | [−0.0756, +0.0004] | **−0.0419** | **[−0.0773, −0.0057]** |

On validation the neural-vs-diagonal interval just touches zero; on test it
does not. Adding a hidden layer and 3,936 parameters made re-identification
*worse* than 28 interpretable weights.

---

## 1. What was run

One frozen architecture family, declared before training: a single hidden
layer projecting the 28 standardized features to a small embedding, scored by
cosine.

    z = W₂ · tanh(W₁x + b₁) + b₂        s(q,c) = cos(z_q, z_c)

| | |
|---|---|
| Depth | 1 hidden layer, fixed — not searched |
| Declared grid | hidden ∈ {32, 64} × embedding ∈ {16, 32} = **4 configurations** |
| Objective | InfoNCE, temperature 0.05, the **same** positives and same-role hard negatives as qop.2 |
| Optimizer | full-batch gradient descent with momentum 0.9, lr 0.05 |
| Early stopping | validation within-role MRR every 25 epochs, patience 3, best checkpoint restored |
| Seeds | fixed for init and negative sampling |

Implemented in numpy with analytic gradients rather than a deep learning
framework. The bead asks for a compact representation and names no
dependency; the modeling contract (`D040`) makes `pyproject.toml` Conditional
on the bead justifying one, and a multi-gigabyte dependency for a two-layer
network over 753 training rows is not justifiable. The gradient is checked
against a numerical one in the test suite (agreement to 1e-6).

### Arms

| Hidden | Embedding | Params | Best val MRR | Best epoch | Early stopped |
|---|---|---|---|---|---|
| 32 | 16 | 1,456 | 0.5429 | 50 | yes |
| 32 | 32 | 1,984 | 0.5785 | 75 | yes |
| 64 | 16 | 2,896 | 0.6016 | 25 | yes |
| **64** | **32** | **3,936** | **0.6112** | 75 | yes |

Selected `hidden=64, embedding=32` on validation. Every arm stopped early.

## 2. Fair comparison, asserted not assumed

Cosine, diagonal and neural are scored on **identical query sets and
identical candidate pools**, checked at runtime rather than trusted: the run
raises if the three methods' query keys differ or if their pool sizes differ.
Test: 253 queries, within-role pools of 20 / 48 / 90 / 95.

The diagonal arm is not retrained here — its weights are read from
`artifacts/benchmark/diagonal-results.json`, so the model compared is exactly
the one qop.2 recorded.

## 3. Calibration — the score is not informative

For each query, the top-1 similarity and whether that top-1 is actually the
same player, binned into score quintiles (test split):

| Top-1 score range | n | Mean score | Top-1 accuracy |
|---|---|---|---|
| 0.622 – 0.795 | 51 | 0.738 | 0.451 |
| 0.795 – 0.840 | 50 | 0.819 | 0.420 |
| 0.840 – 0.871 | 51 | 0.857 | 0.451 |
| 0.871 – 0.909 | 50 | 0.890 | 0.580 |
| 0.909 – 0.981 | 51 | 0.939 | 0.451 |

**Accuracy is flat.** A neural similarity of 0.94 is no more likely to be
correct than one of 0.74. Cosine similarity in the learned embedding space is
a ranking signal, not a confidence signal, and nothing downstream should read
it as one. This matters more than the MRR gap for any product that would want
to say "we are fairly sure about this one".

## 4. By role, and failure cases

| Role | n (test) | Neural MRR | Gates decision |
|---|---|---|---|
| Midfielder | 90 | 0.7170 | no |
| Defender | 95 | 0.5836 | no |
| Forward | 48 | 0.5814 | no |
| Goalkeeper | 20 | 0.3390 | no |

No role reaches the 100-query minimum, so no subgroup gates anything — the
same inert-gate finding as `D041`/`D042`, still owned by `scoutlens-qop.5`.

The ten worst-ranked queries are recorded in the artifact with role and pool
size only. A high rank there means the method failed to re-identify that
player across the two halves of the season. That is a statement about the
measurement, not about the player.

## 5. Limitation worth stating plainly

**The selected configuration is the largest in the declared grid.** Validation
MRR rises monotonically with capacity across all four arms (0.543 → 0.579 →
0.602 → 0.611), so a larger network might close the gap to the diagonal
metric.

That does **not** license running one. Extending the grid after seeing the
result is architecture search — an explicit non-goal of this bead — and a
post-hoc grid extension is exactly what preregistration exists to prevent. If
someone wants to test more capacity, it needs a new preregistration with its
own hash and its own decision record, and the result of *this* run stands on
the record either way.

The honest reading is therefore narrow: **within the declared family and
budget, the neural projection does not beat the diagonal metric.** It is not
a claim that no neural model ever could.

## 6. Cost

| | |
|---|---|
| Train, all four arms | 39.8 s |
| End-to-end incl. test | 49.7 s (budget 1,800 s) |
| Peak RSS | 1.42 GiB (budget 4 GiB) |
| Artifact | 17.7 KiB (budget 5 MiB) |
| Selected model | 3,936 parameters |

Against the diagonal metric's 28 weights, the neural model is two orders of
magnitude more parameters, is not interpretable feature by feature, produces
an uncalibrated score, and performs worse. There is no axis on which it wins.

## 7. Consequence

`scoutlens-qop.4` takes the KEEP or DROP decision and is blocked on
`scoutlens-qop.5`. This run contributes one clear input: **the neural arm is
out.** The live question is diagonal versus cosine, which is the
interpretability and maintenance trade described in
[`diagonal-metric-benchmark.md`](diagonal-metric-benchmark.md) §7.

Nothing public changes. The showcase still ships Baseline B.

This is a null result and it is published as one, per the project's standing
position that a null is a result. It is not a reason to try again differently
without a new preregistration.

## 8. Reproduction

```bash
uv run --frozen python -m scoutlens.benchmark.run_neural
uv run --frozen python -m scoutlens.benchmark.run_neural --with-test
uv run --frozen pytest tests/benchmark -q
```

Writes `artifacts/benchmark/neural-results.json`: gate evidence read from
qop.2, every arm with its learning curve and checkpoint digest, the
three-way comparison, calibration, subgroups, failure cases and costs.

As in qop.2, the `cost` timings, `peak_rss_bytes`, `artifact_bytes` and
`_manifest.generated_at` are observations of the run rather than results and
are excluded from any byte-identity check.

Every other value regenerates identically, including the learning curves and
the per-arm checkpoint digests. Reported calibration statistics pass through
the same 12-significant-digit precision pin introduced in `D041`: numpy
reduces sums in parallel, so an unquantized bin mean drifted in its last ULPs
between runs even with bit-identical checkpoints.
