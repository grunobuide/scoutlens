# Writing a ScoutLens model adapter

ScoutLens does not ship a model. It ships a contract, a validator, and one
reference adapter that speaks the OpenAI-compatible HTTP format — so you can
point it at whatever you run locally, or write your own adapter for something
that speaks a different protocol.

This guide is for the second case. Frozen by `scoutlens-jtt.6.2`.

## 1. The shape

An adapter is four members. There is no base class to inherit — the protocol is
structural, so anything with these members satisfies it:

```python
class MyAdapter:
    adapter_id = "my-adapter"        # stable; part of the cache key
    adapter_version = "1.0.0"        # changes when behaviour changes
    model_id = "whatever-i-run"      # the model this instance targets

    def complete(self, request: AdapterRequest) -> AdapterResponse | AdapterFailure:
        ...
```

`complete` receives a provider-neutral `AdapterRequest` — a system prompt, a
user prompt, the bundle digest, and the prompt-contract and schema versions —
and returns a response or a typed failure.

**It must never raise for a model or transport fault.** A failure is an outcome
an eval records beside its successes; an exception pushes callers toward a bare
`except` that erases the reason.

## 2. The failure taxonomy

Six reasons, and the distinctions are the point — each implies a different
action:

| Reason | Means | Retry? |
|---|---|---|
| `timeout` | no response within the deadline | **yes, once** |
| `network` | refused, reset, DNS, or a 5xx | **yes, once** |
| `authentication` | 401 / 403 | no — a second identical call fails identically |
| `rate_limit` | 429 | no — backoff is the caller's policy |
| `invalid_response` | the model answered, and the answer was unusable | no |
| `configuration` | the adapter cannot run at all | no |

### One retry, transport only

A timeout is worth retrying because **the request never landed** — asking again
is asking once. A response that failed validation is not: the model already
answered, the answer was wrong, and asking again turns a measurable refusal into
a slot machine.

`scoutlens-jtt.6.1`'s validator is the arbiter of correctness. Nothing in an
adapter may retry past it.

`invalid_response` is where this bites in practice. A model that replies in
prose instead of JSON has given you a *model-quality* outcome. Record it. Do not
re-roll it.

## 3. Prove it conforms

```bash
uv run --frozen python -m scoutlens.explanations.adapters.conformance \
    --adapter mypackage.myadapter:build
```

`--adapter` takes `module:factory`, where `factory` is a zero-argument callable
returning your adapter. A factory rather than a class because your adapter may
need a client, a local path or an endpoint, and the suite has no business
guessing how to build it.

The suite never calls a real model. It drives your adapter with synthetic
requests, so it is safe in CI with no credential and no network.

What it checks:

| Check | Why |
|---|---|
| `protocol_shape` | the four members are present |
| `identity` | all three identifiers are non-empty strings; the cache key depends on them |
| `returns_result` | nothing escapes as an exception |
| `unknown_digest` | a bundle you have no answer for produces a failure, not invented content |
| `failure_typed` | the reason is a `FailureReason`, `retryable` agrees with the taxonomy, and the detail is actionable |
| `telemetry` | no credential, no prompt content, a real latency |
| `retry_discipline` | a non-transport failure was not retried |

Exit code 0 means every check passed. **A green run says your adapter behaves at
the boundary. It says nothing about whether the model explains well** — that is
`scoutlens-jtt.6.3`, and the conformance suite is not evidence for it.

## 4. Rules that are not negotiable

**Credentials come from the environment.** Never a CLI argument — a key in
`argv` is visible in every process listing on the machine. Never a file in the
repository. Never a log line, where it outlives the run in whatever collects the
logs. The reference adapter reads `SCOUTLENS_MODEL_API_KEY`; yours may name its
own variable, but it reads an environment variable.

**Telemetry carries no secret and no personal data.** Report latency always,
token counts only when the endpoint reports them, cost only when a price was
configured. Do not invent a token count to fill a field, and do not guess what a
model charges.

**No provider SDK in the base runtime.** The reference adapter speaks the wire
format over `requests`, which this project already depends on. That is why one
small adapter reaches llama.cpp, vLLM, Ollama, LM Studio, LocalAI and most
hosted services. If your adapter needs a vendor package, depend on it in *your*
package — not in ScoutLens.

**Offline by default.** The default test and CI path makes no network call and
needs no credential. The recorded eval report is a *replay* of stored responses
(`D057` §4.6); a live run is separate, differently named telemetry that never
overwrites it.

## 5. The stop condition

If a provider capability requires weakening the contract, the validator, or the
offline default, **that provider is unsupported**.

Do not add provider-specific behaviour to the neutral interface to make one
endpoint pass. An interface that grows a special case per vendor is no longer a
contract — it is a compatibility layer pretending to be one, and the next author
cannot tell which parts they are allowed to rely on.

## 6. Running against a local model

The reference adapter needs a base URL and a model id, and has no vendor
default — a default endpoint would make one provider the implicit standard and
send your evidence somewhere you did not choose.

```bash
export SCOUTLENS_MODEL_BASE_URL=http://127.0.0.1:11434/v1
export SCOUTLENS_MODEL_ID=llama3.1:8b
# export SCOUTLENS_MODEL_API_KEY=...   # only if your server needs one
```

Then the opt-in smoke test:

```bash
SCOUTLENS_ONLINE_SMOKE=1 uv run --frozen pytest tests/explanations/test_online_smoke.py -q
```

It skips unless the flag **and** an endpoint are both set. Either alone is a
foot-gun: a stale endpoint variable should not silently start making calls, and
the flag alone should not fail a run with nothing to call.
