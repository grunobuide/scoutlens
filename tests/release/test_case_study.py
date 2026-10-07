"""The case study may not disagree with the artifact it describes.

`jtt.7.3` AC2: *no copied metric disagrees with artifacts and every claim follows
the frozen claims matrix.* A prose document is the easiest place in a project for
a number to go stale, because nothing executes it.

So every number the case study states is matched against
`research-summary.json` — the artifact the site itself renders. A figure that
drifts fails the build rather than quietly misinforming a reader who has no way
to check it.

The tables were swept first. The prose and the screenshots' alt text carry just
as many figures — `0.2387`, rank `249`, `0.9069` — so they are swept too
(`scoutlens-9a3.21`): every number there is either bound to the field it was
copied from, in `FIGURES`, or named in `STRUCTURAL` with a reason. A bound
figure is checked per occurrence, not against a pool, so a one-digit edit fails
even where it would land on some other published number.
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
#: match. Each is checked elsewhere or is a property of the design. One reason
#: per entry: an entry nobody can justify is a figure hiding from the sweep.
STRUCTURAL = {
    "1", "2", "3", "4", "5", "6", "7", "8", "9", "10",  # section and list numbering, `§4`/`§7`, `n=1`, `run 1`
    "0.95",     # the preregistered live threshold (thresholds.py)
    "64",       # eval corpus size (corpus tests)
    "32", "28", # feature counts, stated in the artifact's own copy
    "450",      # minutes floor per period
    "2.0.0", "1.0.0",  # contract versions, not measurements
    "2017", "18", "2015", "16",  # the two seasons, 2017/18 and 2015/16, split at the slash
    "2:53",     # the n=1 comprehension run, from D056
    "1,257", "1,061", "26", "19", "16", "12", "15", "2",  # population sizes and median ranks; see MEASURED
    # --- added by scoutlens-9a3.21, for the prose sweep ---
    "76",       # the walkthrough's length in seconds, held to the container by test_media_walkthrough.py
    "90",       # the 90-second first-understanding design target, not a result (D056)
}

#: The entries above that are really artifact values. The table sweep reads only
#: decimals, so allowlisting them cost it nothing; in prose an allowlisted count
#: would let a stale one through, so there each must be bound in `FIGURES`.
MEASURED = {"1,257", "1,061", "26", "19", "16", "12", "15", "450", "32", "28"}

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


# --- the prose and the alt text, figure by figure (scoutlens-9a3.21) -----
#
# The table sweep above matches a decimal against the pool of every published
# value. That cannot work for prose: `16` is a median rank, a season and a pool
# member at once, and a one-digit slip from 16 to 15 lands on another published
# number. So each prose figure is bound to the one field it was copied from, by
# the words around it, and checked occurrence by occurrence.

#: Commands are not figures (the profile key in the CLI example has digits), the
#: tables are swept above, and a link target is an address.
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

#: Every sourced figure in the prose and the alt text, in document order. A
#: template is the document's own wording, so rewording a sentence that carries
#: a figure means rewording its binding here — which is the point.
FIGURES: tuple[Figure, ...] = (
    # The short version.
    Figure("prose", "whether {} event-derived measurements", (manifest("population", "feature_count"),)),
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
    Figure(
        "prose",
        "beats the fingerprint by more than {}×",
        (times_greater(TEAM, "baseline_c_mrr", than=(GLOBAL, "fingerprint_mrr")),),
    ),
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


def _sweep(case_study: str) -> Swept:
    body = FENCE.sub("", case_study)
    body = "\n".join(line for line in body.splitlines() if not line.strip().startswith("|"))
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

        loose = {
            token.group()
            for token in FIGURE_TOKEN.finditer(text)
            if not any(start <= token.start() and token.end() <= end for start, end in bound)
        }
        unaccounted = sorted(token for token in loose if token not in STRUCTURAL or token in MEASURED)
        assert not unaccounted, (
            f"these figures in the case study's {where} are bound to no source: {unaccounted}. "
            "Bind each in FIGURES, or add it to STRUCTURAL with the reason it is not a measurement."
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
