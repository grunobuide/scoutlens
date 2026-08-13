"""CLI exporter for the complete ``scoutlens.showcase/1.0.0`` dataset.

Run from the repository root:

    uv run python -m scoutlens.showcase.export
"""

from __future__ import annotations

import argparse
import datetime
import json
from pathlib import Path
from typing import Any

from scoutlens.evaluation.run_manifest import (
    CONFIG_PATH,
    REPO_ROOT,
    build_run_manifest,
    load_experiment_config,
    sha256_file,
)
from scoutlens.showcase.builder import build_showcase_bundle, load_showcase_inputs
from scoutlens.showcase.catalog import (
    CONTRACT,
    EXPECTED_PROFILE_COUNT,
    FEATURED_PROFILE_KEY,
    FEATURED_PROFILE_REASON,
    SCHEMA_VERSION,
)
from scoutlens.showcase.io import (
    discard_staging,
    make_staging_directory,
    publish_directory,
    sha256_bytes,
    write_canonical_json,
)
from scoutlens.showcase.representation import (
    DIAGONAL_CONFIG_PATH as DIAGONAL_UNCERTAINTY_CONFIG_PATH,
)
from scoutlens.showcase.representation import load_representation
from scoutlens.showcase.research import SOURCE_FILES
from scoutlens.showcase.uncertainty import (
    DEFAULT_BOOTSTRAP_RUN_DIR,
    FEATURE_FILE,
    NEIGHBOR_FILE,
    RETRIEVAL_FILE,
    RUN_METADATA_FILE,
    load_bootstrap_summaries,
)
from scoutlens.showcase.validation import (
    validate_bundle,
    validate_published_directory,
    validate_v2_bundle,
)
from scoutlens.uncertainty.config import UNCERTAINTY_CONFIG_PATH

DEFAULT_PROCESSED_DIR = REPO_ROOT / "data" / "processed"
DEFAULT_ARTIFACT_DIR = REPO_ROOT / "artifacts"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "public" / "showcase" / "v1"
DEFAULT_UNCERTAINTY_RUN_DIR = DEFAULT_BOOTSTRAP_RUN_DIR

V1_SCHEMA_VERSION = "1.0.0"
V2_SCHEMA_VERSION = "2.0.0"
SUPPORTED_SCHEMA_VERSIONS = (V1_SCHEMA_VERSION, V2_SCHEMA_VERSION)
V2_REPRESENTATION_PATH = "representation.json"


def _input_inventory(processed_dir: Path, artifact_dir: Path, bootstrap_run_dir: Path) -> list[tuple[str, Path]]:
    processed = [
        "period_profiles.parquet",
        "events.parquet",
        "matches.parquet",
        "minutes.parquet",
        "players.parquet",
        "teams.parquet",
        "competitions.parquet",
    ]
    bootstrap = [
        (FEATURE_FILE, bootstrap_run_dir / FEATURE_FILE),
        (RETRIEVAL_FILE, bootstrap_run_dir / RETRIEVAL_FILE),
        (NEIGHBOR_FILE, bootstrap_run_dir / NEIGHBOR_FILE),
        (RUN_METADATA_FILE, bootstrap_run_dir / RUN_METADATA_FILE),
    ]
    return [
        *((f"processed/{name}", processed_dir / name) for name in processed),
        *((f"research/{name}", artifact_dir / name) for name in SOURCE_FILES.values()),
        *((f"uncertainty/{name}", path) for name, path in bootstrap),
        (
            "config/uncertainty.json",
            REPO_ROOT / "config" / "uncertainty.json",
        ),
        (
            "schema/showcase-1.0.0.schema.json",
            REPO_ROOT / "src" / "scoutlens" / "showcase" / "schemas" / "showcase-1.0.0.schema.json",
        ),
    ]


def build_representation_artifact(representation, dataset_version: str, training: dict) -> dict:
    """Assemble representation.json from an already-verified representation.

    Nothing here is hand-authored: every field is read from the object that
    `load_representation` returned only after recomputing its digests and
    cross-checking the weights against the recorded D042 benchmark.
    """
    return {
        "contract": CONTRACT,
        "schema_version": V2_SCHEMA_VERSION,
        "dataset_version": dataset_version,
        "representation": {
            "id": representation.id,
            "ranking_method": "weighted_cosine_diagonal_v1",
            "weight_digest": representation.weight_digest,
            "feature_order": list(representation.feature_order),
            "feature_order_digest": representation.feature_order_digest,
            "feature_count": len(representation.feature_order),
            "weights": [
                {"feature_id": feature, "weight": representation.weights_by_feature[feature]}
                for feature in representation.feature_order
            ],
            "training": {
                "provider": "wyscout_pappalardo",
                "season": "2017/18",
                "split_digest": training["split_digest"],
                "split": training["split"],
                "population": {
                    "players": int(training["population"]["players"]),
                    "minutes_threshold_per_period": int(
                        training["population"]["minutes_threshold_per_period"]
                    ),
                },
            },
            "lineage": {
                "protocol_hash": representation.lineage["protocol_hash"],
                "spec_hash": representation.lineage["spec_hash"],
                "decision_records": list(representation.lineage["decision_records"]),
            },
            "uncertainty_design": "match_bootstrap_diagonal_v1",
            "audit_baseline": {
                "method": "cosine_v1",
                "contract": "scoutlens.showcase/1.0.0",
                "note": (
                    "Frozen cosine remains the transparent audit baseline (D045); "
                    "w = 1 reproduces it exactly."
                ),
            },
            "prohibited_claims": [
                "no causal claim",
                "no recruitment or transfer-success claim",
                "no prediction of future performance",
            ],
        },
    }


def _records_for(path: str, artifact: dict) -> int:
    if path == V2_REPRESENTATION_PATH:
        return len(artifact["representation"]["weights"])
    if path == "feature-catalog.json":
        return len(artifact["features"])
    if path == "players.index.json":
        return len(artifact["profiles"])
    if path == "research-summary.json":
        return len(artifact["experiments"])
    return 1


def _build_manifest(
    *,
    bundle,
    generated_at: str,
    config: dict,
    inventory: list[tuple[str, Path]],
    serialized: dict[str, bytes],
    representation: Any = None,
) -> dict:
    run_manifest = build_run_manifest(config, [path for _, path in inventory], config_path=CONFIG_PATH)
    return {
        "contract": CONTRACT,
        "schema_version": SCHEMA_VERSION if representation is None else V2_SCHEMA_VERSION,
        "dataset_version": bundle.dataset_version,
        **({} if representation is None else {"representation_id": representation.id}),
        "generated_at": generated_at,
        "featured_profile": {
            "profile_key": FEATURED_PROFILE_KEY,
            "editorial": True,
            "reason": FEATURED_PROFILE_REASON,
        },
        "source": {
            "provider": "wyscout_pappalardo",
            "season": "2017/18",
            "title": "Soccer match event dataset",
            "citation": (
                "Pappalardo, L., Cintia, P., Rossi, A. et al. A public data set of spatio-temporal "
                "match events in soccer competitions. Scientific Data 6, 236 (2019)."
            ),
            "source_url": "https://doi.org/10.6084/m9.figshare.c.4415000.v5",
            "licence": "CC BY 4.0",
            "licence_url": "https://creativecommons.org/licenses/by/4.0/",
            "redistribution_note": (
                "ScoutLens publishes attributed player-period aggregates only; raw provider rows remain excluded."
            ),
        },
        "population": {
            "analytical_unit": "player_competition",
            "chronological_periods": ["a", "b"],
            "domestic_competition_ids": config["domestic_leagues"],
            "minutes_threshold_per_period": config["primary_minutes_threshold"],
            "profile_count": bundle.profile_count,
            "feature_count": 32,
        },
        "producer": {
            "git_commit": run_manifest["git_commit"],
            "git_dirty": run_manifest["git_dirty"],
            "source_sha256": run_manifest["source_sha256"],
            "config_path": "config/experiment.json",
            "config_sha256": run_manifest["config_sha256"],
            "python_version": run_manifest["python_version"],
            "polars_version": run_manifest["polars_version"],
        },
        "inputs": [
            {
                "logical_name": logical_name,
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
                "public": False,
            }
            for logical_name, path in sorted(inventory)
        ],
        "files": [
            {
                "path": path,
                "media_type": "application/json",
                "sha256": sha256_bytes(serialized[path]),
                "bytes": len(serialized[path]),
                "records": _records_for(path, bundle.artifacts[path]),
            }
            for path in sorted(serialized)
        ],
    }


def export_showcase(
    *,
    processed_dir: Path = DEFAULT_PROCESSED_DIR,
    artifact_dir: Path = DEFAULT_ARTIFACT_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    bootstrap_run_dir: Path = DEFAULT_UNCERTAINTY_RUN_DIR,
    generated_at: str | None = None,
    schema_version: str = V1_SCHEMA_VERSION,
    representation_artifact: Path | None = None,
    expected_profile_count: int | None = EXPECTED_PROFILE_COUNT,
) -> dict[str, int | str]:
    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        raise ValueError(
            f"unsupported schema version {schema_version!r}; supported: "
            f"{list(SUPPORTED_SCHEMA_VERSIONS)}"
        )
    representation = None
    if schema_version == V2_SCHEMA_VERSION:
        # v2 needs BOTH the representation and the matching diagonal run.
        # Either alone would let a bundle claim a representation it was not
        # scored under, or carry intervals from a different metric.
        if representation_artifact is None:
            raise ValueError(
                "v2 export requires --representation-artifact; a v2 bundle that cannot name "
                "the representation that produced its rankings is unpublishable"
            )
        if bootstrap_run_dir == DEFAULT_UNCERTAINTY_RUN_DIR:
            raise ValueError(
                "v2 export requires --bootstrap-run-dir pointing at a diagonal uncertainty "
                "run; the v1 run describes cosine rank stability"
            )
        representation = load_representation(benchmark_path=representation_artifact)
    config = load_experiment_config()
    inventory = _input_inventory(processed_dir, artifact_dir, bootstrap_run_dir)
    missing = [str(path) for _, path in inventory if not path.is_file()]
    if missing:
        raise FileNotFoundError("missing showcase inputs: " + ", ".join(missing))

    inputs = load_showcase_inputs(processed_dir, artifact_dir, config["domestic_leagues"])
    uncertainty = load_bootstrap_summaries(
        bootstrap_run_dir,
        uncertainty_config_path=(
            UNCERTAINTY_CONFIG_PATH if representation is None else DIAGONAL_UNCERTAINTY_CONFIG_PATH
        ),
        representation=representation,
    )
    bundle = build_showcase_bundle(
        inputs,
        competition_ids=config["domestic_leagues"],
        minutes_threshold=config["primary_minutes_threshold"],
        expected_profile_count=expected_profile_count,
        uncertainty=uncertainty,
        representation=representation,
    )
    if representation is None:
        validate_bundle(bundle, research_sources=inputs.research_sources)

    timestamp = generated_at or datetime.datetime.now(datetime.timezone.utc).isoformat()
    staging = make_staging_directory(output_dir)
    try:
        artifacts = dict(bundle.artifacts)
        if representation is not None:
            training = json.loads(
                DIAGONAL_UNCERTAINTY_CONFIG_PATH.read_text(encoding="utf-8")
            )["representation"]["training"]
            artifacts[V2_REPRESENTATION_PATH] = build_representation_artifact(
                representation, bundle.dataset_version, training
            )
        serialized = {
            path: write_canonical_json(staging / path, artifact)
            for path, artifact in sorted(artifacts.items())
        }
        manifest = _build_manifest(
            bundle=bundle,
            generated_at=timestamp,
            config=config,
            inventory=inventory,
            serialized=serialized,
            representation=representation,
        )
        write_canonical_json(staging / "manifest.json", manifest)
        if representation is not None:
            # Fail-closed BEFORE the atomic swap, so a rejected build leaves
            # the previous target untouched.
            validate_v2_bundle({**artifacts, "manifest.json": manifest})
        budgets = validate_published_directory(
            staging,
            expected_profile_count=EXPECTED_PROFILE_COUNT,
            research_sources=inputs.research_sources,
        )
        publish_directory(staging, output_dir)
    except Exception:
        discard_staging(staging)
        raise

    return {
        "dataset_version": bundle.dataset_version,
        "profile_count": bundle.profile_count,
        **budgets,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed-dir", type=Path, default=DEFAULT_PROCESSED_DIR)
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--bootstrap-run-dir", type=Path, default=DEFAULT_UNCERTAINTY_RUN_DIR)
    parser.add_argument(
        "--schema-version",
        choices=SUPPORTED_SCHEMA_VERSIONS,
        default=V1_SCHEMA_VERSION,
        help="Contract major to produce. Omitting it preserves v1 behaviour exactly.",
    )
    parser.add_argument(
        "--representation-artifact",
        type=Path,
        default=None,
        help="D045 benchmark artifact the pinned weights are verified against. Required for 2.0.0.",
    )
    parser.add_argument(
        "--generated-at",
        help="Optional ISO-8601 timestamp for deterministic replay tests; defaults to current UTC time.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = export_showcase(
        processed_dir=args.processed_dir,
        artifact_dir=args.artifact_dir,
        output_dir=args.output_dir,
        bootstrap_run_dir=args.bootstrap_run_dir,
        generated_at=args.generated_at,
        schema_version=args.schema_version,
        representation_artifact=args.representation_artifact,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
