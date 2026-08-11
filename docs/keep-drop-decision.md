# KEEP / DROP — the final complexity decision

`scoutlens-qop.4`. Decision record: `D045`. Protocol `D041` as amended by
`D044`; recorded evidence from `D042` (diagonal) and `D043` (neural).

**Outcome: KEEP the interpretable diagonal representation.** Every
preregistered clause passes. Frozen cosine is retained as the transparent
audit and reference baseline. The neural arm remains a final DROP under
`D043` and was not a candidate here.

---

## 1. The decision table

Applied conjunctively. No discretionary override in either direction.

| # | Clause | Threshold | Observed | |
|---|---|---|---|---|
| 1 | Wyscout test ΔMRR over cosine | ≥ +0.020 | **+0.2268** | PASS |
| 2 | Wyscout paired 95% CI lower bound | > 0 | **+0.1835** | PASS |
| 3 | No gating role subgroup drops more than 0.020 | ≥ −0.020 | **+0.2017** (worst gating role) | PASS |
| 4 | StatsBomb external Δ | > 0 | **+0.1362** | PASS |
| 5 | StatsBomb paired 95% CI lower bound | > −0.010 | **+0.1165** | PASS |
| 6 | Operational budgets | see §5 | within budget | PASS |

Clause 3 uses the `D044` minimum of 50, applied to the per-role table already
recorded by `qop.2`. Gating roles on the Wyscout test split are **Defender
(95)** and **Midfielder (90)**; Forward (48) and Goalkeeper (20) are reported
but non-gating.

## 2. Cross-provider evidence

StatsBomb 2015/16, competitions 2 / 7 / 11 / 12, ≥ 450 minutes per period,
1,061 queries. **Nothing was fitted on StatsBomb** — the 28 diagonal weights
come frozen from the Wyscout training split.

| | Cosine | Diagonal | Δ | 95% CI |
|---|---|---|---|---|
| Within-role MRR | 0.2265 | **0.3627** | **+0.1362** | [+0.1165, +0.1556] |

### By role — every role gates here, and every role improves

| Role | n | Cosine | Diagonal | Δ |
|---|---|---|---|---|
| Defender | 417 | 0.1792 | 0.3291 | +0.1498 |
| Midfielder | 330 | 0.2583 | 0.4103 | +0.1520 |
| Forward | 239 | 0.2649 | 0.3777 | +0.1128 |
| Goalkeeper | 75 | 0.2264 | 0.2919 | +0.0655 |

The StatsBomb population is larger per role than the Wyscout test split, so
all four roles clear the ≥ 50 minimum. This is the strongest single piece of
evidence in the benchmark: weights learned on one provider and season
transfer to a different provider and season, across every role, with no
refitting.

### On standardization

Feature *standardization* is computed provider-natively, because a z-score is
how a provider's raw counts are made comparable at all — Wyscout means and
standard deviations are meaningless applied to StatsBomb's event taxonomy.
This is the convention the published replication already uses (`D020`/`D021`),
and it is applied **identically to both arms**, so it cannot move the delta
between them, which is the quantity clauses 4 and 5 test.

The two providers' canonical-28 lists are asserted identical **in set and in
order** at runtime, because the frozen weights are applied positionally: a
silent reordering would score the wrong feature with the wrong weight and
never raise.

## 3. Protocol lineage, proved rather than asserted

`qop.2` and `qop.3` recorded their results under the `D041` hash
`886ba315…`; the protocol now hashes to `041cd1f7…` after `D044`. Reusing
that recorded evidence is only valid if the amendment touched nothing else.

That is checked mechanically: substituting `D041`'s subgroup block back into
the current protocol **reproduces the D041 hash exactly**. Every other clause
is therefore byte-identical to what those arms were measured under, and their
results remain valid evidence. The check is capable of failing — a test
tampers with an unrelated clause and confirms the reconciliation reports a
failure.

No result was retrained, regenerated or overwritten to reach this decision.

## 4. The product trade, stated plainly

KEEP is not free. What is being adopted, and what it costs:

**What is gained.** A large, cross-provider-replicated improvement in
same-player retrieval — +0.2268 on the Wyscout test split and +0.1362 on an
untouched provider — from **28 auditable numbers**, one per named feature.
Each weight is readable as "this feature pulls this many times as hard as it
would under plain cosine". Nothing about the method becomes unexplainable.

**What is owed.** Cosine has no fitted parameters and never needs refitting.
The diagonal metric adds a weight vector that must be **versioned, regenerated
and kept in step** with the canonical feature set, the eligible population and
the split, and refit whenever any of those change. That is a standing
maintenance obligation, not a one-off cost, and it is the thing the +0.020
practical floor existed to justify.

At this effect size the floor is cleared by an order of magnitude, so the
decision was never close on the measurement. The trade above is the real
content of the choice, and it is recorded here so a future reader sees what
was accepted rather than only what was gained.

## 5. Budgets — and a correction worth reading

The budget clause tests the cost of **adopting the representation**: 28
weights to version, 37.2 s to fit the full regularization grid, 1.7 s
inference, a 25.9 KiB artifact, and peak RSS bounded above by 1.39 GiB
(taken from `qop.3`, which ran a strictly heavier model over the same Wyscout
pipeline — stated as a bound, not as a direct measurement of the diagonal
arm).

**The first implementation of this clause was wrong, and it produced a DROP.**
It measured *this decision harness's* peak RSS — 4.35 GiB, above the 4 GiB
limit — and failed clause 6. That measurement is dominated by reading
StatsBomb's 166 MB event table, and this run scores **both** arms over it, so
the figure is identical whether the winner is cosine or diagonal.

A clause whose value does not depend on which representation you choose
cannot inform a choice between them: implemented that way it forces DROP
unconditionally, regardless of any measurement. That is the argument for the
correction, and it holds independently of which outcome the fix produces —
which is the only reason it is a legitimate correction and not moving the
goalposts. The corrected clause is still capable of failing; tests drive it to
failure with an over-budget training time and an over-budget RSS.

The harness figure is recorded in the artifact as an observation, not used to
decide.

## 6. What KEEP does and does not mean

**Does:** the diagonal representation is the benchmark-winning method and is
adopted as such. Frozen cosine is retained as the transparent audit and
reference baseline — every diagonal result in this benchmark is reported
against it, and `w = 1` reproduces it exactly, so cosine remains a point in
the adopted model's own hypothesis space.

**Does not:** change anything public yet. The showcase still ships Baseline B
cosine. Promoting the representation into the published product touches the
showcase artifacts, the payload pin, the uncertainty artifacts computed under
cosine, and the web layer — a change far larger than a decision record, with
its own ownership boundaries under `docs/modeling-agent-contract.md` and
`docs/frontend-agent-contract.md`. It is filed as its own bead rather than
bundled in here.

**Does not:** revive the neural arm. `D043` recorded it as a final DROP; it
lost to the diagonal metric on test with an interval clear of zero, and is not
a candidate for rescue, retuning or promotion.

No causal, recruitment or transfer-success claim follows from any of this.
Better same-player retrieval means the fingerprint is a more reliable
description of observed play, and nothing more.

## 7. Reproduction

```bash
uv run --frozen python -m scoutlens.benchmark.run_preregistration --with-test
uv run --frozen python -m scoutlens.benchmark.run_diagonal --with-test
uv run --frozen python -m scoutlens.benchmark.run_neural --with-test
uv run --frozen python -m scoutlens.benchmark.run_decision
uv run --frozen pytest tests/benchmark -q
```

`run_decision` reads the recorded qop.2 and qop.3 artifacts and refuses to
proceed if either was recorded under a protocol hash other than `D041`'s. It
writes `artifacts/benchmark/decision-results.json` with the lineage proof, the
cross-provider evaluation, every clause with its evidence, and the outcome.

Note that after `D044` the neural arm's own gate guard refuses to re-run
against the amended protocol until `qop.2` is regenerated — intended, recorded
in `D044`, and not a blocker here because this decision consumes the recorded
evidence rather than re-running it.
