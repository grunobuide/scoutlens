"""The corpus says what it covers; these tests hold it to that.

A coverage matrix is the easiest artifact in a project to falsify by accident.
Nothing stops a dimension being listed, never exercised, and reported as
covered — so every claim the corpus makes about itself is checked here against
what the cases actually do, and the pinned profile selection is re-derived from
the published data rather than trusted.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from conftest import requires_showcase, requires_v1

from scoutlens.explanations.evals import degrade
from scoutlens.explanations.evals.corpus import (
    ALIGNMENT_BANDS,
    ALIGNMENT_SELECTION,
    DEGRADED_FAMILY,
    SMALL_SAMPLE_SELECTION,
    Dimension,
    Expectation,
    ShowcaseArtifacts,
    alignment_matrix,
    build_corpus,
    coverage_matrix,
    materialise,
)
from scoutlens.explanations.evals.mutations import MUTATIONS, REQUIRES_SETUP, SAFETY_CRITICAL
from scoutlens.explanations.evals.runner import run_case
from scoutlens.explanations.policy import EvidenceStatus
from scoutlens.explanations.schema import validate_output_schema
from scoutlens.showcase.schema import validate_schema

pytestmark = requires_showcase

MINIMUM_CASES = 60


@pytest.fixture(scope="module")
def artifacts() -> ShowcaseArtifacts:
    return ShowcaseArtifacts()


def test_the_corpus_meets_its_declared_size() -> None:
    """AC1: at least 60 uniquely identified cases."""
    cases = build_corpus()
    assert len(cases) >= MINIMUM_CASES
    assert len({case.case_id for case in cases}) == len(cases)


def test_every_declared_dimension_has_a_case() -> None:
    """A dimension nobody exercises is a coverage claim with nothing behind it."""
    matrix = coverage_matrix()
    uncovered = sorted(name for name, ids in matrix.items() if not ids)
    assert not uncovered, f"declared but never exercised: {uncovered}"
    assert set(matrix) == {str(dimension) for dimension in Dimension}


def test_the_alignment_matrix_reports_its_one_empty_cell() -> None:
    """Goalkeepers have no weak-alignment cell, and the matrix says so.

    Pinned as a fact about the published data. If a repin ever puts a goalkeeper
    below 0.70 this fails, which is the correct outcome: the corpus would then
    be under-covering a cell it could fill.
    """
    matrix = alignment_matrix()
    empty = {
        (role, band)
        for role, bands in matrix.items()
        for band, case_id in bands.items()
        if case_id is None
    }
    assert empty == {("Goalkeeper", "weak")}


@pytest.mark.parametrize(("key", "profile_key"), sorted(ALIGNMENT_SELECTION.items()))
def test_each_pinned_profile_is_still_in_its_band(
    key: tuple[str, str], profile_key: str, artifacts: ShowcaseArtifacts
) -> None:
    """The pin is a claim about the data; re-derive it rather than trust it."""
    role, band = key
    profile = artifacts.profile(profile_key)
    score = profile["retrieval"]["global"]["similarity_score"]
    low, high = ALIGNMENT_BANDS[band]
    assert profile["identity"]["role"] == role
    assert low <= score < high, f"{profile_key} scores {score}, outside {band} {(low, high)}"


def test_the_small_sample_pins_are_still_the_smallest_in_their_role(
    artifacts: ShowcaseArtifacts,
) -> None:
    """Read from the index, which is one file, so this stays cheap enough to always run."""
    by_role: dict[str, list[tuple[int, str]]] = {}
    for entry in artifacts.index():
        by_role.setdefault(entry["role"], []).append(
            (entry["total_minutes"], entry["profile_key"])
        )
    for role, pinned in SMALL_SAMPLE_SELECTION.items():
        assert min(by_role[role])[1] == pinned


def test_every_mutation_appears_in_the_corpus() -> None:
    """A mutation nothing runs is a guard nothing proves."""
    used = {case.mutation for case in build_corpus() if case.mutation}
    assert used == set(MUTATIONS)


def test_every_safety_critical_mutation_is_a_reject_case() -> None:
    reject = {
        case.mutation
        for case in build_corpus()
        if case.expectation is Expectation.REJECT and case.mutation
    }
    assert SAFETY_CRITICAL <= reject


def test_mutations_needing_setup_are_given_it(artifacts: ShowcaseArtifacts) -> None:
    """The four that cannot run on a plain bundle are run on one that can carry them."""
    for case in build_corpus():
        if case.mutation in REQUIRES_SETUP and case.expectation is Expectation.REJECT:
            material = materialise(case, artifacts)
            assert material.response is not None
            assert material.expected_rule == MUTATIONS[case.mutation][1]


@requires_v1
@pytest.mark.parametrize("case", build_corpus(), ids=lambda case: case.case_id)
def test_every_case_does_what_it_says(case: Any, artifacts: ShowcaseArtifacts) -> None:
    """The suite, case by case, so a failure names the one that broke."""
    result = run_case(case, artifacts)
    assert result.as_expected, (
        f"{case.case_id}: {result.diagnostic.summary if result.diagnostic else 'unexpected'}"
    )


@pytest.mark.parametrize(
    "case",
    [case for case in build_corpus() if case.expectation is Expectation.REJECT],
    ids=lambda case: case.case_id,
)
def test_each_rejection_case_trips_exactly_one_rule(
    case: Any, artifacts: ShowcaseArtifacts
) -> None:
    """One broken property, one rule.

    Stronger than the runner's own judgement, which only asks that the expected
    rule fired. If a case starts tripping two, the corpus can no longer say
    which guard is doing the work — and a guard that is never solely
    responsible for a rejection can be removed without a single test noticing.
    """
    result = run_case(case, artifacts)
    assert result.rules_fired == (result.expected_rule,), (
        f"{case.case_id} fired {list(result.rules_fired)}, expected only {result.expected_rule!r}"
    )


# --- the degradations ------------------------------------------------------


def test_an_unmeasured_family_is_still_a_publishable_profile(
    v2_profile: dict[str, Any],
) -> None:
    """A case built on an impossible artifact proves nothing about the real one."""
    degraded = degrade.unmeasure_family(v2_profile, DEGRADED_FAMILY)
    validate_schema(degraded, label="degraded profile", major=2)
    assert degraded != v2_profile


def test_insufficient_uncertainty_is_still_a_publishable_profile(
    v2_profile: dict[str, Any],
) -> None:
    degraded = degrade.insufficient_rank_uncertainty(v2_profile)
    validate_schema(degraded, label="degraded profile", major=2)
    uncertainty = degraded["retrieval"]["global"]["uncertainty"]
    assert uncertainty["status"] == "insufficient"
    assert uncertainty["median_rank"] is None
    assert uncertainty["rank_ci_95"] is None


def test_degrading_leaves_the_original_untouched(v2_profile: dict[str, Any]) -> None:
    """Every degradation copies. A shared fixture mutated in place would make
    case order significant, and a suite whose result depends on case order is
    not a suite."""
    before = json.dumps(v2_profile, sort_keys=True)
    degrade.unmeasure_family(v2_profile, DEGRADED_FAMILY)
    degrade.impute_query_period(v2_profile, DEGRADED_FAMILY)
    degrade.insufficient_rank_uncertainty(v2_profile)
    degrade.insufficient_neighbour_stability(v2_profile)
    assert json.dumps(v2_profile, sort_keys=True) == before


def test_an_unmeasured_family_demotes_its_features_and_nothing_else(
    v2_profile: dict[str, Any], representation: dict[str, Any]
) -> None:
    """Feature rows become `unmeasured`; the family aggregate is untouched.

    The aggregate stays weighted because the schema leaves no legal way to blank
    it — `contribution` is non-nullable, family ids are named in `evidence_refs`,
    and `evidence_index` has a `minItems` of 240 — and because it is still true:
    every family sum continues to equal its members' contributions, which are
    not what the degradation removed.
    """
    from scoutlens.explanations import build_bundle

    degraded = degrade.unmeasure_family(v2_profile, DEGRADED_FAMILY)
    bundle = build_bundle(degraded, representation)
    statuses = {
        row["kind"]: row["status"] for row in bundle["evidence"] if row["family"] == DEGRADED_FAMILY
    }
    assert statuses["feature_contribution"] == str(EvidenceStatus.UNMEASURED)
    assert statuses["family_contribution"] == str(EvidenceStatus.WEIGHTED)


def test_a_mismatched_representation_keeps_the_feature_order(
    representation: dict[str, Any],
) -> None:
    """Only the name changes, so only provenance can catch the drift."""
    degraded = degrade.mismatch_representation(representation)
    original = representation.get("representation", representation)
    changed = degraded.get("representation", degraded)
    assert changed["id"] != original["id"]
    assert changed["feature_order"] == original["feature_order"]
    assert changed["feature_order_digest"] == original["feature_order_digest"]


# --- the responses ---------------------------------------------------------


@pytest.mark.parametrize("case", build_corpus(), ids=lambda case: case.case_id)
def test_every_synthesised_response_is_json_serialisable(
    case: Any, artifacts: ShowcaseArtifacts
) -> None:
    """The replay digest is taken over these; an unserialisable one would break it."""
    if case.major == 1 and not (artifacts.root / "v1" / "players").exists():
        pytest.skip("requires a hydrated v1 payload")
    material = materialise(case, artifacts)
    json.dumps(material.response, sort_keys=True)


@pytest.mark.parametrize(
    "case",
    [case for case in build_corpus() if case.expectation is Expectation.ACCEPT],
    ids=lambda case: case.case_id,
)
def test_every_accepted_response_matches_the_output_schema(
    case: Any, artifacts: ShowcaseArtifacts
) -> None:
    """Schema first, grounding second. A case that failed the schema would be
    rejected for a reason that says nothing about what it was written to test."""
    if case.major == 1 and not (artifacts.root / "v1" / "players").exists():
        pytest.skip("requires a hydrated v1 payload")
    validate_output_schema(materialise(case, artifacts).response)
