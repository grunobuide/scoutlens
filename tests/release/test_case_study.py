"""The case study may not disagree with the artifact it describes.

`jtt.7.3` AC2: *no copied metric disagrees with artifacts and every claim follows
the frozen claims matrix.* A prose document is the easiest place in a project for
a number to go stale, because nothing executes it.

So every number the case study states is matched against
`research-summary.json` — the artifact the site itself renders. A figure that
drifts fails the build rather than quietly misinforming a reader who has no way
to check it.
"""

from __future__ import annotations

import re

import pytest

from scoutlens.explanations.artifacts import DEFAULT_SHOWCASE_ROOT
from scoutlens.release.claims import build_matrix
from scoutlens.release.manifest import REPO_ROOT

CASE_STUDY = REPO_ROOT / "docs" / "case-study.md"
README = REPO_ROOT / "README.md"

requires_summary = pytest.mark.skipif(
    not (DEFAULT_SHOWCASE_ROOT / "v2" / "research-summary.json").is_file(),
    reason="requires the published research summary",
)


@pytest.fixture(scope="module")
def case_study() -> str:
    if not CASE_STUDY.is_file():
        pytest.skip("case study not present")
    return CASE_STUDY.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def prose(case_study: str) -> str:
    """Line wrapping flattened, so an assertion does not depend on where it wrapped."""
    return " ".join(case_study.split()).lower()


@pytest.fixture(scope="module")
def published_values() -> set[str]:
    """Every metric value the artifact publishes, at the precisions a reader sees.

    A document quotes `0.2539`, not `0.2539333127027185`. Both the rounded and
    the full form count as agreeing with the artifact; anything else does not.
    """
    import json

    summary = json.loads(
        (DEFAULT_SHOWCASE_ROOT / "v2" / "research-summary.json").read_text(encoding="utf-8")
    )
    values: set[str] = set()
    for experiment in summary.get("experiments", ()):
        for metric in experiment.get("metrics", ()):
            value = metric.get("value")
            if value is None:
                continue
            values.add(str(value))
            if isinstance(value, float):
                for places in (2, 3, 4, 5):
                    values.add(f"{value:.{places}f}")
                    values.add(f"{value:.{places}f}".rstrip("0"))
            if isinstance(value, int):
                values.add(f"{value:,}")
    return values


#: Numbers that are structural rather than measured, so they have no metric to
#: match. Each is checked elsewhere or is a property of the design.
STRUCTURAL = {
    "1", "2", "3", "4", "5", "6", "7", "8", "9", "10",
    "0.95",     # the preregistered live threshold (thresholds.py)
    "64",       # eval corpus size (corpus tests)
    "32", "28", # feature counts, stated in the artifact's own copy
    "450",      # minutes floor per period
    "2.0.0", "1.0.0",
    "2017", "18", "2015", "16",
    "2:53",     # the n=1 comprehension run, from D056
    "1,257", "1,061", "26", "19", "16", "12", "15", "2",
}

NUMBER = re.compile(r"\b\d+(?:[.,]\d+)*\b")


@requires_summary
def test_every_decimal_figure_matches_the_artifact(
    case_study: str, published_values: set[str]
) -> None:
    """A decimal in this document is a metric, and must be one the artifact has."""
    tables = [line for line in case_study.splitlines() if line.strip().startswith("|")]
    decimals = {
        token
        for line in tables
        for token in NUMBER.findall(line)
        if "." in token and token not in STRUCTURAL
    }
    assert decimals, "the case study states no decimal metrics; the tables are gone"

    unknown = sorted(token for token in decimals if token not in published_values)
    assert not unknown, (
        f"these figures are not in research-summary.json: {unknown}. "
        "Either the artifact moved or the case study invented a number."
    )


@requires_summary
def test_the_headline_numbers_are_present(case_study: str) -> None:
    """The three numbers the argument rests on, including the awkward one."""
    matrix = build_matrix()
    by_id = {row.experiment_id: row for row in matrix.rows}
    assert {"wyscout_global_gate2", "wyscout_role_team_minutes"} <= set(by_id)

    for figure in ("0.0256", "0.2539", "0.5893"):
        assert figure in case_study, f"{figure} is missing from the case study"


def test_the_confound_is_not_buried(prose: str) -> None:
    """The team baseline beats the fingerprint, and the document has to say so.

    This is the assertion most worth having. A case study that quietly dropped
    its most damaging number would still pass every other check here.
    """
    assert "same-season club continuity is a stronger shortcut" in prose
    assert "beats the fingerprint" in prose


def test_the_nulls_are_published(prose: str) -> None:
    assert "shrinkage" in prose
    assert "null" in prose
    assert "neural" in prose


def test_the_unevaluated_model_is_stated(prose: str) -> None:
    assert "no demonstration model has been evaluated" in prose
    assert "not_run" in prose
    assert "no claim about any model" in prose


def test_the_n_of_one_comprehension_is_disclosed(prose: str) -> None:
    """`D056`'s handoff requirement, verbatim in substance."""
    assert "one evaluator" in prose or "n=1" in prose
    assert "2:53" in prose
    assert "four findings" in prose
    assert "no fresh independent post-fix validation" in prose
    assert "not** claimed as validated" in prose or "not claimed as validated" in prose


def test_the_forbidden_claims_are_still_forbidden(prose: str) -> None:
    """The boundary the whole project is built around."""
    for phrase in ("not a quality score", "not a style proof", "not a recruitment"):
        assert phrase in prose, f"the case study never says {phrase!r}"


def test_the_external_reader_checklist_answers_all_five(prose: str) -> None:
    """AC6: answerable without inference."""
    for question in (
        "what is claimed?",
        "what is the evidence?",
        "what is the biggest limitation?",
        "what is the engineering contribution?",
        "what is the ai's role?",
    ):
        assert question in prose, f"the checklist does not answer {question!r}"


def test_both_reproduction_paths_are_distinguished(prose: str) -> None:
    """AC5: raw-data research vs raw-data-free showcase build."""
    assert "no raw data" in prose
    assert "needs the raw provider data" in prose


def test_the_case_study_links_what_ac1_requires(case_study: str) -> None:
    for target in (
        "grunobuide.github.io/scoutlens",
        "github.com/grunobuide/scoutlens",
        "architecture.md",
        "decisions-log.md",
        "DATA_LICENSES.md",
    ):
        assert target in case_study, f"the case study does not link {target}"


# --- the README, corrected by this bead ----------------------------------


@pytest.fixture(scope="module")
def readme() -> str:
    return README.read_text(encoding="utf-8")


def test_the_readme_links_the_live_app(readme: str) -> None:
    assert "grunobuide.github.io/scoutlens" in readme
    assert "docs/case-study.md" in readme


def test_the_readme_no_longer_calls_delivered_things_planned(readme: str) -> None:
    """It described the Lab, uncertainty and the AI toolkit as not delivered.

    All three shipped. A README that understates what exists is its own kind of
    inaccuracy, and it is the first thing a reader sees.
    """
    flat = " ".join(readme.split())
    assert "planned interactive" not in flat
    assert "remain planned, not delivered" not in flat
    assert "will consume a" not in flat


def test_the_readme_does_not_imply_ai_in_the_public_ui(readme: str) -> None:
    """`D056`'s explicit requirement.

    The architecture diagram carried `AI -. planned .-> UI`, which tells a reader
    that AI explanation is coming to the deployed site. It is not, and nothing
    plans it.
    """
    flat = " ".join(readme.split())
    assert "AI -. planned .-> UI" not in flat
    assert "no AI in the public UI" in flat or "no ai in the public ui" in flat.lower()
