"""Read the published showcase artifacts an explanation is derived from.

One reader, because there is one set of published files and two consumers: the
eval corpus and the CLI. It lived in `evals.corpus` until `jtt.6.4` needed it
from outside, and a CLI importing the eval suite's internals to read a profile
would have been the wrong dependency in the wrong direction.

It reads and caches. It validates nothing beyond presence — the showcase
schema is `scoutlens.showcase`'s boundary, and re-checking it here would put a
second opinion about artifact validity in a module that has no business holding
one.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SHOWCASE_ROOT = REPO_ROOT / "public" / "showcase"

HYDRATE_COMMAND = "uv run --frozen python -m scoutlens.showcase.payload hydrate"


class ShowcaseUnavailable(RuntimeError):
    """The published artifacts are not present in this checkout.

    Raised rather than returning empty, because a caller that silently got
    nothing would report zero cases passing zero checks and look like a clean
    run. `public/showcase/*/players/` is gitignored, so this is the normal
    state of a fresh clone and the message says what to do about it.
    """


@dataclass
class ShowcaseArtifacts:
    """Reads published profiles, the representation and the manifest."""

    root: Path = field(default_factory=lambda: DEFAULT_SHOWCASE_ROOT)
    _cache: dict[tuple[int, str], dict[str, Any]] = field(default_factory=dict, repr=False)

    def available(self) -> bool:
        return (self.root / "v2" / "representation.json").exists()

    def _read(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            raise ShowcaseUnavailable(
                f"{path} is not present. Hydrate the showcase payload first:\n    "
                f"{HYDRATE_COMMAND}"
            )
        return json.loads(path.read_text(encoding="utf-8"))

    def profile(self, profile_key: str, *, major: int = 2) -> dict[str, Any]:
        cached = self._cache.get((major, profile_key))
        if cached is None:
            cached = self._read(self.root / f"v{major}" / "players" / f"{profile_key}.json")
            self._cache[(major, profile_key)] = cached
        return cached

    def representation(self) -> dict[str, Any]:
        return self._read(self.root / "v2" / "representation.json")

    def dataset_version(self) -> str:
        return str(self._read(self.root / "v2" / "manifest.json")["dataset_version"])

    def index(self) -> list[dict[str, Any]]:
        return list(self._read(self.root / "v2" / "players.index.json")["profiles"])


__all__ = [
    "DEFAULT_SHOWCASE_ROOT",
    "HYDRATE_COMMAND",
    "REPO_ROOT",
    "ShowcaseArtifacts",
    "ShowcaseUnavailable",
]
