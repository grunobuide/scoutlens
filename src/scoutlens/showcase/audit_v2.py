"""Standalone independent audit of a published showcase-v2 candidate.

This module deliberately does **not** import the producer. It does not call
`build_showcase_bundle`, `_evidence_for_candidate`, `validate_bundle` or
`validate_v2_bundle`, and it does not read any summary the exporter returned.
An audit that reuses the code under audit only proves that code agrees with
itself.

What it does instead: read the published JSON, read the weights out of
`representation.json`, and recompute both similarity decompositions from the
`query_global_z` / `candidate_global_z` values stored in the evidence rows -

    contribution_i          = q_i c_i / ( ||q|| ||c|| )
    weighted_contribution_i = w_i q_i c_i / ( ||sqrt(w) q|| ||sqrt(w) c|| )

- then compare every recomputed number against the published one. Feature
  order, family membership and catalog order are read from
  `feature-catalog.json` rather than imported from the research layer, so a
  disagreement between catalog and profiles is itself detectable.

The only ScoutLens import is the JSON Schema validator, which the bead
explicitly permits as a schema primitive.

Usage::

    python -m scoutlens.showcase.audit_v2 \\
        --v1-root public/showcase/v1 \\
        --candidate-a <dir> --candidate-b <dir> \\
        --expected-profiles 1257
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from scoutlens.showcase.schema import validate_schema

RANKING_METHOD = "weighted_cosine_diagonal_v1"
UNCERTAINTY_DESIGN = "match_bootstrap_diagonal_v1"
RETRIEVAL_METHOD = "combined_scaler_diagonal_v1"
REPRESENTATION_PATH = "representation.json"

#: Per-item agreement between the recomputed and published decompositions.
#: Wide enough for a different summation order, far tighter than anything that
#: could reorder a ranking.
ITEM_TOLERANCE = 1e-9

#: The normative reconstruction tolerance from the v2 contract.
SCORE_TOLERANCE = 1e-6

#: Fields that describe the player rather than the ranking. The measurement
#: frame is unscaled, so the diagonal representation cannot move them: every
#: one must be byte-equal to v1.
FINGERPRINT_FIELDS = (
    "raw_value",
    "global_z_score",
    "global_percentile",
    "within_role_percentile",
    "imputed_for_model",
    "support",
)


@dataclasses.dataclass
class AuditReport:
    label: str
    failures: list[str] = dataclasses.field(default_factory=list)
    stats: dict[str, Any] = dataclasses.field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return not self.failures

    def fail(self, message: str) -> None:
        self.failures.append(message)

    def render(self) -> str:
        lines = [f"== {self.label}: {'PASS' if self.passed else 'FAIL'}"]
        for key in sorted(self.stats):
            lines.append(f"   {key}: {self.stats[key]}")
        for failure in self.failures[:40]:
            lines.append(f"   FAIL {failure}")
        if len(self.failures) > 40:
            lines.append(f"   ... and {len(self.failures) - 40} more failures")
        return "\n".join(lines)


# --- reading ---------------------------------------------------------------


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _published_files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*.json"))
    }


def _digest(values: list) -> str:
    """The contract's digest: sha256 over a compact JSON array in declared order.

    Reimplemented here rather than imported, because a digest checked with the
    function that produced it is not checked.
    """
    payload = json.dumps(values, separators=(",", ":"), sort_keys=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# --- the recomputation -----------------------------------------------------


def _decompose(
    rows: list[dict], weights: dict[str, float]
) -> tuple[dict[str, float], dict[str, float], float, float]:
    """Recompute both decompositions for one subject from its evidence rows.

    Returns `(contribution_by_feature, weighted_by_feature, cosine, score)`.
    """
    query = {row["feature_id"]: float(row["query_global_z"]) for row in rows}
    candidate = {row["feature_id"]: float(row["candidate_global_z"]) for row in rows}

    query_norm = math.sqrt(math.fsum(value**2 for value in query.values()))
    candidate_norm = math.sqrt(math.fsum(value**2 for value in candidate.values()))
    denominator = query_norm * candidate_norm

    weighted_query_norm = math.sqrt(
        math.fsum(weights.get(feature, 0.0) * value**2 for feature, value in query.items())
    )
    weighted_candidate_norm = math.sqrt(
        math.fsum(weights.get(feature, 0.0) * value**2 for feature, value in candidate.items())
    )
    weighted_denominator = weighted_query_norm * weighted_candidate_norm

    contributions = {
        feature: (query[feature] * candidate[feature] / denominator if denominator > 0 else 0.0)
        for feature in query
    }
    weighted = {
        feature: (
            weights.get(feature, 0.0) * query[feature] * candidate[feature] / weighted_denominator
            if weighted_denominator > 0
            else 0.0
        )
        for feature in query
    }
    return (
        contributions,
        weighted,
        math.fsum(contributions.values()),
        math.fsum(weighted.values()),
    )


# --- per-candidate audit ---------------------------------------------------


def _audit_representation(artifact: dict, report: AuditReport) -> tuple[str, dict[str, float]]:
    representation = artifact["representation"]
    identity = representation["id"]

    if representation["ranking_method"] != RANKING_METHOD:
        report.fail(f"representation ranking_method is {representation['ranking_method']!r}")
    if representation["uncertainty_design"] != UNCERTAINTY_DESIGN:
        report.fail(f"representation uncertainty_design is {representation['uncertainty_design']!r}")

    order = list(representation["feature_order"])
    weights_declared = representation["weights"]
    if [entry["feature_id"] for entry in weights_declared] != order:
        report.fail("weights are not in feature_order; permuted weights describe a different metric")
    if len(order) != representation["feature_count"] or len(set(order)) != len(order):
        report.fail("feature_order is not a unique list of feature_count entries")

    recomputed_weight_digest = _digest(
        [[entry["feature_id"], round(float(entry["weight"]), 12)] for entry in weights_declared]
    )
    if recomputed_weight_digest != representation["weight_digest"]:
        report.fail(
            f"weight_digest mismatch: recomputed {recomputed_weight_digest}, "
            f"declared {representation['weight_digest']}"
        )
    recomputed_order_digest = _digest(order)
    if recomputed_order_digest != representation["feature_order_digest"]:
        report.fail(
            f"feature_order_digest mismatch: recomputed {recomputed_order_digest}, "
            f"declared {representation['feature_order_digest']}"
        )
    if identity != f"rep-{representation['weight_digest'][:16]}":
        report.fail(f"representation id {identity} does not derive from its weight digest")
    if any(float(entry["weight"]) < 0 for entry in weights_declared):
        report.fail("a negative weight would invert a feature's meaning")

    weights = {entry["feature_id"]: float(entry["weight"]) for entry in weights_declared}
    report.stats["representation_id"] = identity
    report.stats["weighted_features"] = len(weights)
    return identity, weights


def _audit_profile(
    profile: dict,
    *,
    weights: dict[str, float],
    representation_id: str,
    catalog_order: dict[str, int],
    families: dict[str, str],
    index_by_key: dict[str, dict],
    report: AuditReport,
) -> None:
    key = profile["profile_key"]

    if profile["retrieval"]["method"] != RETRIEVAL_METHOD:
        report.fail(f"{key}: retrieval.method is {profile['retrieval']['method']!r}")

    for label, value in _walk_field(profile, "representation_id"):
        if value != representation_id:
            report.fail(f"{key}: {label} names representation {value!r}")
    for label, value in _walk_field(profile, "design_version"):
        if value is not None and value != UNCERTAINTY_DESIGN:
            report.fail(f"{key}: {label} carries uncertainty design {value!r}")

    by_subject: dict[str, list[dict]] = {}
    for item in profile["evidence_index"]:
        by_subject.setdefault(item["subject"], []).append(item)

    expected_scores = {"self_retrieval": profile["retrieval"]["global"]["similarity_score"]}
    for neighbor in profile["neighbors"]:
        expected_scores[f"neighbor:{neighbor['profile_key']}"] = neighbor["similarity_score"]
    if set(by_subject) != set(expected_scores):
        report.fail(f"{key}: evidence subjects do not match retrieval subjects")
        return

    for subject, items in sorted(by_subject.items()):
        feature_rows = [item for item in items if item["kind"] == "feature_contribution"]
        family_rows = [item for item in items if item["kind"] == "family_contribution"]
        if len(feature_rows) != len(catalog_order):
            report.fail(f"{key}/{subject}: {len(feature_rows)} feature rows, expected {len(catalog_order)}")
            continue
        if {row["feature_id"] for row in feature_rows} != set(catalog_order):
            report.fail(f"{key}/{subject}: feature evidence does not cover the catalog")
            continue

        contributions, weighted, cosine, score = _decompose(feature_rows, weights)

        for row in feature_rows:
            feature = row["feature_id"]
            expected_weight = weights.get(feature, 0.0)
            if abs(float(row["feature_weight"]) - expected_weight) > ITEM_TOLERANCE:
                report.fail(f"{key}/{subject}/{feature}: feature_weight is not the published weight")
            if abs(float(row["contribution"]) - contributions[feature]) > ITEM_TOLERANCE:
                report.fail(f"{key}/{subject}/{feature}: contribution does not recompute")
            if abs(float(row["weighted_contribution"]) - weighted[feature]) > ITEM_TOLERANCE:
                report.fail(f"{key}/{subject}/{feature}: weighted_contribution does not recompute")
            if row["family"] != families[feature]:
                report.fail(f"{key}/{subject}/{feature}: family disagrees with the catalog")

        published = expected_scores[subject]
        if published is None:
            report.fail(f"{key}/{subject}: published score is null")
        elif abs(score - float(published)) > SCORE_TOLERANCE:
            report.fail(
                f"{key}/{subject}: recomputed similarity {score} does not reconstruct "
                f"published {published}"
            )
        if abs(math.fsum(float(row["weighted_contribution"]) for row in feature_rows) - float(published or 0.0)) > SCORE_TOLERANCE:
            report.fail(f"{key}/{subject}: published weighted contributions do not sum to the score")

        for row in family_rows:
            members = [feature for feature, family in families.items() if family == row["family"]]
            if abs(float(row["contribution"]) - math.fsum(contributions[m] for m in members)) > ITEM_TOLERANCE:
                report.fail(f"{key}/{subject}/{row['family']}: family contribution does not recompute")
            if abs(float(row["weighted_contribution"]) - math.fsum(weighted[m] for m in members)) > ITEM_TOLERANCE:
                report.fail(f"{key}/{subject}/{row['family']}: weighted family contribution does not recompute")
        if abs(math.fsum(float(row["contribution"]) for row in family_rows) - cosine) > SCORE_TOLERANCE:
            report.fail(f"{key}/{subject}: family contributions do not reconstruct the cosine audit view")

        expected_order = sorted(
            feature_rows,
            key=lambda row: (-abs(float(row["weighted_contribution"])), catalog_order[row["feature_id"]]),
        )
        if [row["feature_id"] for row in feature_rows] != [row["feature_id"] for row in expected_order]:
            report.fail(f"{key}/{subject}: feature evidence is not in the published order")

    neighbors = profile["neighbors"]
    expected_neighbors = sorted(
        neighbors, key=lambda neighbor: (-float(neighbor["similarity_score"]), neighbor["profile_key"])
    )
    if neighbors != expected_neighbors:
        report.fail(f"{key}: neighbors are not ordered by descending similarity_score")
    if [neighbor["rank"] for neighbor in neighbors] != list(range(1, len(neighbors) + 1)):
        report.fail(f"{key}: neighbor ranks are not 1..n")
    if len({neighbor["profile_key"] for neighbor in neighbors}) != len(neighbors):
        report.fail(f"{key}: neighbors are not distinct")
    query_player = profile["identity"]["player_key"]
    if any(neighbor["player_key"] == query_player for neighbor in neighbors):
        report.fail(f"{key}: the same human appears among its own neighbors")
    if any(neighbor["role"] != profile["identity"]["role"] for neighbor in neighbors):
        report.fail(f"{key}: a neighbor has a different role")
    for neighbor in neighbors:
        if neighbor["profile_key"] not in index_by_key:
            report.fail(f"{key}: neighbor {neighbor['profile_key']} does not resolve through the index")

    for outcome_name in ("global", "within_role", "baseline_role_minutes"):
        outcome = profile["retrieval"][outcome_name]
        rank = outcome["self_rank"]
        if not 1 <= rank <= outcome["candidate_count"]:
            report.fail(f"{key}/{outcome_name}: self_rank {rank} outside the candidate pool")
        if abs(float(outcome["reciprocal_rank"]) - 1.0 / rank) > ITEM_TOLERANCE:
            report.fail(f"{key}/{outcome_name}: reciprocal_rank does not match self_rank")


def _walk_field(node: Any, field: str, path: str = "") -> list[tuple[str, Any]]:
    found: list[tuple[str, Any]] = []
    if isinstance(node, dict):
        for name, value in node.items():
            child = f"{path}.{name}" if path else name
            if name == field:
                found.append((child, value))
            else:
                found.extend(_walk_field(value, field, child))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            found.extend(_walk_field(value, field, f"{path}[{index}]"))
    return found


def audit_candidate(root: Path, *, expected_profiles: int, label: str = "candidate") -> AuditReport:
    report = AuditReport(label=f"{label} {root}")
    files = _published_files(root)

    # Parse defensively before anything else. A corrupt artifact is a finding,
    # not a crash: an auditor that raises on the payload it was pointed at
    # reports nothing about the rest of the bundle.
    parsed: dict[str, Any] = {}
    for path, payload in files.items():
        try:
            parsed[path] = json.loads(payload)
        except ValueError as error:
            report.fail(f"{path}: not valid JSON ({error})")

    required = {"manifest.json", REPRESENTATION_PATH, "feature-catalog.json", "players.index.json"}
    absent_required = sorted(required - set(parsed))
    if absent_required:
        report.fail(f"missing or unreadable required artifacts: {absent_required}")
        return report
    manifest = parsed["manifest.json"]

    # Artifacts that fail the schema are recorded and then excluded from the
    # semantic pass. Auditing one anyway means reaching for fields the schema
    # just proved absent, which raises instead of reporting - the whole bundle
    # then yields a traceback rather than a list of findings, and the other
    # 1,256 profiles go unexamined.
    invalid: set[str] = set()
    for path, artifact in parsed.items():
        try:
            validate_schema(artifact, label=path, major=2)
        except ValueError as error:
            report.fail(str(error)[:200])
            invalid.add(path)

    declared = {entry["path"]: entry for entry in manifest["files"]}
    on_disk = {path for path in files if path != "manifest.json"}
    if set(declared) != on_disk:
        missing = sorted(on_disk - set(declared))
        extra = sorted(set(declared) - on_disk)
        report.fail(f"manifest file set differs from disk: undeclared={missing[:3]} missing={extra[:3]}")
    if REPRESENTATION_PATH not in declared:
        report.fail("the manifest does not hash the representation")
    for path, entry in sorted(declared.items()):
        if path not in files:
            continue
        payload = files[path]
        if entry["bytes"] != len(payload):
            report.fail(f"{path}: manifest byte count is {entry['bytes']}, file is {len(payload)}")
        actual = hashlib.sha256(payload).hexdigest()
        if entry["sha256"] != actual:
            report.fail(f"{path}: manifest sha256 does not match the file")

    if invalid & {REPRESENTATION_PATH, "feature-catalog.json", "players.index.json"}:
        # Without a valid representation, catalog or index there is nothing to
        # audit the profiles against, so stop here with the findings so far
        # rather than inventing a baseline.
        return report
    representation_id, weights = _audit_representation(parsed[REPRESENTATION_PATH], report)
    if manifest.get("representation_id") != representation_id:
        report.fail("the manifest names a different representation than representation.json")

    catalog = parsed["feature-catalog.json"]["features"]
    catalog_order = {feature["feature_id"]: feature["order"] for feature in catalog}
    families = {feature["feature_id"]: feature["family"] for feature in catalog}
    absent = sorted(set(catalog_order) - set(weights))
    report.stats["catalog_features"] = len(catalog_order)
    report.stats["features_excluded_from_ranking"] = len(absent)

    index = parsed["players.index.json"]["profiles"]
    index_by_key = {item["profile_key"]: item for item in index}
    profile_paths = sorted(path for path in parsed if path.startswith("players/"))
    if len(profile_paths) != expected_profiles:
        report.fail(f"{len(profile_paths)} profiles published, expected {expected_profiles}")
    if len(index) != expected_profiles:
        report.fail(f"{len(index)} index entries, expected {expected_profiles}")
    if manifest["population"]["profile_count"] != expected_profiles:
        report.fail(f"manifest profile_count is {manifest['population']['profile_count']}")

    for path in profile_paths:
        if path in invalid:
            continue
        profile = parsed[path]
        if path != f"players/{profile['profile_key']}.json":
            report.fail(f"{path}: file name and profile key differ")
        _audit_profile(
            profile,
            weights=weights,
            representation_id=representation_id,
            catalog_order=catalog_order,
            families=families,
            index_by_key=index_by_key,
            report=report,
        )

    report.stats["dataset_version"] = manifest["dataset_version"]
    report.stats["profiles_audited"] = len(profile_paths)
    report.stats["files"] = len(files)
    return report


# --- candidate comparison and the v1 diff ----------------------------------


def compare_candidates(first: Path, second: Path) -> AuditReport:
    report = AuditReport(label=f"determinism {first.name} vs {second.name}")
    left = _published_files(first)
    right = _published_files(second)
    if set(left) != set(right):
        report.fail(f"file sets differ: only-a={sorted(set(left) - set(right))[:3]} only-b={sorted(set(right) - set(left))[:3]}")
    differing = sorted(path for path in set(left) & set(right) if left[path] != right[path])
    if differing:
        report.fail(f"{len(differing)} files differ, first: {differing[:3]}")
    report.stats["files_compared"] = len(set(left) & set(right))
    report.stats["identical"] = len(set(left) & set(right)) - len(differing)
    return report


def compare_with_v1(v1_root: Path, v2_root: Path) -> AuditReport:
    """Count what the diagonal representation changed, and prove what it must not.

    The measurement frame is unscaled, so no fingerprint value may move. The
    role-and-minutes baseline never touches the fingerprint, so its ranks may
    not move either. And if nothing at all moved, the representation is not
    being applied - an all-unchanged result is a failure, not a success.
    """
    report = AuditReport(label="v1 -> v2 comparison")
    v1_keys = {path.stem for path in (v1_root / "players").glob("*.json")}
    v2_keys = {path.stem for path in (v2_root / "players").glob("*.json")}
    if v1_keys != v2_keys:
        report.fail(f"population differs: only-v1={sorted(v1_keys - v2_keys)[:3]} only-v2={sorted(v2_keys - v1_keys)[:3]}")

    counts: Counter[str] = Counter()
    for key in sorted(v1_keys & v2_keys):
        before = _read_json(v1_root / "players" / f"{key}.json")
        after = _read_json(v2_root / "players" / f"{key}.json")

        for period in ("a", "b"):
            for old, new in zip(
                before["periods"][period]["features"],
                after["periods"][period]["features"],
                strict=True,
            ):
                if old["feature_id"] != new["feature_id"]:
                    report.fail(f"{key}/{period}: feature order changed")
                    break
                for field in FINGERPRINT_FIELDS:
                    if old[field] != new[field]:
                        report.fail(f"{key}/{period}/{old['feature_id']}: {field} changed between majors")
                    else:
                        counts["fingerprint_values_unchanged"] += 1

        if before["identity"] != after["identity"]:
            report.fail(f"{key}: identity changed between majors")
        if before["cohort"] != after["cohort"]:
            report.fail(f"{key}: cohort changed between majors")
        if {item["code"] for item in before["caveats"]} != {item["code"] for item in after["caveats"]}:
            report.fail(f"{key}: caveat codes changed between majors")

        if before["retrieval"]["baseline_role_minutes"]["self_rank"] != after["retrieval"]["baseline_role_minutes"]["self_rank"]:
            report.fail(f"{key}: the role-and-minutes baseline rank moved, but it never uses the fingerprint")

        for outcome in ("global", "within_role"):
            if before["retrieval"][outcome]["self_rank"] != after["retrieval"][outcome]["self_rank"]:
                counts[f"{outcome}_self_rank_changed"] += 1
            if before["retrieval"][outcome]["cosine_similarity"] != after["retrieval"][outcome]["similarity_score"]:
                counts[f"{outcome}_score_changed"] += 1

        if [n["profile_key"] for n in before["neighbors"]] != [n["profile_key"] for n in after["neighbors"]]:
            counts["neighbor_order_changed"] += 1
        if {n["profile_key"] for n in before["neighbors"]} != {n["profile_key"] for n in after["neighbors"]}:
            counts["neighbor_set_changed"] += 1

    report.stats.update(counts)
    report.stats["profiles_compared"] = len(v1_keys & v2_keys)
    if counts["global_score_changed"] == 0:
        report.fail(
            "no global score changed between majors; a diagonal representation that reproduces "
            "cosine exactly is either unapplied or all-ones"
        )
    return report


# --- CLI -------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--v1-root", type=Path, required=True)
    parser.add_argument("--candidate-a", type=Path, required=True)
    parser.add_argument("--candidate-b", type=Path)
    parser.add_argument("--expected-profiles", type=int, required=True)
    args = parser.parse_args(argv)

    reports = [audit_candidate(args.candidate_a, expected_profiles=args.expected_profiles, label="candidate A")]
    if args.candidate_b is not None:
        reports.append(
            audit_candidate(args.candidate_b, expected_profiles=args.expected_profiles, label="candidate B")
        )
        reports.append(compare_candidates(args.candidate_a, args.candidate_b))
    reports.append(compare_with_v1(args.v1_root, args.candidate_a))

    for report in reports:
        print(report.render())
    passed = all(report.passed for report in reports)
    print(f"\n== AUDIT {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
