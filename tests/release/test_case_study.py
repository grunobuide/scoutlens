"""The case study may not disagree with the artifact it describes.

`jtt.7.3` AC2: *no copied metric disagrees with artifacts and every claim follows
the frozen claims matrix.* A prose document is the easiest place in a project for
a number to go stale, because nothing executes it.

So every number the case study states is matched against
`research-summary.json` — the artifact the site itself renders. A figure that
drifts fails the build rather than quietly misinforming a reader who has no way
to check it.

The prose and the screenshots' alt text carry figures — `0.2387`, rank `249`,
`0.9069` — so they are swept (`scoutlens-9a3.21`): every number there is either
bound to the field it was copied from, in `FIGURES`, or named in `STRUCTURAL`
with a reason. A bound figure is checked per occurrence, not against a pool, so
a one-digit edit fails even where it would land on some other published number.

The tables were once matched against that pool, decimals only, so a median rank
moved from 16 to 17, a population moved from 1,257 to 1,999 or two replication
MRRs swapped between rows all passed (`scoutlens-9a3.28`). Every table is now
declared in `TABLES`, row by row, each figure bound to its
`(experiment_id, metric_id)`.

The opening also carries the narrative's frozen thesis and boundary (§2 of
`public-experience-narrative.md`, `D066`), its question is the opening of the
narrative's 30-second explanation (§3, `scoutlens-9a3.34`), and the checklist
states `research.supported_claim` verbatim. All three are read from their owners
at test time, never copied here.

This file is what makes the case study's copies of published figures legitimate:
narrative §9 permits a copy only where a binding here holds it to its source
(`D071`).
"""

from __future__ import annotations

import json
import math
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pytest

from scoutlens.explanations.artifacts import DEFAULT_SHOWCASE_ROOT
from scoutlens.release.claims import build_matrix
from scoutlens.release.manifest import REPO_ROOT

CASE_STUDY = REPO_ROOT / "docs" / "case-study.md"
README = REPO_ROOT / "README.md"
V2 = DEFAULT_SHOWCASE_ROOT / "v2"
SUMMARY = V2 / "research-summary.json"
MANIFEST = V2 / "manifest.json"
HYDRATE = "uv run --frozen python -m scoutlens.showcase.payload hydrate"

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


#: Numbers in the prose and the alt text that are structural rather than
#: measured, so they have no metric to match. Each is checked elsewhere or is a
#: property of the design. One reason per entry: an entry nobody can justify is
#: a figure hiding from the sweep. A measured value never belongs here — it is
#: bound in `FIGURES` — and the tables have their own, narrower set.
#:
#: Until `scoutlens-9a3.28` this set also held the feature counts, the minutes
#: floor, the split seasons, the population sizes and the median ranks, for a
#: table sweep that read only decimals; the prose sweep had to un-allow them
#: through a second set. Every one of them is now bound where it appears.
#:
#: Until `scoutlens-9a3.34` it also held every bare 1 to 10, anywhere, for the
#: section numbers. Median ranks of 2 and 12 are published, so that let a new
#: unbound "median rank of 2" through. Small integers are now accounted for only
#: where they are structure: the sweep drops Markdown's own numbering (`_sweep`),
#: and `STRUCTURAL_CONTEXTS` names the in-sentence references.
STRUCTURAL = {
    "0.95",     # the preregistered live threshold (thresholds.py)
    "64",       # eval corpus size (corpus tests)
    "2.0.0", "1.0.0",  # contract versions, not measurements
    "2:53",     # the n=1 comprehension run, from D056
    # --- added by scoutlens-9a3.21, for the prose sweep ---
    "76",       # the walkthrough's length in seconds, held to the container by test_media_walkthrough.py
    "90",       # the 90-second first-understanding design target, not a result (D056)
}

#: Figures that are structural because of the words around them, not their
#: value: a figure inside a match is accounted for, the same figure anywhere
#: else is not. One reason per pattern, as for `STRUCTURAL`.
STRUCTURAL_CONTEXTS = {
    re.compile(r"§\d+\b"): "a cross-reference to a numbered section, here or in another document",
    re.compile(r"\bn=1\b"): "the one-evaluator comprehension run (D056), held by test_comprehension_disclosure.py",
    re.compile(r"\bRun 1\b"): "the same run, by its ordinal",
    re.compile(r"\bscoutlens-[\w.]*\w"): "a bead id (`scoutlens-9a3.11`): an identifier, not a figure",
}


@requires_summary
def test_the_headline_numbers_are_present(case_study: str) -> None:
    """The three numbers the argument rests on, including the awkward one."""
    matrix = build_matrix()
    by_id = {row.experiment_id: row for row in matrix.rows}
    assert {"wyscout_global_gate2", "wyscout_role_team_minutes"} <= set(by_id)

    for figure in ("0.0256", "0.2539", "0.5893"):
        assert figure in case_study, f"{figure} is missing from the case study"


# --- the prose and the alt text, figure by figure (scoutlens-9a3.21) -----
#
# Matching a figure against the pool of every published value cannot work: `16`
# is a median rank, a season and a pool member at once, and a one-digit slip
# from 16 to 15 lands on another published number. So each prose figure is
# bound to the one field it was copied from, by the words around it, and
# checked occurrence by occurrence. The tables get the same treatment below.

#: Commands are not figures (the profile key in the CLI example has digits), the
#: tables are swept by `TABLES`, and a link target is an address.
FENCE = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)
IMAGE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
LINK_TARGET = re.compile(r"\]\([^)]*\)")

#: One figure as a reader sees it: `1,257`, `0.2387`, `2017/18`, `2:53`, `2.0.0`.
#: Not a digit glued to a letter or a dot (`D058`, `v2`, `scoutlens.showcase`),
#: but a suffix may follow (`249th`, `2×`), so a stale ordinal is still caught.
FIGURE_TOKEN = re.compile(r"(?<![\w.])\d+(?:[.,:/]\d+)*(?!\d)")

#: What a `{}` in a `Figure` template matches. Wide enough for a dataset version.
SLOT = r"([\w.,/:-]*\w)"


@dataclass(frozen=True)
class Swept:
    prose: str  # outside tables, code and images; line wrapping flattened
    alt: str  # every image's alt text, one per line


@dataclass(frozen=True)
class Artifacts:
    summary: dict[str, Any]
    manifest: dict[str, Any]
    profile: dict[str, Any] | None


@dataclass(frozen=True)
class Source:
    name: str  # where the figure was copied from, for the failure message
    read: Callable[[Artifacts], str]
    from_profile: bool = False


@dataclass(frozen=True)
class Figure:
    """Figures in context: `template` is the document's text with `{}` per figure."""

    where: str  # "prose" or "alt"
    template: str
    sources: tuple[Source, ...]

    def pattern(self) -> re.Pattern[str]:
        parts = self.template.split("{}")
        assert len(parts) - 1 == len(self.sources), f"slot/source mismatch in {self.template!r}"
        return re.compile(SLOT.join(re.escape(part) for part in parts))


def _render(value: Any, places: int) -> str:
    """As the site prints it: thousands separated, decimals at a fixed precision."""
    if places == 0:
        assert value == int(value), f"{value!r} is rendered as a whole number"
        return f"{int(value):,}"
    return f"{value:.{places}f}"


def _experiment(artifacts: Artifacts, experiment_id: str) -> dict[str, Any]:
    by_id = {e["experiment_id"]: e for e in artifacts.summary["experiments"]}
    return by_id[experiment_id]


def metric(experiment_id: str, metric_id: str) -> Source:
    """A summary metric at the precision the summary itself says to display."""

    def read(artifacts: Artifacts) -> str:
        by_id = {m["metric_id"]: m for m in _experiment(artifacts, experiment_id)["metrics"]}
        found = by_id[metric_id]
        return _render(found["value"], found["display_precision"])

    return Source(f"research-summary {experiment_id}.{metric_id}", read)


def population(experiment_id: str, pattern: str) -> Source:
    """A count or season out of an experiment's own population statement."""

    def read(artifacts: Artifacts) -> str:
        stated = _experiment(artifacts, experiment_id)["population"]
        found = re.search(pattern, stated)
        assert found, f"{experiment_id}'s population no longer states {pattern!r}: {stated!r}"
        return found.group(1)

    return Source(f"research-summary {experiment_id}.population", read)


def feature_count(experiment_id: str, metric_id: str) -> Source:
    """The feature count a metric's label names (`28-feature canonical MRR`)."""

    def read(artifacts: Artifacts) -> str:
        by_id = {m["metric_id"]: m for m in _experiment(artifacts, experiment_id)["metrics"]}
        found = re.match(r"(\d+)-feature ", by_id[metric_id]["label"])
        assert found, f"{experiment_id}.{metric_id}'s label no longer names a feature count"
        return found.group(1)

    return Source(f"research-summary {experiment_id}.{metric_id}.label", read)


def summary(key: str) -> Source:
    return Source(f"research-summary {key}", lambda artifacts: str(artifacts.summary[key]))


def manifest(*path: str) -> Source:
    def read(artifacts: Artifacts) -> str:
        value: Any = artifacts.manifest
        for key in path:
            value = value[key]
        return _render(value, 0) if isinstance(value, int) else str(value)

    return Source(f"manifest {'.'.join(path)}", read)


def licence_version() -> Source:
    """`CC BY 4.0` is one badge; the slot holds its version, so the badge is checked whole."""

    def read(artifacts: Artifacts) -> str:
        licence = artifacts.manifest["source"]["licence"]
        assert licence.startswith("CC BY "), f"the licence is now {licence!r}; reword the alt text"
        return licence.removeprefix("CC BY ")

    return Source("manifest source.licence", read)


def times_greater(experiment_id: str, metric_id: str, than: tuple[str, str]) -> Source:
    """`more than 2×` is derived, so it is held to the ratio it summarises."""

    def read(artifacts: Artifacts) -> str:
        def value(eid: str, mid: str) -> float:
            by_id = {m["metric_id"]: m for m in _experiment(artifacts, eid)["metrics"]}
            return float(by_id[mid]["value"])

        return str(math.floor(value(experiment_id, metric_id) / value(*than)))

    return Source(f"research-summary {experiment_id}.{metric_id} / {than[0]}.{than[1]}", read)


def profile(*path: str, places: int = 0) -> Source:
    """A value the featured profile publishes, as the Lab's retrieval card prints it."""

    def read(artifacts: Artifacts) -> str:
        value: Any = artifacts.profile
        assert value is not None
        for key in path:
            value = value[key]
        return _render(value, places)

    return Source(f"featured profile {'.'.join(path)}", read, from_profile=True)


def card(name: str, field: str, places: int = 0) -> Source:
    return profile("retrieval", name, field, places=places)


GLOBAL = "wyscout_global_gate2"
TEAM = "wyscout_role_team_minutes"
WY_TRANSFER = "wyscout_transferred_players"
SB_GLOBAL = "statsbomb_global_replication"
SB_TRANSFER = "statsbomb_transferred_players"
COUNT = r"^([\d,]+) "
SEASON = r"(\d{4}/\d{2})"

#: The team baseline over the fingerprint, which the prose states twice as `more than 2×`.
TEAM_OVER_FINGERPRINT = times_greater(TEAM, "baseline_c_mrr", than=(GLOBAL, "fingerprint_mrr"))

#: Every sourced figure in the prose and the alt text, in document order. A
#: template is the document's own wording, so rewording a sentence that carries
#: a figure means rewording its binding here — which is the point.
FIGURES: tuple[Figure, ...] = (
    # The short version. The question is §3 of the narrative, verbatim; its two
    # figures are the manifest's, as on `/science` (`scoutlens-9a3.34`).
    Figure("prose", "event data from the {} season, split", (manifest("source", "season"),)),
    Figure("prose", "whether {} simple measurements", (manifest("population", "feature_count"),)),
    Figure(
        "prose",
        "baseline scoring **{} MRR**, the {}-feature fingerprint scores **{}**",
        (metric(GLOBAL, "baseline_a_mrr"), manifest("population", "feature_count"), metric(GLOBAL, "fingerprint_mrr")),
    ),
    Figure(
        "prose",
        "a median self-rank of **{}** out of {} candidates",
        (metric(GLOBAL, "median_rank"), population(GLOBAL, COUNT)),
    ),
    Figure("prose", "a different season at **{}**", (metric(SB_GLOBAL, "fingerprint_mrr"),)),
    Figure("prose", "minutes* scores **{}**", (metric(TEAM, "baseline_c_mrr"),)),
    Figure("prose", "more than {}× the fingerprint, at", (TEAM_OVER_FINGERPRINT,)),
    Figure("prose", "at a median rank of {}.", (metric(TEAM, "median_rank"),)),
    # What it looks like: the stills' alt text, and the sentence under them.
    Figure(
        "alt",
        '"{}", "CC BY {}" and the dataset version {}.',
        (manifest("source", "season"), licence_version(), summary("dataset_version")),
    ),
    Figure(
        "alt",
        "Global: rank {} of {}, reciprocal rank {}, similarity score {}.",
        (
            card("global", "self_rank"),
            card("global", "candidate_count"),
            card("global", "reciprocal_rank", 4),
            card("global", "similarity_score", 4),
        ),
    ),
    Figure(
        "alt",
        "Within role: rank {} of {}, same reciprocal rank and score.",
        (card("within_role", "self_rank"), card("within_role", "candidate_count")),
    ),
    Figure(
        "alt",
        "Role and minutes baseline: rank {} of {}, reciprocal rank {}, similarity score not used.",
        (
            card("baseline_role_minutes", "self_rank"),
            card("baseline_role_minutes", "candidate_count"),
            card("baseline_role_minutes", "reciprocal_rank", 4),
        ),
    ),
    Figure("alt", "uncertainty from {} valid resamples", (profile("uncertainty", "valid_resamples"),)),
    Figure(
        "prose",
        "puts Modric first out of {}; the role-and-minutes control puts him {}th.",
        (card("global", "candidate_count"), card("baseline_role_minutes", "self_rank")),
    ),
    # §2. Hypothesis and the frozen task.
    Figure(
        "prose",
        "(second half). {} eligible player × competition units from the {} Wyscout/Pappalardo",
        (population(GLOBAL, COUNT), population(GLOBAL, SEASON)),
    ),
    Figure("prose", "at least {} minutes in *each* period", (manifest("population", "minutes_threshold_per_period"),)),
    # §4. The confound.
    Figure("prose", "beats the fingerprint by more than {}×", (TEAM_OVER_FINGERPRINT,)),
    Figure("prose", "role and minutes narrows {} candidates", (population(TEAM, COUNT),)),
    # §5. Replication, and the transferred players.
    Figure(
        "prose",
        "a different season ({}), four leagues, {} eligible units, {} canonical features",
        (population(SB_GLOBAL, SEASON), population(SB_GLOBAL, COUNT), feature_count(SB_GLOBAL, "fingerprint_mrr")),
    ),
    Figure(
        "prose",
        "settle it: {} in Wyscout (MRR {}, encouraging) and {} in StatsBomb (MRR {}, inconclusive)",
        (
            metric(WY_TRANSFER, "transferred_count"),
            metric(WY_TRANSFER, "fingerprint_mrr"),
            metric(SB_TRANSFER, "transferred_count"),
            metric(SB_TRANSFER, "fingerprint_mrr"),
        ),
    ),
    # §6. System design.
    Figure("prose", "(`scoutlens.showcase/{}`)", (summary("schema_version"),)),
    Figure("prose", "data.** {} profiles are distributed", (manifest("population", "profile_count"),)),
    # §9. Known limitations.
    Figure(
        "prose",
        "transfer samples.** {} and {} players.",
        (metric(WY_TRANSFER, "transferred_count"), metric(SB_TRANSFER, "transferred_count")),
    ),
)


HEADING_NUMBER = re.compile(r"^(#{2,6} )\d+\. ")
LIST_MARKER = re.compile(r"^\d+\. ")


def _without_markdown_numbering(lines: list[str]) -> list[str]:
    """A heading's number and an ordered list item's marker are Markdown, not prose.

    A wrapped sentence can also put `2. ` at the start of a line ("…at a median
    rank of" / "2. Same-season…"), so a marker is dropped only where a list can
    be: after a blank line, after another item, or after an item's indented
    continuation. Anywhere else the figure stays in the prose and is swept.
    """
    kept: list[str] = []
    in_list = False
    for line in lines:
        if HEADING_NUMBER.match(line):
            line, in_list = HEADING_NUMBER.sub(r"\1", line), False
        elif LIST_MARKER.match(line) and (in_list or not kept or not kept[-1].strip()):
            line, in_list = LIST_MARKER.sub("", line), True
        else:
            in_list = in_list and line.startswith((" ", "\t"))
        kept.append(line)
    return kept


def _sweep(case_study: str) -> Swept:
    body = FENCE.sub("", case_study)
    lines = [line for line in body.splitlines() if not line.strip().startswith("|")]
    body = "\n".join(_without_markdown_numbering(lines))
    alt = "\n".join(" ".join(text.split()) for text in IMAGE.findall(body))
    prose = " ".join(LINK_TARGET.sub("]", IMAGE.sub(" ", body)).split())
    return Swept(prose=prose, alt=alt)


@pytest.fixture(scope="module")
def swept(case_study: str) -> Swept:
    return _sweep(case_study)


def _load(path: Any) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _featured_profile_path() -> Any:
    """The committed manifest names the featured profile; its payload is hydrated."""
    if not MANIFEST.is_file():
        return None
    return V2 / "players" / f"{_load(MANIFEST)['featured_profile']['profile_key']}.json"


FEATURED_PROFILE = _featured_profile_path()

#: `public/showcase/v2/players/` is gitignored, so an un-hydrated clone skips the
#: profile half. CI sets this variable after hydrating, and there a missing
#: profile is an outage, not a choice: the test runs and fails rather than
#: skipping (the same rule as `tests/explanations/conftest.py`, `iex.10`).
REQUIRE_SHOWCASE = os.environ.get("SCOUTLENS_REQUIRE_SHOWCASE", "").strip() == "1"

requires_featured_profile = pytest.mark.skipif(
    not REQUIRE_SHOWCASE and not (FEATURED_PROFILE is not None and FEATURED_PROFILE.is_file()),
    reason=f"requires a hydrated public/showcase/v2 ({HYDRATE})",
)


def _disagreements(figures: list[Figure], artifacts: Artifacts, text: Swept) -> list[str]:
    problems = []
    for figure in figures:
        expected = tuple(source.read(artifacts) for source in figure.sources)
        matches = list(figure.pattern().finditer(getattr(text, figure.where)))
        if not matches:
            problems.append(f"{figure.template!r} is no longer in the case study's {figure.where}")
        for match in matches:
            if match.groups() != expected:
                names = ", ".join(source.name for source in figure.sources)
                problems.append(
                    f"{figure.template!r}: the case study says {match.groups()}, "
                    f"the artifact says {expected} ({names})"
                )
    return problems


def test_every_figure_in_the_prose_and_alt_text_is_bound_or_structural(swept: Swept) -> None:
    """The sweep itself, and it needs no artifact: only the document.

    A number with no binding and no structural reason is a figure nothing
    checks. It fails here even on a clone that cannot read the artifact.
    """
    assert swept.alt, "the case study has no image alt text; the stills are gone"
    for where in ("prose", "alt"):
        text = getattr(swept, where)
        bound: list[tuple[int, int]] = []
        for figure in (f for f in FIGURES if f.where == where):
            spans = [match.span() for match in figure.pattern().finditer(text)]
            assert spans, (
                f"{figure.template!r} is no longer in the case study's {where}. "
                "Reword the binding with the sentence; never drop it."
            )
            bound.extend(spans)
        structural = [match.span() for pattern in STRUCTURAL_CONTEXTS for match in pattern.finditer(text)]

        loose = {
            token.group()
            for token in FIGURE_TOKEN.finditer(text)
            if not any(start <= token.start() and token.end() <= end for start, end in bound + structural)
        }
        unaccounted = sorted(token for token in loose if token not in STRUCTURAL)
        assert not unaccounted, (
            f"these figures in the case study's {where} are bound to no source: {unaccounted}. "
            "Bind each in FIGURES, or add it (or the words that make it structural) to STRUCTURAL "
            "(STRUCTURAL_CONTEXTS) with the reason it is not a measurement."
        )


@requires_summary
def test_every_bound_figure_matches_the_summary(swept: Swept) -> None:
    """The prose figures copied from `research-summary.json` and the manifest."""
    artifacts = Artifacts(summary=_load(SUMMARY), manifest=_load(MANIFEST), profile=None)
    figures = [f for f in FIGURES if not any(source.from_profile for source in f.sources)]
    assert figures

    problems = _disagreements(figures, artifacts, swept)
    assert not problems, "the case study disagrees with the artifact:\n" + "\n".join(problems)


@pytest.fixture(scope="module")
def featured_profile() -> dict[str, Any]:
    assert FEATURED_PROFILE is not None and FEATURED_PROFILE.is_file(), (
        f"SCOUTLENS_REQUIRE_SHOWCASE=1 and the featured profile is absent. Hydrate first:\n    {HYDRATE}"
    )
    return _load(FEATURED_PROFILE)


@requires_summary
@requires_featured_profile
def test_the_featured_profile_figures_match_its_published_values(
    swept: Swept, featured_profile: dict[str, Any]
) -> None:
    """The retrieval still's alt text, and the sentence that reads it out.

    The screenshot is of the featured profile's Lab page, so its numbers are
    that profile's published values — not the summary's.
    """
    summary_json = _load(SUMMARY)
    assert featured_profile["dataset_version"] == summary_json["dataset_version"], (
        "the hydrated profile is not from the dataset the summary describes"
    )
    artifacts = Artifacts(summary=summary_json, manifest=_load(MANIFEST), profile=featured_profile)
    figures = [f for f in FIGURES if any(source.from_profile for source in f.sources)]
    assert figures

    problems = _disagreements(figures, artifacts, swept)
    assert not problems, "the case study disagrees with the featured profile:\n" + "\n".join(problems)

    # What the alt text says in words rather than digits.
    retrieval = featured_profile["retrieval"]
    cards = ("global", "within_role", "baseline_role_minutes")
    assert f"using representation {retrieval['method']}." in swept.alt
    assert retrieval["global"]["self_rank"] == 1, "the prose says the fingerprint puts him first"
    for field in ("reciprocal_rank", "similarity_score"):  # "same reciprocal rank and score"
        assert _render(retrieval["within_role"][field], 4) == _render(retrieval["global"][field], 4)
    assert retrieval["baseline_role_minutes"]["similarity_score"] is None  # "similarity score not used"
    resamples = featured_profile["uncertainty"]["valid_resamples"]
    assert all(retrieval[card]["uncertainty"]["valid_resamples"] == resamples for card in cards), (
        "the alt text says each card reports the same number of valid resamples"
    )


# --- the tables, row by row (scoutlens-9a3.28) ---------------------------
#
# A pool can tell that `0.2031` is a published value; it cannot tell that it is
# the replication's fingerprint MRR rather than its within-role one, and it
# never read an integer. So every table is declared here in document order: its
# header, then each row as one `Cell` per column, with every figure bound to the
# `(experiment_id, metric_id)` it was copied from. A row moved, swapped, added
# or dropped fails, and so does a figure one digit off.

WITHIN = "wyscout_within_role_gate2"
SB_WITHIN = "statsbomb_within_role_replication"
SHRINKAGE = "wyscout_ratio_shrinkage"

#: The only figures a table may carry unbound, each with its reason. Narrower
#: than `STRUCTURAL`: a table has no section numbers, so a bare `2` in one is a
#: measurement until shown otherwise.
TABLE_STRUCTURAL = {
    "5": "the k of recall@5 — the metric's definition, not its value",
}


@dataclass(frozen=True)
class Cell:
    """One table cell as a reader sees it, emphasis stripped: `{}` per bound figure.

    `whole` binds the entire cell to one source — a cell that *is* a published
    sentence, not a sentence with figures in it. `free` is a cell whose wording
    this file does not own; it is matched as anything, so every figure in it
    must be in `TABLE_STRUCTURAL`.
    """

    template: str
    sources: tuple[Source, ...] = ()
    whole: bool = False
    free: bool = False

    def pattern(self) -> re.Pattern[str]:
        if self.free:
            return re.compile(r".*")
        if self.whole:
            assert self.template == "{}" and len(self.sources) == 1, f"a whole cell has one source: {self!r}"
            return re.compile(r"(.+)")
        parts = self.template.split("{}")
        assert len(parts) - 1 == len(self.sources), f"slot/source mismatch in {self.template!r}"
        return re.compile(SLOT.join(re.escape(part) for part in parts))


def text(literal: str) -> Cell:
    return Cell(literal)


def value(experiment_id: str, metric_id: str) -> Cell:
    return Cell("{}", (metric(experiment_id, metric_id),))


FREE = Cell("", free=True)
NONE = text("—")  # a metric the experiment does not have, stated as absent


@dataclass(frozen=True)
class Table:
    name: str  # for the failure message
    header: tuple[str, ...]
    rows: tuple[tuple[Cell, ...], ...]


#: Every table in the case study, in document order.
TABLES: tuple[Table, ...] = (
    Table(
        "§3 Evidence",
        ("Experiment", "Metric", "Value"),
        (
            (text("Role + minutes baseline"), text("MRR"), value(GLOBAL, "baseline_a_mrr")),
            (
                Cell("{}-feature fingerprint", (feature_count(GLOBAL, "fingerprint_mrr"),)),
                text("MRR"),
                value(GLOBAL, "fingerprint_mrr"),
            ),
            (
                text(""),
                text("median self-rank"),
                Cell("{} of {}", (metric(GLOBAL, "median_rank"), population(GLOBAL, COUNT))),
            ),
            (text("Within role only"), text("MRR"), value(WITHIN, "fingerprint_mrr")),
            (text(""), text("median self-rank"), value(WITHIN, "median_rank")),
            (text(""), text("recall@5"), value(WITHIN, "recall_at_5")),
        ),
    ),
    Table(
        "§4 The confound",
        ("Baseline", "MRR", "median rank"),
        (
            (text("Role + minutes"), value(GLOBAL, "baseline_a_mrr"), NONE),
            (text("Role + team + minutes"), value(TEAM, "baseline_c_mrr"), value(TEAM, "median_rank")),
            (
                Cell("{}-feature fingerprint", (feature_count(GLOBAL, "fingerprint_mrr"),)),
                value(GLOBAL, "fingerprint_mrr"),
                value(GLOBAL, "median_rank"),
            ),
        ),
    ),
    Table(
        "§5 Replication",
        ("", "MRR", "median rank"),
        (
            (text("Role + minutes baseline"), value(SB_GLOBAL, "baseline_a_mrr"), NONE),
            (text("Canonical fingerprint"), value(SB_GLOBAL, "fingerprint_mrr"), value(SB_GLOBAL, "median_rank")),
            (text("Within role only"), value(SB_WITHIN, "fingerprint_mrr"), value(SB_WITHIN, "median_rank")),
        ),
    ),
    Table(
        "§5 The shrinkage null",
        ("", "raw", "shrunk"),
        (
            (text("Global MRR"), value(SHRINKAGE, "raw_global_mrr"), value(SHRINKAGE, "shrunk_global_mrr")),
            (
                text("Within-role MRR"),
                value(SHRINKAGE, "raw_within_role_mrr"),
                value(SHRINKAGE, "shrunk_within_role_mrr"),
            ),
        ),
    ),
    Table(
        "For the reader in a hurry",
        ("Question", "Answer"),
        (
            (text("What is claimed?"), Cell("{}", (summary("supported_claim"),), whole=True)),
            (
                text("What is the evidence?"),
                Cell(
                    "{} MRR vs a {} baseline on {} units; replicated at {} on a different provider and season; "
                    "survives restriction to the same role.",
                    (
                        metric(GLOBAL, "fingerprint_mrr"),
                        metric(GLOBAL, "baseline_a_mrr"),
                        population(GLOBAL, COUNT),
                        metric(SB_GLOBAL, "fingerprint_mrr"),
                    ),
                ),
            ),
            (
                text("What is the biggest limitation?"),
                Cell(
                    "A role + team + minutes baseline scores {} — better than the fingerprint. "
                    "Same-season club continuity is a stronger shortcut.",
                    (metric(TEAM, "baseline_c_mrr"),),
                ),
            ),
            (text("What is the engineering contribution?"), FREE),
            (text("What is the AI's role?"), FREE),
        ),
    ),
)


@dataclass(frozen=True)
class ParsedTable:
    line: int  # the header's line in the case study, for the failure message
    header: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]


TABLE_SEPARATOR = re.compile(r"^\|(?:\s*:?-+:?\s*\|)+$")


def _cells(line: str) -> tuple[str, ...]:
    """A row's cells, emphasis stripped and whitespace collapsed: what a reader sees."""
    return tuple(" ".join(cell.replace("*", "").split()) for cell in line.strip()[1:-1].split("|"))


def _tables(case_study: str) -> list[ParsedTable]:
    """Every markdown table outside a code fence, in document order."""
    body = FENCE.sub(lambda fence: "\n" * fence.group().count("\n"), case_study)  # keeps line numbers
    runs: list[list[tuple[int, str]]] = [[]]
    for number, line in enumerate(body.splitlines(), start=1):
        if line.strip().startswith("|"):
            runs[-1].append((number, line.strip()))
        elif runs[-1]:
            runs.append([])
    tables = []
    for run in (run for run in runs if run):
        (line, header), *rest = run
        assert rest and TABLE_SEPARATOR.match(rest[0][1]), f"the table at line {line} has no separator row"
        tables.append(ParsedTable(line, _cells(header), tuple(_cells(row) for _, row in rest[1:])))
    return tables


def _matched_rows(case_study: str) -> list[tuple[str, int, tuple[Cell, ...], tuple[re.Match[str], ...]]]:
    """Each declared row against the document's, cell by cell: (table, row, cells, matches).

    The shape is asserted here — the same tables in the same order, the same
    header, the same number of rows and columns, every cell matching its
    template whole — so a row cannot move between tables or swap with another.
    """
    parsed = _tables(case_study)
    assert len(parsed) == len(TABLES), (
        f"the case study has {len(parsed)} tables and TABLES declares {len(TABLES)}. "
        "Declare a new table here, figure by figure; never leave one unbound."
    )
    matched = []
    for declared, found in zip(TABLES, parsed, strict=True):
        where = f"{declared.name} (line {found.line})"
        assert found.header == declared.header, f"{where}: the header is {found.header}, not {declared.header}"
        assert len(found.rows) == len(declared.rows), (
            f"{where}: {len(found.rows)} rows in the document, {len(declared.rows)} declared"
        )
        for index, (cells, row) in enumerate(zip(declared.rows, found.rows, strict=True), start=1):
            assert len(row) == len(cells), f"{where}, row {index}: {len(row)} cells, {len(cells)} declared"
            matches = []
            for cell, content in zip(cells, row, strict=True):
                match = cell.pattern().fullmatch(content)
                assert match, f"{where}, row {index}: {content!r} does not read as {cell.template!r}"
                matches.append(match)
            matched.append((declared.name, index, cells, tuple(matches)))
    return matched


def test_every_table_is_declared_and_every_figure_in_it_bound(case_study: str) -> None:
    """The table sweep, artifact-free: every figure in a table sits in a bound slot.

    Like the prose sweep, it needs only the document, so an unbound figure fails
    even on a clone that cannot read the artifact.
    """
    for table in _tables(case_study):
        figures = FIGURE_TOKEN.findall(" ".join(table.header))
        assert not figures, f"the table at line {table.line} has a figure in its header: {figures}"

    unbound = []
    for name, index, cells, matches in _matched_rows(case_study):
        for cell, match in zip(cells, matches, strict=True):
            bound = [match.span(group) for group in range(1, len(cell.sources) + 1)]
            for token in FIGURE_TOKEN.finditer(match.string):
                inside = any(start <= token.start() and token.end() <= end for start, end in bound)
                if not inside and token.group() not in TABLE_STRUCTURAL:
                    unbound.append(f"{name}, row {index}: {token.group()!r} in {match.string!r}")
    assert not unbound, (
        "these table figures are bound to no source:\n" + "\n".join(unbound) + "\n"
        "Bind each in TABLES, or add it to TABLE_STRUCTURAL with the reason it is not a measurement."
    )


@requires_summary
def test_every_table_row_matches_its_metrics(case_study: str) -> None:
    """Each table row against the `(experiment_id, metric_id)` it states."""
    artifacts = Artifacts(summary=_load(SUMMARY), manifest=_load(MANIFEST), profile=None)
    problems = []
    for name, index, cells, matches in _matched_rows(case_study):
        for cell, match in zip(cells, matches, strict=True):
            expected = tuple(" ".join(source.read(artifacts).split()) for source in cell.sources)
            if match.groups() != expected:
                names = ", ".join(source.name for source in cell.sources)
                problems.append(
                    f"{name}, row {index}: the case study says {match.groups()}, "
                    f"the artifact says {expected} ({names})"
                )
    assert not problems, "a case-study table disagrees with the artifact:\n" + "\n".join(problems)


# --- the thesis, the boundary and the claim, verbatim (scoutlens-9a3.28) --

NARRATIVE = REPO_ROOT / "docs" / "public-experience-narrative.md"

#: `D066`: §2 says "ScoutLens"; the public identity contract substitutes the
#: display name and permits no other edit. The same constant as
#: `web/src/content/narrative.ts` and `e2e/claims-consistency.spec.ts`.
FROZEN_NAME = "ScoutLens"
DISPLAY_NAME = "Yumusarái Labs"

#: The Lab boundary `D066` retired. The desktop still was captured before it
#: (`d79e336`), so its alt text describes it until `scoutlens-jtt.27`
#: re-captures the still. Nothing else in the case study may say it.
RETIRED_LAB_BOUNDARY = "not a quality score, style proof, recruitment ranking, or automated verdict"


def _narrative_section(heading: str) -> list[str]:
    """The lines of one `## ` section of the narrative, heading excluded."""
    narrative = NARRATIVE.read_text(encoding="utf-8")
    section = re.search(rf"^## {re.escape(heading)}$(.*?)^## ", narrative, re.MULTILINE | re.DOTALL)
    assert section, f"the narrative has no '## {heading}' section"
    return section.group(1).splitlines()


def _first_blockquote(lines: list[str]) -> str:
    """The first blockquote in `lines`, as one line; empty if there is none."""
    quote: list[str] = []
    for line in lines:
        if line.startswith(">"):
            quote.append(line[1:])
        elif quote:
            break
    return " ".join(" ".join(quote).split())


def _frozen_quote(label: str) -> str:
    """The blockquote under `**{label}` in §2 of the narrative, as one line.

    The same reading as `frozenQuote` in `e2e/claims-consistency.spec.ts`, so
    the site and the case study are held to one text.
    """
    lines = _narrative_section("2. Frozen thesis")
    start = next((i for i, line in enumerate(lines) if line.startswith(f"**{label}")), None)
    assert start is not None, f"§2 of the narrative has no {label!r} label"
    quote = _first_blockquote(lines[start + 1 :])
    assert quote, f"§2's {label!r} label has no blockquote under it"
    return quote


#: How many of §3's sentences open the explanation: the ones `/science` renders
#: as its orientation (`ORIENTATION_SENTENCES` in `e2e/science-evidence-surface.spec.ts`).
OPENING_SENTENCES = 2


def _explanation_opening(manifest_json: dict[str, Any]) -> str:
    """§3's opening, with exactly the substitutions the narrative permits.

    The same reading as `expectedOrientation` in
    `e2e/science-evidence-surface.spec.ts`: the display name for "ScoutLens",
    and the season and the measurement count read from the manifest. Each
    anchor must be present once before it is replaced, so an unrelated `32` is
    never rewritten.
    """
    explanation = _first_blockquote(_narrative_section("3. The 30-second explanation"))
    sentences = re.split(r"(?<=[.?])\s+(?=[A-Z])", explanation)
    # A sentence added to or split in §3 fails here, rather than silently
    # shifting which sentences the case study is held to.
    assert len(sentences) == 4, f"§3 is no longer four sentences: {sentences}"
    opening = " ".join(sentences[:OPENING_SENTENCES])
    for anchor, replacement in (
        (FROZEN_NAME, DISPLAY_NAME),
        ("the 2017/18 season", f"the {manifest_json['source']['season']} season"),
        ("whether 32 simple", f"whether {manifest_json['population']['feature_count']} simple"),
    ):
        assert opening.count(anchor) == 1, f"§3's opening no longer contains {anchor!r} exactly once"
        opening = opening.replace(anchor, replacement)
    return opening


def _as_read(markdown: str) -> str:
    """What a reader reads: blockquote markers and emphasis removed, whitespace collapsed."""
    unquoted = "\n".join(re.sub(r"^\s*>\s?", "", line) for line in markdown.splitlines())
    return " ".join(unquoted.replace("*", "").split())


def test_the_opening_states_the_narratives_thesis_and_boundary_verbatim_and_adjacent(case_study: str) -> None:
    """§2's thesis, then its boundary, in the short version — the site's own two sentences.

    *Verbatim* is §2's text with one substitution, the display name for
    "ScoutLens" (`D066`). *Adjacent* is §2's "never separated by other copy",
    made exact: once blockquote markers and emphasis are removed and whitespace
    collapsed, the boundary follows the thesis after a single space. A line
    break, or a paragraph break inside one blockquote, passes; any word, link
    or figure between them fails.
    """
    frozen_thesis = _frozen_quote("Thesis")
    assert frozen_thesis.count(FROZEN_NAME) == 1, "§2's thesis no longer names the project once; revisit D066"
    thesis = frozen_thesis.replace(FROZEN_NAME, DISPLAY_NAME)
    boundary = _frozen_quote("Boundary sentence")
    assert FROZEN_NAME not in boundary

    opening = re.search(r"^## The short version$(.*?)^#", case_study, re.MULTILINE | re.DOTALL)
    assert opening, "the case study has no 'The short version' section"
    read = _as_read(opening.group(1))
    assert thesis in read, f"the short version does not state §2's thesis verbatim:\n    {thesis}"
    assert boundary in read, f"the short version does not state §2's boundary verbatim:\n    {boundary}"
    assert f"{thesis} {boundary}" in read, "something sits between the thesis and its boundary"


@requires_summary
def test_the_question_is_the_narratives_explanation_opening_verbatim(case_study: str) -> None:
    """§9 of the narrative says the case study consumes its 30-second explanation.

    So "The question." is §3's opening — the `/science` orientation's two
    sentences — with nothing added or dropped: the paragraph, as read, *is* the
    expected text, not merely contains it (`scoutlens-9a3.34`).
    """
    expected = _explanation_opening(_load(MANIFEST))
    paragraph = re.search(r"^\*\*The question\.\*\*(.*?)\n[ \t]*\n", case_study, re.MULTILINE | re.DOTALL)
    assert paragraph, "the case study has no '**The question.**' paragraph"
    assert _as_read(paragraph.group(1)) == expected, (
        f"the case study's question is not §3's opening verbatim:\n    {expected}"
    )


@requires_summary
def test_what_is_claimed_is_the_supported_claim_verbatim(case_study: str) -> None:
    """The checklist's answer is `research.supported_claim`, not a paraphrase of it."""
    claim = " ".join(_load(SUMMARY)["supported_claim"].split())
    answers = {row[0]: row[1:] for table in _tables(case_study) for row in table.rows if row}
    assert "What is claimed?" in answers, "the checklist no longer asks what is claimed"
    assert answers["What is claimed?"] == (claim,), (
        f"the case study answers {answers['What is claimed?']}; the artifact's supported claim is {claim!r}"
    )


def test_the_retired_lab_boundary_is_not_restated(case_study: str, swept: Swept) -> None:
    """`D066` replaced it; only the old still's description may still quote it."""
    outside_images = _as_read(IMAGE.sub(" ", case_study))
    assert RETIRED_LAB_BOUNDARY not in outside_images, "the case study restates the Lab boundary D066 retired"
    assert swept.alt.count(RETIRED_LAB_BOUNDARY) <= 1


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
    """`D056`'s handoff requirement, verbatim in substance.

    Presence only; `test_comprehension_disclosure.py` also forbids the opposite
    claim and names the four findings, in this document and the release notes.
    """
    assert "one evaluator" in prose or "n=1" in prose
    assert "2:53" in prose
    assert "four findings" in prose
    assert "no fresh independent retest" in prose
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
