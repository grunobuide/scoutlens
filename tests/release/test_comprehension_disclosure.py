"""Three handoff documents say what the one comprehension run did and did not show.

`scoutlens-9a3.24`. `D056` let the communication gate close on **one** human
review, on the condition that the case study and the release notes disclose it:
n=1, the failed initial run, the corrections, and the absence of a fresh
independent retest. Run 1 was a block at 2:53 against a 90-second design
target, and none of its four findings is measured as fixed.

The closure audit found two of these documents calling that *validated* in the
same sentence that reported the block, and none of them naming the four
findings. The earlier test only checked that phrases were present, so a
sentence could carry the right words and still claim the wrong thing. This
checks both directions, per document: the claim `D056` forbids is absent, and
every part of the disclosure it requires is present.
"""

from __future__ import annotations

import re

import pytest

from scoutlens.release.manifest import REPO_ROOT

DOCUMENTS = ("docs/case-study.md", "CHANGELOG.md", "docs/release-candidate-v1.md")

#: Wording that would report a comprehension result `D056` says was not obtained.
FORBIDDEN = {
    "a validation claim": r"validated with",
    "comprehension reported as validated": r"comprehension (?:was|is|has been) (?:validated|improved)",
    "the target reported as met": r"(?:met|meets|achieved|achieves|reached|reaches|passed|passes) (?:the )?90-second",
    "the target reported as met, passively": (
        r"90-second (?:first-understanding )?(?:target|goal)[^.]{0,80}?\b(?:was|is|has been) (?:met|achieved|reached)"
    ),
    "a reading time claimed": r"(?:within|under|in) 90 seconds",
}

#: Each part of the disclosure `D056` requires, as a pattern over flattened text.
REQUIRED = {
    "one evaluator, tested not validated": r"tested with one evaluator",
    "run 1 was a block at 2:53": r"block at 2:53",
    "90 seconds is a design target not met": r"90-second[^.]{0,120}design target[^.]{0,40}not claimed as met",
    "no fresh independent retest": r"no fresh independent retest",
    "comprehension not claimed": r"not claimed as validated or improved",
    "the decision cited": r"\bd056\b",
}

#: Run 1's four findings (`docs/public-understanding-check.md` §6), each by its
#: own words and the bead that remediated it. The bead must follow its finding
#: closely, so a finding cannot be satisfied by a bead cited somewhere else.
FINDINGS = {
    "AI role (Q6)": (r"ai role", "scoutlens-9a3.11"),
    "recall of the unsupported claims (Q4)": (r"recall of the unsupported claims", "scoutlens-9a3.12"),
    "team-continuity confound (Q3)": (r"team-continuity confound", "scoutlens-9a3.13"),
    "two-period framing (Q2)": (r"two-period framing", "scoutlens-9a3.14"),
}

#: How far a finding's bead may sit from its words: one list item or table row.
NEAR = 250


def _flatten(text: str) -> str:
    """Wrapping, emphasis and code marks removed, so a phrase is found wherever it broke."""
    return " ".join(text.replace("*", "").replace("`", "").split()).lower()


@pytest.fixture(scope="module", params=DOCUMENTS)
def document(request: pytest.FixtureRequest) -> tuple[str, str]:
    path = REPO_ROOT / request.param
    if not path.is_file():
        pytest.skip(f"{request.param} not present")
    return request.param, _flatten(path.read_text(encoding="utf-8"))


def test_no_document_claims_a_comprehension_result(document: tuple[str, str]) -> None:
    """`D056`: not a successful comprehension study, and not a retrospective pass."""
    name, text = document
    found = {
        label: match.group(0)
        for label, pattern in FORBIDDEN.items()
        if (match := re.search(pattern, text))
    }
    assert not found, f"{name} claims what run 1 did not show: {found}"


def test_every_document_discloses_the_limited_evidence(document: tuple[str, str]) -> None:
    name, text = document
    missing = [label for label, pattern in REQUIRED.items() if not re.search(pattern, text)]
    assert not missing, f"{name} does not state: {missing}"


def test_every_document_names_the_four_findings_and_their_beads(document: tuple[str, str]) -> None:
    """The `scoutlens-9a3.7` handoff required the corrections to be named, not counted."""
    name, text = document
    missing = [
        label
        for label, (words, bead) in FINDINGS.items()
        if not re.search(rf"{words}.{{0,{NEAR}}}?{re.escape(bead)}", text)
    ]
    assert not missing, f"{name} does not name, with its remediating bead: {missing}"
