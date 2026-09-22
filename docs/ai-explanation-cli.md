# The local explanation CLI

How to generate one grounded explanation on your own machine, plug in your own
model, and reproduce the evaluation report — without a credential for any
particular vendor, and without editing ScoutLens source.

Bead `scoutlens-jtt.6.4`. The contract it enforces is
[`ai-explanation-contract.md`](ai-explanation-contract.md); the adapter boundary
is [`ai-adapter-guide.md`](ai-adapter-guide.md); the evaluation method is
[`ai-eval-method.md`](ai-eval-method.md).

---

## 1. The thirty-second version

```bash
uv sync --frozen --all-groups
uv run --frozen python -m scoutlens.showcase.payload hydrate
uv run --frozen python -m scoutlens.explanations.cli explain --profile wy-8287-c-795
```

No credential, no network, no model. You get a validated explanation in which
every number is traceable to the published artifact it was copied from, and
every sentence cites evidence that exists.

## 2. What the default explainer is, and why it is not a model

The default `--adapter` is `deterministic`: it builds the explanation the bundle
supports, directly from the bundle. The output says so — `model_id: none`, and
a closing line stating that no model produced the text.

This is not a placeholder. It does two jobs:

* **It proves the contract is satisfiable.** A validator that rejected
  everything would look, from the outside, exactly like a strict one. Something
  has to pass, and the deterministic explainer is the thing that passes.
* **It sets the bar honestly.** A model is not being asked to do something no
  program can do. It is being asked to say the same things *better* — and it is
  held to the identical validator, with no exemption for being a model.

So the interesting comparison is not "did the model produce output" but "did the
model clear a bar a plain function already clears".

## 3. Running your own model

An adapter is any object with `adapter_id`, `adapter_version`, `model_id` and
`complete(request)`. Nothing else, and nothing provider-specific — see
[`ai-adapter-guide.md`](ai-adapter-guide.md).

Check it against the boundary first. This never calls a real model, so it is
safe with no credential:

```bash
uv run --frozen python -m scoutlens.explanations.cli conformance --adapter mypackage.myadapter:build
```

Then use it:

```bash
uv run --frozen python -m scoutlens.explanations.cli explain \
    --profile wy-8287-c-795 --adapter mypackage.myadapter:build --online
```

`--adapter` takes `module:factory` — an importable module and a **zero-argument
factory** in it. A factory rather than a class because construction is yours:
your adapter may need a client, a local path or an endpoint, and this tool has
no business guessing.

The shipped reference adapter,
`scoutlens.explanations.adapters.openai_compat:OpenAICompatibleAdapter`, speaks
the OpenAI-compatible wire format to any `base_url` you configure — llama.cpp,
vLLM, Ollama, or a hosted service — with no provider SDK in the base runtime.

## 4. Offline by default, and enforced

Without `--online` the process **refuses to open a socket**. The guard wraps the
adapter call, so an adapter that tries to reach a network fails with exit code 4
and a clear message rather than quietly succeeding.

That makes "the default path is offline" a property of the code rather than a
claim about intent — which matters, because it is the kind of claim nobody
re-checks once it is written down.

Credentials come from `SCOUTLENS_MODEL_API_KEY` in the environment and from
nowhere else. There is no `--api-key` flag and there never will be: arguments
land in shell history, in `ps` output and in CI logs, and a secret that has been
in any of those has to be rotated. A test asserts no CLI option can carry one.

## 5. What a refused answer does

If the adapter fails, or its answer does not match the output schema, or the
validator rejects it, the command returns the **typed deterministic fallback**
and exits non-zero.

| Exit | Meaning |
|---|---|
| 0 | validated explanation |
| 1 | fallback returned — the generated answer was refused |
| 2 | showcase artifacts missing; hydrate first |
| 3 | usage error (bad adapter spec, unknown profile) |
| 4 | an adapter tried to reach the network while offline |

**The refused output is never printed, never written and never persisted.** That
is the stop condition on this bead, and it is checked on both channels the tool
can leak through: a test plants a forbidden recruitment claim in a model's
answer and asserts the giveaway phrase appears in neither stdout, stderr, nor
the `--output` file.

The fallback is itself put through the same validator. A fallback exempted from
validation would be the one unchecked path in the system, and the one an
incident would travel down — it runs precisely when something has already gone
wrong.

## 6. What the record contains

`--format json` (or `--output`) emits the full record:

* **provenance** — profile key, dataset version, representation id, ranking
  method, the bundle digest (the evidence hash the explanation answered),
  prompt-contract and output-schema versions, adapter id/version and model id.
* **explanation** — the validated claims, each citing evidence ids that resolve.
* **telemetry** — latency, and token counts and cost when the adapter reports
  them. Never invented: an adapter that does not report tokens leaves them null.
* **fallback_reason** and **rejected_rules**, when the answer was refused.

No endpoint URL and no credential ever appear. An endpoint is often private
infrastructure, and a URL in a file someone later shares is a disclosure nobody
intended.

Rendered text never calls the similarity score a *confidence* or a plain
*cosine*. A similarity is a distance under a fitted representation; a confidence
would be a statement about how sure the system is, which this study never
estimates; and unweighted cosine is the audit baseline rather than the published
score (`D045`, `D047`, `D049`).

## 7. Reproducing the evaluation report

```bash
uv run --frozen python -m scoutlens.explanations.evals.run_report --check
```

`--check` writes nothing and proves the committed
`artifacts/ai-evals/grounded-explanations-v1.json` is exactly what the command
produces. Drop `--check` to regenerate it. Both are offline and need no
credential.

Read [`ai-eval-method.md`](ai-eval-method.md) before quoting a number from that
file: the replay measures the validator, the corpus and the fallback, and is not
evidence about any model.

To put a real model through the corpus:

```bash
uv run --frozen python -m scoutlens.explanations.evals.run_live \
    --adapter mypackage.myadapter:build --output runs/my-model.json --runs 3
```

That writes telemetry, never a recorded result, and refuses to write anywhere
under `artifacts/ai-evals/`.

## 8. Other commands

```bash
# a few valid profile keys to try
uv run --frozen python -m scoutlens.explanations.cli profiles --limit 10

# the frozen v1 cosine audit baseline, reachable only by asking for it
uv run --frozen python -m scoutlens.explanations.cli explain \
    --profile wy-8287-c-795 --audit-baseline
```

The v2 representation is the default and v1 is never reached by omission:
`build_bundle` refuses a v1 profile that was not explicitly flagged, which is
the guard that stops a v1 explanation being presented with v2 semantics.

Note that a clean clone **cannot** run `--audit-baseline`: there is one payload
pin and it hydrates v2 only, so no v1 profiles are available. See
`scoutlens-jtt.18`.

## 9. What this tool does not do

* It does not recompute anything. Every number is copied from a published
  artifact; the CLI computes no similarity, no rank, no percentile and no
  interval.
* It does not judge football. The validator checks whether a claim is
  *supported*, never whether it is insightful.
* It makes no recommendation, ranks nobody by quality, asserts no playing
  style, predicts nothing and claims no causation — in the CLI as everywhere
  else in this project.
* It is not a web feature. There is no AI anywhere in the published site, and
  nothing here runs in a browser or a backend.
