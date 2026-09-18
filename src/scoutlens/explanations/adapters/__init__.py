"""Model adapters for the grounded-explanation contract.

The adapter is the only component in this package that talks to a model.
Everything around it — bundle, validator, evals — is deterministic and offline,
which is what makes a model's contribution measurable rather than assumed.

* `protocol` — the neutral boundary: request, response, typed failures, and the
  retry rule that transport faults get one more attempt and answered-but-wrong
  gets none.
* `fake` — `ScriptedAdapter` for offline replay, `FaultAdapter` for proving each
  failure reason is reachable and distinct.
* `openai_compat` — the reference adapter, speaking the OpenAI-compatible wire
  format over `requests`. No provider SDK, so a clone can point it at
  llama.cpp, vLLM, Ollama or a hosted service without changing this package.
* `cache` — six-part evidence-keyed cache, so a stale answer cannot be served
  under a changed prompt, schema or adapter.
* `conformance` — the suite and CLI a project user runs against their own
  adapter. Deliberately **not** re-exported here: importing it from the package
  `__init__` makes `python -m …adapters.conformance` emit a `RuntimeWarning`
  about double import, and that command is the one this project tells adapter
  authors to run. Import it from its own module.

Nothing here judges explanation quality. A conforming adapter is one that
behaves at the boundary; whether the model says anything worth reading is
`scoutlens-jtt.6.3`'s question.
"""

from __future__ import annotations

from scoutlens.explanations.adapters.cache import ResponseCache, cache_key
from scoutlens.explanations.adapters.fake import FaultAdapter, ScriptedAdapter
from scoutlens.explanations.adapters.openai_compat import OpenAICompatibleAdapter
from scoutlens.explanations.adapters.protocol import (
    ADAPTER_PROTOCOL_VERSION,
    RETRYABLE,
    AdapterError,
    AdapterFailure,
    AdapterRequest,
    AdapterResponse,
    AdapterResult,
    AdapterUsage,
    ExplanationAdapter,
    FailureReason,
)

__all__ = [
    "ADAPTER_PROTOCOL_VERSION",
    "RETRYABLE",
    "AdapterError",
    "AdapterFailure",
    "AdapterRequest",
    "AdapterResponse",
    "AdapterResult",
    "AdapterUsage",
    "ExplanationAdapter",
    "FailureReason",
    "FaultAdapter",
    "OpenAICompatibleAdapter",
    "ResponseCache",
    "ScriptedAdapter",
    "cache_key",
]
