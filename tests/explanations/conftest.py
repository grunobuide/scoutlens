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
import os
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

#: A committed v1 profile, so the audit-baseline path is testable without one
#: (`scoutlens-jtt.18`).
#:
#: `web/e2e/fixtures/lab-max-content/` is a delegated fixture pack built by
#: `web/scripts/fixture-pack.mjs` and verified against its own checksum
#: manifest. It is schema-valid v1, it is committed, and a clean clone has it —
#: which is the property the hydrated payload lacks and cannot regain.
V1_FIXTURE_PROFILE = (
    REPO_ROOT / "web" / "e2e" / "fixtures" / "lab-max-content" / "players" / "wy-900001-c-901.json"
)


#: Force the fixture even on a machine that still has a hydrated v1 tree.
#:
#: This exists because of a specific, recorded failure. The eval corpus was
#: first written on a machine with a leftover v1 payload from before the repin;
#: every test passed there and failed the moment CI hydrated v2 only. A
#: developer with that leftover cannot otherwise reproduce what CI sees, which
#: is the condition that produced the bug in the first place.
V1_SOURCE_OVERRIDE = os.environ.get("SCOUTLENS_V1_SOURCE", "").strip()


def _v1_source() -> Path | None:
    """A hydrated v1 payload if one exists, else the committed fixture.

    Real data wins when it is present — it is the better test. The fixture is
    what makes the path testable at all in CI, where no v1 payload is
    obtainable (`scoutlens-jtt.18`).
    """
    if V1_SOURCE_OVERRIDE == "fixture":
        return V1_FIXTURE_PROFILE if V1_FIXTURE_PROFILE.exists() else None
    if V1_PROFILE.exists():
        return V1_PROFILE
    if V1_FIXTURE_PROFILE.exists():
        return V1_FIXTURE_PROFILE
    return None

HYDRATE = "uv run --frozen python -m scoutlens.showcase.payload hydrate"

#: Set to "1" where a missing payload is an outage rather than a local choice.
#:
#: The guards below skip on a developer's un-hydrated clone, which is a kindness
#: and the right default. In CI it is a trap: `public/showcase/*/players/` is
#: gitignored, so for as long as the `pytest` job did not hydrate, every test in
#: this directory skipped and a green check meant nothing about the explanation
#: contract — 54 tests on `main`, and 384 once `scoutlens-jtt.6.3` landed. The
#: suites reported passing; nobody was told they had not run.
#:
#: `scoutlens-iex.10` added the hydrate step. This variable is the part that
#: keeps it added: a skip guard that also protects a CI outage will hide the
#: next one exactly as silently as it hid this one.
REQUIRE_SHOWCASE = os.environ.get("SCOUTLENS_REQUIRE_SHOWCASE", "").strip() == "1"


def _guard(available: bool, *, what: str, reason: str) -> pytest.MarkDecorator:
    """Skip when the payload is absent — unless absence is an outage.

    Raises at collection rather than failing one test: the payload is missing
    for the whole directory or for none of it, and one loud error naming the
    remedy reads better than several hundred identical failures.
    """
    if not available and REQUIRE_SHOWCASE:
        raise RuntimeError(
            f"SCOUTLENS_REQUIRE_SHOWCASE=1 and {what} is absent, so these tests would "
            f"silently skip. Hydrate the payload before pytest:\n    {HYDRATE}\n"
            "If this fired in CI, the hydrate step was dropped from the job - see "
            "scoutlens-iex.10."
        )
    return pytest.mark.skipif(not available, reason=reason)


#: The contract is exercised against published artifacts. A clone that has not
#: hydrated them skips rather than silently testing nothing.
requires_showcase = _guard(
    V2_PROFILE.exists() and (V2_DIR / "representation.json").exists(),
    what="a hydrated public/showcase/v2",
    reason=f"requires a hydrated public/showcase/v2 ({HYDRATE})",
)
#: v1 is deliberately *not* covered by `REQUIRE_SHOWCASE`.
#:
#: There is one payload pin and `scoutlens-jtt.17` repinned it to v2, so
#: `python -m scoutlens.showcase.payload hydrate` produces v2 and only v2 —
#: verified by running it against an emptied checkout. A v1 payload in a working
#: tree is a leftover from before that repin, and CI has no way to obtain one.
#:
#: So an absent v1 PAYLOAD is a genuine absence with no remedy. What changed in
#: `scoutlens-jtt.18` is that the payload is no longer the only source: the
#: delegated fixture pack ships a committed, schema-valid v1 profile, so the
#: audit-baseline path is exercised in CI after all. A hydrated v1 tree still
#: wins when one exists, because real data is the better test when it is there.
#:
#: What this does NOT do is put the fixture into the eval corpus. The recorded
#: report must describe what the pin produces, and a frontend fixture is not
#: that — see `D060`.
requires_v1 = pytest.mark.skipif(
    _v1_source() is None,
    reason="requires a v1 profile: either a hydrated public/showcase/v1 or the committed fixture",
)
#: For the few tests the fixture cannot serve: the CLI and the eval corpus
#: resolve real profiles *by key* from `public/showcase/v1`, so only a hydrated
#: v1 tree can run them, and CI never has one.
#:
#: `scoutlens-jtt.18` widened `requires_v1` to accept the fixture and left these
#: on it. They then ran in CI against a tree that is not there, and `main` went
#: red on both Python versions; locally they passed, because this machine still
#: has the leftover payload - the exact trap the override above exists for.
#: `SCOUTLENS_V1_SOURCE=fixture` therefore skips these too, so a developer can
#: reproduce what CI sees.
requires_v1_payload = pytest.mark.skipif(
    V1_SOURCE_OVERRIDE == "fixture"
    or not all((V1_DIR / "players" / f"{key}.json").exists() for key in ("wy-10131-c-364", "wy-8287-c-795")),
    reason="requires a hydrated public/showcase/v1; this path resolves profiles by key, so the fixture cannot stand in",
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
    source = _v1_source()
    assert source is not None, "requires_v1 should have skipped this test"
    return _read(source)


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
    "requires_v1_payload",
    "rows_with_status",
    "valid_output",
]
