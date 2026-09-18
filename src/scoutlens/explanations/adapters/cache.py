"""Evidence-keyed response cache.

The key is what makes this safe. It covers the adapter, its version, the model,
the prompt-contract version, the output schema version and the bundle digest —
six things, every one of which changes what a correct answer looks like.

Leave any of them out and the cache starts lying. Drop the prompt version and a
rewritten instruction serves yesterday's answers; drop the schema version and an
output shaped for the old contract passes as current; drop the adapter version
and a fixed bug keeps returning its own bug. A cache that can serve a stale
answer under a new contract is worse than no cache, because the staleness is
invisible in exactly the runs that matter.
"""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scoutlens.explanations.adapters.protocol import AdapterRequest


def cache_key(
    *,
    adapter_id: str,
    adapter_version: str,
    model_id: str,
    request: AdapterRequest,
) -> str:
    """The six-part identity of one model call."""
    material = {
        "adapter_id": adapter_id,
        "adapter_version": adapter_version,
        "model_id": model_id,
        "prompt_contract_version": request.prompt_contract_version,
        "schema_version": request.schema_version,
        "bundle_digest": request.bundle_digest,
    }
    encoded = json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass
class ResponseCache:
    """In-memory, optionally mirrored to disk.

    Deliberately not an LRU and not size-bounded: an eval run is hundreds of
    calls, not millions, and an eviction policy would introduce a second reason
    for a miss that nobody could distinguish from a key change.
    """

    directory: Path | None = None

    def __post_init__(self) -> None:
        self._memory: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()
        if self.directory is not None:
            self.directory.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path | None:
        return None if self.directory is None else self.directory / f"{key}.json"

    def get(self, key: str) -> dict[str, Any] | None:
        with self._lock:
            hit = self._memory.get(key)
        if hit is not None:
            return hit

        path = self._path(key)
        if path is None or not path.exists():
            return None
        try:
            stored = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            # A corrupt entry is a miss, never an error. The call is repeatable;
            # failing the run over a damaged cache file would be the cache
            # deciding an outcome it has no business deciding.
            return None
        with self._lock:
            self._memory[key] = stored
        return stored

    def put(self, key: str, content: dict[str, Any]) -> None:
        with self._lock:
            self._memory[key] = content
        path = self._path(key)
        if path is None:
            return
        # Write-then-rename so a crash mid-write cannot leave a half-file that
        # a later run would read as a legitimate response.
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(content, sort_keys=True), encoding="utf-8")
        temporary.replace(path)

    def __len__(self) -> int:
        with self._lock:
            return len(self._memory)


__all__ = ["ResponseCache", "cache_key"]
