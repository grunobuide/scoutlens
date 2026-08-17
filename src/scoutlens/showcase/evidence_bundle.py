"""Deterministic scientific-evidence archive for the diagonal uncertainty run.

The 1.6 MiB `match_bootstrap_diagonal_v1` outputs are the evidence behind every
interval published in showcase-v2. They are **offline audit evidence, not a
runtime input**: the public site never fetches them, and hydration never needs
them. Packing them separately keeps that boundary visible - a reader auditing
the intervals downloads this, and a browser rendering the Lab does not.

The archive carries exactly six members: the four approved run outputs, a
generated `CHECKSUMS.json` and a generated `README.md`. Everything else in the
run directory - checkpoints above all, at 287 MB - is excluded by an allowlist
rather than by a filter, because a filter ships whatever nobody thought to
exclude.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import tarfile
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from scoutlens.evaluation.run_manifest import REPO_ROOT
from scoutlens.showcase.io import canonical_json_bytes

EVIDENCE_CONTRACT = "scoutlens.showcase-scientific-evidence"
EVIDENCE_SCHEMA_VERSION = "1.0.0"
EVIDENCE_FORMAT = "tar+gzip"

DESIGN_VERSION = "match_bootstrap_diagonal_v1"
RANKING_METHOD = "weighted_cosine_diagonal_v1"
RUN_FORMAT = "scoutlens.match-bootstrap-summary/1"

#: Exactly what may enter the archive from the run directory, in archive order.
SOURCE_MEMBERS = (
    "run.json",
    "feature-uncertainty.parquet",
    "retrieval-uncertainty.parquet",
    "neighbor-stability.parquet",
)
GENERATED_MEMBERS = ("CHECKSUMS.json", "README.md")
ARCHIVE_MEMBERS = tuple(sorted(SOURCE_MEMBERS + GENERATED_MEMBERS))

#: The evidence bundle is small by construction; anything near this size means
#: something unapproved got in.
MAX_ARCHIVE_BYTES = 8 * 1024 * 1024

DEFAULT_RUN_DIR = REPO_ROOT / "artifacts" / "uncertainty" / DESIGN_VERSION
DEFAULT_REPRESENTATION_PATH = REPO_ROOT / "public" / "showcase" / "v2" / "representation.json"


@dataclass(frozen=True)
class EvidenceBuild:
    filename: str
    sha256: str
    archive_bytes: int
    member_count: int
    representation_id: str
    dataset_version: str

    def as_dict(self) -> dict[str, int | str]:
        return {
            "archive_bytes": self.archive_bytes,
            "dataset_version": self.dataset_version,
            "filename": self.filename,
            "member_count": self.member_count,
            "representation_id": self.representation_id,
            "sha256": self.sha256,
        }


def _validate_member_name(name: str) -> None:
    """Reject anything that is not a plain file at the archive root.

    A member named `../x` or `/etc/x` extracts outside the destination. The
    allowlist already forbids it; this refuses it again on the way out and on
    the way back in, because extraction is where the damage happens.
    """
    path = PurePosixPath(name)
    if (
        "\\" in name
        or path.is_absolute()
        or path.as_posix() != name
        or len(path.parts) != 1
        or name in {".", ".."}
    ):
        raise ValueError(f"unsafe archive member path: {name!r}")


def load_run(run_dir: Path) -> dict[str, Any]:
    """Read `run.json` and refuse anything that is not the D047 design.

    A cosine run, an unfinished run or a run scored under another
    representation describes intervals that do not belong to the published
    rankings.
    """
    path = run_dir / "run.json"
    try:
        run = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load uncertainty run from {path}: {exc}") from exc

    manifest = run.get("manifest")
    if not isinstance(manifest, dict):
        raise ValueError("run.json has no manifest")
    if run.get("format") != RUN_FORMAT:
        raise ValueError(f"unsupported run format: {run.get('format')!r}")
    if manifest.get("design_version") != DESIGN_VERSION:
        raise ValueError(
            f"evidence bundle requires design {DESIGN_VERSION}, run declares "
            f"{manifest.get('design_version')!r}"
        )
    if manifest.get("ranking_method") != RANKING_METHOD:
        raise ValueError(
            f"evidence bundle requires scorer {RANKING_METHOD}, run declares "
            f"{manifest.get('ranking_method')!r}"
        )
    if run.get("status") != "available":
        raise ValueError(f"run status is {run.get('status')!r}; only a completed run is evidence")
    requested = manifest.get("requested_resamples")
    if run.get("completed_resamples") != requested or run.get("valid_resamples") != requested:
        raise ValueError(
            f"run completed {run.get('completed_resamples')} and validated "
            f"{run.get('valid_resamples')} of {requested} resamples"
        )
    if not isinstance(manifest.get("representation_id"), str):
        raise ValueError("run.json does not name a representation")
    return run


def verify_representation(run: dict[str, Any], representation_path: Path) -> tuple[str, str]:
    """Cross-check the run against the representation actually published.

    Returns `(representation_id, dataset_version)`. The run naming a
    representation is not the same as the run naming the *published* one.
    """
    try:
        artifact = json.loads(representation_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load representation from {representation_path}: {exc}") from exc
    representation = artifact["representation"]
    published_id = representation["id"]
    if run["manifest"]["representation_id"] != published_id:
        raise ValueError(
            f"run was scored under representation {run['manifest']['representation_id']}, "
            f"but {published_id} is published"
        )
    if representation["uncertainty_design"] != DESIGN_VERSION:
        raise ValueError("the published representation names a different uncertainty design")
    if representation["ranking_method"] != RANKING_METHOD:
        raise ValueError("the published representation names a different scorer")
    return published_id, artifact["dataset_version"]


def build_checksums(run_dir: Path, run: dict[str, Any]) -> dict[str, Any]:
    """Canonical logical path, bytes and SHA-256 for every approved source.

    Also reconciles the three parquet outputs against the digests `run.json`
    recorded when it wrote them: a file that changed after the run is evidence
    of nothing.
    """
    declared = {value["path"]: value for value in run["outputs"].values()}
    files = []
    for name in SOURCE_MEMBERS:
        _validate_member_name(name)
        path = run_dir / name
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"approved evidence source is missing or not a regular file: {name}")
        payload = path.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        if name in declared:
            recorded = declared[name]
            if recorded["sha256"] != digest or recorded["bytes"] != len(payload):
                raise ValueError(f"{name}: differs from the digest run.json recorded for it")
        files.append({"path": name, "bytes": len(payload), "sha256": digest})
    return {
        "contract": EVIDENCE_CONTRACT,
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "design_version": DESIGN_VERSION,
        "representation_id": run["manifest"]["representation_id"],
        "files": files,
    }


def build_readme(run: dict[str, Any], *, representation_id: str, dataset_version: str) -> str:
    """The method note that ships with the evidence.

    It records identity, design and completeness, and states the caveat
    boundary. It deliberately copies **no headline performance number**: a
    result quoted beside its own evidence invites the reader to trust the quote
    instead of the evidence, and the numbers live in the ledger and the research
    summary where they can be revised in one place.
    """
    manifest = run["manifest"]
    requested = manifest["requested_resamples"]
    return f"""# ScoutLens showcase-v2 scientific evidence

Offline audit evidence for the uncertainty intervals published in
`{dataset_version}`. **Not a public-site runtime input**: the ScoutLens web
application never fetches this archive, and hydrating the showcase payload does
not need it. It exists so that an interval can be recomputed by someone who did
not run it.

## Identity

| | |
|---|---|
| Representation | `{representation_id}` |
| Ranking method | `{RANKING_METHOD}` |
| Uncertainty design | `{DESIGN_VERSION}` |
| Resamples | {run["completed_resamples"]}/{requested} completed, {run["valid_resamples"]}/{requested} valid |
| Profiles | {manifest["profile_count"]} |
| Draw plan | `{manifest["draw_plan_sha256"]}` |
| Cohort | `{manifest["cohort_sha256"]}` |
| Experiment config | `{manifest["experiment_config_path"]}` @ `{manifest["experiment_config_sha256"]}` |

## Contents

| File | What it is |
|---|---|
| `run.json` | Run manifest: design, lineage, input digests, execution record. |
| `feature-uncertainty.parquet` | Per-feature resampled intervals. |
| `retrieval-uncertainty.parquet` | Self-rank and recall intervals. |
| `neighbor-stability.parquet` | Neighbour selection rates and rank intervals. |
| `CHECKSUMS.json` | Logical path, byte count and SHA-256 for each of the four above. |

Verify before use: recompute each SHA-256 and compare against `CHECKSUMS.json`.

## What these intervals mean, and what they do not

They describe **sampling stability under match-level resampling** for rankings
produced by `{RANKING_METHOD}`, and nothing else. They are not confidence
statements about a player's ability, not measurement error, and not predictive
intervals.

Intervals computed under the v1 cosine design do not apply here and are not
interchangeable with these: they describe the stability of a different metric.

Nothing in this bundle supports a causal claim, a recruitment or
transfer-success judgement, or a prediction of future performance. Statistical
similarity between fingerprints is a description of observed play.

## Reproduction

```bash
uv run --frozen python -m scoutlens.uncertainty.run \\
  --config config/uncertainty-diagonal.json \\
  --resamples {requested}
```

Regenerating with the same config and draw plan reproduces the same summaries;
the draw plan digest above is what makes that checkable.
"""


def _tar_member(archive: tarfile.TarFile, name: str, payload: bytes) -> None:
    _validate_member_name(name)
    info = tarfile.TarInfo(name)
    info.size = len(payload)
    info.mtime = 0
    info.mode = 0o644
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    archive.addfile(info, io.BytesIO(payload))


def _archive_identity(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def build_evidence_archive(
    run_dir: Path,
    output_path: Path,
    *,
    representation_path: Path = DEFAULT_REPRESENTATION_PATH,
    sidecar: bool = True,
) -> EvidenceBuild:
    run_dir = run_dir.resolve()
    output_path = output_path.resolve()
    if output_path.exists():
        raise ValueError(f"refusing to overwrite an existing archive: {output_path}")

    run = load_run(run_dir)
    representation_id, dataset_version = verify_representation(run, representation_path)
    checksums = build_checksums(run_dir, run)
    readme = build_readme(run, representation_id=representation_id, dataset_version=dataset_version)

    members: dict[str, bytes] = {name: (run_dir / name).read_bytes() for name in SOURCE_MEMBERS}
    members["CHECKSUMS.json"] = canonical_json_bytes(checksums)
    members["README.md"] = readme.encode("utf-8")
    if set(members) != set(ARCHIVE_MEMBERS):
        raise ValueError(f"member set differs from the allowlist: {sorted(members)}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(f".{output_path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("wb") as raw:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0) as compressed:
                with tarfile.open(fileobj=compressed, mode="w|", format=tarfile.USTAR_FORMAT) as archive:
                    for name in ARCHIVE_MEMBERS:
                        _tar_member(archive, name, members[name])
        digest, archive_bytes = _archive_identity(temporary)
        if archive_bytes > MAX_ARCHIVE_BYTES:
            raise ValueError(f"evidence archive exceeds {MAX_ARCHIVE_BYTES} bytes: {archive_bytes}")
        temporary.replace(output_path)
    finally:
        temporary.unlink(missing_ok=True)

    build = EvidenceBuild(
        filename=output_path.name,
        sha256=digest,
        archive_bytes=archive_bytes,
        member_count=len(ARCHIVE_MEMBERS),
        representation_id=representation_id,
        dataset_version=dataset_version,
    )
    # Verify the bytes that were written, not the bytes that were intended.
    verify_evidence_archive(output_path)
    if sidecar:
        write_evidence_sidecar(output_path, build, checksums)
    return build


def verify_evidence_archive(archive_path: Path) -> dict[str, Any]:
    """Read a built archive back and refuse it unless it is exactly the bundle.

    Run on every build. An archive nobody has opened is a claim, not an asset.
    """
    with tarfile.open(archive_path, mode="r:gz") as archive:
        members = archive.getmembers()
        names = []
        payloads: dict[str, bytes] = {}
        for member in members:
            _validate_member_name(member.name)
            if not member.isfile():
                raise ValueError(f"archive member is not a regular file: {member.name}")
            extracted = archive.extractfile(member)
            if extracted is None:
                raise ValueError(f"cannot read archive member: {member.name}")
            payloads[member.name] = extracted.read()
            names.append(member.name)
    if names != list(ARCHIVE_MEMBERS):
        raise ValueError(
            f"archive members are not the allowlist in canonical order: {names}"
        )
    checksums = json.loads(payloads["CHECKSUMS.json"])
    if canonical_json_bytes(checksums) != payloads["CHECKSUMS.json"]:
        raise ValueError("CHECKSUMS.json is not canonically serialized")
    recorded = {entry["path"]: entry for entry in checksums["files"]}
    if set(recorded) != set(SOURCE_MEMBERS):
        raise ValueError(f"CHECKSUMS.json does not cover exactly the approved sources: {sorted(recorded)}")
    for name, entry in sorted(recorded.items()):
        payload = payloads[name]
        if entry["bytes"] != len(payload) or entry["sha256"] != hashlib.sha256(payload).hexdigest():
            raise ValueError(f"{name}: archived bytes do not match CHECKSUMS.json")
    return checksums


def write_evidence_sidecar(output_path: Path, build: EvidenceBuild, checksums: dict[str, Any]) -> Path:
    """Hand `scoutlens-qop.6.6` the identity and digests it needs to publish."""
    sidecar_path = output_path.with_name(f"{output_path.name}.metadata.json")
    document = {
        "contract": EVIDENCE_CONTRACT,
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "kind": "scientific_evidence_candidate",
        "dataset_version": build.dataset_version,
        "representation_id": build.representation_id,
        "design_version": DESIGN_VERSION,
        "ranking_method": RANKING_METHOD,
        "archive": {
            "candidate_filename": build.filename,
            "proposed_filename": (
                f"scoutlens-showcase-evidence-{build.dataset_version}-{build.sha256}.tar.gz"
            ),
            "format": EVIDENCE_FORMAT,
            "bytes": build.archive_bytes,
            "sha256": build.sha256,
            "member_count": build.member_count,
            "members": list(ARCHIVE_MEMBERS),
        },
        "sources": checksums["files"],
        "runtime_input": False,
    }
    sidecar_path.write_bytes(canonical_json_bytes(document))
    return sidecar_path


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_parser = subparsers.add_parser("build", help="build the deterministic evidence archive")
    build_parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    build_parser.add_argument("--output", type=Path, required=True)
    build_parser.add_argument("--representation", type=Path, default=DEFAULT_REPRESENTATION_PATH)

    verify_parser = subparsers.add_parser("verify", help="re-verify a built evidence archive")
    verify_parser.add_argument("--archive", type=Path, required=True)
    args = parser.parse_args(argv)

    if args.command == "build":
        result: dict[str, Any] = build_evidence_archive(
            args.run_dir, args.output, representation_path=args.representation
        ).as_dict()
    else:
        result = {"members": list(ARCHIVE_MEMBERS), "checksums": verify_evidence_archive(args.archive)}
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
