from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
import tarfile
from pathlib import Path

import pytest

import scoutlens.showcase.payload as payload_module
from scoutlens.showcase.io import canonical_json_bytes
from scoutlens.showcase.payload import (
    MAX_ARCHIVE_BYTES,
    PayloadBuild,
    PayloadMetadata,
    build_payload_archive,
    hydrate_payload,
    load_payload_metadata,
)
from scoutlens.showcase.validation import validate_published_directory

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_SHOWCASE_ROOT = REPO_ROOT / "public" / "showcase" / "v1"
HAS_REAL_PAYLOAD = (REAL_SHOWCASE_ROOT / "players").is_dir()
SHA = "0" * 64
DATASET_VERSION = "wyscout-2017-18-v1-0123456789ab"


def _file_entry(path: str, payload: bytes) -> dict[str, object]:
    return {
        "bytes": len(payload),
        "media_type": "application/json",
        "path": path,
        "records": 1,
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def _write_fixture(root: Path) -> tuple[Path, dict[str, bytes]]:
    payloads = {
        "players/wy-1-c-1.json": b'{"profile":"one"}\n',
        "players/wy-2-c-1.json": b'{"profile":"two"}\n',
    }
    for name, payload in payloads.items():
        destination = root / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
    placeholder = b"{}\n"
    manifest = {
        "contract": "scoutlens.showcase",
        "dataset_version": DATASET_VERSION,
        "featured_profile": {"editorial": True, "profile_key": "wy-1-c-1", "reason": "Fixture"},
        "files": [
            _file_entry("feature-catalog.json", placeholder),
            _file_entry("players.index.json", placeholder),
            *(_file_entry(name, payload) for name, payload in payloads.items()),
        ],
        "generated_at": "2026-07-28T00:00:00+00:00",
        "inputs": [{"bytes": 1, "logical_name": "fixture", "public": False, "sha256": SHA}],
        "population": {
            "analytical_unit": "player_competition",
            "chronological_periods": ["a", "b"],
            "domestic_competition_ids": [1],
            "feature_count": 32,
            "minutes_threshold_per_period": 450,
            "profile_count": 2,
        },
        "producer": {
            "config_path": "config/experiment.json",
            "config_sha256": SHA,
            "git_commit": None,
            "git_dirty": None,
            "polars_version": "fixture",
            "python_version": "fixture",
            "source_sha256": SHA,
        },
        "schema_version": "1.0.0",
        "source": {
            "citation": "Fixture citation",
            "licence": "CC BY 4.0",
            "licence_url": "https://creativecommons.org/licenses/by/4.0/",
            "provider": "wyscout_pappalardo",
            "redistribution_note": "Derived fixture aggregates only.",
            "season": "2017/18",
            "source_url": "https://example.test/source",
            "title": "Fixture source",
        },
    }
    (root / "manifest.json").write_bytes(canonical_json_bytes(manifest))
    return root, payloads


def _metadata(build: PayloadBuild) -> dict[str, object]:
    filename = f"fixture-{build.dataset_version}-{build.sha256}.tar.gz"
    return {
        "archive": {
            "bytes": build.archive_bytes,
            "filename": filename,
            "format": "tar+gzip",
            "sha256": build.sha256,
            "url": f"https://example.test/{filename}",
        },
        "contract": "scoutlens.showcase-payload-pack",
        "dataset_version": build.dataset_version,
        "path_count": build.path_count,
        "schema_version": "1.0.0",
    }


def _write_metadata(path: Path, value: dict[str, object]) -> None:
    path.write_bytes(canonical_json_bytes(value))


def _write_archive(path: Path, members: dict[str, bytes]) -> None:
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w|", format=tarfile.USTAR_FORMAT) as archive:
                for name, payload in members.items():
                    info = tarfile.TarInfo(name)
                    info.size = len(payload)
                    info.mtime = 0
                    archive.addfile(info, io.BytesIO(payload))


def _metadata_for_archive(base: dict[str, object], archive: Path) -> dict[str, object]:
    value = json.loads(json.dumps(base))
    payload = archive.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    filename = f"fixture-{value['dataset_version']}-{digest}.tar.gz"
    value["archive"]["bytes"] = len(payload)
    value["archive"]["filename"] = filename
    value["archive"]["sha256"] = digest
    value["archive"]["url"] = f"https://example.test/{filename}"
    return value


def _assert_existing_target_survives_failure(
    source: Path,
    archive: Path,
    metadata: dict[str, object],
    tmp_path: Path,
    match: str,
) -> None:
    metadata_path = tmp_path / "payload.json"
    _write_metadata(metadata_path, metadata)
    target = tmp_path / "published" / "players"
    target.mkdir(parents=True)
    sentinel = target / "existing.json"
    sentinel.write_text("existing", encoding="utf-8")
    with pytest.raises(ValueError, match=match):
        hydrate_payload(
            archive_path=archive,
            metadata_path=metadata_path,
            manifest_path=source / "manifest.json",
            output_dir=target,
        )
    assert sentinel.read_text(encoding="utf-8") == "existing"
    assert list(target.iterdir()) == [sentinel]


def test_repository_payload_pin_is_content_addressed_and_within_budget() -> None:
    metadata = load_payload_metadata(REPO_ROOT / "config" / "showcase-payload-pack.json")
    assert metadata.dataset_version == "wyscout-2017-18-v1-1ea86c4a4dbb"
    assert metadata.path_count == 1257
    assert metadata.archive_bytes == 19_624_821
    assert metadata.sha256 in metadata.filename
    assert metadata.dataset_version in metadata.filename
    assert metadata.archive_bytes <= MAX_ARCHIVE_BYTES


def test_payload_archive_is_deterministic_and_hydrates_atomically(tmp_path: Path) -> None:
    source, payloads = _write_fixture(tmp_path / "source")
    first = tmp_path / "payload.tar.gz"
    second = tmp_path / "second.tar.gz"
    first_build = build_payload_archive(source, first)
    second_build = build_payload_archive(source, second)

    assert first.read_bytes() == second.read_bytes()
    assert first_build.sha256 == second_build.sha256
    assert first_build.path_count == 2
    metadata_path = tmp_path / "payload.json"
    _write_metadata(metadata_path, _metadata(first_build))
    target = tmp_path / "published" / "players"
    target.mkdir(parents=True)
    (target / "stale.json").write_text("stale", encoding="utf-8")

    result = hydrate_payload(
        archive_path=first,
        metadata_path=metadata_path,
        manifest_path=source / "manifest.json",
        output_dir=target,
    )

    assert result["path_count"] == 2
    assert {path.name: path.read_bytes() for path in target.iterdir()} == {
        name.rsplit("/", maxsplit=1)[-1]: payload for name, payload in payloads.items()
    }


def test_hydration_downloads_the_pinned_archive_when_no_local_path_is_given(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, payloads = _write_fixture(tmp_path / "source")
    archive = tmp_path / "payload.tar.gz"
    build = build_payload_archive(source, archive)
    metadata_path = tmp_path / "payload.json"
    _write_metadata(metadata_path, _metadata(build))

    def copy_pinned_archive(metadata: PayloadMetadata, destination: Path) -> None:
        assert metadata.sha256 == build.sha256
        destination.write_bytes(archive.read_bytes())

    monkeypatch.setattr(payload_module, "_download_archive", copy_pinned_archive)
    target = tmp_path / "published" / "players"
    hydrate_payload(
        metadata_path=metadata_path,
        manifest_path=source / "manifest.json",
        output_dir=target,
    )
    assert {path.name: path.read_bytes() for path in target.iterdir()} == {
        name.rsplit("/", maxsplit=1)[-1]: payload for name, payload in payloads.items()
    }


def test_hydration_rejects_wrong_archive_hash_before_publication(tmp_path: Path) -> None:
    source, _ = _write_fixture(tmp_path / "source")
    archive = tmp_path / "payload.tar.gz"
    build = build_payload_archive(source, archive)
    metadata = _metadata(build)
    wrong_digest = "f" * 64
    wrong_filename = f"fixture-{build.dataset_version}-{wrong_digest}.tar.gz"
    metadata["archive"]["filename"] = wrong_filename
    metadata["archive"]["sha256"] = wrong_digest
    metadata["archive"]["url"] = f"https://example.test/{wrong_filename}"
    _assert_existing_target_survives_failure(source, archive, metadata, tmp_path, "sha256 mismatch")


def test_hydration_rejects_traversal_path_before_publication(tmp_path: Path) -> None:
    source, payloads = _write_fixture(tmp_path / "source")
    reference = tmp_path / "reference.tar.gz"
    build = build_payload_archive(source, reference)
    archive = tmp_path / "traversal.tar.gz"
    _write_archive(archive, {"../escape.json": next(iter(payloads.values()))})
    metadata = _metadata_for_archive(_metadata(build), archive)
    _assert_existing_target_survives_failure(source, archive, metadata, tmp_path, "unsafe archive member")
    assert not (tmp_path / "escape.json").exists()


@pytest.mark.parametrize(
    "members",
    [
        {"players/wy-1-c-1.json": b'{"profile":"one"}\n'},
        {
            "players/wy-1-c-1.json": b'{"profile":"one"}\n',
            "players/wy-2-c-1.json": b'{"profile":"two"}\n',
            "players/wy-3-c-1.json": b'{"profile":"extra"}\n',
        },
    ],
    ids=["missing", "extra"],
)
def test_hydration_rejects_missing_or_extra_payloads_before_publication(
    tmp_path: Path,
    members: dict[str, bytes],
) -> None:
    source, _ = _write_fixture(tmp_path / "source")
    reference = tmp_path / "reference.tar.gz"
    build = build_payload_archive(source, reference)
    archive = tmp_path / "wrong-set.tar.gz"
    _write_archive(archive, members)
    metadata = _metadata_for_archive(_metadata(build), archive)
    _assert_existing_target_survives_failure(source, archive, metadata, tmp_path, "member set differs")


def test_hydration_rejects_per_file_checksum_mismatch_before_publication(tmp_path: Path) -> None:
    source, payloads = _write_fixture(tmp_path / "source")
    reference = tmp_path / "reference.tar.gz"
    build = build_payload_archive(source, reference)
    archive = tmp_path / "wrong-content.tar.gz"
    changed = dict(payloads)
    changed["players/wy-2-c-1.json"] = b'{"profile":"tampered"}\n'
    _write_archive(archive, changed)
    metadata = _metadata_for_archive(_metadata(build), archive)
    _assert_existing_target_survives_failure(source, archive, metadata, tmp_path, "integrity metadata mismatch")


@pytest.mark.skipif(
    os.environ.get("SCOUTLENS_SHOWCASE_PAYLOAD_INTEGRATION") != "1" or not HAS_REAL_PAYLOAD,
    reason="requires local showcase profiles and SCOUTLENS_SHOWCASE_PAYLOAD_INTEGRATION=1",
)
def test_real_payload_is_deterministic_complete_and_hydrates(tmp_path: Path) -> None:
    first = tmp_path / "first.tar.gz"
    second = tmp_path / "second.tar.gz"
    first_build = build_payload_archive(REAL_SHOWCASE_ROOT, first)
    second_build = build_payload_archive(REAL_SHOWCASE_ROOT, second)
    assert first.read_bytes() == second.read_bytes()
    assert first_build.sha256 == second_build.sha256
    assert first_build.archive_bytes == second_build.archive_bytes
    assert first_build.dataset_version == second_build.dataset_version
    assert first_build.path_count == second_build.path_count
    assert first_build.path_count == 1257
    assert first_build.archive_bytes <= MAX_ARCHIVE_BYTES

    metadata_path = tmp_path / "payload.json"
    _write_metadata(metadata_path, _metadata(first_build))
    published = tmp_path / "published" / "v1"
    published.mkdir(parents=True)
    for name in ("feature-catalog.json", "manifest.json", "players.index.json", "research-summary.json"):
        artifact = json.loads((REAL_SHOWCASE_ROOT / name).read_text(encoding="utf-8"))
        (published / name).write_bytes(canonical_json_bytes(artifact))
    hydrate_payload(
        archive_path=first,
        metadata_path=metadata_path,
        manifest_path=published / "manifest.json",
        output_dir=published / "players",
    )
    validate_published_directory(published)
