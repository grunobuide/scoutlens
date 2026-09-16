"""Load and apply the explanation contract's JSON Schemas.

Mirrors `scoutlens.showcase.schema` deliberately: same resource layout, same
fail-closed posture on an unknown version, same error shape. A reader who has
audited one boundary should not have to learn a second idiom to audit this one.

Schema validation is the first gate, never the only one. A structurally perfect
output can still fabricate a citation, cite an excluded feature as ranking
evidence, or assert a number the artifact does not publish - none of which a
schema can express. `validator.validate_output` owns those.
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files
from typing import Any

from jsonschema import Draft202012Validator

from scoutlens.explanations.policy import BUNDLE_SCHEMA_VERSION, OUTPUT_SCHEMA_VERSION

BUNDLE_SCHEMA_FILES = {BUNDLE_SCHEMA_VERSION: "explanation-bundle-1.0.0.schema.json"}
OUTPUT_SCHEMA_FILES = {OUTPUT_SCHEMA_VERSION: "explanation-output-1.0.0.schema.json"}


def _load(resource: str) -> dict[str, Any]:
    path = files("scoutlens.explanations.schemas").joinpath(resource)
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=4)
def _validator(resource: str) -> Draft202012Validator:
    schema = _load(resource)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _resolve(files_map: dict[str, str], version: str, kind: str) -> str:
    resource = files_map.get(version)
    if resource is None:
        raise ValueError(
            f"unsupported {kind} schema version {version!r}; known versions: {sorted(files_map)}"
        )
    return resource


def validate_bundle_schema(bundle: Any, *, version: str = BUNDLE_SCHEMA_VERSION) -> None:
    """Raise if the bundle does not match its schema."""
    _apply(_resolve(BUNDLE_SCHEMA_FILES, version, "bundle"), bundle, label="explanation bundle")


def validate_output_schema(output: Any, *, version: str = OUTPUT_SCHEMA_VERSION) -> None:
    """Raise if the output does not match its schema."""
    _apply(_resolve(OUTPUT_SCHEMA_FILES, version, "output"), output, label="explanation output")


def _apply(resource: str, instance: Any, *, label: str) -> None:
    errors = sorted(
        _validator(resource).iter_errors(instance),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        raise ValueError(f"{label}: JSON Schema violation at {location}: {error.message}")
