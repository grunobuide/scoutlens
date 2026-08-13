"""Diagonal ranking and dual evidence core (`scoutlens-qop.6.4.1`).

The failure this suite exists to prevent: scaling the *measurement* frame. The
diagonal score is cosine over sqrt(w)-scaled vectors, so the cheapest
implementation scales the standardized frame once and lets everything else run
unchanged — which silently replaces every published z-score and fingerprint
with a weighted number that means nothing to a reader.
"""

from __future__ import annotations

import json
import math

import pytest

from scoutlens.features.aggregation import FEATURE_COLUMNS
from scoutlens.showcase.builder import _evidence_for_candidate, _retrieval_outcome
from scoutlens.showcase.representation import (
    DIAGONAL_CONFIG_PATH,
    RANKING_METHOD,
    DiagonalRepresentation,
    load_representation,
)

REPRESENTATION_ID = "rep-f018e6041ccbad10"


@pytest.fixture(scope="module")
def representation() -> DiagonalRepresentation:
    return load_representation()


@pytest.fixture
def config() -> dict:
    return json.loads(DIAGONAL_CONFIG_PATH.read_text(encoding="utf-8"))


def _write(tmp_path, config: dict):
    path = tmp_path / "uncertainty-diagonal.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


def _unit_representation() -> DiagonalRepresentation:
    """Every canonical feature at weight 1 and nothing excluded: the diagonal
    metric's identity element, which must reproduce plain cosine."""
    return DiagonalRepresentation(
        id="rep-0000000000000000",
        weights_by_feature={feature: 1.0 for feature in FEATURE_COLUMNS},
        excluded_features=(),
        feature_order=tuple(FEATURE_COLUMNS),
        weight_digest="0" * 64,
        feature_order_digest="0" * 64,
        lineage={},
    )


def _vectors() -> tuple[dict, dict]:
    query = {feature: 0.0 for feature in FEATURE_COLUMNS}
    candidate = {feature: 0.0 for feature in FEATURE_COLUMNS}
    for index, feature in enumerate(FEATURE_COLUMNS[:6]):
        query[feature] = float(index + 1) * (1 if index % 2 == 0 else -1)
        candidate[feature] = float(6 - index) * (1 if index % 3 == 0 else -1)
    return query, candidate


# --- AC1: verification before use -----------------------------------------


def test_the_frozen_representation_loads_and_verifies(representation) -> None:
    assert representation.id == REPRESENTATION_ID
    assert len(representation.feature_order) == 28
    assert len(representation.excluded_features) == 4
    assert representation.weight_digest.startswith("f018e604")


def test_an_altered_weight_is_rejected(tmp_path, config) -> None:
    config["representation"]["weights"][3]["weight"] += 0.5
    with pytest.raises(ValueError, match="weight_digest"):
        load_representation(_write(tmp_path, config))


def test_a_reordered_feature_list_is_rejected(tmp_path, config) -> None:
    order = config["representation"]["feature_order"]
    order[2], order[5] = order[5], order[2]
    with pytest.raises(ValueError, match="weights are not in feature_order|feature_order_digest"):
        load_representation(_write(tmp_path, config))


def test_a_missing_feature_is_rejected(tmp_path, config) -> None:
    config["representation"]["feature_order"].pop()
    config["representation"]["weights"].pop()
    with pytest.raises(ValueError, match="feature_count|weight_digest"):
        load_representation(_write(tmp_path, config))


def test_an_extra_feature_is_rejected(tmp_path, config) -> None:
    config["representation"]["feature_order"].append("a_feature_that_does_not_exist")
    config["representation"]["weights"].append(
        {"feature_id": "a_feature_that_does_not_exist", "weight": 1.0}
    )
    with pytest.raises(ValueError, match="feature_count|weight_digest"):
        load_representation(_write(tmp_path, config))


def test_a_negative_weight_is_rejected(tmp_path, config) -> None:
    config["representation"]["weights"][0]["weight"] = -0.001
    with pytest.raises(ValueError, match="negative weights|weight_digest"):
        load_representation(_write(tmp_path, config))


def test_an_id_not_derived_from_its_own_digest_is_rejected(tmp_path, config) -> None:
    config["representation"]["id"] = "rep-ffffffffffffffff"
    with pytest.raises(ValueError, match="not derived from its own weight digest"):
        load_representation(_write(tmp_path, config))


def test_a_wrong_ranking_method_is_rejected(tmp_path, config) -> None:
    config["representation"]["ranking_method"] = "cosine_v1"
    with pytest.raises(ValueError, match="ranking_method must be"):
        load_representation(_write(tmp_path, config))


def test_missing_decision_lineage_is_rejected(tmp_path, config) -> None:
    config["representation"]["lineage"]["decision_records"] = ["D042"]
    with pytest.raises(ValueError, match="omits"):
        load_representation(_write(tmp_path, config))


def test_weights_that_drifted_from_the_benchmark_are_rejected(tmp_path, config) -> None:
    """The representation must be the one D042 recorded, not a rounded copy."""
    for entry in config["representation"]["weights"]:
        entry["weight"] = round(entry["weight"], 3)
    rewritten = _write(tmp_path, config)
    # digests are recomputed from the rounded weights, so only the benchmark
    # cross-check can catch this
    from scoutlens.showcase.validation import weight_digest

    patched = json.loads(rewritten.read_text(encoding="utf-8"))
    digest = weight_digest(patched["representation"]["weights"])
    patched["representation"]["weight_digest"] = digest
    patched["representation"]["id"] = f"rep-{digest[:16]}"
    rewritten.write_text(json.dumps(patched), encoding="utf-8")
    with pytest.raises(ValueError, match="drifted from"):
        load_representation(rewritten)


# --- AC2/AC6: the measurement frame is never scaled ------------------------


def test_stored_z_scores_come_from_the_unscaled_frame(representation) -> None:
    query, candidate = _vectors()
    _, _, evidence = _evidence_for_candidate("self_retrieval", "self", query, candidate, representation)
    for row in evidence:
        if row["kind"] != "feature_contribution":
            continue
        feature = row["feature_id"]
        assert row["query_global_z"] == query[feature], feature
        assert row["candidate_global_z"] == candidate[feature], feature


def test_weighting_does_not_change_the_stored_z_scores(representation) -> None:
    """The same guard from the other direction: weighted and unweighted runs
    must publish identical z-scores."""
    query, candidate = _vectors()
    _, _, plain = _evidence_for_candidate("self_retrieval", "self", query, candidate)
    _, _, weighted = _evidence_for_candidate(
        "self_retrieval", "self", query, candidate, representation
    )
    plain_z = {r["feature_id"]: (r["query_global_z"], r["candidate_global_z"]) for r in plain}
    weighted_z = {r["feature_id"]: (r["query_global_z"], r["candidate_global_z"]) for r in weighted}
    assert plain_z == weighted_z


def test_the_unweighted_audit_contribution_survives_weighting(representation) -> None:
    """D045 keeps cosine as the audit baseline, so the unweighted decomposition
    must still be published alongside the weighted one."""
    query, candidate = _vectors()
    cosine_plain, _, plain = _evidence_for_candidate("self_retrieval", "self", query, candidate)
    cosine_weighted, similarity, weighted = _evidence_for_candidate(
        "self_retrieval", "self", query, candidate, representation
    )
    assert math.isclose(cosine_plain, cosine_weighted, abs_tol=1e-12)
    assert not math.isclose(similarity, cosine_weighted, abs_tol=1e-9)
    plain_c = {r["evidence_id"]: r["contribution"] for r in plain}
    weighted_c = {r["evidence_id"]: r["contribution"] for r in weighted}
    assert plain_c == weighted_c


# --- AC3: unit weights reproduce v1 ---------------------------------------


def test_unit_weights_reproduce_the_v1_cosine_bit_for_bit() -> None:
    query, candidate = _vectors()
    cosine, _, plain = _evidence_for_candidate("self_retrieval", "self", query, candidate)
    _, similarity, weighted = _evidence_for_candidate(
        "self_retrieval", "self", query, candidate, _unit_representation()
    )
    assert math.isclose(similarity, cosine, rel_tol=0, abs_tol=1e-12)
    for plain_row, weighted_row in zip(plain, weighted, strict=True):
        assert plain_row["evidence_id"] == weighted_row["evidence_id"]
        assert math.isclose(
            plain_row["contribution"], weighted_row["weighted_contribution"], abs_tol=1e-12
        )


def test_unit_weights_preserve_the_v1_evidence_order() -> None:
    query, candidate = _vectors()
    _, _, plain = _evidence_for_candidate("self_retrieval", "self", query, candidate)
    _, _, weighted = _evidence_for_candidate(
        "self_retrieval", "self", query, candidate, _unit_representation()
    )
    assert [r["evidence_id"] for r in plain] == [r["evidence_id"] for r in weighted]


# --- AC5: both decompositions reconstruct their score ----------------------


def test_both_decompositions_reconstruct_their_own_score(representation) -> None:
    query, candidate = _vectors()
    cosine, similarity, evidence = _evidence_for_candidate(
        "neighbor:wy-1-c-2", "neighbor-wy-1-c-2", query, candidate, representation
    )
    features = [r for r in evidence if r["kind"] == "feature_contribution"]
    families = [r for r in evidence if r["kind"] == "family_contribution"]

    assert math.isclose(sum(r["contribution"] for r in features), cosine, abs_tol=1e-9)
    assert math.isclose(sum(r["contribution"] for r in families), cosine, abs_tol=1e-9)
    assert math.isclose(sum(r["weighted_contribution"] for r in features), similarity, abs_tol=1e-9)
    assert math.isclose(sum(r["weighted_contribution"] for r in families), similarity, abs_tol=1e-9)


def test_a_tampered_weighted_contribution_breaks_reconstruction(representation) -> None:
    query, candidate = _vectors()
    _, similarity, evidence = _evidence_for_candidate(
        "self_retrieval", "self", query, candidate, representation
    )
    features = [r for r in evidence if r["kind"] == "feature_contribution"]
    features[0]["weighted_contribution"] += 1e-3
    assert not math.isclose(
        sum(r["weighted_contribution"] for r in features), similarity, abs_tol=1e-9
    )


def test_evidence_ordering_is_deterministic(representation) -> None:
    query, candidate = _vectors()
    first = _evidence_for_candidate("self_retrieval", "self", query, candidate, representation)[2]
    second = _evidence_for_candidate("self_retrieval", "self", query, candidate, representation)[2]
    assert [r["evidence_id"] for r in first] == [r["evidence_id"] for r in second]
    features = [r for r in first if r["kind"] == "feature_contribution"]
    magnitudes = [abs(r["weighted_contribution"]) for r in features]
    assert magnitudes == sorted(magnitudes, reverse=True)


# --- AC4/AC6: representation binding and excluded features -----------------


def test_every_evidence_row_carries_the_representation_id(representation) -> None:
    query, candidate = _vectors()
    _, _, evidence = _evidence_for_candidate("self_retrieval", "self", query, candidate, representation)
    assert {row["representation_id"] for row in evidence} == {REPRESENTATION_ID}


def test_excluded_features_carry_weight_zero_and_contribute_nothing(representation) -> None:
    query, candidate = _vectors()
    _, _, evidence = _evidence_for_candidate("self_retrieval", "self", query, candidate, representation)
    excluded = set(representation.excluded_features)
    for row in evidence:
        if row["kind"] == "feature_contribution" and row["feature_id"] in excluded:
            assert row["feature_weight"] == 0.0
            assert row["weighted_contribution"] == 0.0


def test_an_implicit_zero_weight_fails_closed(representation) -> None:
    with pytest.raises(ValueError, match="pins neither a weight nor an exclusion"):
        representation.weight_vector([*FEATURE_COLUMNS, "a_feature_nobody_pinned"])


def test_retrieval_outcome_names_the_score_by_version(representation) -> None:
    v1 = _retrieval_outcome(10, 3, 0.5, ["e1"], None)
    assert "cosine_similarity" in v1 and "similarity_score" not in v1
    assert "representation_id" not in v1

    v2 = _retrieval_outcome(10, 3, 0.5, ["e1"], None, representation)
    assert "similarity_score" in v2 and "cosine_similarity" not in v2
    assert v2["representation_id"] == REPRESENTATION_ID


def test_the_ranking_method_constant_matches_the_contract() -> None:
    assert RANKING_METHOD == "weighted_cosine_diagonal_v1"


def test_sqrt_weight_vector_squares_back_to_the_weights(representation) -> None:
    columns = list(FEATURE_COLUMNS)
    weights = representation.weight_vector(columns)
    roots = representation.sqrt_weight_vector(columns)
    for weight, root in zip(weights, roots, strict=True):
        assert math.isclose(root * root, weight, rel_tol=0, abs_tol=1e-12)
