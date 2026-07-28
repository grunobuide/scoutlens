"""Canonical JSON and recoverable directory publication primitives."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize portable, deterministic UTF-8 JSON with a trailing newline."""
    text = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return (text + "\n").encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_canonical_json(path: Path, value: Any) -> bytes:
    payload = canonical_json_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return payload


def canonical_content_digest(files: Mapping[str, Any]) -> str:
    """Hash logical paths and canonical placeholder-version payloads.

    The dataset version cannot hash bytes that already contain that version
    without creating a circular fixed-point problem. Builders therefore pass
    their semantic payloads with a stable ``__DATASET_VERSION__`` placeholder.
    Paths and length prefixes make the digest unambiguous and independent of
    filesystem order.
    """
    digest = hashlib.sha256()
    for relative_path in sorted(files):
        path_bytes = relative_path.encode("utf-8")
        payload = canonical_json_bytes(files[relative_path])
        digest.update(len(path_bytes).to_bytes(8, "big"))
        digest.update(path_bytes)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def make_staging_directory(target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=f".{target.name}-staging-", dir=target.parent))


def publish_directory(staging: Path, target: Path) -> None:
    """Replace ``target`` only after a complete staging directory exists.

    The previous directory is retained until the new directory has moved into
    place and is restored if that move fails. Targets are constrained to a
    single explicit directory; callers cannot pass a filesystem root.
    """
    staging = staging.resolve()
    target = target.resolve()
    if not staging.is_dir():
        raise ValueError(f"staging directory does not exist: {staging}")
    if target == Path(target.anchor) or target.parent == target:
        raise ValueError(f"refusing broad publication target: {target}")
    if staging.parent != target.parent:
        raise ValueError("staging and target must be siblings for atomic publication")

    backup: Path | None = None
    if target.exists():
        backup = target.with_name(f".{target.name}-backup-{uuid.uuid4().hex}")
        target.replace(backup)
    try:
        staging.replace(target)
    except Exception:
        if backup is not None and backup.exists() and not target.exists():
            backup.replace(target)
        raise
    if backup is not None:
        shutil.rmtree(backup)


def discard_staging(staging: Path) -> None:
    if staging.exists() and staging.is_dir():
        shutil.rmtree(staging)

