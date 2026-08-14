"""End-to-end bounded showcase-v2 export (`scoutlens-qop.6.4.2`, AC2 and AC5).

Bounded means one competition rather than the full 1,257: the
contract semantics are proven end to end without a production regeneration,
which is explicitly this leaf's non-goal.

Opt-in, like the other integration suites, because it needs local processed
Wyscout data and the diagonal uncertainty run. Skipped by default so the
offline suite stays offline.

This suite is the first thing to route a schema-complete artifact through
`major=2`, and it is what found both blockers it since cleared: the frozen v2
schema pinned `schema_version` to `"1.0.0"` on four artifact types
(`scoutlens-qop.6.4.5`, `D048`), and the publication path was v1-hardcoded
below the contract validator.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from scoutlens.showcase.export import V2_REPRESENTATION_PATH, V2_SCHEMA_VERSION, export_showcase

REPO_ROOT = Path(__file__).resolve().parents[2]
PROCESSED = REPO_ROOT / "data" / "processed"
DIAGONAL_RUN = REPO_ROOT / "artifacts" / "uncertainty" / "match_bootstrap_diagonal_v1"
BENCHMARK = REPO_ROOT / "artifacts" / "benchmark" / "diagonal-results.json"

#: The editorially featured profile is ``wy-8287-c-795``, so the bounded
#: cohort is competition 795: the manifest names that profile and validation
#: requires it to resolve. Choosing a cohort without it would have meant
#: relaxing a published-directory rule to fit a fixture.
BOUNDED_COMPETITION = 795
REPRESENTATION_ID = "rep-f018e6041ccbad10"

pytestmark = [
    pytest.mark.skipif(
        os.environ.get("SCOUTLENS_SHOWCASE_INTEGRATION") != "1"
        or not (PROCESSED / "period_profiles.parquet").is_file()
        or not (DIAGONAL_RUN / "run.json").is_file(),
        reason="requires local processed data, the diagonal uncertainty run and SCOUTLENS_SHOWCASE_INTEGRATION=1",
    ),
]


def _export(output_dir: Path, *, generated_at: str = "2026-08-13T00:00:00+00:00") -> dict:
    return export_showcase(
        output_dir=output_dir,
        schema_version=V2_SCHEMA_VERSION,
        representation_artifact=BENCHMARK,
        bootstrap_run_dir=DIAGONAL_RUN,
        competition_ids=[BOUNDED_COMPETITION],
        expected_profile_count=None,
        generated_at=generated_at,
    )


def _collect_representation_ids(value, found: set[str]) -> None:
    if isinstance(value, dict):
        if isinstance(value.get("representation_id"), str):
            found.add(value["representation_id"])
        for child in value.values():
            _collect_representation_ids(child, found)
    elif isinstance(value, list):
        for child in value:
            _collect_representation_ids(child, found)


@pytest.fixture(scope="module")
def exported(tmp_path_factory) -> Path:
    target = tmp_path_factory.mktemp("v2") / "showcase-v2"
    _export(target)
    return target


# --- AC2 -------------------------------------------------------------------


def test_the_bundle_publishes_a_representation(exported: Path) -> None:
    artifact = json.loads((exported / V2_REPRESENTATION_PATH).read_text(encoding="utf-8"))
    assert artifact["schema_version"] == V2_SCHEMA_VERSION
    assert artifact["representation"]["id"] == REPRESENTATION_ID
    assert len(artifact["representation"]["weights"]) == 28


def test_the_manifest_hashes_every_published_file(exported: Path) -> None:
    manifest = json.loads((exported / "manifest.json").read_text(encoding="utf-8"))
    published = {entry["path"]: entry for entry in manifest["files"]}
    assert V2_REPRESENTATION_PATH in published

    on_disk = {
        path.relative_to(exported).as_posix()
        for path in exported.rglob("*.json")
        if path.name != "manifest.json"
    }
    assert on_disk == set(published)

    for path, entry in published.items():
        payload = (exported / path).read_bytes()
        assert entry["bytes"] == len(payload), path
        assert entry["sha256"] == hashlib.sha256(payload).hexdigest(), path


def test_the_manifest_declares_v2_and_names_the_representation(exported: Path) -> None:
    manifest = json.loads((exported / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == V2_SCHEMA_VERSION
    assert manifest["representation_id"] == REPRESENTATION_ID
    assert manifest["population"]["domestic_competition_ids"] == [BOUNDED_COMPETITION]


def test_every_representation_reference_in_the_bundle_agrees(exported: Path) -> None:
    """Retrieval, neighbour, evidence and uncertainty blocks must all name the
    same representation; a bundle mixing two is unpublishable."""
    found: set[str] = set()
    for path in sorted(exported.rglob("*.json")):
        _collect_representation_ids(json.loads(path.read_text(encoding="utf-8")), found)
    assert found == {REPRESENTATION_ID}


def test_profiles_report_a_similarity_score_not_a_cosine(exported: Path) -> None:
    profile = json.loads(
        next(iter(sorted((exported / "players").glob("*.json")))).read_text(encoding="utf-8")
    )
    outcome = profile["retrieval"]["global"]
    assert "similarity_score" in outcome
    assert "cosine_similarity" not in outcome
    assert outcome["representation_id"] == REPRESENTATION_ID
    for neighbor in profile["neighbors"]:
        assert "similarity_score" in neighbor
        assert "cosine_similarity" not in neighbor


def test_uncertainty_is_diagonal_throughout(exported: Path) -> None:
    """No cosine interval may enter a diagonal bundle: a v1 interval describes
    the stability of a different metric."""
    profile = json.loads(
        next(iter(sorted((exported / "players").glob("*.json")))).read_text(encoding="utf-8")
    )
    assert profile["uncertainty"]["design_version"] == "match_bootstrap_diagonal_v1"
    assert profile["uncertainty"]["representation_id"] == REPRESENTATION_ID


# --- AC5 -------------------------------------------------------------------

RUNTIME_PROVENANCE = {"generated_at", "producer", "inputs"}


def _canonical(directory: Path) -> dict[str, str]:
    digests = {}
    for path in sorted(directory.rglob("*.json")):
        relative = path.relative_to(directory).as_posix()
        payload = path.read_bytes()
        if relative == "manifest.json":
            manifest = json.loads(payload)
            for key in RUNTIME_PROVENANCE:
                manifest.pop(key, None)
            payload = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
        digests[relative] = hashlib.sha256(payload).hexdigest()
    return digests


def test_two_bounded_exports_are_canonically_identical(tmp_path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    _export(first)
    _export(second)
    assert _canonical(first) == _canonical(second)


def test_a_failed_build_leaves_the_previous_target_untouched(tmp_path) -> None:
    """Validation runs before the atomic swap, so a rejected build must not
    replace a good directory with a partial one."""
    target = tmp_path / "target"
    _export(target)
    before = _canonical(target)

    with pytest.raises(Exception):
        export_showcase(
            output_dir=target,
            schema_version=V2_SCHEMA_VERSION,
            representation_artifact=BENCHMARK,
            bootstrap_run_dir=DIAGONAL_RUN,
            competition_ids=[BOUNDED_COMPETITION],
            # The frozen count does not match a bounded cohort, so the build
            # fails after staging and before publication.
            expected_profile_count=1257,
            generated_at="2026-08-13T00:00:00+00:00",
        )

    assert _canonical(target) == before
