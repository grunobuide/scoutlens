"""The showcase-major-aware payload pin (`scoutlens-qop.6.6.1`).

Two versions are easy to confuse here and must not be: the payload schema
versions the *pin document*, and `showcase_schema_version` names the *artifact
contract* being hydrated. Most of this file is refusals, because a pin is the
one file that redirects every clean clone's hydration - a wrong one is not a
degraded experience, it is a different dataset presented as this one.

The fixtures are synthetic so each refusal can be provoked exactly; the real v2
candidate is exercised by the opt-in tests at the bottom.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from scoutlens.showcase.io import canonical_json_bytes
from scoutlens.showcase.payload import (
    PAYLOAD_CONTRACT,
    PAYLOAD_SCHEMA_VERSION,
    PAYLOAD_SCHEMA_VERSION_V2,
    build_pin_document,
    load_payload_metadata,
    write_pin,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_V2_ROOT = REPO_ROOT / "public" / "showcase" / "v2"
REAL_CANDIDATE = REPO_ROOT / "artifacts" / "showcase-payload" / "showcase-v2-payload-candidate.tar.gz"

V2_DATASET = "wyscout-2017-18-v2-0123456789ab"
V1_DATASET = "wyscout-2017-18-v1-0123456789ab"
REPRESENTATION_ID = "rep-f018e6041ccbad10"
SHA = "a" * 64


def _v1_pin(**overrides: object) -> dict:
    filename = f"scoutlens-showcase-{V1_DATASET}-{SHA}.tar.gz"
    document: dict = {
        "archive": {
            "bytes": 1024,
            "filename": filename,
            "format": "tar+gzip",
            "sha256": SHA,
            "url": f"https://example.test/{filename}",
        },
        "contract": PAYLOAD_CONTRACT,
        "dataset_version": V1_DATASET,
        "path_count": 1257,
        "schema_version": PAYLOAD_SCHEMA_VERSION,
    }
    document.update(overrides)
    return document


def _v2_pin(**overrides: object) -> dict:
    filename = f"scoutlens-showcase-{V2_DATASET}-{SHA}.tar.gz"
    document: dict = {
        "archive": {
            "bytes": 2048,
            "filename": filename,
            "format": "tar+gzip",
            "sha256": SHA,
            "url": f"https://example.test/{filename}",
        },
        "contract": PAYLOAD_CONTRACT,
        "dataset_version": V2_DATASET,
        "manifest_sha256": "b" * 64,
        "path_count": 1257,
        "representation": {"id": REPRESENTATION_ID, "sha256": "c" * 64},
        "schema_version": PAYLOAD_SCHEMA_VERSION_V2,
        "showcase_schema_version": "2.0.0",
    }
    document.update(overrides)
    return document


def _write(tmp_path: Path, document: dict, name: str = "pin.json") -> Path:
    path = tmp_path / name
    path.write_bytes(canonical_json_bytes(document))
    return path


# --- the two schemas are exact and distinct -------------------------------


def test_the_repository_pin_still_loads_and_targets_v1() -> None:
    """AC1: the shipped pin must keep working, unchanged, before any repin."""
    metadata = load_payload_metadata()
    assert metadata.schema_version == PAYLOAD_SCHEMA_VERSION
    assert metadata.dataset_version.startswith("wyscout-2017-18-v1-")
    assert metadata.showcase_major == 1
    assert metadata.showcase_root.name == "v1"
    assert metadata.path_count == 1257
    # The legacy shape predates the distinction and must not acquire v2 fields.
    assert metadata.showcase_schema_version is None
    assert metadata.representation_id is None


def test_a_v2_pin_loads_and_targets_v2(tmp_path: Path) -> None:
    metadata = load_payload_metadata(_write(tmp_path, _v2_pin()))
    assert metadata.showcase_major == 2
    assert metadata.showcase_root.name == "v2"
    assert metadata.representation_id == REPRESENTATION_ID


def test_a_v1_pin_carrying_a_v2_field_is_rejected(tmp_path: Path) -> None:
    """The key sets are exact, so a document cannot straddle both shapes."""
    document = _v1_pin()
    document["representation"] = {"id": REPRESENTATION_ID, "sha256": "c" * 64}
    with pytest.raises(ValueError, match="fields differ"):
        load_payload_metadata(_write(tmp_path, document))


def test_a_v2_pin_missing_its_representation_is_rejected(tmp_path: Path) -> None:
    document = _v2_pin()
    del document["representation"]
    with pytest.raises(ValueError, match="fields differ"):
        load_payload_metadata(_write(tmp_path, document))


def test_an_unknown_payload_schema_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unsupported payload metadata schema"):
        load_payload_metadata(_write(tmp_path, _v2_pin(schema_version="3.0.0")))


def test_a_v2_pin_naming_a_v1_dataset_is_rejected(tmp_path: Path) -> None:
    document = _v2_pin(dataset_version=V1_DATASET)
    document["archive"]["filename"] = f"scoutlens-showcase-{V1_DATASET}-{SHA}.tar.gz"
    document["archive"]["url"] = f"https://example.test/{document['archive']['filename']}"
    with pytest.raises(ValueError, match="must name a wyscout-2017-18-v2-"):
        load_payload_metadata(_write(tmp_path, document))


def test_a_v2_pin_promising_the_wrong_artifact_contract_is_rejected(tmp_path: Path) -> None:
    """The pin schema and the showcase contract are different numbers; a v2 pin
    that claims to hydrate showcase 1.0.0 is describing something else."""
    with pytest.raises(ValueError, match="hydrates showcase 2.0.0"):
        load_payload_metadata(_write(tmp_path, _v2_pin(showcase_schema_version="1.0.0")))


def test_a_non_https_url_is_rejected(tmp_path: Path) -> None:
    document = _v2_pin()
    document["archive"]["url"] = document["archive"]["url"].replace("https://", "http://")
    with pytest.raises(ValueError, match="HTTPS"):
        load_payload_metadata(_write(tmp_path, document))


def test_a_filename_that_is_not_content_addressed_is_rejected(tmp_path: Path) -> None:
    document = _v2_pin()
    document["archive"]["filename"] = "payload.tar.gz"
    document["archive"]["url"] = "https://example.test/payload.tar.gz"
    with pytest.raises(ValueError, match="not content-addressed"):
        load_payload_metadata(_write(tmp_path, document))


# --- writing a pin ---------------------------------------------------------


def test_writing_a_pin_refuses_to_replace_without_authority(tmp_path: Path) -> None:
    output = tmp_path / "pin.json"
    write_pin(_v2_pin(), output)
    with pytest.raises(ValueError, match="refusing to replace"):
        write_pin(_v2_pin(), output)
    write_pin(_v2_pin(), output, replace=True)


def test_a_pin_that_cannot_be_read_back_is_never_published(tmp_path: Path) -> None:
    """The writer round-trips through the loader, so a malformed document does
    not become the file every clone reads."""
    output = tmp_path / "pin.json"
    with pytest.raises(ValueError):
        write_pin(_v2_pin(showcase_schema_version="1.0.0"), output)
    assert not output.exists()


# --- hydration selects its own target --------------------------------------


@pytest.mark.skipif(
    not (REAL_V2_ROOT / "manifest.json").is_file(),
    reason="requires the published showcase-v2 dataset",
)
def test_a_v2_pin_resolves_the_v2_root_and_never_v1(tmp_path: Path) -> None:
    """AC4: the hydration target is derived from the validated pin, so a v2 pin
    can never quietly land in the v1 tree."""
    manifest_bytes = (REAL_V2_ROOT / "manifest.json").read_bytes().replace(b"\r\n", b"\n")
    representation_bytes = (
        (REAL_V2_ROOT / "representation.json").read_bytes().replace(b"\r\n", b"\n")
    )
    dataset = json.loads(manifest_bytes)["dataset_version"]
    document = _v2_pin(
        dataset_version=dataset,
        manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        representation={
            "id": json.loads(representation_bytes)["representation"]["id"],
            "sha256": hashlib.sha256(representation_bytes).hexdigest(),
        },
    )
    document["archive"]["filename"] = f"scoutlens-showcase-{dataset}-{SHA}.tar.gz"
    document["archive"]["url"] = f"https://example.test/{document['archive']['filename']}"

    metadata = load_payload_metadata(_write(tmp_path, document))
    assert metadata.showcase_root == REAL_V2_ROOT
    assert metadata.showcase_root.name != "v1"


# --- the real candidate ----------------------------------------------------

integration = pytest.mark.skipif(
    os.environ.get("SCOUTLENS_SHOWCASE_PAYLOAD_INTEGRATION") != "1"
    or not REAL_CANDIDATE.is_file()
    or not (REAL_V2_ROOT / "manifest.json").is_file(),
    reason="requires the qop.6.4.4 candidate and SCOUTLENS_SHOWCASE_PAYLOAD_INTEGRATION=1",
)


def _real_arguments() -> dict:
    sidecar = REAL_CANDIDATE.with_name(f"{REAL_CANDIDATE.name}.metadata.json")
    proposed = json.loads(sidecar.read_text(encoding="utf-8"))["archive"]["proposed_filename"]
    return {
        "sidecar_path": sidecar,
        "archive_path": REAL_CANDIDATE,
        "manifest_path": REAL_V2_ROOT / "manifest.json",
        "representation_path": REAL_V2_ROOT / "representation.json",
        "url": f"https://example.test/releases/{proposed}",
    }


@integration
def test_the_real_candidate_pins_deterministically(tmp_path: Path) -> None:
    arguments = _real_arguments()
    first = build_pin_document(**arguments)
    second = build_pin_document(**arguments)
    assert canonical_json_bytes(first) == canonical_json_bytes(second)

    manifest_bytes = (REAL_V2_ROOT / "manifest.json").read_bytes().replace(b"\r\n", b"\n")
    assert first["manifest_sha256"] == hashlib.sha256(manifest_bytes).hexdigest()
    assert first["path_count"] == 1257
    assert first["schema_version"] == PAYLOAD_SCHEMA_VERSION_V2

    # Loadable, which is the only definition of a usable pin.
    written = write_pin(first, tmp_path / "pin.json")
    assert load_payload_metadata(written).showcase_major == 2


@integration
def test_one_byte_of_archive_drift_refuses_the_pin(tmp_path: Path) -> None:
    arguments = _real_arguments()
    tampered = tmp_path / REAL_CANDIDATE.name
    payload = bytearray(REAL_CANDIDATE.read_bytes())
    payload[len(payload) // 2] ^= 0x01
    tampered.write_bytes(bytes(payload))
    arguments["archive_path"] = tampered

    with pytest.raises(ValueError, match="sidecar describes"):
        build_pin_document(**arguments)


@integration
def test_a_wrong_url_refuses_the_pin() -> None:
    arguments = _real_arguments()
    arguments["url"] = "https://example.test/releases/some-other-name.tar.gz"
    with pytest.raises(ValueError, match="must end with"):
        build_pin_document(**arguments)


@integration
def test_a_foreign_representation_refuses_the_pin(tmp_path: Path) -> None:
    arguments = _real_arguments()
    artifact = json.loads((REAL_V2_ROOT / "representation.json").read_text(encoding="utf-8"))
    artifact["representation"]["id"] = "rep-ffffffffffffffff"
    foreign = tmp_path / "representation.json"
    foreign.write_bytes(canonical_json_bytes(artifact))
    arguments["representation_path"] = foreign

    with pytest.raises(ValueError, match="different representations"):
        build_pin_document(**arguments)
