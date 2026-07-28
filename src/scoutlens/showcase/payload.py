"""Deterministic packaging and fail-closed hydration for showcase profiles.

The complete player-profile directory is intentionally excluded from Git. This
module turns the exporter output into a content-addressed release asset and can
hydrate a clean clone without access to provider or processed data.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import tarfile
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import requests

from scoutlens.evaluation.run_manifest import REPO_ROOT
from scoutlens.showcase.io import canonical_json_bytes, discard_staging, make_staging_directory, publish_directory
from scoutlens.showcase.schema import validate_schema

PAYLOAD_CONTRACT = "scoutlens.showcase-payload-pack"
PAYLOAD_SCHEMA_VERSION = "1.0.0"
PAYLOAD_FORMAT = "tar+gzip"
MAX_ARCHIVE_BYTES = 25 * 1024 * 1024
DEFAULT_SHOWCASE_ROOT = REPO_ROOT / "public" / "showcase" / "v1"
DEFAULT_MANIFEST_PATH = DEFAULT_SHOWCASE_ROOT / "manifest.json"
DEFAULT_OUTPUT_DIR = DEFAULT_SHOWCASE_ROOT / "players"
DEFAULT_METADATA_PATH = REPO_ROOT / "config" / "showcase-payload-pack.json"
SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")


@dataclass(frozen=True)
class PayloadMetadata:
    dataset_version: str
    filename: str
    sha256: str
    archive_bytes: int
    path_count: int
    url: str


@dataclass(frozen=True)
class PayloadBuild:
    dataset_version: str
    filename: str
    sha256: str
    archive_bytes: int
    path_count: int

    def as_dict(self) -> dict[str, int | str]:
        return {
            "archive_bytes": self.archive_bytes,
            "dataset_version": self.dataset_version,
            "filename": self.filename,
            "path_count": self.path_count,
            "sha256": self.sha256,
        }


def _require_exact_keys(value: dict[str, Any], expected: set[str], *, label: str) -> None:
    if set(value) != expected:
        raise ValueError(f"{label} fields differ: expected {sorted(expected)}, got {sorted(value)}")


def load_payload_metadata(path: Path = DEFAULT_METADATA_PATH) -> PayloadMetadata:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load payload metadata from {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("payload metadata must be a JSON object")
    _require_exact_keys(
        value,
        {"archive", "contract", "dataset_version", "path_count", "schema_version"},
        label="payload metadata",
    )
    if value["contract"] != PAYLOAD_CONTRACT or value["schema_version"] != PAYLOAD_SCHEMA_VERSION:
        raise ValueError("unsupported payload metadata contract")
    archive = value["archive"]
    if not isinstance(archive, dict):
        raise ValueError("payload metadata archive must be an object")
    _require_exact_keys(archive, {"bytes", "filename", "format", "sha256", "url"}, label="archive")

    dataset_version = value["dataset_version"]
    filename = archive["filename"]
    digest = archive["sha256"]
    archive_bytes = archive["bytes"]
    path_count = value["path_count"]
    url = archive["url"]
    if not isinstance(dataset_version, str) or not dataset_version.startswith("wyscout-2017-18-v1-"):
        raise ValueError("invalid payload dataset_version")
    if not isinstance(filename, str) or PurePosixPath(filename).name != filename or not filename.endswith(".tar.gz"):
        raise ValueError("invalid payload archive filename")
    if archive["format"] != PAYLOAD_FORMAT:
        raise ValueError(f"unsupported payload archive format: {archive['format']}")
    if not isinstance(digest, str) or SHA256_PATTERN.fullmatch(digest) is None:
        raise ValueError("invalid payload archive sha256")
    if digest not in filename or dataset_version not in filename:
        raise ValueError("payload archive filename is not content-addressed")
    if not isinstance(archive_bytes, int) or isinstance(archive_bytes, bool) or archive_bytes <= 0:
        raise ValueError("invalid payload archive byte count")
    if archive_bytes > MAX_ARCHIVE_BYTES:
        raise ValueError("payload archive exceeds the 25 MiB budget")
    if not isinstance(path_count, int) or isinstance(path_count, bool) or path_count <= 0:
        raise ValueError("invalid payload path count")
    if not isinstance(url, str) or not url.startswith("https://") or not url.endswith(f"/{filename}"):
        raise ValueError("payload archive URL must be HTTPS and end with the pinned filename")
    return PayloadMetadata(dataset_version, filename, digest, archive_bytes, path_count, url)


def _load_manifest(path: Path) -> dict[str, Any]:
    try:
        payload = path.read_bytes()
        manifest = json.loads(payload)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load showcase manifest from {path}: {exc}") from exc
    if not isinstance(manifest, dict):
        raise ValueError("showcase manifest must be a JSON object")
    # Git may have checked out this tracked one-line JSON with CRLF on Windows.
    # Accept that transport-only conversion while rejecting every other byte drift.
    if canonical_json_bytes(manifest) != payload.replace(b"\r\n", b"\n"):
        raise ValueError("manifest.json is not canonically serialized")
    validate_schema(manifest, label="manifest.json")
    return manifest


def _expected_player_entries(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    files = manifest["files"]
    all_paths = [entry["path"] for entry in files]
    if len(all_paths) != len(set(all_paths)):
        raise ValueError("manifest contains duplicate file paths")
    entries = {entry["path"]: entry for entry in files if entry["path"].startswith("players/")}
    if len(entries) != manifest["population"]["profile_count"]:
        raise ValueError("manifest player file count differs from population profile_count")
    for name in entries:
        _validate_member_name(name)
    return entries


def _validate_member_name(name: str) -> None:
    path = PurePosixPath(name)
    if (
        "\\" in name
        or path.is_absolute()
        or path.as_posix() != name
        or len(path.parts) != 2
        or path.parts[0] != "players"
        or path.parts[1] in {".", ".."}
        or not path.parts[1].endswith(".json")
    ):
        raise ValueError(f"unsafe archive member path: {name!r}")


def _archive_identity(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _verify_source_files(source_root: Path, entries: dict[str, dict[str, Any]]) -> None:
    players_dir = source_root / "players"
    if not players_dir.is_dir():
        raise ValueError(f"showcase player directory is missing: {players_dir}")
    actual: set[str] = set()
    for path in players_dir.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"player payload cannot contain symlinks: {path}")
        if path.is_file():
            actual.add(path.relative_to(source_root).as_posix())
    if actual != set(entries):
        missing = sorted(set(entries) - actual)
        extra = sorted(actual - set(entries))
        raise ValueError(f"player source set differs from manifest; missing={missing[:3]}, extra={extra[:3]}")
    for name, entry in entries.items():
        payload = (source_root / PurePosixPath(name)).read_bytes()
        if len(payload) != entry["bytes"] or hashlib.sha256(payload).hexdigest() != entry["sha256"]:
            raise ValueError(f"{name}: manifest integrity metadata mismatch")


def build_payload_archive(source_root: Path, output_path: Path) -> PayloadBuild:
    """Build a deterministic archive containing exactly manifest player paths."""
    source_root = source_root.resolve()
    manifest = _load_manifest(source_root / "manifest.json")
    entries = _expected_player_entries(manifest)
    _verify_source_files(source_root, entries)
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(f".{output_path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("wb") as raw:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0) as compressed:
                with tarfile.open(fileobj=compressed, mode="w|", format=tarfile.USTAR_FORMAT) as archive:
                    for name in sorted(entries):
                        source = source_root / PurePosixPath(name)
                        info = tarfile.TarInfo(name)
                        info.size = source.stat().st_size
                        info.mtime = 0
                        info.mode = 0o644
                        info.uid = 0
                        info.gid = 0
                        info.uname = ""
                        info.gname = ""
                        with source.open("rb") as handle:
                            archive.addfile(info, handle)
        digest, archive_bytes = _archive_identity(temporary)
        if archive_bytes > MAX_ARCHIVE_BYTES:
            raise ValueError(f"payload archive exceeds 25 MiB: {archive_bytes} bytes")
        temporary.replace(output_path)
    finally:
        temporary.unlink(missing_ok=True)
    return PayloadBuild(
        dataset_version=manifest["dataset_version"],
        filename=output_path.name,
        sha256=digest,
        archive_bytes=archive_bytes,
        path_count=len(entries),
    )


def _download_archive(metadata: PayloadMetadata, destination: Path) -> None:
    try:
        with requests.get(metadata.url, stream=True, timeout=120) as response:
            response.raise_for_status()
            downloaded = 0
            with destination.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        downloaded += len(chunk)
                        if downloaded > metadata.archive_bytes:
                            raise ValueError("download exceeded the pinned archive byte count")
                        handle.write(chunk)
    except requests.RequestException as exc:
        raise ValueError(f"cannot download pinned payload archive: {exc}") from exc


def _hydrate_verified_archive(
    archive_path: Path,
    *,
    metadata: PayloadMetadata,
    manifest: dict[str, Any],
    output_dir: Path,
) -> dict[str, int | str]:
    digest, archive_bytes = _archive_identity(archive_path)
    if archive_bytes != metadata.archive_bytes:
        raise ValueError(f"archive byte count mismatch: expected {metadata.archive_bytes}, got {archive_bytes}")
    if digest != metadata.sha256:
        raise ValueError(f"archive sha256 mismatch: expected {metadata.sha256}, got {digest}")
    if manifest["dataset_version"] != metadata.dataset_version:
        raise ValueError("payload dataset_version differs from manifest")
    entries = _expected_player_entries(manifest)
    if len(entries) != metadata.path_count:
        raise ValueError("payload path_count differs from manifest")

    staging = make_staging_directory(output_dir)
    try:
        with tarfile.open(archive_path, mode="r:gz") as archive:
            members = archive.getmembers()
            names: list[str] = []
            for member in members:
                _validate_member_name(member.name)
                if not member.isfile():
                    raise ValueError(f"archive member is not a regular file: {member.name}")
                names.append(member.name)
            if len(names) != len(set(names)):
                raise ValueError("archive contains duplicate member paths")
            if set(names) != set(entries):
                missing = sorted(set(entries) - set(names))
                extra = sorted(set(names) - set(entries))
                raise ValueError(f"archive member set differs from manifest; missing={missing[:3]}, extra={extra[:3]}")

            for member in members:
                extracted = archive.extractfile(member)
                if extracted is None:
                    raise ValueError(f"cannot read archive member: {member.name}")
                payload = extracted.read()
                entry = entries[member.name]
                if len(payload) != entry["bytes"] or hashlib.sha256(payload).hexdigest() != entry["sha256"]:
                    raise ValueError(f"{member.name}: manifest integrity metadata mismatch")
                destination = staging / PurePosixPath(member.name).name
                destination.write_bytes(payload)
        publish_directory(staging, output_dir)
    except Exception:
        discard_staging(staging)
        raise
    return {
        "archive_bytes": archive_bytes,
        "dataset_version": metadata.dataset_version,
        "path_count": len(entries),
        "sha256": digest,
    }


def hydrate_payload(
    *,
    archive_path: Path | None = None,
    metadata_path: Path = DEFAULT_METADATA_PATH,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, int | str]:
    """Hydrate ``players/`` only after every archive and manifest check passes."""
    metadata = load_payload_metadata(metadata_path)
    manifest = _load_manifest(manifest_path)
    if archive_path is not None:
        return _hydrate_verified_archive(
            archive_path.resolve(),
            metadata=metadata,
            manifest=manifest,
            output_dir=output_dir,
        )
    with tempfile.TemporaryDirectory(prefix="scoutlens-payload-download-") as directory:
        downloaded = Path(directory) / metadata.filename
        _download_archive(metadata, downloaded)
        return _hydrate_verified_archive(
            downloaded,
            metadata=metadata,
            manifest=manifest,
            output_dir=output_dir,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_parser = subparsers.add_parser("build", help="build a deterministic player payload archive")
    build_parser.add_argument("--source-root", type=Path, default=DEFAULT_SHOWCASE_ROOT)
    build_parser.add_argument("--output", type=Path, required=True)

    hydrate_parser = subparsers.add_parser("hydrate", help="verify and atomically hydrate the player payload")
    hydrate_parser.add_argument("--archive", type=Path)
    hydrate_parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA_PATH)
    hydrate_parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    hydrate_parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    if args.command == "build":
        result = build_payload_archive(args.source_root, args.output).as_dict()
    else:
        result = hydrate_payload(
            archive_path=args.archive,
            metadata_path=args.metadata,
            manifest_path=args.manifest,
            output_dir=args.output_dir,
        )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
