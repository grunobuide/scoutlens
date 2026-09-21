"""Bundles and outputs built from the published artifacts, not from hand-written JSON.

Stored fixtures would go stale the moment the showcase repins, and a stale
fixture that still passes is worse than no fixture: it reports that a contract
holds against data nobody publishes any more. So the canonical valid output is
*derived* from the real bundle, and every adversarial case is a named mutation
of it.

That also makes each adversarial fixture a one-line statement of the thing it
breaks, which is what a reader needs when a rule fires in an eval six months
from now.

**The builders themselves live in the package**, in
`scoutlens.explanations.evals.responses`. They moved there when `jtt.6.3` made
the corpus a deliverable: a project user evaluating their own adapter needs the
same reference output this repository tests against, and it is not available to
them from a test directory. Re-exported here so the tests that predate the move
read unchanged, and so there is exactly one definition of "the canonical
accepted explanation" to keep correct.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scoutlens.explanations import BundleOptions, build_bundle
from scoutlens.explanations.evals.responses import (
    first_weighted_feature,
    neighbour_evidence,
    reference_output,
    rows_with_status,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
V2_DIR = REPO_ROOT / "public" / "showcase" / "v2"
V1_DIR = REPO_ROOT / "public" / "showcase" / "v1"
V2_PROFILE = V2_DIR / "players" / "wy-8287-c-795.json"
V1_PROFILE = V1_DIR / "players" / "wy-10131-c-364.json"

#: The contract is exercised against published artifacts. A clone that has not
#: hydrated them skips rather than silently testing nothing.
requires_showcase = pytest.mark.skipif(
    not V2_PROFILE.exists() or not (V2_DIR / "representation.json").exists(),
    reason="requires a hydrated public/showcase/v2 (python -m scoutlens.showcase.payload hydrate)",
)
requires_v1 = pytest.mark.skipif(
    not V1_PROFILE.exists(),
    reason="requires a hydrated public/showcase/v1 for the audit-baseline path",
)


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def v2_profile() -> dict[str, Any]:
    return _read(V2_PROFILE)


@pytest.fixture(scope="session")
def representation() -> dict[str, Any]:
    return _read(V2_DIR / "representation.json")


@pytest.fixture(scope="session")
def v1_profile() -> dict[str, Any]:
    return _read(V1_PROFILE)


@pytest.fixture()
def bundle(v2_profile: dict[str, Any], representation: dict[str, Any]) -> dict[str, Any]:
    return build_bundle(v2_profile, representation)


@pytest.fixture()
def audit_bundle(v1_profile: dict[str, Any]) -> dict[str, Any]:
    return build_bundle(v1_profile, options=BundleOptions(audit_baseline=True))


#: The canonical accepted explanation, under the name the older tests use.
valid_output = reference_output

__all__ = [
    "first_weighted_feature",
    "neighbour_evidence",
    "reference_output",
    "requires_showcase",
    "requires_v1",
    "rows_with_status",
    "valid_output",
]
