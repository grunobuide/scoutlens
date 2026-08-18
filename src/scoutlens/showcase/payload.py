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
from scoutlens.showcase.schema import artifact_major, validate_schema

PAYLOAD_CONTRACT = "scoutlens.showcase-payload-pack"

# Two versions that are easy to confuse and must not be. PAYLOAD_SCHEMA_VERSION
# versions *the pin document itself*; SHOWCASE_SCHEMA_VERSION_* identifies the
# artifact contract being hydrated. A v2 pin is schema 2.0.0 describing a
# showcase 2.0.0 dataset, but the two numbers move independently and blurring
# them is how a pin ends up promising a dataset it does not describe.
PAYLOAD_SCHEMA_VERSION = "1.0.0"
PAYLOAD_SCHEMA_VERSION_V2 = "2.0.0"
SUPPORTED_PAYLOAD_SCHEMA_VERSIONS = (PAYLOAD_SCHEMA_VERSION, PAYLOAD_SCHEMA_VERSION_V2)

#: Payload schema -> the showcase major it may hydrate, and that major's
#: dataset-version prefix. Exact, so a mixed pin cannot validate.
SHOWCASE_MAJOR_BY_PAYLOAD_SCHEMA = {PAYLOAD_SCHEMA_VERSION: 1, PAYLOAD_SCHEMA_VERSION_V2: 2}

_V1_KEYS = {"archive", "contract", "dataset_version", "path_count", "schema_version"}
_V2_KEYS = _V1_KEYS | {"showcase_schema_version", "manifest_sha256", "representation"}
_ARCHIVE_KEYS = {"bytes", "filename", "format", "sha256", "url"}
_REPRESENTATION_KEYS = {"id", "sha256"}
PAYLOAD_FORMAT = "tar+gzip"
MAX_ARCHIVE_BYTES = 25 * 1024 * 1024
DEFAULT_SHOWCASE_ROOT = REPO_ROOT / "public" / "showcase" / "v1"
DEFAULT_MANIFEST_PATH = DEFAULT_SHOWCASE_ROOT / "manifest.json"
DEFAULT_OUTPUT_DIR = DEFAULT_SHOWCASE_ROOT / "players"
REPRESENTATION_FILENAME = "representation.json"
DEFAULT_METADATA_PATH = REPO_ROOT / "config" / "showcase-payload-pack.json"
SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")


def showcase_root_for(major: int) -> Path:
    """Where a given showcase major's published artifacts live."""
    return REPO_ROOT / "public" / "showcase" / f"v{major}"


def _require_sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError(f"invalid {label}")
    return value


@dataclass(frozen=True)
class PayloadMetadata:
    dataset_version: str
    filename: str
    sha256: str
    archive_bytes: int
    path_count: int
    url: str
    schema_version: str = PAYLOAD_SCHEMA_VERSION
    #: The showcase artifact contract this pin hydrates, or None for a v1 pin,
    #: whose legacy shape predates the distinction.
    showcase_schema_version: str | None = None
    manifest_sha256: str | None = None
    representation_id: str | None = None
    representation_sha256: str | None = None

    @property
    def showcase_major(self) -> int:
        return SHOWCASE_MAJOR_BY_PAYLOAD_SCHEMA[self.schema_version]

    @property
    def showcase_root(self) -> Path:
        return showcase_root_for(self.showcase_major)


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
    schema_version = value.get("schema_version")
    if value.get("contract") != PAYLOAD_CONTRACT:
        raise ValueError("unsupported payload metadata contract")
    if schema_version not in SUPPORTED_PAYLOAD_SCHEMA_VERSIONS:
        raise ValueError(
            f"unsupported payload metadata schema {schema_version!r}; "
            f"known: {list(SUPPORTED_PAYLOAD_SCHEMA_VERSIONS)}"
        )
    # Exact key sets per schema, so a document that mixes the legacy shape with
    # v2 fields is rejected outright rather than validating on the union.
    _require_exact_keys(
        value,
        _V1_KEYS if schema_version == PAYLOAD_SCHEMA_VERSION else _V2_KEYS,
        label=f"payload metadata {schema_version}",
    )
    major = SHOWCASE_MAJOR_BY_PAYLOAD_SCHEMA[schema_version]
    archive = value["archive"]
    if not isinstance(archive, dict):
        raise ValueError("payload metadata archive must be an object")
    _require_exact_keys(archive, _ARCHIVE_KEYS, label="archive")

    showcase_schema_version: str | None = None
    manifest_sha256: str | None = None
    representation_id: str | None = None
    representation_sha256: str | None = None
    if schema_version == PAYLOAD_SCHEMA_VERSION_V2:
        showcase_schema_version = value["showcase_schema_version"]
        if showcase_schema_version != "2.0.0":
            raise ValueError(
                f"a {PAYLOAD_SCHEMA_VERSION_V2} pin hydrates showcase 2.0.0, not "
                f"{showcase_schema_version!r}"
            )
        manifest_sha256 = _require_sha256(value["manifest_sha256"], "pinned manifest_sha256")
        representation = value["representation"]
        if not isinstance(representation, dict):
            raise ValueError("payload metadata representation must be an object")
        _require_exact_keys(representation, _REPRESENTATION_KEYS, label="representation")
        representation_id = representation["id"]
        if not isinstance(representation_id, str) or not representation_id.startswith("rep-"):
            raise ValueError("invalid pinned representation id")
        representation_sha256 = _require_sha256(
            representation["sha256"], "pinned representation sha256"
        )

    dataset_version = value["dataset_version"]
    filename = archive["filename"]
    digest = archive["sha256"]
    archive_bytes = archive["bytes"]
    path_count = value["path_count"]
    url = archive["url"]
    expected_prefix = f"wyscout-2017-18-v{major}-"
    if not isinstance(dataset_version, str) or not dataset_version.startswith(expected_prefix):
        raise ValueError(
            f"a schema {schema_version} pin must name a {expected_prefix}* dataset, "
            f"got {dataset_version!r}"
        )
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
    return PayloadMetadata(
        dataset_version=dataset_version,
        filename=filename,
        sha256=digest,
        archive_bytes=archive_bytes,
        path_count=path_count,
        url=url,
        schema_version=schema_version,
        showcase_schema_version=showcase_schema_version,
        manifest_sha256=manifest_sha256,
        representation_id=representation_id,
        representation_sha256=representation_sha256,
    )


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
    # The major comes from the manifest itself. Packing a v2 dataset against the
    # v1 schema would reject it, and packing it against whichever schema is
    # newest would validate a payload nobody has read.
    validate_schema(manifest, label="manifest.json", major=artifact_major(manifest))
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


def build_payload_archive(source_root: Path, output_path: Path, *, sidecar: bool = False) -> PayloadBuild:
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
    build = PayloadBuild(
        dataset_version=manifest["dataset_version"],
        filename=output_path.name,
        sha256=digest,
        archive_bytes=archive_bytes,
        path_count=len(entries),
    )
    if sidecar:
        write_payload_sidecar(output_path, build, manifest)
    return build


def proposed_archive_name(prefix: str, dataset_version: str, digest: str) -> str:
    """The content-addressed name a release asset must be published under.

    Identity first, then the digest of the exact bytes: a consumer that pins the
    name has pinned the content, and a rebuild that differs cannot silently take
    the same URL.
    """
    return f"{prefix}-{dataset_version}-{digest}.tar.gz"


def write_payload_sidecar(output_path: Path, build: PayloadBuild, manifest: dict[str, Any]) -> Path:
    """Hand `scoutlens-qop.6.6` everything it needs to publish and re-verify.

    Written beside the candidate rather than into the pin: this leaf never
    publishes and never repins, so the proposed name is a proposal.
    """
    sidecar_path = output_path.with_name(f"{output_path.name}.metadata.json")
    document = {
        "contract": PAYLOAD_CONTRACT,
        "schema_version": PAYLOAD_SCHEMA_VERSION,
        "kind": "player_payload_candidate",
        "dataset_version": build.dataset_version,
        "showcase_schema_version": manifest["schema_version"],
        "representation_id": manifest.get("representation_id"),
        "archive": {
            "candidate_filename": build.filename,
            "proposed_filename": proposed_archive_name(
                "scoutlens-showcase", build.dataset_version, build.sha256
            ),
            "format": PAYLOAD_FORMAT,
            "bytes": build.archive_bytes,
            "sha256": build.sha256,
            "member_count": build.path_count,
        },
        "source": {
            "manifest_sha256": hashlib.sha256(canonical_json_bytes(manifest)).hexdigest(),
            "profile_count": manifest["population"]["profile_count"],
        },
    }
    sidecar_path.write_bytes(canonical_json_bytes(document))
    return sidecar_path


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


def _verify_showcase_identity(metadata: PayloadMetadata, manifest_path: Path) -> None:
    """For a v2 pin, check the on-disk dataset is the one the pin describes.

    The archive carries players only; the manifest and representation are
    tracked in Git and could be at any revision. Pinning their digests is what
    stops a v2 player set being hydrated against a manifest that never produced
    it - a mismatch the per-file checks would not catch, because every extracted
    profile would match a manifest that is simply the wrong one.
    """
    if metadata.schema_version != PAYLOAD_SCHEMA_VERSION_V2:
        return

    actual_manifest = hashlib.sha256(
        manifest_path.read_bytes().replace(b"\r\n", b"\n")
    ).hexdigest()
    if actual_manifest != metadata.manifest_sha256:
        raise ValueError(
            f"{manifest_path.name} digest {actual_manifest} does not match the pinned "
            f"{metadata.manifest_sha256}"
        )

    representation_path = manifest_path.parent / REPRESENTATION_FILENAME
    try:
        representation_bytes = representation_path.read_bytes().replace(b"\r\n", b"\n")
    except OSError as exc:
        raise ValueError(f"a v2 pin requires {representation_path}: {exc}") from exc
    actual_representation = hashlib.sha256(representation_bytes).hexdigest()
    if actual_representation != metadata.representation_sha256:
        raise ValueError(
            f"{REPRESENTATION_FILENAME} digest {actual_representation} does not match the "
            f"pinned {metadata.representation_sha256}"
        )
    published_id = json.loads(representation_bytes)["representation"]["id"]
    if published_id != metadata.representation_id:
        raise ValueError(
            f"{REPRESENTATION_FILENAME} publishes {published_id}, pinned {metadata.representation_id}"
        )


def hydrate_payload(
    *,
    archive_path: Path | None = None,
    metadata_path: Path = DEFAULT_METADATA_PATH,
    manifest_path: Path | None = None,
    output_dir: Path | None = None,
) -> dict[str, int | str]:
    """Hydrate ``players/`` only after every archive and manifest check passes.

    With no explicit paths the target is derived from the validated pin rather
    than from a hard-coded v1 root, and only after validation: a pin that fails
    its own checks never gets to say where it would have written.
    """
    metadata = load_payload_metadata(metadata_path)
    if manifest_path is None:
        manifest_path = metadata.showcase_root / "manifest.json"
    if output_dir is None:
        output_dir = metadata.showcase_root / "players"

    manifest = _load_manifest(manifest_path)
    if artifact_major(manifest) != metadata.showcase_major:
        raise ValueError(
            f"{manifest_path} declares showcase major {artifact_major(manifest)}, but the pin "
            f"hydrates major {metadata.showcase_major}"
        )
    _verify_showcase_identity(metadata, manifest_path)
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
    build_parser.add_argument(
        "--sidecar",
        action="store_true",
        help="also write <output>.metadata.json for the publication leaf",
    )

    hydrate_parser = subparsers.add_parser("hydrate", help="verify and atomically hydrate the player payload")
    hydrate_parser.add_argument("--archive", type=Path)
    hydrate_parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA_PATH)
    # Default None so the target is derived from the validated pin. Explicit
    # paths stay available for tests and recovery, and still have to agree with
    # every pinned identity.
    hydrate_parser.add_argument("--manifest", type=Path, default=None)
    hydrate_parser.add_argument("--output-dir", type=Path, default=None)

    pin_parser = subparsers.add_parser("pin", help="build a candidate showcase-v2 payload pin")
    pin_parser.add_argument("--sidecar", type=Path, required=True)
    pin_parser.add_argument("--verified-archive", type=Path, required=True)
    pin_parser.add_argument("--manifest", type=Path, required=True)
    pin_parser.add_argument("--representation", type=Path, required=True)
    pin_parser.add_argument("--url", required=True)
    pin_parser.add_argument("--output", type=Path, required=True)
    pin_parser.add_argument(
        "--replace",
        action="store_true",
        help="overwrite an existing pin; retargets every clean clone's hydration",
    )
    args = parser.parse_args()

    if args.command == "build":
        result = build_payload_archive(args.source_root, args.output, sidecar=args.sidecar).as_dict()
    elif args.command == "pin":
        document = build_pin_document(
            sidecar_path=args.sidecar,
            archive_path=args.verified_archive,
            manifest_path=args.manifest,
            representation_path=args.representation,
            url=args.url,
        )
        written = write_pin(document, args.output, replace=args.replace)
        result = {"pin": str(written), **{k: v for k, v in document.items() if k != "archive"}}
    else:
        result = hydrate_payload(
            archive_path=args.archive,
            metadata_path=args.metadata,
            manifest_path=args.manifest,
            output_dir=args.output_dir,
        )
    print(json.dumps(result, indent=2, sort_keys=True))




def build_pin_document(
    *,
    sidecar_path: Path,
    archive_path: Path,
    manifest_path: Path,
    representation_path: Path,
    url: str,
) -> dict[str, Any]:
    """Assemble a v2 pin from bytes that are verified here, not trusted.

    Every field is recomputed from the artefacts themselves and then required to
    agree with the `qop.6.4.4` sidecar. The sidecar is a convenience for the
    operator, never the authority: a pin built from a sidecar alone would attest
    to whatever the sidecar happened to say.
    """
    archive_path = archive_path.resolve()
    digest, archive_bytes = _archive_identity(archive_path)

    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    if canonical_json_bytes(sidecar) != sidecar_path.read_bytes().replace(b"\r\n", b"\n"):
        raise ValueError(f"{sidecar_path.name} is not canonically serialized")
    if sidecar.get("contract") != PAYLOAD_CONTRACT:
        raise ValueError(f"{sidecar_path.name} is not a payload sidecar")
    declared = sidecar["archive"]
    if declared["sha256"] != digest or declared["bytes"] != archive_bytes:
        raise ValueError(
            f"sidecar describes {declared['bytes']} bytes / {declared['sha256'][:12]}, "
            f"archive is {archive_bytes} / {digest[:12]}"
        )

    manifest = _load_manifest(manifest_path)
    if artifact_major(manifest) != 2:
        raise ValueError("the pin command builds showcase 2.0.0 pins only")
    manifest_digest = hashlib.sha256(
        manifest_path.read_bytes().replace(b"\r\n", b"\n")
    ).hexdigest()
    dataset_version = manifest["dataset_version"]
    if sidecar["dataset_version"] != dataset_version:
        raise ValueError(
            f"sidecar names {sidecar['dataset_version']}, manifest is {dataset_version}"
        )

    representation_bytes = representation_path.read_bytes().replace(b"\r\n", b"\n")
    representation = json.loads(representation_bytes)["representation"]
    representation_digest = hashlib.sha256(representation_bytes).hexdigest()
    if representation["id"] != manifest.get("representation_id"):
        raise ValueError("manifest and representation name different representations")
    if sidecar.get("representation_id") != representation["id"]:
        raise ValueError("sidecar names a different representation than the dataset")

    entries = _expected_player_entries(manifest)
    if declared["member_count"] != len(entries):
        raise ValueError(
            f"sidecar counts {declared['member_count']} members, manifest declares {len(entries)}"
        )

    filename = proposed_archive_name("scoutlens-showcase", dataset_version, digest)
    if declared["proposed_filename"] != filename:
        raise ValueError(
            f"sidecar proposes {declared['proposed_filename']}, content addressing gives {filename}"
        )
    if not url.startswith("https://"):
        raise ValueError("the pinned URL must be HTTPS")
    if not url.endswith(f"/{filename}"):
        raise ValueError(f"the pinned URL must end with /{filename}")
    if archive_bytes > MAX_ARCHIVE_BYTES:
        raise ValueError(f"payload archive exceeds the budget: {archive_bytes} bytes")

    return {
        "archive": {
            "bytes": archive_bytes,
            "filename": filename,
            "format": PAYLOAD_FORMAT,
            "sha256": digest,
            "url": url,
        },
        "contract": PAYLOAD_CONTRACT,
        "dataset_version": dataset_version,
        "manifest_sha256": manifest_digest,
        "path_count": len(entries),
        "representation": {"id": representation["id"], "sha256": representation_digest},
        "schema_version": PAYLOAD_SCHEMA_VERSION_V2,
        "showcase_schema_version": "2.0.0",
    }


def write_pin(document: dict[str, Any], output_path: Path, *, replace: bool = False) -> Path:
    """Write a pin candidate atomically, refusing to clobber one by default.

    Replacing a pin retargets every clean clone's hydration, so it takes an
    explicit flag rather than an overwrite nobody had to ask for.
    """
    output_path = output_path.resolve()
    if output_path.exists() and not replace:
        raise ValueError(f"refusing to replace an existing pin without --replace: {output_path}")
    payload = canonical_json_bytes(document)
    # Round-trip through the loader before publishing: a pin that this module
    # cannot read is not a pin.
    temporary = output_path.with_name(f".{output_path.name}.{uuid.uuid4().hex}.tmp")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        temporary.write_bytes(payload)
        load_payload_metadata(temporary)
        temporary.replace(output_path)
    finally:
        temporary.unlink(missing_ok=True)
    return output_path


if __name__ == "__main__":
    main()
