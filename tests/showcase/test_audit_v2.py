"""The standalone v2 auditor (`scoutlens-qop.6.4.3`).

The tamper tests are the point. An auditor that has only ever been shown a good
bundle has not been shown to audit anything, so each check below is exercised by
breaking exactly the thing it is supposed to catch.

Two of them would otherwise pass for the wrong reason: mutating a published
value changes the file's bytes, so the manifest integrity check fires first and
the semantic check never runs. `_tamper` therefore rewrites the file
canonically **and** repairs its manifest entry, leaving a bundle that is
byte-consistent and semantically wrong - which is the only interesting kind.
`test_a_single_flipped_byte_is_caught` covers the other direction on purpose.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any, Callable

import pytest

from scoutlens.showcase.audit_v2 import (
    _decompose,
    _digest,
    audit_candidate,
    compare_candidates,
    compare_with_v1,
)
from scoutlens.showcase.export import V2_SCHEMA_VERSION, export_showcase
from scoutlens.showcase.io import canonical_json_bytes
from scoutlens.showcase.validation import records_for

REPO_ROOT = Path(__file__).resolve().parents[2]
PROCESSED = REPO_ROOT / "data" / "processed"
DIAGONAL_RUN = REPO_ROOT / "artifacts" / "uncertainty" / "match_bootstrap_diagonal_v1"
BENCHMARK = REPO_ROOT / "artifacts" / "benchmark" / "diagonal-results.json"
PUBLISHED_V1 = REPO_ROOT / "public" / "showcase" / "v1"

BOUNDED_COMPETITION = 795


# --- pure recomputation, offline ------------------------------------------


def test_the_decomposition_reduces_to_cosine_when_every_weight_is_one() -> None:
    """`w = 1` must reproduce the v1 score exactly. It is the property that
    makes frozen cosine a faithful audit baseline rather than a different
    family of method (D045)."""
    rows = [
        {"feature_id": "a", "query_global_z": 1.0, "candidate_global_z": 2.0},
        {"feature_id": "b", "query_global_z": -3.0, "candidate_global_z": 0.5},
        {"feature_id": "c", "query_global_z": 0.0, "candidate_global_z": 4.0},
    ]
    weights = {"a": 1.0, "b": 1.0, "c": 1.0}
    contributions, weighted, cosine, score = _decompose(rows, weights)
    assert contributions == pytest.approx(weighted)
    assert cosine == pytest.approx(score)


def test_a_zero_weight_removes_a_feature_from_the_score_but_not_the_audit_view() -> None:
    """The two decompositions answer different questions: the weighted one
    reconstructs what is shown, the unweighted one is what the weighting
    changed."""
    rows = [
        {"feature_id": "a", "query_global_z": 1.0, "candidate_global_z": 2.0},
        {"feature_id": "b", "query_global_z": 3.0, "candidate_global_z": 3.0},
    ]
    contributions, weighted, _, _ = _decompose(rows, {"a": 1.0, "b": 0.0})
    assert weighted["b"] == 0.0
    assert contributions["b"] != 0.0


def test_a_degenerate_vector_scores_zero_rather_than_dividing_by_zero() -> None:
    rows = [{"feature_id": "a", "query_global_z": 0.0, "candidate_global_z": 0.0}]
    contributions, weighted, cosine, score = _decompose(rows, {"a": 1.0})
    assert (contributions["a"], weighted["a"], cosine, score) == (0.0, 0.0, 0.0, 0.0)


def test_the_digest_is_order_sensitive() -> None:
    """The same weights in a different feature order describe a different
    metric, so the digest must separate them."""
    assert _digest([["a", 1.0], ["b", 2.0]]) != _digest([["b", 2.0], ["a", 1.0]])


def test_an_empty_candidate_directory_fails_rather_than_passing_vacuously() -> None:
    report = audit_candidate(Path("does-not-exist"), expected_profiles=1)
    assert not report.passed
    assert "missing or unreadable required artifacts" in report.failures[0]


# --- against a real bounded export ----------------------------------------

pytestmark_integration = pytest.mark.skipif(
    os.environ.get("SCOUTLENS_SHOWCASE_INTEGRATION") != "1"
    or not (PROCESSED / "period_profiles.parquet").is_file()
    or not (DIAGONAL_RUN / "run.json").is_file()
    or not (PUBLISHED_V1 / "players").is_dir(),
    reason="requires local processed data, the diagonal uncertainty run, a hydrated v1 payload "
    "and SCOUTLENS_SHOWCASE_INTEGRATION=1",
)


@pytest.fixture(scope="module")
def bounded(tmp_path_factory) -> tuple[Path, int]:
    target = tmp_path_factory.mktemp("audit") / "showcase-v2"
    result = export_showcase(
        output_dir=target,
        schema_version=V2_SCHEMA_VERSION,
        representation_artifact=BENCHMARK,
        bootstrap_run_dir=DIAGONAL_RUN,
        competition_ids=[BOUNDED_COMPETITION],
        expected_profile_count=None,
        generated_at="2026-08-13T00:00:00+00:00",
    )
    return target, int(result["profile_count"])


def _tamper(source: Path, destination: Path, relative: str, mutate: Callable[[Any], None]) -> Path:
    """Copy a bundle, mutate one artifact, and repair its manifest entry.

    Repairing the entry is what makes the test meaningful: without it the
    integrity check fires and the semantic check under test never runs.
    """
    shutil.copytree(source, destination)
    path = destination / relative
    artifact = json.loads(path.read_text(encoding="utf-8"))
    mutate(artifact)
    payload = canonical_json_bytes(artifact)
    path.write_bytes(payload)

    manifest_path = destination / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for entry in manifest["files"]:
        if entry["path"] == relative:
            import hashlib

            entry["bytes"] = len(payload)
            entry["sha256"] = hashlib.sha256(payload).hexdigest()
            entry["records"] = records_for(relative, artifact)
    manifest_path.write_bytes(canonical_json_bytes(manifest))
    return destination


def _first_profile(root: Path) -> str:
    return sorted(path.name for path in (root / "players").glob("*.json"))[0]


@pytestmark_integration
def test_a_clean_bounded_export_passes(bounded) -> None:
    root, count = bounded
    report = audit_candidate(root, expected_profiles=count)
    assert report.passed, report.render()
    assert report.stats["profiles_audited"] == count
    assert report.stats["weighted_features"] == 28
    assert report.stats["features_excluded_from_ranking"] == 4


@pytestmark_integration
def test_two_exports_of_the_same_inputs_compare_identical(bounded, tmp_path) -> None:
    root, _ = bounded
    copy = tmp_path / "copy"
    shutil.copytree(root, copy)
    report = compare_candidates(root, copy)
    assert report.passed, report.render()
    assert report.stats["identical"] == report.stats["files_compared"]


@pytestmark_integration
def test_a_changed_file_fails_the_determinism_comparison(bounded, tmp_path) -> None:
    root, _ = bounded
    copy = tmp_path / "copy"
    shutil.copytree(root, copy)
    (copy / "feature-catalog.json").write_bytes(b"{}")
    report = compare_candidates(root, copy)
    assert not report.passed
    assert "files differ" in report.failures[0]


@pytestmark_integration
def test_one_tampered_weight_is_caught(bounded, tmp_path) -> None:
    root, count = bounded

    def mutate(artifact: dict) -> None:
        artifact["representation"]["weights"][3]["weight"] += 0.01

    target = _tamper(root, tmp_path / "weight", "representation.json", mutate)
    report = audit_candidate(target, expected_profiles=count)
    assert not report.passed
    assert any("weight_digest mismatch" in failure for failure in report.failures)


@pytestmark_integration
def test_one_tampered_contribution_is_caught(bounded, tmp_path) -> None:
    root, count = bounded
    name = _first_profile(root)

    def mutate(artifact: dict) -> None:
        for item in artifact["evidence_index"]:
            if item["kind"] == "feature_contribution":
                item["weighted_contribution"] += 1e-3
                return

    target = _tamper(root, tmp_path / "contribution", f"players/{name}", mutate)
    report = audit_candidate(target, expected_profiles=count)
    assert not report.passed
    assert any("weighted_contribution does not recompute" in failure for failure in report.failures)


@pytestmark_integration
def test_one_tampered_score_is_caught(bounded, tmp_path) -> None:
    root, count = bounded
    name = _first_profile(root)

    def mutate(artifact: dict) -> None:
        artifact["retrieval"]["global"]["similarity_score"] *= 0.9

    target = _tamper(root, tmp_path / "score", f"players/{name}", mutate)
    report = audit_candidate(target, expected_profiles=count)
    assert not report.passed
    assert any("does not reconstruct published" in failure for failure in report.failures)


@pytestmark_integration
def test_one_reordered_neighbor_pair_is_caught(bounded, tmp_path) -> None:
    root, count = bounded
    name = _first_profile(root)

    def mutate(artifact: dict) -> None:
        neighbors = artifact["neighbors"]
        neighbors[0], neighbors[1] = neighbors[1], neighbors[0]
        for rank, neighbor in enumerate(neighbors, start=1):
            neighbor["rank"] = rank

    target = _tamper(root, tmp_path / "order", f"players/{name}", mutate)
    report = audit_candidate(target, expected_profiles=count)
    assert not report.passed
    assert any("not ordered by descending similarity_score" in failure for failure in report.failures)


@pytestmark_integration
def test_one_foreign_uncertainty_representation_id_is_caught(bounded, tmp_path) -> None:
    root, count = bounded
    name = _first_profile(root)

    def mutate(artifact: dict) -> None:
        artifact["uncertainty"]["representation_id"] = "rep-ffffffffffffffff"

    target = _tamper(root, tmp_path / "uncertainty", f"players/{name}", mutate)
    report = audit_candidate(target, expected_profiles=count)
    assert not report.passed
    assert any("names representation" in failure for failure in report.failures)


@pytestmark_integration
def test_a_single_flipped_byte_is_caught(bounded, tmp_path) -> None:
    """The other direction: no manifest repair, so the integrity check is what
    must fire."""
    root, count = bounded
    target = tmp_path / "byte"
    shutil.copytree(root, target)
    path = target / "players" / _first_profile(root)
    payload = bytearray(path.read_bytes())
    payload[-2] = payload[-2] ^ 0x20
    path.write_bytes(bytes(payload))

    report = audit_candidate(target, expected_profiles=count)
    assert not report.passed
    assert any("sha256 does not match" in failure for failure in report.failures)


@pytestmark_integration
def test_a_corrupted_key_is_reported_rather_than_raised(bounded, tmp_path) -> None:
    """The case that produced a traceback in `scoutlens-qop.6.6.3`.

    A byte flip inside a key name leaves valid JSON that fails the schema. The
    auditor used to record that failure and then audit the artifact anyway,
    reaching for the field the schema had just proved absent - so the run died
    with a KeyError and said nothing about the other profiles. It must report
    and carry on.
    """
    root, count = bounded
    target = tmp_path / "corrupt-key"
    shutil.copytree(root, target)
    path = target / "players" / _first_profile(root)
    payload = path.read_text(encoding="utf-8").replace(
        '"candidate_global_z"', '"candidate_global_Z"', 1
    )
    path.write_text(payload, encoding="utf-8")

    report = audit_candidate(target, expected_profiles=count)

    assert not report.passed
    assert any("JSON Schema violation" in failure for failure in report.failures)
    # The other profiles were still audited: a single bad artifact must not
    # blind the auditor to the rest of the bundle.
    assert report.stats["profiles_audited"] == count


@pytestmark_integration
def test_a_wrong_profile_count_stops_publication(bounded) -> None:
    root, count = bounded
    report = audit_candidate(root, expected_profiles=count + 1)
    assert not report.passed
    assert any("profiles published, expected" in failure for failure in report.failures)


@pytestmark_integration
def test_the_v1_comparison_catches_a_fingerprint_that_moved(bounded) -> None:
    """A positive control for the invariant the production run must satisfy.

    The bounded export narrows the population to one competition, so the
    standardizing scaler is fit over a different cohort and every `global_z_score`
    legitimately moves. That makes it exactly the payload the fingerprint check
    exists to reject - and it does. In production the cohort is identical to v1,
    so the same check must instead report zero changes.
    """
    root, _ = bounded
    report = compare_with_v1(PUBLISHED_V1, root)

    assert not report.passed
    assert any("population differs" in failure for failure in report.failures)
    assert any("global_z_score changed between majors" in failure for failure in report.failures)
    assert report.stats["global_score_changed"] > 0
    assert report.stats["profiles_compared"] > 0
