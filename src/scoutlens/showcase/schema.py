"""Load and apply the formal JSON Schema for the public artifact boundary."""

from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files
from typing import Any

from jsonschema import Draft202012Validator


@lru_cache(maxsize=1)
def showcase_schema() -> dict:
    schema_path = files("scoutlens.showcase.schemas").joinpath("showcase-1.0.0.schema.json")
    return json.loads(schema_path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def showcase_validator() -> Draft202012Validator:
    schema = showcase_schema()
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def validate_schema(artifact: Any, *, label: str) -> None:
    errors = sorted(showcase_validator().iter_errors(artifact), key=lambda error: list(error.absolute_path))
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        raise ValueError(f"{label}: JSON Schema violation at {location}: {error.message}")

