"""Versioned experiment config + run manifest (D015, beads scoutlens-a72).

Closes the reproducibility gap left open by D013's lightweight fix
(which recorded only git commit + timestamp): experiment parameters now
live in one versioned file, `config/experiment.json`, instead of being
re-declared as inlined constants in each `run_*.py`, and every generated
artifact embeds a `_manifest` recording exactly what produced it —
config (values + file hash), code (git commit + source-tree hash),
environment (Python / Polars / platform), and a sha256 per consumed input
file. The dirty flag prevents an uncommitted run from presenting HEAD as
the whole source state. Two artifacts with equal manifests minus
`generated_at` were produced by the same code, config, and data.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import platform
import subprocess
from pathlib import Path

import polars as pl

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = REPO_ROOT / "config" / "experiment.json"
SOURCE_ROOT = REPO_ROOT / "src" / "scoutlens"


def load_experiment_config(path: Path = CONFIG_PATH) -> dict:
    """Parse the versioned experiment config. No defaults are filled in:
    a missing key should fail loudly at the call site rather than
    silently reverting to a hardcoded value the config no longer
    controls."""
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_source_tree(root: Path = SOURCE_ROOT) -> str:
    """Hash the relative paths and bytes of every scientific Python source.

    Paths are part of the digest so moving or renaming a module changes the
    source identity even when its bytes do not. Length prefixes make the
    stream unambiguous, and sorted POSIX paths keep it platform-independent.
    """
    digest = hashlib.sha256()
    files = sorted(
        (path for path in root.rglob("*.py") if path.is_file()),
        key=lambda path: path.relative_to(root).as_posix(),
    )
    for path in files:
        relative_path = path.relative_to(root).as_posix().encode("utf-8")
        contents = path.read_bytes()
        digest.update(len(relative_path).to_bytes(8, "big"))
        digest.update(relative_path)
        digest.update(len(contents).to_bytes(8, "big"))
        digest.update(contents)
    return digest.hexdigest()


def _git_commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _git_dirty() -> bool | None:
    """Whether tracked files differ from HEAD; None outside a Git checkout."""
    try:
        status = subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=REPO_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return bool(status.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def build_run_manifest(
    config: dict, input_paths: list[Path], config_path: Path = CONFIG_PATH
) -> dict:
    """The provenance block embedded as `_manifest` in every artifact.

    `input_paths` must be every data file the run read — the checksums
    are the point: they tie the published numbers to the exact bytes of
    the (gitignored, locally-built) processed data, which the git commit
    alone cannot do.
    """
    try:
        config_ref = config_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:  # config outside the repo (tests, ad-hoc runs)
        config_ref = config_path.as_posix()
    return {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "git_dirty": _git_dirty(),
        "source_sha256": sha256_source_tree(),
        "python_version": platform.python_version(),
        "polars_version": pl.__version__,
        "platform": platform.platform(),
        "config_path": config_ref,
        "config_sha256": sha256_file(config_path),
        "config": config,
        "inputs": {
            p.name: {"sha256": sha256_file(p), "bytes": p.stat().st_size}
            for p in sorted(input_paths)
        },
    }
