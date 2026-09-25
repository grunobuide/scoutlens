"""The portfolio documents, held to the identity boundary rather than to a word.

`scoutlens-vif.5`. The published name is Yumusarái Labs; every technical
identifier stays `scoutlens`. A rename applied to prose is the easiest place in
this project to get that wrong in either direction — a stale wordmark on one
side, a "finished" rename that broke a working link on the other.

So the assertions here come in pairs. The brand must be present where a reader
looks for it, and absent from every identifier. The one file that may not be
renamed is named explicitly, because a future tidy-up would look correct.

Numbers, caveats and limitations are not this file's business:
`test_case_study.py` owns them and stays read-only to this bead. What is
asserted here is that a convergence pass did not quietly move any of them.
"""

from __future__ import annotations

import json
import re

import pytest

from scoutlens.explanations.artifacts import DEFAULT_SHOWCASE_ROOT
from scoutlens.release.manifest import REPO_ROOT

BRAND = "Yumusarái Labs"
ASCII_SLUG = "yumusarai-labs"
RETIRED = "ScoutLens"

README = REPO_ROOT / "README.md"
CASE_STUDY = REPO_ROOT / "docs" / "case-study.md"
MEDIA_NOTE = REPO_ROOT / "docs" / "media" / "README.md"
CONTRACT = REPO_ROOT / "docs" / "public-identity-contract.md"

#: The one file whose name carries the old brand and must keep it. It is a
#: frozen historical document; renaming it breaks the link and rewrites the
#: identity of a record that was written under that name.
FROZEN_BRIEF = "docs/00_ScoutLens_Project_Brief_v1.md"


def _prose(text: str) -> str:
    """Flatten to a sentence-matchable string.

    Emphasis markers are removed before matching: whether a document writes
    `**one** evaluator` or `one evaluator` is a typographic choice, and an
    assertion about what a document *says* should not break when someone
    bolds half the phrase.
    """
    return " ".join(text.split()).replace("**", "").replace("*", "").lower()


@pytest.fixture(scope="module")
def readme() -> str:
    return README.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def case_study() -> str:
    return CASE_STUDY.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def media_note() -> str:
    return MEDIA_NOTE.read_text(encoding="utf-8")


# --- the brand is where a reader looks -----------------------------------


def test_both_documents_lead_with_the_published_name(readme: str, case_study: str) -> None:
    assert readme.splitlines()[0].startswith(f"# {BRAND}")
    assert case_study.splitlines()[0].startswith(f"# {BRAND}")


def test_the_accent_is_not_quietly_dropped(readme: str, case_study: str) -> None:
    """`Yumusarai Labs` is the ASCII fallback for places that cannot carry an
    accent. A Markdown file is not such a place."""
    for name, text in (("README", readme), ("case study", case_study)):
        assert "Yumusarai Labs" not in text, f"{name} uses the ASCII fallback in prose"


# --- the technical names stay, and the documents say why -----------------


def test_both_documents_explain_why_the_technical_name_did_not_change(
    readme: str, case_study: str
) -> None:
    """AC1's explanation, asserted by what it has to establish, not by phrasing.

    A reader who sees `scoutlens` in a command after reading `Yumusarái Labs`
    at the top needs to know that is deliberate. Both documents must say so and
    both must point at the contract that freezes it.
    """
    for name, text in (("README", readme), ("case study", case_study)):
        flat = " ".join(text.split())
        assert "public-identity-contract.md" in flat, f"{name} does not link the contract"
        assert "D058" in flat, f"{name} does not cite the decision"
        assert "`scoutlens`" in flat, f"{name} never names the technical identifier"


def test_the_frozen_brief_keeps_its_name(readme: str) -> None:
    """The rename that would look like tidying and would break a link."""
    assert FROZEN_BRIEF in readme
    assert (REPO_ROOT / FROZEN_BRIEF).is_file()


def test_no_document_invents_a_new_namespace(readme: str, case_study: str) -> None:
    """The ASCII slug is a search/text convention, not a package or a domain."""
    for name, text in (("README", readme), ("case study", case_study)):
        assert f"{ASCII_SLUG}.com" not in text
        assert f"github.com/grunobuide/{ASCII_SLUG}" not in text
        assert f"import {ASCII_SLUG}" not in text


def test_every_technical_identifier_survived_the_pass(readme: str) -> None:
    """Each of these would break something real if the rename had reached it."""
    for identifier in (
        "grunobuide.github.io/scoutlens",
        "github.com/grunobuide/scoutlens",
        "scoutlens.showcase",
        "python -m scoutlens.showcase.payload hydrate",
        "SCOUTLENS_",
    ):
        assert identifier in readme, f"{identifier} is missing from the README"


def test_the_case_study_reproduction_commands_still_run_the_package(
    case_study: str,
) -> None:
    for command in (
        "python -m scoutlens.showcase.payload hydrate",
        "python -m scoutlens.evaluation.run_report",
        "python -m scoutlens.explanations.cli explain",
    ):
        assert command in case_study


# --- the convergence pass changed nothing it should not ------------------


def test_the_licence_statement_still_describes_the_code(readme: str) -> None:
    """`MIT` covers the code, and the code is still named `scoutlens`.

    The tempting edit here was `**Yumusarái Labs code:** MIT`, which would say
    the licence covers a brand. It covers this repository.
    """
    assert "**This repository's code:** [MIT](LICENSE)" in readme
    assert f"**{BRAND} code:**" not in readme
    assert "CC BY 4.0" in readme
    assert "StatsBomb Open Data" in readme


def test_the_unevaluated_model_disclaimer_is_intact(case_study: str) -> None:
    flat = _prose(case_study)
    assert "no demonstration model has been evaluated" in flat
    assert "not_run" in flat
    assert "no claim about any model" in flat


def test_the_n_of_one_comprehension_limit_is_intact(case_study: str) -> None:
    flat = _prose(case_study)
    assert "one evaluator" in flat
    assert "2:53" in flat
    assert "no fresh independent post-fix validation" in flat


def test_the_confound_is_still_the_headline_limitation(case_study: str) -> None:
    flat = _prose(case_study)
    assert "same-season club continuity is a stronger shortcut" in flat
    assert "0.5893" in flat


def test_the_missing_video_is_still_reported_as_missing(
    case_study: str, media_note: str
) -> None:
    """AC4. A convergence pass may not turn stills into a video by omission."""
    assert "no demo video" in _prose(case_study)
    flat_note = " ".join(media_note.split())
    assert "There is no demo video or GIF" in flat_note
    assert "scoutlens-jtt.20" in flat_note or "jtt.20" in flat_note


# --- the media, and where it came from -----------------------------------


MEDIA = (
    "lab-desktop.png",
    "lab-evidence-desktop.png",
    "lab-retrieval-desktop.png",
    "science-desktop.png",
    "lab-mobile.png",
)


def test_every_image_has_alt_text_in_the_media_note(media_note: str) -> None:
    for image in MEDIA:
        assert (MEDIA_NOTE.parent / image).is_file(), f"{image} is missing"
        assert f"`{image}`" in media_note, f"{image} has no alt-text entry"


def test_the_media_note_records_its_provenance(media_note: str) -> None:
    """AC3. A screenshot with no recorded source is not evidence of anything.

    Commit, URL, capture command and digests, so a reader can tell which
    version of the site an image shows — and so a local build cannot later be
    passed off as production.
    """
    flat = " ".join(media_note.split())
    assert "capture-media.mjs" in flat
    assert "grunobuide.github.io/scoutlens" in flat
    assert "wy-8287-c-795" in flat, "the named profile makes the capture reproducible"
    assert re.search(r"\b[0-9a-f]{64}\b", flat), "no sha256 digest is recorded"
    assert re.search(r"\b[0-9a-f]{7,40}\b", flat), "no source commit is recorded"


def test_the_alt_text_describes_the_current_wordmark(media_note: str) -> None:
    """The failure this bead exists to prevent: media showing an obsolete brand.

    Alt text is the only machine-checkable description of what an image shows,
    so it is where a stale screenshot becomes detectable.
    """
    assert BRAND in media_note
    flat = " ".join(media_note.split())
    # The retired name may appear only where the note explains the exception.
    for sentence in re.split(r"(?<=[.!?]) ", flat):
        if RETIRED in sentence:
            assert "provenance" in sentence.lower() or "artifact" in sentence.lower(), (
                f"the media note mentions {RETIRED!r} outside the documented "
                f"exception: {sentence!r}"
            )


# --- nothing here is a second source for a number ------------------------


def test_this_file_does_not_become_a_second_numbers_test() -> None:
    """AC5. `test_case_study.py` owns the figures; this file must not fork it.

    Two files asserting the same metrics drift apart, and the project's own
    rule is that there is one source for a published number.
    """
    source = (REPO_ROOT / "tests" / "release" / "test_public_identity_docs.py").read_text(
        encoding="utf-8"
    )
    decimals = set(re.findall(r"\b0\.\d{4}\b", source))
    assert decimals <= {"0.5893"}, (
        f"this file asserts metric values it does not own: {sorted(decimals)}. "
        "Figures belong to test_case_study.py, which checks them against the artifact."
    )


def test_the_published_artifact_identity_is_unchanged() -> None:
    """A documentation pass may not move the data the documents describe."""
    manifest = json.loads(
        (DEFAULT_SHOWCASE_ROOT / "v2" / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["dataset_version"] == "wyscout-2017-18-v2-332766e3a822"
    assert manifest["representation_id"] == "rep-f018e6041ccbad10"
    assert manifest["contract"] == "scoutlens.showcase"
    # The occurrence the site shows and this rename may not touch.
    assert RETIRED in manifest["source"]["redistribution_note"]


def test_the_contract_this_bead_follows_is_present() -> None:
    contract = CONTRACT.read_text(encoding="utf-8")
    assert BRAND in contract
    assert "do-not-rename" in contract.lower()
