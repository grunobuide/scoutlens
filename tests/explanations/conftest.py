"""Bundles and outputs built from the published artifacts, not from hand-written JSON.

Stored fixtures would go stale the moment the showcase repins, and a stale
fixture that still passes is worse than no fixture: it reports that a contract
holds against data nobody publishes any more. So the canonical valid output is
*derived* from the real bundle, and every adversarial case is a named mutation
of it.

That also makes each adversarial fixture a one-line statement of the thing it
breaks, which is what a reader needs when a rule fires in an eval six months
from now.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from scoutlens.explanations import BundleOptions, build_bundle
from scoutlens.explanations.policy import CONTRACT, OUTPUT_SCHEMA_VERSION

REPO_ROOT = Path(__file__).resolve().parents[2]
V2_DIR = REPO_ROOT / "public" / "showcase" / "v2"
V1_DIR = REPO_ROOT / "public" / "showcase" / "v1"
V2_PROFILE = V2_DIR / "players" / "wy-8287-c-795.json"
V1_PROFILE = V1_DIR / "players" / "wy-10131-c-364.json"

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
#: So an absent v1 is a genuine absence with no remedy, not a dropped step, and
#: making it an error would turn this guard into a permanently red CI job.
#: The cost is real and recorded rather than hidden: the audit-baseline cases —
#: `tests/explanations/test_audit_baseline.py` and the two v1 cases in the eval
#: corpus — do not run in CI and cannot until a v1 payload is obtainable there.
requires_v1 = pytest.mark.skipif(
    not V1_PROFILE.exists(),
    reason="requires a public/showcase/v1 payload, which the v2 pin cannot hydrate",
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


def rows_with_status(bundle: dict[str, Any], status: str) -> list[dict[str, Any]]:
    return [row for row in bundle["evidence"] if row["status"] == status]


def first_weighted_feature(bundle: dict[str, Any]) -> dict[str, Any]:
    for row in bundle["evidence"]:
        if row["status"] == "weighted" and row["kind"] == "feature_contribution":
            return row
    raise AssertionError("the published profile has no weighted feature evidence")


def neighbour_evidence(bundle: dict[str, Any]) -> dict[str, Any]:
    for row in bundle["evidence"]:
        if row["subject"].startswith("neighbor:") and row["status"] == "weighted":
            return row
    raise AssertionError("the published profile has no neighbour evidence")


def valid_output(bundle: dict[str, Any]) -> dict[str, Any]:
    """The canonical accepted explanation for a bundle.

    Deliberately minimal and deliberately complete: one claim per surface the
    contract defines, every number tied to the field it came from, and the full
    mandatory caveat set because it cites neighbour evidence.
    """
    feature = first_weighted_feature(bundle)
    neighbour = neighbour_evidence(bundle)
    retrieval = bundle["retrieval"]
    provenance = bundle["provenance"]

    claims = [
        {
            "surface": "provenance",
            "text": (
                f"These numbers come from {provenance['ranking_method']}"
                + (
                    f" ({provenance['representation_id']})."
                    if provenance.get("representation_id")
                    else "."
                )
            ),
            "evidence_ids": [feature["evidence_id"]],
        },
        {
            "surface": "retrieval_outcome",
            "text": (
                f"The player's own second-half profile was ranked {retrieval['self_rank']} "
                f"of {retrieval['candidate_count']} candidates."
            ),
            "evidence_ids": [feature["evidence_id"]],
            "values": [
                {"field": "self_rank", "value": retrieval["self_rank"]},
                {"field": "candidate_count", "value": retrieval["candidate_count"]},
            ],
        },
        {
            "surface": "feature_contribution",
            "text": f"{feature['feature_id']} contributed to that alignment.",
            "evidence_ids": [feature["evidence_id"]],
            "values": [
                {
                    "field": "weighted_contribution",
                    "value": feature["weighted_contribution"],
                    "evidence_id": feature["evidence_id"],
                }
            ],
        },
        {
            "surface": "similarity",
            "text": "A neighbouring profile sits close to this one under the same representation.",
            "evidence_ids": [neighbour["evidence_id"]],
        },
        {
            "surface": "limitation",
            "text": "Same-season club continuity can make this retrieval easier than it looks.",
            "evidence_ids": [feature["evidence_id"]],
        },
    ]

    return {
        "contract": CONTRACT,
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "profile_key": bundle["profile_key"],
        "bundle_digest": bundle["bundle_digest"],
        "claims": claims,
        "caveat_codes": sorted(caveat["code"] for caveat in bundle["caveats"]),
    }
