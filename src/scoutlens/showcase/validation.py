"""Fail-closed validation for showcase schemas, cross-links, and bytes."""

from __future__ import annotations

import gzip
import json
import math
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
from scoutlens.showcase.schema import validate_schema

CATALOG_GZIP_BUDGET = 400 * 1024
PROFILE_GZIP_BUDGET = 30 * 1024


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


def _validate_evidence(profile: dict) -> None:
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
    expected_scores = {"self_retrieval": profile["retrieval"]["global"]["cosine_similarity"]}
    expected_scores.update(
        {f"neighbor:{neighbor['profile_key']}": neighbor["cosine_similarity"] for neighbor in profile["neighbors"]}
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
        expected_order = sorted(
            feature_items,
            key=lambda item: (-abs(item["contribution"]), FEATURE_ORDER[item["feature_id"]]),
        )
        if feature_items != expected_order:
            raise ValueError(f"{profile['profile_key']}/{subject}: feature evidence order is not deterministic")
        score = expected_scores[subject]
        if score is None:
            raise ValueError(f"{profile['profile_key']}/{subject}: cosine evidence has a null score")
        if not math.isclose(math.fsum(item["contribution"] for item in feature_items), score, abs_tol=1e-9):
            raise ValueError(f"{profile['profile_key']}/{subject}: feature contributions do not reconstruct cosine")
        if not math.isclose(math.fsum(item["contribution"] for item in family_items), score, abs_tol=1e-9):
            raise ValueError(f"{profile['profile_key']}/{subject}: family contributions do not reconstruct cosine")


def _validate_profile(profile: dict, index_by_key: dict[str, dict], feature_ids: list[str]) -> None:
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
            if value["uncertainty"]["status"] != "pending":
                raise ValueError(f"{key}: nested feature uncertainty must be pending in v1")

    query_player = profile["identity"]["player_key"]
    role = profile["identity"]["role"]
    neighbors = profile["neighbors"]
    if len({neighbor["profile_key"] for neighbor in neighbors}) != 5:
        raise ValueError(f"{key}: neighbors are not distinct")
    if any(neighbor["player_key"] == query_player for neighbor in neighbors):
        raise ValueError(f"{key}: same-human profile leaked into neighbors")
    if any(neighbor["role"] != role for neighbor in neighbors):
        raise ValueError(f"{key}: neighbor role differs from query role")
    expected_neighbors = sorted(
        neighbors, key=lambda neighbor: (-neighbor["cosine_similarity"], neighbor["profile_key"])
    )
    if neighbors != expected_neighbors or [neighbor["rank"] for neighbor in neighbors] != [1, 2, 3, 4, 5]:
        raise ValueError(f"{key}: neighbors are not deterministically ranked")
    if any(neighbor["profile_key"] not in index_by_key for neighbor in neighbors):
        raise ValueError(f"{key}: neighbor profile does not resolve through the index")

    mandatory = {
        "fingerprint_not_style_proof",
        "similarity_not_recruitment",
        "same_season_team_confound",
        "within_role_display_differs_from_global_model",
        "uncertainty_pending",
    }
    caveat_codes = {item["code"] for item in profile["caveats"]}
    if not mandatory.issubset(caveat_codes):
        raise ValueError(f"{key}: mandatory caveats missing: {sorted(mandatory - caveat_codes)}")
    if role == "Goalkeeper" and "goalkeeper_feature_coverage_weak" not in caveat_codes:
        raise ValueError(f"{key}: goalkeeper coverage caveat missing")
    if profile["uncertainty"]["status"] != "pending":
        raise ValueError(f"{key}: top-level uncertainty must be pending in v1")
    _validate_evidence(profile)


def validate_bundle(
    bundle: ShowcaseBundle,
    *,
    expected_profile_count: int | None = EXPECTED_PROFILE_COUNT,
    research_sources: dict[str, dict] | None = None,
) -> None:
    artifacts = bundle.artifacts
    for path, artifact in artifacts.items():
        validate_schema(artifact, label=path)
        _walk_numbers(artifact, path)
        if artifact["contract"] != CONTRACT or artifact["schema_version"] != SCHEMA_VERSION:
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

    for path in sorted(actual_paths):
        profile = artifacts[path]
        if path != f"players/{profile['profile_key']}.json":
            raise ValueError(f"{path}: file name and profile key differ")
        _validate_profile(profile, index_by_key, feature_ids)

    research = artifacts["research-summary.json"]
    if research_sources is not None:
        expected_research = build_research_summary(bundle.dataset_version, research_sources)
        if research != expected_research:
            raise ValueError("research summary values drifted from their versioned source artifacts")

    for path, artifact in artifacts.items():
        if path != "research-summary.json" and "statsbomb" in json.dumps(artifact).casefold():
            raise ValueError(f"{path}: StatsBomb data is permitted only in aggregate research experiments")


def _records_for(path: str, artifact: dict) -> int:
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
) -> dict[str, int]:
    manifest_path = directory / "manifest.json"
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    validate_schema(manifest, label="manifest.json")
    _walk_numbers(manifest, "manifest.json")
    if canonical_json_bytes(manifest) != manifest_bytes:
        raise ValueError("manifest.json is not canonically serialized")

    manifest_paths = {entry["path"] for entry in manifest["files"]}
    actual_paths = {
        path.relative_to(directory).as_posix()
        for path in directory.rglob("*.json")
        if path.name != "manifest.json"
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
        if entry["records"] != _records_for(relative_path, artifact):
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
    )
    if manifest["population"]["profile_count"] != len(artifacts["players.index.json"]["profiles"]):
        raise ValueError("manifest profile count differs from index")
    if manifest["featured_profile"]["profile_key"] not in {
        item["profile_key"] for item in artifacts["players.index.json"]["profiles"]
    }:
        raise ValueError("manifest featured profile does not resolve")
    return measure_gzip_budgets(directory)
