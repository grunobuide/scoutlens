"""The audit document has to stay true, or it is worse than no document.

`docs/release-candidate-v1.md` records digests, versions and counts. Every one
of those is a copy of something computable, and a copy nobody checks is a claim
that quietly stops being true. So the checkable ones are checked here against
the live tree.

Deliberately **not** checked: the git commit and anything derived from it. A
candidate is a decision about a specific commit, and the document recording one
cannot also be inside it.
"""

from __future__ import annotations

import re

import pytest

from scoutlens.release.claims import build_matrix
from scoutlens.release.manifest import REPO_ROOT, build_manifest

DOC = REPO_ROOT / "docs" / "release-candidate-v1.md"

requires_doc = pytest.mark.skipif(not DOC.is_file(), reason="release-candidate doc not present")
pytestmark = requires_doc

#: `| \`path\` | \`sha256\` |` rows in the document's identity tables.
DIGEST_ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*`([0-9a-f]{64})`\s*\|", re.MULTILINE)


@pytest.fixture(scope="module")
def doc() -> str:
    return DOC.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def prose(doc: str) -> str:
    """The document with its line wrapping flattened.

    Searching a hard-wrapped document for a phrase finds nothing the moment the
    phrase straddles a newline, which makes the assertion depend on where the
    author's editor happened to wrap. That is a property of the formatting, not
    of the claim being checked.
    """
    return " ".join(doc.split()).lower()


@pytest.fixture(scope="module")
def manifest() -> dict:
    return build_manifest()


def test_every_digest_the_document_records_is_current(doc: str, manifest: dict) -> None:
    """A stale digest in a freeze record is the whole failure mode."""
    rows = DIGEST_ROW.findall(doc)
    assert rows, "the document records no digests; the identity tables are gone"

    live = {**manifest["config_digests"], **manifest["artifact_digests"]}
    checked = 0
    for path, recorded in rows:
        if path not in live:
            continue  # a digest of something the manifest does not track, e.g. the payload archive
        actual = live[path]
        if actual is None:
            continue  # not present in this checkout
        assert recorded == actual, f"{path}: document says {recorded[:12]}, tree has {actual[:12]}"
        checked += 1

    assert checked >= 6, f"only {checked} digests cross-checked; the tables may have been gutted"


def test_the_document_records_the_version_being_frozen(doc: str, manifest: dict) -> None:
    assert f"`{manifest['project_version']}`" in doc
    assert manifest["project_version"] != "0.0.0"


def test_the_document_records_the_dataset_and_representation(doc: str, manifest: dict) -> None:
    showcase = manifest["contracts"]["showcase"]
    assert showcase["dataset_version"] in doc
    assert showcase["representation_id"] in doc
    assert manifest["payload_pin"]["archive_sha256"] in doc


def test_the_document_records_every_contract_version(doc: str, manifest: dict) -> None:
    """A contract frozen without being named is a contract nobody pinned."""
    for key, version in manifest["contracts"].items():
        if key == "showcase":
            continue
        label = key.replace("_", " ")
        assert version in doc, f"{label} version {version} is not recorded"


def test_the_claim_counts_match_the_artifact(doc: str) -> None:
    matrix = build_matrix()
    assert f"{len(matrix.rows)} claims" in doc
    for row in matrix.rows:
        assert row.experiment_id in doc, f"{row.experiment_id} is missing from the matrix table"


def test_the_document_states_what_is_not_claimed(prose: str) -> None:
    """The boundary is the part most worth keeping honest."""
    for phrase in ("playing style", "recruitment", "predicts future"):
        assert phrase in prose, f"the document never states that {phrase!r} is not claimed"


def test_the_document_records_the_unevaluated_model(prose: str) -> None:
    """The largest gap in the release is the one most easily dropped from a summary."""
    assert "not_run" in prose
    assert "no claim about any model" in prose


def test_every_bead_the_document_cites_looks_like_a_bead(doc: str) -> None:
    cited = set(re.findall(r"scoutlens-[a-z0-9]+(?:\.\d+)*", doc))
    assert cited, "the document cites no beads"
    assert "scoutlens-jtt.7.1" in cited


def test_the_reproduction_section_names_real_commands(doc: str) -> None:
    """A reproduction section listing commands that do not exist is a trap."""
    for command in (
        "scoutlens.release.manifest",
        "scoutlens.release.claims",
        "scoutlens.explanations.evals.run_report --check",
        "scoutlens.showcase.payload hydrate",
    ):
        assert command in doc, f"{command} is not in the reproduction section"

    for module in ("release/manifest.py", "release/claims.py"):
        assert (REPO_ROOT / "src" / "scoutlens" / module).is_file(), module


def test_the_changelog_agrees_with_the_frozen_version(manifest: dict) -> None:
    changelog = REPO_ROOT / "CHANGELOG.md"
    if not changelog.is_file():
        pytest.skip("no changelog in this checkout")
    text = changelog.read_text(encoding="utf-8")
    assert f"[{manifest['project_version']}]" in text
    assert "not_run" in text or "no demonstration model" in text.lower()


def test_the_licence_statements_agree() -> None:
    """Four files state the code licence. A 1.0.0 in which they disagree is not one.

    `DATA_LICENSES.md` said 'not yet decided' while `LICENSE`, `pyproject.toml`
    and `README.md` all said MIT. Found during this audit; asserted here so it
    cannot drift apart again.
    """
    licence = (REPO_ROOT / "LICENSE").read_text(encoding="utf-8")
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    data_licences = (REPO_ROOT / "DATA_LICENSES.md").read_text(encoding="utf-8")

    assert "MIT License" in licence
    assert 'license = "MIT"' in pyproject
    assert "[MIT](LICENSE)" in readme
    assert "[MIT](LICENSE)" in data_licences
    assert "not yet decided" not in data_licences


def test_the_document_is_not_a_stub(doc: str) -> None:
    """A freeze record that fits on a screen has not audited anything."""
    assert len(doc) > 8000
    for heading in ("What is being frozen", "Gate results", "Claims matrix", "Findings"):
        assert heading in doc
