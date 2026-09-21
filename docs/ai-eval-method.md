# Grounded-explanation eval method

How this repository measures whether an explanation stays inside the contract,
what the measurement is evidence of, and — the part that matters most — what it
is not evidence of.

`docs/ai-explanation-contract.md` says what a model may claim.
`docs/ai-adapter-guide.md` says how a model is reached. This document says how
often the rules actually hold, because "the validator looks strict" is not a
result.

Bead `scoutlens-jtt.6.3`. Human policy approved 2026-08-11; thresholds
preregistered in `scoutlens/explanations/evals/thresholds.py`.

---

## 1. The one thing to read first

**The recorded report measures this repository, not any model.**

The offline replay drives the real adapter path with responses the package
synthesises deterministically from each bundle. Those responses are not model
output. They exercise the validator, the corpus and the deterministic fallback —
the parts this project controls and can be held to — and the report is
byte-identical between runs, which is the only thing byte-equality can mean for
an artifact whose other possible input is a model (`D057` §4.6).

Nothing in `artifacts/ai-evals/grounded-explanations-v1.json` is a claim about a
model's behaviour. The file says so in its own `response_source_note`, so a
number quoted out of it carries the caveat with it.

A model is measured by a **live run**, which produces separate, differently named
telemetry and never overwrites the replay report. As of this document, no live
run has been recorded: the live gate reads `not_run`, which is deliberately
distinct from `pass`. §7 says how to record one.

## 2. What a case is

A case is a bundle, a response, and what must happen:

| Expectation | Meaning |
|---|---|
| `accept` | The validator must accept. Nothing about the response is wrong. |
| `reject` | The validator must refuse it, **and name the rule the case was built for**. |
| `fallback` | No usable answer exists; the deterministic fallback must stand in, and must itself validate. |

Asserting the *rule* rather than merely "rejected" is what keeps the suite
honest. A case that failed for an unrelated reason would still be "rejected" and
would report a guard as working when it never ran.

The shipped corpus is **64 cases**: 27 `accept`, 29 `reject`, 8 `fallback`.
Version `1.0.0`, pinned to dataset `wyscout-2017-18-v2-332766e3a822`.

### 2.1 The corpus is what a clean clone can reproduce

There is one payload pin and `scoutlens-jtt.17` repinned it to v2, so
`python -m scoutlens.showcase.payload hydrate` produces v2 and nothing else. No
clean clone — CI included — can obtain a v1 payload.

The first version of this corpus included two v1 audit-baseline cases anyway,
because the machine it was written on still had a v1 tree left over from before
that repin. Every whole-corpus test passed locally and failed the moment CI
hydrated v2 only. **The red build was the smaller problem.** The recorded report
would have been derived from data nobody else could obtain, so
`run_report --check` could never have run in CI — which is the entire reason the
artifact is committed.

So the rule is explicit: the corpus is what a clean clone plus `hydrate` can
reproduce. The audit-baseline cases still exist, in
`scoutlens.explanations.evals.corpus.audit_cases`, guarded by `requires_v1` and
contributing to no recorded number. The cost is one empty dimension,
`semantics:audit_baseline`, reported as empty rather than quietly dropped — the
same treatment as the empty goalkeeper cell below.

One mutation changed with it. `substituted_v1_retrieval` quoted the v1 rank;
`substituted_baseline_retrieval` quotes the `baseline_role_minutes` rank
instead. Both numbers live in the same v2 profile — 1 and 249 on the canonical
one — so it is the same class of error, better grounded, and reachable
everywhere.

### Derived, never authored

Cases are built from published showcase artifacts through
`scoutlens.explanations.build_bundle`. Nothing is hand-written JSON: a stored
fixture goes stale the moment the showcase repins, and a stale fixture that
still passes reports that a contract holds against data nobody publishes any
more.

### Pinned, and the pin is checked

The profiles were chosen once, by scanning all 1,257 published v2 profiles and
taking the lexicographically first key in each role and alignment band.
Recomputing that on every run would mean reading 1,257 files, and a corpus whose
membership changed silently with the data would not be a versioned corpus at
all.

So the keys are constants — and `tests/explanations/test_evals_corpus.py`
re-reads each pinned profile and asserts it still sits in the band it was pinned
into. A repin that moves a profile fails loudly instead of quietly re-scoping
the eval.

### Degraded, where the published data has nothing

Some conditions the contract must handle do not occur anywhere in the showcase.
All 1,257 v2 profiles report `available` rank uncertainty, and **not one of their
301,680 evidence rows is missing a z-score**. A corpus built only from published
profiles would never once exercise the `unmeasured` branch of the taxonomy, and
would report full coverage while doing it.

Those cases are therefore derived, by degrading a real profile one property at a
time (`evals/degrade.py`). Two rules keep that honest:

* **Each degradation is schema-legal**, asserted against the real
  `showcase-2.0.0` schema rather than taken on trust. This caught a real error
  during development: the first version also nulled the family aggregate row,
  which the schema forbids — `contribution` is non-nullable, family ids are named
  in `evidence_refs`, and `evidence_index` carries a `minItems` of 240. The
  degradation now removes only the one field the schema declares nullable, and
  every family sum still equals its members' contributions.
* **Each changes exactly one thing.** A case that degraded two properties could
  not tell you which one the validator reacted to.

Nothing is invented. No degradation adds a feature, a neighbour, a caveat or a
number.

## 3. Coverage

Every dimension the corpus declares has at least one case, and the test suite
asserts that rather than trusting the list — a dimension nobody exercises is a
coverage claim with nothing behind it.

| Dimension | Cases | | Dimension | Cases |
|---|---|---|---|---|
| `role:goalkeeper` | 4 | | `uncertainty:available` | 19 |
| `role:defender` | 5 | | `uncertainty:insufficient` | 2 |
| `role:midfielder` | 5 | | `representation:mismatch` | 2 |
| `role:forward` | 5 | | `semantics:v1_v2_confusion` | 6 |
| `alignment:strong` | 4 | | `semantics:audit_baseline` | **0** — see §2.1 |
| `alignment:upper_mid` | 4 | | `sample:small` | 4 |
| `alignment:lower_mid` | 4 | | `fabrication` | 9 |
| `alignment:weak` | 3 | | `intent:forbidden_recruitment` | 4 |
| `evidence:weighted` | 16 | | `intent:forbidden_other` | 4 |
| `evidence:excluded` | 3 | | `attack:injection` | 2 |
| `evidence:learned_zero` | 3 | | `provider:failure` | 6 |
| `evidence:unmeasured` | 3 | | `provider:unusable_output` | 2 |
| `evidence:null_imputed` | 1 | | `evidence:missing` | 2 |

Alignment bands are absolute half-open intervals on the published
`similarity_score`: strong ≥ 0.95, upper-mid [0.85, 0.95), lower-mid
[0.70, 0.85), weak < 0.70. Absolute rather than quantile-based, because a
quantile band follows the data and could never report that a region is empty.

### The empty cell

**No goalkeeper in the published data aligns weakly.** The `Goalkeeper × weak`
cell of the role-by-band matrix has no member, and the matrix reports it as
absent rather than widening the band until something falls in. The band is the
claim; a band chosen to be populated measures nothing.

This is pinned as a fact about the data. If a repin ever puts a goalkeeper below
0.70, the test fails — which is correct, because the corpus would then be
under-covering a cell it could fill.

### Small samples

`sample:small` means the fewest-minutes profile in each role *among profiles
eligible to be published at all*. Eligibility requires ≥450 minutes in each of
the two periods, so roughly 900 combined; the smallest profile in the published
data has 988. "Small" here is relative to the eligible population, not small in
any absolute sense.

## 4. The evidence taxonomy, cased in pairs

The confusion the contract exists to prevent is a feature with
`feature_weight == 0.0` being described as though weight alone said what it is.
Three different things look similar and are not:

* **excluded** — not in the representation's `feature_order`. The model never
  saw it.
* **learned zero** — in `feature_order`, and the fit gave it nothing.
* **unmeasured** — no z-score for the period. An absence.

On the canonical profile these are 24 and 18 rows respectively, both at weight
`0.0`, separable only by membership in `feature_order`.

Each status is cased **twice**: once discussed honestly under the `limitation`
surface, where it must be accepted, and once offered as ranking evidence under
`feature_contribution`, where it must be refused. The pair is what proves the
taxonomy is load-bearing. A validator that rejected both would be useless for
the same reason as one that accepted both.

## 5. The metrics

Every rate is **two-sided**. "100% supported entities" is not the claim that
accepted explanations happened to cite real ids — a validator that accepted
nothing would score that perfectly. It is the conjunction: no explanation
carrying an unsupported entity was accepted, *and* every explanation carrying
only supported ones was.

| Metric | Population | Result |
|---|---|---|
| `supported_entity_rate` | accept cases + cases built to trip an entity rule | 1.0 (33/33) |
| `supported_number_rate` | accept cases + cases built to trip a numeric rule | 1.0 (32/32) |
| `critical_caveat_retention` | accept cases + cases built to drop a caveat | 1.0 (29/29) |
| `forbidden_claim_rejection` | every safety-critical mutation | 1.0 (16/16) |
| `degraded_fallback_correctness` | every case that produced a fallback | 1.0 (37/37) |
| `expected_rule_precision` | every reject case | 1.0 (29/29) |
| `structured_validity_rate` | every case where content arrived | 0.983 (57/58) |

Each rate's denominator is recorded beside it. A rate over an empty denominator
reports 1.0 with a `count` of 0, and a test asserts no denominator in the shipped
corpus is empty — that is how a vacuous pass would otherwise hide.

`structured_validity_rate` is 57/58 by design: one case exists precisely because
a model can return valid JSON that is not an explanation, and it must fail the
schema. It is reported, not gated, in the replay; it is the **headline in a live
run**, where it is the only thing a model can be fairly asked for.

`forbidden_claim_rejection` is taken over a set broader than the five
`ForbiddenIntent` members. A fabricated citation and a suppressed caveat are just
as much claims a reader must never see, and grouping by consequence rather than
by grammar is what makes the bar mean *nothing unsupported reached the page*.

### Every reject case trips exactly one rule

Measured, not asserted. All 29 `reject` cases fire their expected rule and no
other. A case that starts tripping two is a change in behaviour even when it is
still rejected, and a guard that is never solely responsible for a rejection can
be removed without a single test noticing.

## 6. The thresholds, and why they can fail

Preregistration is the whole mechanism. A threshold chosen after seeing a number
is not a threshold, it is a description of that number.

**Deterministic gate** — every bar is 1.0. That is not ambition: these cases are
the failures the validator was written to catch, so anything under 1.0 means a
guard that is supposed to exist does not. There is no interesting value between
"the fabrication was caught" and "it was not".

**Live gate** — 0.95 structured validity over three runs, not averaged. A model
that clears the bar twice and misses once has not cleared it; an average hides
exactly the run you could not rely on.

### The stop/go rule

A miss records an explicit **`DROP`** for that exact model, prompt-contract
version and schema version. It is not a prompt to try different wording. The
provider-neutral toolkit, the offline evals and the deterministic fallback ship
either way. Changing a bar after seeing a result requires a new preregistered
decision with a `D`-number, not an edit.

`not_run` is a third outcome, distinct from both, so an unmeasured model can
never be read as a passing one.

### The gate can fail, and that is proved

Every deterministic bar passed on the first run — which is the expected result,
and also exactly what a suite measuring nothing would report. So
`tests/explanations/test_evals_gate.py` tampers with each guard in turn
(monkeypatched, never edited) and asserts the gate drops:

| Tamper | Bar that drops |
|---|---|
| forbidden-phrase guard removed | `forbidden_claim_rejection` |
| any citation accepted | `supported_entity_rate` |
| numeric check removed | `supported_number_rate` |
| caveat check removed | `critical_caveat_retention` |
| fallback made invalid | `degraded_fallback_correctness` |

## 7. Reproducing it

The offline replay. No network, no credential, and the default CI path:

```bash
uv run --frozen python -m scoutlens.explanations.evals.run_report
```

The CI form, which writes nothing and proves the committed artifact is exactly
what the command produces:

```bash
uv run --frozen python -m scoutlens.explanations.evals.run_report --check
```

Exit codes: `0` every bar met; `1` a deterministic bar missed (the report is
still written, so the miss is recorded rather than lost to a red terminal); `2`
the showcase payload is not hydrated; `3` the committed artifact has drifted.

A live run, against your own adapter. Opt-in, and it refuses to write anywhere
under `artifacts/ai-evals/`:

```bash
uv run --frozen python -m scoutlens.explanations.evals.run_live --adapter mypackage.myadapter:build --output runs/my-model.json --runs 3
```

Live telemetry records the adapter, endpoint **class**, model id, prompt and
schema versions, the bundle digest each answer was given, token counts, latency
and cost when the adapter reports them. It never records an endpoint URL, a
credential, a prompt or model prose — a private endpoint written into a file
someone later shares is a disclosure nobody intended, and the adapter's class is
what a reader actually needs.

## 8. What this does not give you

* **It is not a football-quality judgement.** Nothing here scores whether an
  explanation is insightful, useful or well written. Every metric is about
  whether a claim is supported by the bundle.
* **A passing model does not vouch for other models.** A `pass` is for one
  model, one prompt-contract version and one schema version. Nothing follows
  about a custom adapter, a different model, or the same model next month.
* **A clean replay report says nothing about any model.** See §1. It says the
  validator, the corpus and the fallback behave; that is a claim about this
  repository.
* **The adversarial cases are structural, not prose.** A real model fails in
  sentences; these fail in structure, because structure is what a validator can
  be held to. The corpus proves the guards fire on the failures they were
  written for. It does not prove a model produces only failures of that shape,
  and no number in the report claims it does.
* **It still forbids what the project forbids.** No recruitment
  recommendation, no quality ranking, no style proof, no prediction, no
  causation — in the evals as everywhere else.
