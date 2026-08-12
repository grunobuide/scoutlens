"""Load and apply the formal JSON Schema for the public artifact boundary.

Two majors are supported. `1.0.0` is the frozen cosine contract and is
immutable; `2.0.0` is the diagonal-representation contract (D047). An unknown
major fails closed rather than falling back to the newest schema — a consumer
that silently validated a future payload against today's rules would report
success for something it does not understand.
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files
from typing import Any

from jsonschema import Draft202012Validator

SCHEMA_FILES = {
    1: "showcase-1.0.0.schema.json",
    2: "showcase-2.0.0.schema.json",
}
"""Major version -> schema resource. Majors are the compatibility unit."""

DEFAULT_MAJOR = 1
"""The major assumed when an artifact carries no `schema_version`, so v1
callers keep their existing behaviour exactly."""


def parse_major(schema_version: str) -> int:
    """Major component of a `MAJOR.MINOR.PATCH` string.

    Raises rather than guessing: an unparseable version is not a version.
    """
    head = str(schema_version).split(".", 1)[0]
    try:
        return int(head)
    except ValueError as error:
        raise ValueError(f"unparseable schema_version {schema_version!r}") from error


def artifact_major(artifact: Any) -> int:
    """The major an artifact declares, or the default when it declares none.

    Only the manifest and the v2 representation artifact carry
    `schema_version`; profiles, catalogues and index files inherit their
    dataset's major, which the caller supplies explicitly.
    """
    if isinstance(artifact, dict) and "schema_version" in artifact:
        return parse_major(artifact["schema_version"])
    return DEFAULT_MAJOR


@lru_cache(maxsize=len(SCHEMA_FILES))
def showcase_schema(major: int = DEFAULT_MAJOR) -> dict:
    resource = SCHEMA_FILES.get(major)
    if resource is None:
        raise ValueError(
            f"unsupported showcase schema major {major}; known majors: "
            f"{sorted(SCHEMA_FILES)}"
        )
    schema_path = files("scoutlens.showcase.schemas").joinpath(resource)
    return json.loads(schema_path.read_text(encoding="utf-8"))


@lru_cache(maxsize=len(SCHEMA_FILES))
def showcase_validator(major: int = DEFAULT_MAJOR) -> Draft202012Validator:
    schema = showcase_schema(major)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def validate_schema(artifact: Any, *, label: str, major: int = DEFAULT_MAJOR) -> None:
    errors = sorted(
        showcase_validator(major).iter_errors(artifact),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        raise ValueError(f"{label}: JSON Schema violation at {location}: {error.message}")
