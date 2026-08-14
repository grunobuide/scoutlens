"""Fail-closed validation for showcase schemas, cross-links, and bytes."""

from __future__ import annotations

import gzip
import hashlib
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from scoutlens.features.aggregation import FEATURE_COLUMNS, FEATURE_FAMILIES
from scoutlens.showcase.builder import ShowcaseBundle
from scoutlens.showcase.catalog import (
    CONTRACT,
    EXPECTED_PROFILE_COUNT,
    FEATURE_ORDER,
    FEATURED_PROFILE_KEY,
    SCHEMA_VERSION,
)
from scoutlens.showcase.io import canonical_json_bytes, sha256_bytes
from scoutlens.showcase.research import build_research_summary
from scoutlens.showcase.schema import parse_major, validate_schema

CATALOG_GZIP_BUDGET = 400 * 1024
PROFILE_GZIP_BUDGET = 30 * 1024

_UNICODE_ESCAPE = re.compile(r"\\u([0-9a-fA-F]{4})")


def _reject_literal_identity_escape(value: str, label: str) -> None:
    if _UNICODE_ESCAPE.search(value):
        raise ValueError(f"{label}: literal \\uXXXX escape text must be normalized before publication")


def _validate_identity_text(item: dict, base: str) -> None:
    _reject_literal_identity_escape(str(item["display_name"]), f"{base}.display_name")
    competition = item.get("competition")
    if competition is not None:
        _reject_literal_identity_escape(str(competition["name"]), f"{base}.competition.name")
        _reject_literal_identity_escape(str(competition["country"]), f"{base}.competition.country")
    for period in item.get("period_contexts", {}).values():
        for team in period["teams"]:
            _reject_literal_identity_escape(str(team["name"]), f"{base}.period_contexts.teams.name")
    for team in item.get("teams", []):
        _reject_literal_identity_escape(str(team["name"]), f"{base}.teams.name")


def _walk_numbers(value: Any, path: str = "root") -> None:
    if isinstance(value, bool) or value is None:
        return
    if isinstance(value, (int, float)):
        if not math.isfinite(value):
            raise ValueError(f"{path}: non-finite number")
        return
    if isinstance(value, dict):
        for key, child in value.items():
            _walk_numbers(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _walk_numbers(child, f"{path}[{index}]")


SCORE_FIELD_BY_MAJOR = {1: "cosine_similarity", 2: "similarity_score"}
"""The published retrieval score, per contract major. v2 renamed it because a
weighted metric must not be published under a name claiming plain cosine
(D047)."""

EVIDENCE_SORT_FIELD_BY_MAJOR = {1: "contribution", 2: "weighted_contribution"}
"""The evidence field the deterministic order is taken over. The rule is
unchanged between majors - descending magnitude, ties broken by catalog order -
but it applies to each major's own contribution to the score it publishes."""


def _score_field(major: int) -> str:
    field = SCORE_FIELD_BY_MAJOR.get(major)
    if field is None:
        raise ValueError(f"unsupported showcase schema major {major}")
    return field


def _validate_evidence(profile: dict, *, major: int) -> None:
    evidence = profile["evidence_index"]
    evidence_by_id = {item["evidence_id"]: item for item in evidence}
    if len(evidence_by_id) != len(evidence):
        raise ValueError(f"{profile['profile_key']}: duplicate evidence ids")
    references = []
    for outcome in profile["retrieval"].values():
        if isinstance(outcome, dict):
            references.extend(outcome["evidence_refs"])
    for neighbor in profile["neighbors"]:
        references.extend(neighbor["evidence_refs"])
    for caveat in profile["caveats"]:
        references.extend(caveat["evidence_refs"])
    missing = sorted(set(references) - set(evidence_by_id))
    if missing:
        raise ValueError(f"{profile['profile_key']}: unresolved evidence refs: {missing[:3]}")

    by_subject: dict[str, list[dict]] = defaultdict(list)
    for item in evidence:
        by_subject[item["subject"]].append(item)
    score_field = _score_field(major)
    expected_scores = {"self_retrieval": profile["retrieval"]["global"][score_field]}
    expected_scores.update(
        {f"neighbor:{neighbor['profile_key']}": neighbor[score_field] for neighbor in profile["neighbors"]}
    )
    if set(by_subject) != set(expected_scores):
        raise ValueError(f"{profile['profile_key']}: evidence subjects do not match retrieval subjects")
    for subject, items in by_subject.items():
        feature_items = [item for item in items if item["kind"] == "feature_contribution"]
        family_items = [item for item in items if item["kind"] == "family_contribution"]
        if len(feature_items) != 32 or len(family_items) != len(FEATURE_FAMILIES):
            raise ValueError(f"{profile['profile_key']}/{subject}: incomplete additive evidence")
        if {item["feature_id"] for item in feature_items} != set(FEATURE_COLUMNS):
            raise ValueError(f"{profile['profile_key']}/{subject}: feature evidence does not cover catalog")
        sort_field = EVIDENCE_SORT_FIELD_BY_MAJOR[major]
        expected_order = sorted(
            feature_items,
            key=lambda item: (-abs(item[sort_field]), FEATURE_ORDER[item["feature_id"]]),
        )
        if feature_items != expected_order:
            raise ValueError(f"{profile['profile_key']}/{subject}: feature evidence order is not deterministic")
        score = expected_scores[subject]
        if score is None:
            raise ValueError(f"{profile['profile_key']}/{subject}: cosine evidence has a null score")
        if major != 1:
            # In v2 `contribution` stays the unweighted cosine audit view, so it
            # reconstructs the cosine rather than the published
            # `similarity_score`. The weighted reconstruction is the normative
            # v2 rule and is checked by validate_v2_weighted_evidence; asserting
            # the v1 identity here would demand that the audit view equal a
            # number it does not describe.
            continue
        if not math.isclose(math.fsum(item["contribution"] for item in feature_items), score, abs_tol=1e-9):
            raise ValueError(f"{profile['profile_key']}/{subject}: feature contributions do not reconstruct cosine")
        if not math.isclose(math.fsum(item["contribution"] for item in family_items), score, abs_tol=1e-9):
            raise ValueError(f"{profile['profile_key']}/{subject}: family contributions do not reconstruct cosine")


def _validate_feature_uncertainty(block: dict, label: str, uncertainty_mode: str) -> None:
    status = block["status"]
    if uncertainty_mode == "pending":
        if status != "pending":
            raise ValueError(f"{label}: nested feature uncertainty must be pending in the no-uncertainty fixture")
        return
    if status not in ("available", "insufficient"):
        raise ValueError(f"{label}: unexpected feature uncertainty status {status!r}")
    valid = block["valid_resamples"]
    if not isinstance(valid, int) or valid < 0:
        raise ValueError(f"{label}: invalid resample count {valid!r}")
    raw = block["raw_ci_95"]
    percentile = block["within_role_percentile_ci_95"]
    if status == "available":
        if raw is None or percentile is None:
            raise ValueError(f"{label}: available feature uncertainty is missing an interval")
    else:
        if raw is not None or percentile is not None:
            raise ValueError(f"{label}: insufficient feature uncertainty must null its intervals")
        return
    if len(raw) != 2 or raw[0] > raw[1]:
        raise ValueError(f"{label}: raw interval is not ordered")
    if len(percentile) != 2 or percentile[0] > percentile[1]:
        raise ValueError(f"{label}: percentile interval is not ordered")
    if not 0 <= percentile[0] <= percentile[1] <= 100:
        raise ValueError(f"{label}: percentile interval out of range")


def _validate_rank_uncertainty(block: dict, label: str, uncertainty_mode: str) -> None:
    status = block["status"]
    if uncertainty_mode == "pending":
        if status != "pending":
            raise ValueError(f"{label}: rank uncertainty must be pending in the no-uncertainty fixture")
        return
    if status not in ("available", "insufficient"):
        raise ValueError(f"{label}: unexpected rank uncertainty status {status!r}")
    valid = block["valid_resamples"]
    if not isinstance(valid, int) or valid < 0:
        raise ValueError(f"{label}: invalid resample count {valid!r}")
    if status == "insufficient":
        for field in ("median_rank", "rank_ci_95", "recall_at_1_rate", "recall_at_5_rate", "recall_at_10_rate"):
            if block[field] is not None:
                raise ValueError(f"{label}: insufficient rank uncertainty must null {field}")
        return
    if block["median_rank"] is None or block["rank_ci_95"] is None:
        raise ValueError(f"{label}: available rank uncertainty is missing a point or interval")
    if not block["median_rank"] >= 1:
        raise ValueError(f"{label}: median rank below 1")
    interval = block["rank_ci_95"]
    if len(interval) != 2 or interval[0] > interval[1] or interval[0] < 1:
        raise ValueError(f"{label}: rank interval is not ordered from rank 1")
    for field in ("recall_at_1_rate", "recall_at_5_rate", "recall_at_10_rate"):
        if block[field] is not None and not 0 <= block[field] <= 1:
            raise ValueError(f"{label}: {field} out of range")


def _validate_neighbor_stability(block: dict, label: str, uncertainty_mode: str) -> None:
    status = block["status"]
    if uncertainty_mode == "pending":
        if status != "pending":
            raise ValueError(f"{label}: neighbor stability must be pending in the no-uncertainty fixture")
        return
    if status not in ("available", "insufficient"):
        raise ValueError(f"{label}: unexpected neighbor stability status {status!r}")
    valid = block["valid_resamples"]
    if not isinstance(valid, int) or valid < 0:
        raise ValueError(f"{label}: invalid resample count {valid!r}")
    if status == "insufficient":
        for field in ("top_5_selection_rate", "median_rank", "rank_ci_95"):
            if block[field] is not None:
                raise ValueError(f"{label}: insufficient neighbor stability must null {field}")
        return
    if block["top_5_selection_rate"] is not None and not 0 <= block["top_5_selection_rate"] <= 1:
        raise ValueError(f"{label}: top-5 selection rate out of range")
    if block["median_rank"] is not None and block["median_rank"] < 1:
        raise ValueError(f"{label}: neighbor median rank below 1")
    interval = block["rank_ci_95"]
    if interval is not None:
        if len(interval) != 2 or interval[0] > interval[1] or interval[0] < 1:
            raise ValueError(f"{label}: neighbor rank interval is not ordered from rank 1")


def _validate_profile(
    profile: dict,
    index_by_key: dict[str, dict],
    feature_ids: list[str],
    uncertainty_mode: str,
    *,
    major: int,
) -> None:
    key = profile["profile_key"]
    if profile["identity"]["player_key"] != index_by_key[key]["player_key"]:
        raise ValueError(f"{key}: index and payload player keys differ")
    for period_name in ("a", "b"):
        period = profile["periods"][period_name]
        values = period["features"]
        if [value["feature_id"] for value in values] != feature_ids:
            raise ValueError(f"{key}/{period_name}: feature order differs from catalog")
        for value in values:
            if not 0 <= value["global_percentile"] <= 100:
                raise ValueError(f"{key}/{period_name}/{value['feature_id']}: global percentile out of range")
            if not 0 <= value["within_role_percentile"] <= 100:
                raise ValueError(f"{key}/{period_name}/{value['feature_id']}: role percentile out of range")
            if value["raw_value"] is None:
                if not value["imputed_for_model"] or value["global_z_score"] != 0:
                    raise ValueError(f"{key}/{period_name}/{value['feature_id']}: null imputation invariant failed")
            elif value["imputed_for_model"]:
                raise ValueError(f"{key}/{period_name}/{value['feature_id']}: observed value marked imputed")
            _validate_feature_uncertainty(
                value["uncertainty"],
                f"{key}/{period_name}/{value['feature_id']}.uncertainty",
                uncertainty_mode,
            )

    query_player = profile["identity"]["player_key"]
    role = profile["identity"]["role"]
    neighbors = profile["neighbors"]
    if len({neighbor["profile_key"] for neighbor in neighbors}) != 5:
        raise ValueError(f"{key}: neighbors are not distinct")
    if any(neighbor["player_key"] == query_player for neighbor in neighbors):
        raise ValueError(f"{key}: same-human profile leaked into neighbors")
    if any(neighbor["role"] != role for neighbor in neighbors):
        raise ValueError(f"{key}: neighbor role differs from query role")
    score_field = _score_field(major)
    expected_neighbors = sorted(
        neighbors, key=lambda neighbor: (-neighbor[score_field], neighbor["profile_key"])
    )
    if neighbors != expected_neighbors or [neighbor["rank"] for neighbor in neighbors] != [1, 2, 3, 4, 5]:
        raise ValueError(f"{key}: neighbors are not deterministically ranked")
    if any(neighbor["profile_key"] not in index_by_key for neighbor in neighbors):
        raise ValueError(f"{key}: neighbor profile does not resolve through the index")
    for rank, neighbor in enumerate(neighbors, start=1):
        _validate_neighbor_stability(
            neighbor["stability"],
            f"{key}.neighbors[{rank}].stability",
            uncertainty_mode,
        )
    for outcome_name in ("global", "within_role", "baseline_role_minutes"):
        outcome = profile["retrieval"][outcome_name]
        _validate_rank_uncertainty(
            outcome["uncertainty"],
            f"{key}.retrieval.{outcome_name}.uncertainty",
            uncertainty_mode,
        )

    mandatory = {
        "fingerprint_not_style_proof",
        "similarity_not_recruitment",
        "same_season_team_confound",
        "within_role_display_differs_from_global_model",
    }
    uncertainty_caveat = "uncertainty_sampling_only" if uncertainty_mode == "available" else "uncertainty_pending"
    mandatory.add(uncertainty_caveat)
    caveat_codes = {item["code"] for item in profile["caveats"]}
    if not mandatory.issubset(caveat_codes):
        raise ValueError(f"{key}: mandatory caveats missing: {sorted(mandatory - caveat_codes)}")
    if role == "Goalkeeper" and "goalkeeper_feature_coverage_weak" not in caveat_codes:
        raise ValueError(f"{key}: goalkeeper coverage caveat missing")
    top = profile["uncertainty"]
    top_status = top["status"]
    if uncertainty_mode == "pending":
        if top_status != "pending":
            raise ValueError(f"{key}: top-level uncertainty must be pending in the no-uncertainty fixture")
    elif top_status not in ("available", "insufficient"):
        raise ValueError(f"{key}: unexpected top-level uncertainty status {top_status!r}")
    elif top_status == "insufficient" and top["valid_resamples"] is not None and top["valid_resamples"] <= 0:
        raise ValueError(f"{key}: top-level insufficient uncertainty has a non-positive resample count")
    elif top_status == "available" and (
        top["valid_resamples"] is None or not isinstance(top["valid_resamples"], int) or top["valid_resamples"] <= 0
    ):
        raise ValueError(f"{key}: top-level available uncertainty has no resample count")
    for field in ("design_version", "seed", "requested_resamples", "interval", "resampling_unit", "cohort_policy"):
        if top[field] is None:
            raise ValueError(f"{key}: top-level uncertainty field {field} must not be null in production")
    if not isinstance(top["warning"], str) or not top["warning"]:
        raise ValueError(f"{key}: top-level uncertainty warning is missing")
    _validate_evidence(profile, major=major)


def validate_bundle(
    bundle: ShowcaseBundle,
    *,
    expected_profile_count: int | None = EXPECTED_PROFILE_COUNT,
    research_sources: dict[str, dict] | None = None,
    uncertainty_mode: str = "available",
    schema_version: str = SCHEMA_VERSION,
) -> None:
    major = parse_major(schema_version)
    artifacts = bundle.artifacts
    for path, artifact in artifacts.items():
        validate_schema(artifact, label=path, major=major)
        _walk_numbers(artifact, path)
        if artifact["contract"] != CONTRACT or artifact["schema_version"] != schema_version:
            raise ValueError(f"{path}: contract identity mismatch")
        if artifact["dataset_version"] != bundle.dataset_version:
            raise ValueError(f"{path}: dataset version mismatch")

    catalog = artifacts["feature-catalog.json"]
    feature_ids = [feature["feature_id"] for feature in catalog["features"]]
    if feature_ids != FEATURE_COLUMNS or [feature["order"] for feature in catalog["features"]] != list(range(32)):
        raise ValueError("feature catalog differs from the frozen 32-feature order")
    family_members = [
        feature["feature_id"]
        for family in FEATURE_FAMILIES
        for feature in catalog["features"]
        if feature["family"] == family
    ]
    if set(family_members) != set(FEATURE_COLUMNS) or len(family_members) != 32:
        raise ValueError("feature families do not partition the catalog")

    index = artifacts["players.index.json"]
    profiles = index["profiles"]
    if expected_profile_count is not None and len(profiles) != expected_profile_count:
        raise ValueError(f"expected {expected_profile_count} index profiles, found {len(profiles)}")
    if len(profiles) != bundle.profile_count:
        raise ValueError("bundle profile count differs from index")
    index_by_key = {item["profile_key"]: item for item in profiles}
    if len(index_by_key) != len(profiles):
        raise ValueError("duplicate profile key in player index")
    expected_paths = {item["artifact_path"] for item in profiles}
    actual_paths = {path for path in artifacts if path.startswith("players/")}
    if expected_paths != actual_paths:
        raise ValueError("player index and payload file set differ")
    if FEATURED_PROFILE_KEY not in index_by_key:
        raise ValueError(f"featured profile is outside the eligible population: {FEATURED_PROFILE_KEY}")

    for position, item in enumerate(profiles):
        _validate_identity_text(item, f"players.index.json.profiles[{position}]")

    for path in sorted(actual_paths):
        profile = artifacts[path]
        if path != f"players/{profile['profile_key']}.json":
            raise ValueError(f"{path}: file name and profile key differ")
        _validate_profile(profile, index_by_key, feature_ids, uncertainty_mode, major=major)
        _validate_identity_text(profile["identity"], f"{path}.identity")
        for rank, neighbor in enumerate(profile["neighbors"], start=1):
            _validate_identity_text(neighbor, f"{path}.neighbors[{rank}]")

    research = artifacts["research-summary.json"]
    if research_sources is not None:
        expected_research = build_research_summary(
            bundle.dataset_version, research_sources, schema_version=schema_version
        )
        if research != expected_research:
            raise ValueError("research summary values drifted from their versioned source artifacts")

    for path, artifact in artifacts.items():
        if path != "research-summary.json" and "statsbomb" in json.dumps(artifact).casefold():
            raise ValueError(f"{path}: StatsBomb data is permitted only in aggregate research experiments")


def records_for(path: str, artifact: dict) -> int:
    """How many records the manifest must declare for an artifact.

    Defined once and imported by the exporter. It was written twice, and the
    two copies disagreed about `representation.json` - one counted its weights,
    the other returned 1 - so every v2 bundle failed its own integrity check.
    A rule that both producer and validator must apply is one rule.
    """
    if path == V2_REPRESENTATION_PATH:
        return len(artifact["representation"]["weights"])
    if path == "feature-catalog.json":
        return len(artifact["features"])
    if path == "players.index.json":
        return len(artifact["profiles"])
    if path == "research-summary.json":
        return len(artifact["experiments"])
    return 1


def measure_gzip_budgets(directory: Path) -> dict[str, int]:
    index_bytes = (directory / "players.index.json").read_bytes()
    catalog_gzip = len(gzip.compress(index_bytes, compresslevel=9, mtime=0))
    profile_sizes = {
        path.name: len(gzip.compress(path.read_bytes(), compresslevel=9, mtime=0))
        for path in (directory / "players").glob("*.json")
    }
    max_profile = max(profile_sizes.values(), default=0)
    if catalog_gzip > CATALOG_GZIP_BUDGET:
        raise ValueError(f"catalog gzip budget exceeded: {catalog_gzip} > {CATALOG_GZIP_BUDGET}")
    if max_profile > PROFILE_GZIP_BUDGET:
        largest = max(profile_sizes, key=lambda name: profile_sizes[name]) if profile_sizes else "<none>"
        raise ValueError(f"profile gzip budget exceeded: {largest} is {max_profile} > {PROFILE_GZIP_BUDGET}")
    return {"catalog_gzip_bytes": catalog_gzip, "max_profile_gzip_bytes": max_profile}


def validate_published_directory(
    directory: Path,
    *,
    expected_profile_count: int | None = EXPECTED_PROFILE_COUNT,
    research_sources: dict[str, dict] | None = None,
    uncertainty_mode: str = "available",
    schema_version: str = SCHEMA_VERSION,
) -> dict[str, int]:
    manifest_path = directory / "manifest.json"
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    validate_schema(manifest, label="manifest.json", major=parse_major(schema_version))
    _walk_numbers(manifest, "manifest.json")
    if canonical_json_bytes(manifest) != manifest_bytes:
        raise ValueError("manifest.json is not canonically serialized")

    manifest_paths = {entry["path"] for entry in manifest["files"]}
    actual_paths = {
        path.relative_to(directory).as_posix() for path in directory.rglob("*.json") if path.name != "manifest.json"
    }
    if manifest_paths != actual_paths:
        raise ValueError("manifest file set differs from published JSON file set")

    artifacts: dict[str, dict] = {}
    entry_by_path = {entry["path"]: entry for entry in manifest["files"]}
    for relative_path in sorted(actual_paths):
        payload = (directory / relative_path).read_bytes()
        artifact = json.loads(payload)
        if canonical_json_bytes(artifact) != payload:
            raise ValueError(f"{relative_path}: artifact is not canonically serialized")
        entry = entry_by_path[relative_path]
        if entry["sha256"] != sha256_bytes(payload) or entry["bytes"] != len(payload):
            raise ValueError(f"{relative_path}: manifest integrity metadata mismatch")
        if entry["records"] != records_for(relative_path, artifact):
            raise ValueError(f"{relative_path}: manifest record count mismatch")
        artifacts[relative_path] = artifact

    bundle = ShowcaseBundle(
        dataset_version=manifest["dataset_version"],
        artifacts=artifacts,
        profile_count=manifest["population"]["profile_count"],
    )
    validate_bundle(
        bundle,
        expected_profile_count=expected_profile_count,
        research_sources=research_sources,
        uncertainty_mode=uncertainty_mode,
        schema_version=schema_version,
    )
    if manifest["population"]["profile_count"] != len(artifacts["players.index.json"]["profiles"]):
        raise ValueError("manifest profile count differs from index")
    if manifest["featured_profile"]["profile_key"] not in {
        item["profile_key"] for item in artifacts["players.index.json"]["profiles"]
    }:
        raise ValueError("manifest featured profile does not resolve")
    return measure_gzip_budgets(directory)


# ---------------------------------------------------------------------------
# Showcase 2.0.0 - diagonal representation contract (D047)
#
# Every rule below is normative in docs/showcase-artifact-contract-v2.md and
# fails closed. A v2 payload that cannot prove which representation produced it
# is not a weaker v2 payload; it is not a v2 payload.
# ---------------------------------------------------------------------------

V2_SCHEMA_VERSION = "2.0.0"
V2_RANKING_METHOD = "weighted_cosine_diagonal_v1"
V2_UNCERTAINTY_DESIGN = "match_bootstrap_diagonal_v1"
V2_REPRESENTATION_PATH = "representation.json"

# Reconstruction tolerance for the weighted evidence sum: wider than float
# noise, far tighter than any difference that could reorder a ranking.
V2_CONTRIBUTION_TOLERANCE = 1e-6


def _v2_digest(values: list) -> str:
    """Canonical digest used for both the weight vector and the feature order."""
    payload = json.dumps(values, separators=(",", ":"), sort_keys=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def weight_digest(weights: list[dict]) -> str:
    """sha256 over [[feature_id, weight], ...] in declared order.

    Order is part of the identity: the same weights attached to a different
    feature order describe a different metric.
    """
    return _v2_digest(
        [[entry["feature_id"], round(float(entry["weight"]), 12)] for entry in weights]
    )


def feature_order_digest(feature_order: list[str]) -> str:
    return _v2_digest(list(feature_order))


def _collect_representation_ids(artifact: Any, found: set[str]) -> None:
    if isinstance(artifact, dict):
        value = artifact.get("representation_id")
        if isinstance(value, str):
            found.add(value)
        for child in artifact.values():
            _collect_representation_ids(child, found)
    elif isinstance(artifact, list):
        for child in artifact:
            _collect_representation_ids(child, found)


def validate_representation_artifact(artifact: dict, *, label: str = V2_REPRESENTATION_PATH) -> str:
    """Validate representation.json and return the representation id."""
    validate_schema(artifact, label=label, major=2)
    representation = artifact["representation"]

    if representation["ranking_method"] != V2_RANKING_METHOD:
        raise ValueError(
            f"{label}: ranking_method must be {V2_RANKING_METHOD}, "
            f"found {representation['ranking_method']}"
        )
    if representation["uncertainty_design"] != V2_UNCERTAINTY_DESIGN:
        raise ValueError(
            f"{label}: uncertainty_design must be {V2_UNCERTAINTY_DESIGN}, "
            f"found {representation['uncertainty_design']}"
        )

    expected_weights = weight_digest(representation["weights"])
    if representation["weight_digest"] != expected_weights:
        raise ValueError(
            f"{label}: weight_digest {representation['weight_digest']} does not match the "
            f"declared weights (recomputed {expected_weights})"
        )

    expected_features = feature_order_digest(representation["feature_order"])
    if representation["feature_order_digest"] != expected_features:
        raise ValueError(
            f"{label}: feature_order_digest {representation['feature_order_digest']} does not "
            f"match the declared feature order (recomputed {expected_features})"
        )

    declared = [entry["feature_id"] for entry in representation["weights"]]
    if declared != list(representation["feature_order"]):
        raise ValueError(
            f"{label}: weights are not in feature_order; a weight vector applied in a different "
            "order describes a different metric"
        )

    return str(representation["id"])


def validate_v2_representation_binding(artifacts: dict[str, dict], representation_id: str) -> None:
    """Every block that carries a representation id must carry the same one."""
    ranking_artifacts = {
        path: artifact for path, artifact in artifacts.items() if path != V2_REPRESENTATION_PATH
    }
    found: set[str] = set()
    for artifact in artifacts.values():
        _collect_representation_ids(artifact, found)
    if ranking_artifacts and not found:
        # representation.json declares its identity as `representation.id`, not
        # as a `representation_id` reference, so a bundle containing only that
        # file has no rankings to bind. Anything else must name what produced it.
        raise ValueError(
            "no artifact references a representation_id; a v2 ranking that cannot name the "
            "representation that produced it is unpublishable"
        )
    mismatched = sorted(found - {representation_id})
    if mismatched:
        raise ValueError(
            f"representation_id mismatch: representation.json declares {representation_id} but "
            f"artifacts also reference {mismatched}"
        )


def validate_v2_weighted_evidence(profile: dict, label: str) -> None:
    """Feature-level weighted contributions must reconstruct the score they explain."""
    by_subject: dict[str, list[dict]] = {}
    for item in profile.get("evidence_index", []):
        if item.get("kind") == "feature_contribution":
            by_subject.setdefault(item["subject"], []).append(item)

    for subject, items in sorted(by_subject.items()):
        total = sum(float(item["weighted_contribution"]) for item in items)
        if subject == "self_retrieval":
            expected = profile["retrieval"]["global"]["similarity_score"]
        else:
            profile_key = subject.split(":", 1)[1]
            match = [n for n in profile["neighbors"] if n["profile_key"] == profile_key]
            if not match:
                raise ValueError(f"{label}: evidence references unknown neighbor {profile_key}")
            expected = match[0]["similarity_score"]
        if expected is None:
            continue
        if abs(total - float(expected)) > V2_CONTRIBUTION_TOLERANCE:
            raise ValueError(
                f"{label}: weighted contributions for {subject} sum to {total}, which does not "
                f"reconstruct similarity_score {expected} within {V2_CONTRIBUTION_TOLERANCE}"
            )


def validate_v2_bundle(artifacts: dict[str, dict]) -> str:
    """Full v2 consistency pass over an in-memory dataset.

    Returns the representation id every artifact agreed on.
    """
    representation_artifact = artifacts.get(V2_REPRESENTATION_PATH)
    if representation_artifact is None:
        raise ValueError(
            f"a v2 dataset must publish {V2_REPRESENTATION_PATH}; without it a consumer cannot "
            "tell which representation produced the rankings"
        )
    representation_id = validate_representation_artifact(representation_artifact)

    for path, artifact in artifacts.items():
        validate_schema(artifact, label=path, major=2)
        declared = artifact.get("schema_version")
        if declared is not None and declared != V2_SCHEMA_VERSION:
            raise ValueError(
                f"{path}: schema_version must be {V2_SCHEMA_VERSION}, found {declared}"
            )

    manifest = artifacts.get("manifest.json")
    if manifest is not None:
        if manifest.get("representation_id") != representation_id:
            raise ValueError(
                f"manifest.json representation_id {manifest.get('representation_id')} does not "
                f"match representation.json {representation_id}"
            )
        published = {entry["path"] for entry in manifest["files"]}
        if V2_REPRESENTATION_PATH not in published:
            raise ValueError(
                f"manifest.json does not hash {V2_REPRESENTATION_PATH}; an unhashed representation "
                "could be swapped without detection"
            )

    validate_v2_representation_binding(artifacts, representation_id)

    for path, artifact in artifacts.items():
        if path.startswith("players/") and "evidence_index" in artifact:
            validate_v2_weighted_evidence(artifact, path)

    return representation_id
