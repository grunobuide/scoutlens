# Diagonal representation — direct adoption-cost measurement

`scoutlens-qop.6.1`. Evidence for the operational interpretation `D045`
recorded, measured directly rather than by proxy.

**Outcome: PASS.** The frozen diagonal adoption path fits, serializes and
scores inside every `D041` budget, with the maximum across three
fresh-process repetitions used as the gate.

This ratifies only the operational interpretation needed before promotion. It
does not re-decide KEEP, does not authorize a public change, and changes no
recorded result.

---

## 1. Why this measurement exists

`D045` argued that the 4.35 GiB peak observed in the `qop.4` decision harness
is StatsBomb ingestion, shared by cosine and diagonal alike, and therefore not
the cost of adopting the diagonal representation. It then quoted the diagonal
arm's own peak as an **upper bound** borrowed from the `qop.3` neural run,
because `qop.2` never recorded RSS directly.

An upper bound taken from a different model is a reasonable argument, not a
measurement. This replaces it with the direct number.

## 2. What was measured

| Included — adoption cannot happen without it | Excluded — both representations pay it equally |
|---|---|
| Wyscout load, period profiles, eligible population and split | StatsBomb ingestion and cross-provider scoring |
| train-only scaler fit | the `qop.4` dual-arm decision harness |
| training pair and hard-negative construction | cosine scoring as a comparison arm |
| the full frozen regularization grid (6 arms) | |
| serialization of the model adoption would version | |
| selected-arm inference over the validation split | |

The exclusions are the point of the exercise: charging a shared pipeline cost
to one of two candidates measures the pipeline, not the choice. The inclusions
are equally the point — every cost that exists *because* the representation is
adopted is inside the measured path, including the whole grid rather than only
the selected arm, because selecting requires fitting all of it.

## 3. Identity binding

A cost measured for a different model says nothing about this one, so each
repetition is bound to the recorded artefacts **before** any budget is
evaluated. If any check fails the command stops and reports `STOP` without
looking at the numbers.

| Anchor | Value |
|---|---|
| D042 spec hash | `47488d603e9246f45fdd3e3d0aa95835bb569e5793444b87950c34e2531aa3bd` |
| D044 protocol hash | `041cd1f7f514133a7e3c45724fef5c7fc1369d0115b8718f6b67f3177e60b4ce` |
| Split assignment digest | `715bdb90af59860c2510d6a69f43970c9734bef4e4e061740658d2496c30d96a` |
| Selected regularization | `0.0` |
| Weights | 28 |

All three runs reproduced the recorded weight vector digit-for-digit — the
training path is deterministic, so re-fitting yields the same 28 weights
`qop.2` recorded. `identity bound: True`.

## 4. Measurements

Three repetitions, each in a **fresh child process**. Peak RSS is a
per-process high-water mark, so repetitions sharing a process would inherit
each other's memory and the second and third numbers would be meaningless.

| Run | Wall | Peak RSS | Serialized | Grid | Inference |
|---|---|---|---|---|---|
| 1 | 30.3 s | 1.46 GiB | 7,462 B | 28.2 s | 1.4 s |
| 2 | 28.3 s | 1.40 GiB | 7,462 B | 26.5 s | 1.3 s |
| 3 | 23.6 s | 1.42 GiB | 7,462 B | 21.7 s | 1.4 s |
| **max** | **30.3 s** | **1.46 GiB** | **7,462 B** | | |

Serialized size is identical across runs, as a deterministic model
serialization should be.

### Against the frozen budgets

| Budget | Limit | Maximum observed | Headroom | |
|---|---|---|---|---|
| Wall clock per arm | 1,800 s | 30.3 s | 59× | PASS |
| Peak RSS | 4 GiB | 1.46 GiB | 2.7× | PASS |
| Serialized artifact | 5 MiB | 7,462 B | 700× | PASS |

**Gated on the maximum, not the best run.** A best-of-three would understate
what adoption costs on a bad day, which is precisely the number a budget
exists to bound.

### The proxy was accurate

`D045` quoted 1.39 GiB as an upper bound from the neural run. The directly
measured maximum is **1.46 GiB** — slightly *above* that bound, because the
neural run's recorded peak came from a differently-ordered process, not
because the diagonal path is heavier than claimed. Either way both figures sit
far inside the 4 GiB limit, so the D045 conclusion is ratified while the bound
it relied on is now superseded by direct measurement.

Stating this plainly matters: the proxy was directionally right but not
conservative, and a bound that can be exceeded by the thing it bounds should
not be load-bearing. It no longer is.

## 5. Recorded results are untouched

`artifacts/benchmark/diagonal-results.json`, `neural-results.json` and
`decision-results.json` are byte-identical before and after this measurement,
verified by SHA-256 and byte count. The model this command serializes is
written to a temporary directory purely so its size can be measured, and is
discarded. No frozen config, threshold, weight or metric changed.

## 6. Machine and runtime

| | |
|---|---|
| OS | Windows 11 (10.0.26200) |
| CPU | Intel64 Family 6 Model 183, 20 logical cores |
| RAM | 31.8 GiB |
| Python | 3.14.4 |
| Polars | 1.42.1 |
| NumPy | 2.3.5 |
| Repo | `341300e` |

These numbers are machine-specific. The budgets are absolute limits rather
than a comparison against this hardware, and the headroom is wide enough
(59× / 2.7× / 700×) that the conclusion is not sensitive to a slower machine —
though a machine with materially less RAM should re-run before relying on the
RSS result.

## 7. Reproduction

```bash
uv run --frozen python -m scoutlens.benchmark.run_adoption_cost --repeat 3
uv run --frozen pytest tests/benchmark/test_adoption_cost.py -q
```

The command exits non-zero on `STOP`, so it is usable as a gate. Every budget
gate is proven capable of failing by tests that drive each one past its limit,
and the boundary itself is pinned: exactly at the limit passes, one unit over
fails.
