"""The release-candidate manifest, held to the one property it exists for.

A manifest whose value depends on when or where it ran cannot identify a
candidate. So the digest is stable across runs, the tree-state fields are
excluded from it and recorded beside it, and a dirty tree is reported rather
than smoothed over.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scoutlens.release.manifest import (
    ARTIFACT_FILES,
    CONFIG_FILES,
    LOCK_FILES,
    REPO_ROOT,
    TEXT_SUFFIXES,
    _sha256,
    build_manifest,
    main,
    manifest_digest,
)


@pytest.fixture(scope="module")
def manifest() -> dict:
    return build_manifest()


def test_two_runs_agree(manifest: dict) -> None:
    """The digest identifies a commit, so it cannot drift between runs."""
    assert manifest_digest(manifest) == manifest_digest(build_manifest())


def test_the_digest_ignores_the_working_tree(manifest: dict) -> None:
    """`dirty` describes the checkout, not the candidate.

    Including it would make a commit's identity depend on whether someone had an
    editor open, which is exactly the kind of thing a content-addressed digest
    is supposed to be immune to.
    """
    dirty = json.loads(json.dumps(manifest))
    dirty["git"]["dirty"] = not dirty["git"]["dirty"]
    dirty["git"]["dirty_paths"] = ["some/scratch/file"]
    assert manifest_digest(dirty) == manifest_digest(manifest)


def test_the_commit_is_part_of_the_identity(manifest: dict) -> None:
    """Two different commits are two different candidates."""
    other = json.loads(json.dumps(manifest))
    other["git"]["commit"] = "0" * 40
    assert manifest_digest(other) != manifest_digest(manifest)


def test_every_named_input_is_recorded(manifest: dict) -> None:
    """A file listed and not hashed would be a silent gap in the freeze."""
    for group, names in (
        ("config_digests", CONFIG_FILES),
        ("dependency_digests", LOCK_FILES),
        ("artifact_digests", ARTIFACT_FILES),
    ):
        assert set(manifest[group]) == set(names), group
        for name, digest in manifest[group].items():
            if (REPO_ROOT / name).is_file():
                assert digest and len(digest) == 64, f"{name} present but not hashed"


def test_the_manifest_records_both_toolchains(manifest: dict) -> None:
    """The site and the science ship together, so both locks are pinned."""
    assert manifest["dependency_digests"]["uv.lock"]
    assert manifest["dependency_digests"]["web/pnpm-lock.yaml"]
    assert manifest["runtime"]["node_version_file"]
    assert manifest["runtime"]["ci_python_versions"] == ["3.11", "3.14"]


def test_the_contract_versions_are_all_named(manifest: dict) -> None:
    contracts = manifest["contracts"]
    for key in (
        "explanation_bundle_schema",
        "explanation_output_schema",
        "prompt_contract",
        "adapter_protocol",
        "eval_corpus",
    ):
        assert contracts[key], key
    assert contracts["showcase"]["dataset_version"]
    assert contracts["showcase"]["schema_version"] == "2.0.0"


def test_the_payload_pin_is_content_addressed(manifest: dict) -> None:
    """The pin is what makes the dataset reproducible from a clean clone."""
    pin = manifest["payload_pin"]
    assert pin["available"] is True
    assert len(pin["archive_sha256"]) == 64
    assert pin["dataset_version"] == manifest["contracts"]["showcase"]["dataset_version"]
    assert pin["representation"]["id"] == manifest["contracts"]["showcase"]["representation_id"]


def test_the_representation_digest_matches_the_published_artifact(manifest: dict) -> None:
    """The pin claims a representation digest; the published file must be it."""
    published = manifest["artifact_digests"]["public/showcase/v2/representation.json"]
    if published is None:
        pytest.skip("representation.json is not present in this checkout")
    assert manifest["payload_pin"]["representation"]["sha256"] == published


def test_a_dirty_tree_is_reported_not_smoothed_over(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture, tmp_path: Path
) -> None:
    """A candidate frozen from a dirty tree is not reproducible, and exits non-zero."""
    import scoutlens.release.manifest as module

    dirty = build_manifest()
    dirty["git"]["dirty"] = True
    dirty["git"]["dirty_paths"] = ["src/scratch.py"]
    monkeypatch.setattr(module, "build_manifest", lambda: dirty)

    assert main(["--output", str(tmp_path / "rc.json")]) == 1
    assert "working tree is dirty" in capsys.readouterr().err

    written = json.loads((tmp_path / "rc.json").read_text(encoding="utf-8"))
    assert written["git"]["dirty"] is True
    assert written["manifest_digest"]


def test_the_manifest_writes_nothing_by_default(capsys: pytest.CaptureFixture) -> None:
    """It reports an identity. Freezing one is a decision, not a side effect."""
    main([])
    printed = json.loads(capsys.readouterr().out)
    assert printed["contract"] == "scoutlens.release-candidate"


# --- the digest identifies content, not the checkout ---------------------


def test_a_text_digest_ignores_line_endings(tmp_path: Path) -> None:
    """The bug CI caught after the audit document had recorded the wrong values.

    `config/experiment.json` and the two uncertainty configs carry no `eol=lf`
    rule, so a Windows checkout holds CRLF and a Linux one holds LF. Hashing raw
    bytes gave the same commit two different identities depending on who ran the
    command, which is not an identity.
    """
    content = '{\n  "a": 1,\n  "b": 2\n}\n'
    lf = tmp_path / "lf.json"
    crlf = tmp_path / "crlf.json"
    lf.write_bytes(content.encode())
    crlf.write_bytes(content.replace("\n", "\r\n").encode())

    assert lf.read_bytes() != crlf.read_bytes(), "the fixture failed to differ"
    assert _sha256(lf) == _sha256(crlf)


def test_a_binary_digest_is_not_normalised(tmp_path: Path) -> None:
    """Only text is normalised. Rewriting bytes inside a binary would be a new bug."""
    payload = bytes([0, 13, 10, 1])
    binary = tmp_path / "payload.bin"
    binary.write_bytes(payload)

    assert ".bin" not in TEXT_SUFFIXES
    assert _sha256(binary) == hashlib.sha256(payload).hexdigest()


def test_the_manifest_states_how_it_digests(manifest: dict) -> None:
    """A digest that silently transforms its input is one nobody can reproduce."""
    assert "normalised" in manifest["digest_mode"]
    assert "sha256" in manifest["digest_mode"]


def test_every_config_the_manifest_pins_is_digested_portably() -> None:
    """Each pinned config is a text file, so each one is normalised."""
    for name in CONFIG_FILES:
        assert Path(name).suffix in TEXT_SUFFIXES, f"{name} would be hashed raw"
