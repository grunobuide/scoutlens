"""CLI exporter for the complete ``scoutlens.showcase/1.0.0`` dataset.

Run from the repository root:

    uv run python -m scoutlens.showcase.export
"""

from __future__ import annotations

import argparse
import datetime
import json
from pathlib import Path

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
from scoutlens.showcase.research import SOURCE_FILES
from scoutlens.showcase.validation import validate_bundle, validate_published_directory

DEFAULT_PROCESSED_DIR = REPO_ROOT / "data" / "processed"
DEFAULT_ARTIFACT_DIR = REPO_ROOT / "artifacts"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "public" / "showcase" / "v1"


def _input_inventory(processed_dir: Path, artifact_dir: Path) -> list[tuple[str, Path]]:
    processed = [
        "period_profiles.parquet",
        "events.parquet",
        "matches.parquet",
        "minutes.parquet",
        "players.parquet",
        "teams.parquet",
        "competitions.parquet",
    ]
    return [
        *((f"processed/{name}", processed_dir / name) for name in processed),
        *((f"research/{name}", artifact_dir / name) for name in SOURCE_FILES.values()),
        (
            "schema/showcase-1.0.0.schema.json",
            REPO_ROOT / "src" / "scoutlens" / "showcase" / "schemas" / "showcase-1.0.0.schema.json",
        ),
    ]


def _records_for(path: str, artifact: dict) -> int:
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
) -> dict:
    run_manifest = build_run_manifest(config, [path for _, path in inventory], config_path=CONFIG_PATH)
    return {
        "contract": CONTRACT,
        "schema_version": SCHEMA_VERSION,
        "dataset_version": bundle.dataset_version,
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
    generated_at: str | None = None,
) -> dict[str, int | str]:
    config = load_experiment_config()
    inventory = _input_inventory(processed_dir, artifact_dir)
    missing = [str(path) for _, path in inventory if not path.is_file()]
    if missing:
        raise FileNotFoundError("missing showcase inputs: " + ", ".join(missing))

    inputs = load_showcase_inputs(processed_dir, artifact_dir, config["domestic_leagues"])
    bundle = build_showcase_bundle(
        inputs,
        competition_ids=config["domestic_leagues"],
        minutes_threshold=config["primary_minutes_threshold"],
        expected_profile_count=EXPECTED_PROFILE_COUNT,
    )
    validate_bundle(bundle, research_sources=inputs.research_sources)

    timestamp = generated_at or datetime.datetime.now(datetime.timezone.utc).isoformat()
    staging = make_staging_directory(output_dir)
    try:
        serialized = {
            path: write_canonical_json(staging / path, artifact)
            for path, artifact in sorted(bundle.artifacts.items())
        }
        manifest = _build_manifest(
            bundle=bundle,
            generated_at=timestamp,
            config=config,
            inventory=inventory,
            serialized=serialized,
        )
        write_canonical_json(staging / "manifest.json", manifest)
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
        generated_at=args.generated_at,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
