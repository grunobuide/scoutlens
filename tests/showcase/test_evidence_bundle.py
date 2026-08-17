"""The scientific-evidence archive (`scoutlens-qop.6.4.4`).

Most of this file is refusals. A packer that has only ever been handed a good
run directory has not been shown to exclude anything, and exclusion is the whole
job here: the run directory also holds 287 MB of checkpoints that must never
reach a release asset.

The fixtures are synthetic rather than the real 1.6 MiB run, so the offline
suite stays offline and each refusal can be provoked exactly. The real run is
exercised by the opt-in tests at the bottom.
"""

from __future__ import annotations

import hashlib
import json
import os
import tarfile
from pathlib import Path

import pytest

from scoutlens.showcase.evidence_bundle import (
    ARCHIVE_MEMBERS,
    DESIGN_VERSION,
    RANKING_METHOD,
    SOURCE_MEMBERS,
    build_evidence_archive,
    build_readme,
    load_run,
    verify_evidence_archive,
    verify_representation,
)
from scoutlens.showcase.io import canonical_json_bytes

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_RUN_DIR = REPO_ROOT / "artifacts" / "uncertainty" / DESIGN_VERSION
REAL_REPRESENTATION = REPO_ROOT / "public" / "showcase" / "v2" / "representation.json"

REPRESENTATION_ID = "rep-f018e6041ccbad10"
DATASET_VERSION = "wyscout-2017-18-v2-0123456789ab"

PARQUET_BODIES = {
    "feature-uncertainty.parquet": b"feature-uncertainty-bytes",
    "retrieval-uncertainty.parquet": b"retrieval-uncertainty-bytes",
    "neighbor-stability.parquet": b"neighbor-stability-bytes",
}


def _run_document() -> dict:
    outputs = {
        name.split("-")[0]: {
            "path": name,
            "bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest(),
            "rows": 1,
        }
        for name, body in PARQUET_BODIES.items()
    }
    return {
        "format": "scoutlens.match-bootstrap-summary/1",
        "status": "available",
        "requested_resamples": 500,
        "completed_resamples": 500,
        "valid_resamples": 500,
        "outputs": outputs,
        "manifest": {
            "design_version": DESIGN_VERSION,
            "ranking_method": RANKING_METHOD,
            "representation_id": REPRESENTATION_ID,
            "requested_resamples": 500,
            "profile_count": 1257,
            "draw_plan_sha256": "05a0019e" * 8,
            "cohort_sha256": "96e23e5b" * 8,
            "experiment_config_path": "config/experiment.json",
            "experiment_config_sha256": "6b04c4eb" * 8,
        },
    }


@pytest.fixture
def run_dir(tmp_path) -> Path:
    directory = tmp_path / "run"
    directory.mkdir()
    for name, body in PARQUET_BODIES.items():
        (directory / name).write_bytes(body)
    # A checkpoint, exactly like the real run directory carries. Nothing below
    # may ever put it in an archive.
    (directory / "checkpoints").mkdir()
    (directory / "checkpoints" / "resample-0001.parquet").write_bytes(b"x" * 64)
    (directory / "run.json").write_text(json.dumps(_run_document()), encoding="utf-8")
    return directory


@pytest.fixture
def representation(tmp_path) -> Path:
    path = tmp_path / "representation.json"
    path.write_bytes(
        canonical_json_bytes(
            {
                "contract": "scoutlens.showcase",
                "schema_version": "2.0.0",
                "dataset_version": DATASET_VERSION,
                "representation": {
                    "id": REPRESENTATION_ID,
                    "ranking_method": RANKING_METHOD,
                    "uncertainty_design": DESIGN_VERSION,
                },
            }
        )
    )
    return path


def _build(run_dir: Path, representation: Path, tmp_path: Path, name: str = "candidate.tar.gz"):
    return build_evidence_archive(run_dir, tmp_path / name, representation_path=representation)


def _members(archive_path: Path) -> list[str]:
    with tarfile.open(archive_path, mode="r:gz") as archive:
        return [member.name for member in archive.getmembers()]


# --- what it packs ---------------------------------------------------------


def test_the_archive_holds_exactly_the_allowlist(run_dir, representation, tmp_path) -> None:
    build = _build(run_dir, representation, tmp_path)
    assert _members(tmp_path / "candidate.tar.gz") == list(ARCHIVE_MEMBERS)
    assert build.member_count == 6
    assert build.representation_id == REPRESENTATION_ID
    assert build.dataset_version == DATASET_VERSION


def test_no_checkpoint_reaches_the_archive(run_dir, representation, tmp_path) -> None:
    """The run directory carries 287 MB of checkpoints. They are excluded by an
    allowlist rather than a filter, because a filter ships whatever nobody
    thought to exclude."""
    _build(run_dir, representation, tmp_path)
    assert not any("checkpoint" in name for name in _members(tmp_path / "candidate.tar.gz"))


def test_every_member_is_a_plain_file_at_the_archive_root(run_dir, representation, tmp_path) -> None:
    _build(run_dir, representation, tmp_path)
    with tarfile.open(tmp_path / "candidate.tar.gz", mode="r:gz") as archive:
        for member in archive.getmembers():
            assert member.isfile()
            assert "/" not in member.name and not member.name.startswith(".")
            assert (member.mtime, member.mode, member.uid, member.gid) == (0, 0o644, 0, 0)
            assert (member.uname, member.gname) == ("", "")


def test_two_builds_are_byte_identical(run_dir, representation, tmp_path) -> None:
    first = _build(run_dir, representation, tmp_path, "first.tar.gz")
    second = _build(run_dir, representation, tmp_path, "second.tar.gz")
    assert first.sha256 == second.sha256
    assert (tmp_path / "first.tar.gz").read_bytes() == (tmp_path / "second.tar.gz").read_bytes()


def test_the_checksums_cover_exactly_the_four_sources(run_dir, representation, tmp_path) -> None:
    _build(run_dir, representation, tmp_path)
    checksums = verify_evidence_archive(tmp_path / "candidate.tar.gz")
    assert [entry["path"] for entry in checksums["files"]] == list(SOURCE_MEMBERS)
    for entry in checksums["files"]:
        payload = (run_dir / entry["path"]).read_bytes()
        assert entry["bytes"] == len(payload)
        assert entry["sha256"] == hashlib.sha256(payload).hexdigest()


def test_the_sidecar_proposes_a_content_addressed_name(run_dir, representation, tmp_path) -> None:
    build = _build(run_dir, representation, tmp_path)
    sidecar = json.loads((tmp_path / "candidate.tar.gz.metadata.json").read_text(encoding="utf-8"))
    assert build.sha256 in sidecar["archive"]["proposed_filename"]
    assert DATASET_VERSION in sidecar["archive"]["proposed_filename"]
    assert sidecar["archive"]["sha256"] == build.sha256
    assert sidecar["representation_id"] == REPRESENTATION_ID
    assert sidecar["runtime_input"] is False


# --- the README states the boundary, not the result ------------------------


def test_the_readme_records_identity_completeness_and_the_caveat_boundary() -> None:
    readme = build_readme(
        _run_document(), representation_id=REPRESENTATION_ID, dataset_version=DATASET_VERSION
    )
    assert REPRESENTATION_ID in readme
    assert RANKING_METHOD in readme and DESIGN_VERSION in readme
    assert "500/500 completed" in readme and "500/500 valid" in readme
    assert "not a public-site runtime input" in readme.lower()
    assert "scoutlens.uncertainty.run" in readme
    for forbidden in ("causal", "recruitment", "transfer-success", "prediction of future performance"):
        assert forbidden in readme.lower()


def test_the_readme_copies_no_headline_performance_number() -> None:
    """A result quoted beside its own evidence invites the reader to trust the
    quote instead of the evidence."""
    readme = build_readme(
        _run_document(), representation_id=REPRESENTATION_ID, dataset_version=DATASET_VERSION
    ).lower()
    for claim in ("mrr", "recall@", "recall at", "precision", "improvement", "outperform", "better than"):
        assert claim not in readme, claim


# --- refusals --------------------------------------------------------------


def test_a_cosine_design_is_refused(run_dir, representation, tmp_path) -> None:
    document = _run_document()
    document["manifest"]["design_version"] = "match_bootstrap_v1"
    (run_dir / "run.json").write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="requires design"):
        _build(run_dir, representation, tmp_path)


def test_a_wrong_scorer_is_refused(run_dir, representation, tmp_path) -> None:
    document = _run_document()
    document["manifest"]["ranking_method"] = "cosine_v1"
    (run_dir / "run.json").write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="requires scorer"):
        _build(run_dir, representation, tmp_path)


def test_a_foreign_representation_is_refused(run_dir, representation, tmp_path) -> None:
    document = _run_document()
    document["manifest"]["representation_id"] = "rep-ffffffffffffffff"
    (run_dir / "run.json").write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="but rep-f018e6041ccbad10 is published"):
        _build(run_dir, representation, tmp_path)


def test_an_incomplete_run_is_refused(run_dir, representation, tmp_path) -> None:
    document = _run_document()
    document["valid_resamples"] = 499
    (run_dir / "run.json").write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="of 500 resamples"):
        _build(run_dir, representation, tmp_path)


def test_a_missing_member_is_refused(run_dir, representation, tmp_path) -> None:
    (run_dir / "neighbor-stability.parquet").unlink()
    with pytest.raises(ValueError, match="missing or not a regular file"):
        _build(run_dir, representation, tmp_path)


def test_a_source_that_drifted_from_run_json_is_refused(run_dir, representation, tmp_path) -> None:
    """One byte. The run recorded a digest when it wrote the file; a file that
    changed afterwards is evidence of nothing."""
    path = run_dir / "retrieval-uncertainty.parquet"
    payload = bytearray(path.read_bytes())
    payload[0] ^= 0x01
    path.write_bytes(bytes(payload))
    with pytest.raises(ValueError, match="differs from the digest run.json recorded"):
        _build(run_dir, representation, tmp_path)


def test_an_extra_file_in_the_run_directory_does_not_change_the_archive(
    run_dir, representation, tmp_path
) -> None:
    """The allowlist is positive: a new file appearing beside the outputs is
    ignored, not packed."""
    before = _build(run_dir, representation, tmp_path, "before.tar.gz")
    (run_dir / "surprise.parquet").write_bytes(b"unapproved")
    after = _build(run_dir, representation, tmp_path, "after.tar.gz")
    assert before.sha256 == after.sha256
    assert _members(tmp_path / "after.tar.gz") == list(ARCHIVE_MEMBERS)


def test_an_existing_archive_is_never_overwritten(run_dir, representation, tmp_path) -> None:
    _build(run_dir, representation, tmp_path)
    with pytest.raises(ValueError, match="refusing to overwrite"):
        _build(run_dir, representation, tmp_path)


def test_a_traversing_member_name_is_refused(run_dir, representation, tmp_path) -> None:
    from scoutlens.showcase.evidence_bundle import _validate_member_name

    for name in ("../escape.json", "/etc/passwd", "nested/file.json", "..", "sub\\file.json"):
        with pytest.raises(ValueError, match="unsafe archive member path"):
            _validate_member_name(name)


def test_a_single_flipped_byte_fails_verification(run_dir, representation, tmp_path) -> None:
    """One byte in the compressed stream. It surfaces either as a decompression
    failure or as a checksum mismatch depending on where it lands; both are
    correct refusals, and passing is not among the options.

    Flipping a byte in the gzip *trailer* would not do: `tarfile` stops after the
    last member and never reads it, so a trailer-only corruption goes unnoticed.
    """
    _build(run_dir, representation, tmp_path)
    archive_path = tmp_path / "candidate.tar.gz"
    payload = bytearray(archive_path.read_bytes())
    payload[len(payload) // 2] ^= 0x40
    archive_path.write_bytes(bytes(payload))
    with pytest.raises(Exception):
        verify_evidence_archive(archive_path)


def test_a_repacked_archive_with_a_wrong_checksum_is_refused(run_dir, representation, tmp_path) -> None:
    """Rebuild the tar by hand with CHECKSUMS.json claiming the wrong digest.
    The archive is well-formed; only the claim inside it is false."""
    _build(run_dir, representation, tmp_path)
    source = tmp_path / "candidate.tar.gz"
    with tarfile.open(source, mode="r:gz") as archive:
        payloads = {
            member.name: archive.extractfile(member).read()  # type: ignore[union-attr]
            for member in archive.getmembers()
        }
    checksums = json.loads(payloads["CHECKSUMS.json"])
    checksums["files"][0]["sha256"] = "0" * 64
    payloads["CHECKSUMS.json"] = canonical_json_bytes(checksums)

    forged = tmp_path / "forged.tar.gz"
    import gzip
    import io

    with forged.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w|", format=tarfile.USTAR_FORMAT) as archive:
                for name in ARCHIVE_MEMBERS:
                    info = tarfile.TarInfo(name)
                    info.size = len(payloads[name])
                    info.mtime, info.mode, info.uid, info.gid = 0, 0o644, 0, 0
                    archive.addfile(info, io.BytesIO(payloads[name]))
    with pytest.raises(ValueError, match="do not match CHECKSUMS.json"):
        verify_evidence_archive(forged)


def test_a_representation_naming_another_design_is_refused(run_dir, representation, tmp_path) -> None:
    artifact = json.loads(representation.read_text(encoding="utf-8"))
    artifact["representation"]["uncertainty_design"] = "match_bootstrap_v1"
    representation.write_bytes(canonical_json_bytes(artifact))
    with pytest.raises(ValueError, match="different uncertainty design"):
        _build(run_dir, representation, tmp_path)


# --- the real run ----------------------------------------------------------

integration = pytest.mark.skipif(
    os.environ.get("SCOUTLENS_SHOWCASE_PAYLOAD_INTEGRATION") != "1"
    or not (REAL_RUN_DIR / "run.json").is_file()
    or not REAL_REPRESENTATION.is_file(),
    reason="requires the diagonal uncertainty run, the published v2 representation "
    "and SCOUTLENS_SHOWCASE_PAYLOAD_INTEGRATION=1",
)


@integration
def test_the_real_run_builds_deterministically(tmp_path) -> None:
    first = build_evidence_archive(
        REAL_RUN_DIR, tmp_path / "a.tar.gz", representation_path=REAL_REPRESENTATION
    )
    second = build_evidence_archive(
        REAL_RUN_DIR, tmp_path / "b.tar.gz", representation_path=REAL_REPRESENTATION
    )
    assert first.sha256 == second.sha256
    assert (tmp_path / "a.tar.gz").read_bytes() == (tmp_path / "b.tar.gz").read_bytes()
    assert first.representation_id == REPRESENTATION_ID
    assert _members(tmp_path / "a.tar.gz") == list(ARCHIVE_MEMBERS)


@integration
def test_the_real_run_lineage_matches_the_published_representation() -> None:
    run = load_run(REAL_RUN_DIR)
    representation_id, dataset_version = verify_representation(run, REAL_REPRESENTATION)
    assert representation_id == REPRESENTATION_ID
    assert dataset_version.startswith("wyscout-2017-18-v2-")
