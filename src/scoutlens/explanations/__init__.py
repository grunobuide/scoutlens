"""Provider-neutral grounded-explanation contract for ScoutLens profiles.

This package defines what a model may be told and what it may say back. It
contains no model, no adapter and no network call: `scoutlens-jtt.6.1` is the
contract, and the adapter that satisfies it arrives separately.

The pieces:

* `policy` - the evidence taxonomy, claim surfaces, mandatory caveats and
  forbidden intents. Vocabulary only.
* `bundle` - builds the deterministic evidence bundle from an already-validated
  showcase profile. Derives, never authors.
* `schema` - JSON Schema for bundle and output, fail-closed on unknown versions.
* `validator` - decides whether an output is supported by its bundle. Offline
  and deterministic, so the same function judges a live adapter and a fixture.
* `prompt` - the versioned prompt contract, written so that every instruction in
  it corresponds to a rule the validator enforces.

Not to be confused with `scoutlens.showcase.evidence_bundle`, which packs the
bootstrap run outputs as an offline audit archive. That is evidence *about* the
intervals; this is evidence *given to* a model.
"""

from __future__ import annotations

from scoutlens.explanations.bundle import BundleError, BundleOptions, build_bundle, bundle_digest
from scoutlens.explanations.policy import (
    BUNDLE_SCHEMA_VERSION,
    CONTRACT,
    MANDATORY_NEIGHBOUR_CAVEATS,
    OUTPUT_SCHEMA_VERSION,
    ClaimSurface,
    EvidenceStatus,
    ForbiddenIntent,
)
from scoutlens.explanations.schema import validate_bundle_schema, validate_output_schema
from scoutlens.explanations.validator import (
    Rejection,
    ValidationResult,
    rejection_rules,
    validate_output,
)

__all__ = [
    "BUNDLE_SCHEMA_VERSION",
    "CONTRACT",
    "MANDATORY_NEIGHBOUR_CAVEATS",
    "OUTPUT_SCHEMA_VERSION",
    "BundleError",
    "BundleOptions",
    "ClaimSurface",
    "EvidenceStatus",
    "ForbiddenIntent",
    "Rejection",
    "ValidationResult",
    "build_bundle",
    "bundle_digest",
    "rejection_rules",
    "validate_bundle_schema",
    "validate_output",
    "validate_output_schema",
]
