"""The versioned case set, and the coverage it claims.

A case is a bundle, a response, and what should happen. Bundles come from
published showcase artifacts or from a named degradation of one; responses come
from `responses` and `mutations`; the expectation is `ACCEPT`, `REJECT` with the
rule that must fire, or `FALLBACK`.

**Membership is pinned, and the pin is checked.** The profiles below were chosen
once, by scanning every published v2 profile and taking the lexicographically
first key in each role and alignment band. Recomputing that at build time would
mean reading 1,257 files on every run, and — worse — a corpus whose membership
silently changed with the data would not be a versioned corpus at all. So the
keys are constants, and `tests/explanations` re-reads each pinned profile and
asserts it still sits in the band it was pinned into. A repin that moves a
profile fails loudly instead of quietly re-scoping the eval.

**One cell of the matrix is empty, and stays empty.** No goalkeeper in the
published data aligns weakly: the lowest goalkeeper similarity is well inside
the `lower_mid` band. The matrix reports that cell as absent rather than
widening the band until something falls into it, because the band is the claim
and a band chosen to be populated measures nothing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Any

from scoutlens.explanations.adapters.protocol import FailureReason
from scoutlens.explanations.bundle import BundleOptions, build_bundle
from scoutlens.explanations.evals import degrade
from scoutlens.explanations.evals.mutations import MUTATIONS, apply_mutation
from scoutlens.explanations.evals.responses import limitation_variant, reference_output
from scoutlens.explanations.policy import EvidenceStatus

CORPUS_VERSION = "1.0.0"
"""Bumped when a case is added, removed or re-expected. Recorded in the report."""

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_SHOWCASE_ROOT = REPO_ROOT / "public" / "showcase"


class CorpusUnavailable(RuntimeError):
    """The published artifacts this corpus is derived from are not present."""


class Expectation(StrEnum):
    """What the suite asserts about a case."""

    ACCEPT = "accept"
    """The validator must accept the response. Nothing about it is wrong."""

    REJECT = "reject"
    """The validator must refuse it, and name the rule the case was built for."""

    FALLBACK = "fallback"
    """No usable answer exists; the deterministic fallback must stand in."""


class Dimension(StrEnum):
    """The conditions the corpus claims to cover.

    Every member has at least one case, and `tests/explanations` asserts that
    rather than trusting the list. A dimension nobody exercises is a claim of
    coverage with nothing behind it, which is the failure mode a matrix is
    supposed to prevent and most often causes.
    """

    ROLE_GOALKEEPER = "role:goalkeeper"
    ROLE_DEFENDER = "role:defender"
    ROLE_MIDFIELDER = "role:midfielder"
    ROLE_FORWARD = "role:forward"

    ALIGNMENT_STRONG = "alignment:strong"
    ALIGNMENT_UPPER_MID = "alignment:upper_mid"
    ALIGNMENT_LOWER_MID = "alignment:lower_mid"
    ALIGNMENT_WEAK = "alignment:weak"

    EVIDENCE_WEIGHTED = "evidence:weighted"
    EVIDENCE_EXCLUDED = "evidence:excluded"
    EVIDENCE_LEARNED_ZERO = "evidence:learned_zero"
    EVIDENCE_UNMEASURED = "evidence:unmeasured"
    EVIDENCE_NULL_IMPUTED = "evidence:null_imputed"
    EVIDENCE_MISSING = "evidence:missing"

    UNCERTAINTY_AVAILABLE = "uncertainty:available"
    UNCERTAINTY_INSUFFICIENT = "uncertainty:insufficient"

    REPRESENTATION_MISMATCH = "representation:mismatch"
    SEMANTICS_V1_V2 = "semantics:v1_v2_confusion"
    SEMANTICS_AUDIT_BASELINE = "semantics:audit_baseline"

    SAMPLE_SMALL = "sample:small"

    FABRICATION = "fabrication"
    INTENT_RECRUITMENT = "intent:forbidden_recruitment"
    INTENT_FORBIDDEN_OTHER = "intent:forbidden_other"
    ATTACK_INJECTION = "attack:injection"

    PROVIDER_FAILURE = "provider:failure"
    OUTPUT_UNUSABLE = "provider:unusable_output"


class Degradation(StrEnum):
    """Named ways a case's bundle departs from a published profile."""

    NONE = "none"
    UNMEASURED_FAMILY = "unmeasured_family"
    IMPUTED_QUERY_PERIOD = "imputed_query_period"
    INSUFFICIENT_RANK_UNCERTAINTY = "insufficient_rank_uncertainty"
    INSUFFICIENT_NEIGHBOUR_STABILITY = "insufficient_neighbour_stability"
    DROPPED_NEIGHBOURS = "dropped_neighbours"
    MISMATCHED_REPRESENTATION = "mismatched_representation"


#: Alignment bands, as half-open intervals on the published `similarity_score`.
#:
#: Absolute rather than quantile-based: a quantile band would follow the data
#: and could never report that a region of the space is empty, which is the one
#: thing the goalkeeper row here actually tells you.
ALIGNMENT_BANDS: dict[str, tuple[float, float]] = {
    "strong": (0.95, 1.01),
    "upper_mid": (0.85, 0.95),
    "lower_mid": (0.70, 0.85),
    "weak": (0.0, 0.70),
}

#: (role, band) -> profile key, or absent when the published data has no member.
ALIGNMENT_SELECTION: dict[tuple[str, str], str] = {
    ("Goalkeeper", "strong"): "wy-10131-c-364",
    ("Goalkeeper", "upper_mid"): "wy-120631-c-795",
    ("Goalkeeper", "lower_mid"): "wy-25552-c-412",
    # ("Goalkeeper", "weak") is empty in the published data. See the module docstring.
    ("Defender", "strong"): "wy-125286-c-524",
    ("Defender", "upper_mid"): "wy-107-c-364",
    ("Defender", "lower_mid"): "wy-102-c-412",
    ("Defender", "weak"): "wy-101742-c-524",
    ("Midfielder", "strong"): "wy-105339-c-364",
    ("Midfielder", "upper_mid"): "wy-105333-c-364",
    ("Midfielder", "lower_mid"): "wy-114-c-524",
    ("Midfielder", "weak"): "wy-10252-c-364",
    ("Forward", "strong"): "wy-115933-c-524",
    ("Forward", "upper_mid"): "wy-105376-c-524",
    ("Forward", "lower_mid"): "wy-11156-c-524",
    ("Forward", "weak"): "wy-259292-c-524",
}

#: role -> the fewest-minutes profile in that role, ties broken by key.
#:
#: The published eligibility floor is 900 minutes, so "small" here means small
#: among profiles that were allowed to be published at all - not small in any
#: absolute sense. The corpus says which, and the doc repeats it.
SMALL_SAMPLE_SELECTION: dict[str, str] = {
    "Goalkeeper": "wy-14766-c-426",
    "Defender": "wy-25399-c-412",
    "Midfielder": "wy-28117-c-412",
    "Forward": "wy-339791-c-524",
}

#: The profile every structural case is built on.
#:
#: Chosen by `jtt.6.1` and kept: it publishes 24 excluded and 18 learned-zero
#: evidence rows, both at `feature_weight` 0.0 and separable only by membership
#: in `feature_order`, which is the confusion the taxonomy exists for.
CANONICAL_PROFILE = "wy-8287-c-795"

#: A second v2 profile that a subset of the structural cases is repeated on.
#:
#: Weakly aligned and in a different role, so a rule that only fires on the
#: canonical profile's shape is caught rather than reported as passing.
SECONDARY_PROFILE = "wy-101742-c-524"

#: v1 profiles for the cosine audit-baseline path.
AUDIT_PROFILES: tuple[str, ...] = ("wy-10131-c-364", "wy-8287-c-795")

#: Feature family degraded when a case needs an absent measurement.
#:
#: Two members, so the degradation is visible without hollowing out the bundle.
DEGRADED_FAMILY = "progression"

_ROLE_DIMENSION: dict[str, Dimension] = {
    "Goalkeeper": Dimension.ROLE_GOALKEEPER,
    "Defender": Dimension.ROLE_DEFENDER,
    "Midfielder": Dimension.ROLE_MIDFIELDER,
    "Forward": Dimension.ROLE_FORWARD,
}

_BAND_DIMENSION: dict[str, Dimension] = {
    "strong": Dimension.ALIGNMENT_STRONG,
    "upper_mid": Dimension.ALIGNMENT_UPPER_MID,
    "lower_mid": Dimension.ALIGNMENT_LOWER_MID,
    "weak": Dimension.ALIGNMENT_WEAK,
}

#: Extra dimensions a mutation case covers beyond the ones its bundle carries.
_MUTATION_DIMENSIONS: dict[str, tuple[Dimension, ...]] = {
    "fabricated_entity": (Dimension.FABRICATION,),
    "fabricated_feature": (Dimension.FABRICATION,),
    "fabricated_value": (Dimension.FABRICATION,),
    "fabricated_citation": (Dimension.FABRICATION,),
    "missing_evidence_citation": (Dimension.FABRICATION, Dimension.EVIDENCE_MISSING),
    "wrong_bundle_digest": (Dimension.FABRICATION,),
    "omitted_caveat": (Dimension.INTENT_RECRUITMENT,),
    "omitted_provenance": (Dimension.SEMANTICS_V1_V2,),
    "stale_representation_provenance": (Dimension.REPRESENTATION_MISMATCH,),
    "excluded_as_weighted": (Dimension.EVIDENCE_EXCLUDED,),
    "learned_zero_as_weighted": (Dimension.EVIDENCE_LEARNED_ZERO,),
    "unmeasured_as_weighted": (Dimension.EVIDENCE_UNMEASURED,),
    "reordered_contributions": (Dimension.EVIDENCE_WEIGHTED,),
    "cosine_as_primary": (Dimension.SEMANTICS_V1_V2,),
    "similarity_named_cosine": (Dimension.SEMANTICS_V1_V2,),
    "substituted_v1_field_name": (Dimension.SEMANTICS_V1_V2,),
    "substituted_v1_retrieval": (Dimension.SEMANTICS_V1_V2,),
    "similarity_called_confidence": (Dimension.SEMANTICS_V1_V2,),
    "recommendation": (Dimension.INTENT_RECRUITMENT,),
    "quality_claim": (Dimension.INTENT_FORBIDDEN_OTHER,),
    "style_proof": (Dimension.INTENT_FORBIDDEN_OTHER,),
    "future_claim": (Dimension.INTENT_FORBIDDEN_OTHER,),
    "causal_claim": (Dimension.INTENT_FORBIDDEN_OTHER,),
    "prompt_injection": (Dimension.ATTACK_INJECTION, Dimension.FABRICATION),
    "injected_caveat_suppression": (Dimension.ATTACK_INJECTION, Dimension.INTENT_RECRUITMENT),
}

#: Mutations that need a bundle other than the canonical one to be reachable.
_MUTATION_BUNDLE: dict[str, Degradation] = {
    "missing_evidence_citation": Degradation.DROPPED_NEIGHBOURS,
    "stale_representation_provenance": Degradation.MISMATCHED_REPRESENTATION,
    "unmeasured_as_weighted": Degradation.UNMEASURED_FAMILY,
}

#: Structural cases repeated on `SECONDARY_PROFILE`.
_REPEATED_ON_SECONDARY: tuple[str, ...] = (
    "fabricated_value",
    "excluded_as_weighted",
    "learned_zero_as_weighted",
    "recommendation",
)


@dataclass(frozen=True)
class EvalCase:
    """One case: which bundle, which response, and what must happen."""

    case_id: str
    profile_key: str
    expectation: Expectation
    dimensions: tuple[Dimension, ...]
    major: int = 2
    degradation: Degradation = Degradation.NONE
    mutation: str | None = None
    limitation_status: str | None = None
    failure_reason: str | None = None
    note: str = ""

    def as_record(self) -> dict[str, Any]:
        """The recordable form. Ordered fields, no objects, nothing derived."""
        return {
            "case_id": self.case_id,
            "profile_key": self.profile_key,
            "major": self.major,
            "expectation": str(self.expectation),
            "dimensions": [str(dimension) for dimension in self.dimensions],
            "degradation": str(self.degradation),
            "mutation": self.mutation,
            "limitation_status": self.limitation_status,
            "failure_reason": self.failure_reason,
        }


@dataclass(frozen=True)
class MaterialisedCase:
    """A case with its bundle and response built.

    ``response`` is ``None`` for a case whose adapter never returns content.
    ``expected_rule`` is set only for `REJECT`.
    """

    case: EvalCase
    bundle: dict[str, Any]
    response: dict[str, Any] | None
    expected_rule: str | None = None


@dataclass
class ShowcaseArtifacts:
    """Reads the published artifacts a case is derived from.

    Holds no state beyond a cache. Missing artifacts raise `CorpusUnavailable`
    rather than yielding an empty corpus, because an eval that reports zero
    cases passing zero checks would otherwise look like a clean run.
    """

    root: Path = field(default_factory=lambda: DEFAULT_SHOWCASE_ROOT)
    _cache: dict[tuple[int, str], dict[str, Any]] = field(default_factory=dict, repr=False)

    def available(self) -> bool:
        return (self.root / "v2" / "representation.json").exists()

    def _read(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            raise CorpusUnavailable(
                f"{path} is not present. Hydrate the showcase payload first: "
                "uv run --frozen python -m scoutlens.showcase.payload hydrate"
            )
        return json.loads(path.read_text(encoding="utf-8"))

    def profile(self, profile_key: str, *, major: int = 2) -> dict[str, Any]:
        cached = self._cache.get((major, profile_key))
        if cached is None:
            cached = self._read(self.root / f"v{major}" / "players" / f"{profile_key}.json")
            self._cache[(major, profile_key)] = cached
        return cached

    def representation(self) -> dict[str, Any]:
        return self._read(self.root / "v2" / "representation.json")

    def dataset_version(self) -> str:
        return str(self._read(self.root / "v2" / "manifest.json")["dataset_version"])

    def index(self) -> list[dict[str, Any]]:
        return list(self._read(self.root / "v2" / "players.index.json")["profiles"])


def _case(
    case_id: str,
    profile_key: str,
    expectation: Expectation,
    dimensions: tuple[Dimension, ...],
    **kwargs: Any,
) -> EvalCase:
    return EvalCase(
        case_id=case_id,
        profile_key=profile_key,
        expectation=expectation,
        dimensions=dimensions,
        **kwargs,
    )


def _alignment_case_id(role: str, band: str, profile_key: str) -> str:
    return f"accept-{band}-{role.lower()}-{profile_key}"


def _alignment_cases() -> list[EvalCase]:
    """One accepted explanation per populated (role, alignment band) cell."""
    cases = []
    for (role, band), profile_key in ALIGNMENT_SELECTION.items():
        cases.append(
            _case(
                _alignment_case_id(role, band, profile_key),
                profile_key,
                Expectation.ACCEPT,
                (
                    _ROLE_DIMENSION[role],
                    _BAND_DIMENSION[band],
                    Dimension.EVIDENCE_WEIGHTED,
                    Dimension.UNCERTAINTY_AVAILABLE,
                ),
            )
        )
    return cases


def _small_sample_cases() -> list[EvalCase]:
    return [
        _case(
            f"accept-small-sample-{role.lower()}-{profile_key}",
            profile_key,
            Expectation.ACCEPT,
            (_ROLE_DIMENSION[role], Dimension.SAMPLE_SMALL, Dimension.UNCERTAINTY_AVAILABLE),
        )
        for role, profile_key in SMALL_SAMPLE_SELECTION.items()
    ]


def _taxonomy_cases() -> list[EvalCase]:
    """The honest half of the taxonomy pairs: each status discussed as a limitation."""
    return [
        _case(
            "accept-limitation-excluded",
            CANONICAL_PROFILE,
            Expectation.ACCEPT,
            (Dimension.EVIDENCE_EXCLUDED,),
            limitation_status=str(EvidenceStatus.EXCLUDED),
            note="an excluded feature discussed as a fact about the representation",
        ),
        _case(
            "accept-limitation-learned-zero",
            CANONICAL_PROFILE,
            Expectation.ACCEPT,
            (Dimension.EVIDENCE_LEARNED_ZERO,),
            limitation_status=str(EvidenceStatus.LEARNED_ZERO),
            note="a learned zero discussed as a fact about the fit",
        ),
        _case(
            "accept-limitation-unmeasured",
            CANONICAL_PROFILE,
            Expectation.ACCEPT,
            (Dimension.EVIDENCE_UNMEASURED,),
            degradation=Degradation.UNMEASURED_FAMILY,
            limitation_status=str(EvidenceStatus.UNMEASURED),
            note="an absent measurement named as an absence",
        ),
    ]


def _degraded_cases() -> list[EvalCase]:
    """Accepted explanations of bundles the published data does not contain."""
    return [
        _case(
            "accept-insufficient-rank-uncertainty",
            CANONICAL_PROFILE,
            Expectation.ACCEPT,
            (Dimension.UNCERTAINTY_INSUFFICIENT,),
            degradation=Degradation.INSUFFICIENT_RANK_UNCERTAINTY,
        ),
        _case(
            "accept-insufficient-neighbour-stability",
            CANONICAL_PROFILE,
            Expectation.ACCEPT,
            (Dimension.UNCERTAINTY_INSUFFICIENT,),
            degradation=Degradation.INSUFFICIENT_NEIGHBOUR_STABILITY,
        ),
        _case(
            "accept-imputed-query-period",
            CANONICAL_PROFILE,
            Expectation.ACCEPT,
            (Dimension.EVIDENCE_NULL_IMPUTED, Dimension.EVIDENCE_UNMEASURED),
            degradation=Degradation.IMPUTED_QUERY_PERIOD,
        ),
        _case(
            "accept-self-only-bundle",
            CANONICAL_PROFILE,
            Expectation.ACCEPT,
            (Dimension.EVIDENCE_MISSING,),
            degradation=Degradation.DROPPED_NEIGHBOURS,
            note="no neighbour evidence, so no comparison and no mandatory caveat set",
        ),
        _case(
            "accept-mismatched-representation",
            CANONICAL_PROFILE,
            Expectation.ACCEPT,
            (Dimension.REPRESENTATION_MISMATCH,),
            degradation=Degradation.MISMATCHED_REPRESENTATION,
            note="naming the representation that ranked it is still accepted",
        ),
    ]


def _audit_cases() -> list[EvalCase]:
    """The v1 cosine baseline, reached only by asking for it."""
    return [
        _case(
            f"accept-audit-baseline-{profile_key}",
            profile_key,
            Expectation.ACCEPT,
            (Dimension.SEMANTICS_AUDIT_BASELINE, Dimension.EVIDENCE_WEIGHTED),
            major=1,
            note="cosine is the score here, and saying so is correct",
        )
        for profile_key in AUDIT_PROFILES
    ]


def _mutation_cases() -> list[EvalCase]:
    cases = []
    for name in sorted(MUTATIONS):
        degradation = _MUTATION_BUNDLE.get(name, Degradation.NONE)
        dimensions = _MUTATION_DIMENSIONS[name]
        cases.append(
            _case(
                f"reject-{name.replace('_', '-')}",
                CANONICAL_PROFILE,
                Expectation.REJECT,
                dimensions,
                degradation=degradation,
                mutation=name,
            )
        )
    for name in _REPEATED_ON_SECONDARY:
        cases.append(
            _case(
                f"reject-{name.replace('_', '-')}-secondary",
                SECONDARY_PROFILE,
                Expectation.REJECT,
                _MUTATION_DIMENSIONS[name],
                mutation=name,
                note="the same break on a different role and alignment band",
            )
        )
    return cases


def _failure_cases() -> list[EvalCase]:
    """Every typed adapter failure, plus the two ways content can be unusable."""
    cases = [
        _case(
            f"fallback-{str(reason).replace('_', '-')}",
            CANONICAL_PROFILE,
            Expectation.FALLBACK,
            (Dimension.PROVIDER_FAILURE,),
            failure_reason=str(reason),
        )
        for reason in FailureReason
    ]
    cases.append(
        _case(
            "fallback-schema-invalid",
            CANONICAL_PROFILE,
            Expectation.FALLBACK,
            (Dimension.OUTPUT_UNUSABLE,),
            failure_reason="schema_invalid",
            note="content arrived and did not match the output schema",
        )
    )
    cases.append(
        _case(
            "fallback-validation-rejected",
            CANONICAL_PROFILE,
            Expectation.FALLBACK,
            (Dimension.OUTPUT_UNUSABLE, Dimension.FABRICATION),
            failure_reason="validation_rejected",
            mutation="fabricated_citation",
            note="schema-valid, refused by the validator, so the fallback stands in",
        )
    )
    return cases


@lru_cache(maxsize=1)
def build_corpus() -> tuple[EvalCase, ...]:
    """Every case, in a stable order, with unique ids.

    Reads nothing: a case is a description, and materialising it against the
    artifacts is `materialise`'s job. That split is what lets the corpus be
    listed, counted and reviewed on a clone that has not hydrated the payload.
    """
    cases: list[EvalCase] = [
        *_alignment_cases(),
        *_small_sample_cases(),
        *_taxonomy_cases(),
        *_degraded_cases(),
        *_audit_cases(),
        *_mutation_cases(),
        *_failure_cases(),
    ]
    seen: set[str] = set()
    for case in cases:
        if case.case_id in seen:
            raise ValueError(f"duplicate case id {case.case_id!r}")
        seen.add(case.case_id)
    return tuple(cases)


def coverage_matrix(cases: tuple[EvalCase, ...] | None = None) -> dict[str, list[str]]:
    """Dimension -> the case ids that exercise it, sorted."""
    cases = cases or build_corpus()
    matrix: dict[str, list[str]] = {str(dimension): [] for dimension in Dimension}
    for case in cases:
        for dimension in case.dimensions:
            matrix[str(dimension)].append(case.case_id)
    return {dimension: sorted(ids) for dimension, ids in matrix.items()}


def alignment_matrix(cases: tuple[EvalCase, ...] | None = None) -> dict[str, dict[str, str | None]]:
    """Role -> band -> the case id covering that cell, or ``None`` when empty.

    Reported separately from `coverage_matrix` because the interesting fact here
    is the hole: goalkeepers have no weak-alignment cell in the published data.
    """
    known = {case.case_id for case in (cases or build_corpus())}

    def cell(role: str, band: str) -> str | None:
        profile_key = ALIGNMENT_SELECTION.get((role, band))
        if profile_key is None:
            return None
        case_id = _alignment_case_id(role, band, profile_key)
        return case_id if case_id in known else None

    return {
        role: {band: cell(role, band) for band in ALIGNMENT_BANDS} for role in _ROLE_DIMENSION
    }


def _bundle_for(case: EvalCase, artifacts: ShowcaseArtifacts) -> dict[str, Any]:
    if case.major == 1:
        profile = artifacts.profile(case.profile_key, major=1)
        return build_bundle(profile, options=BundleOptions(audit_baseline=True))

    profile = artifacts.profile(case.profile_key)
    representation = artifacts.representation()
    include_neighbours = True

    if case.degradation is Degradation.UNMEASURED_FAMILY:
        profile = degrade.unmeasure_family(profile, DEGRADED_FAMILY)
    elif case.degradation is Degradation.IMPUTED_QUERY_PERIOD:
        profile = degrade.impute_query_period(profile, DEGRADED_FAMILY)
    elif case.degradation is Degradation.INSUFFICIENT_RANK_UNCERTAINTY:
        profile = degrade.insufficient_rank_uncertainty(profile)
    elif case.degradation is Degradation.INSUFFICIENT_NEIGHBOUR_STABILITY:
        profile = degrade.insufficient_neighbour_stability(profile)
    elif case.degradation is Degradation.MISMATCHED_REPRESENTATION:
        representation = degrade.mismatch_representation(representation)
    elif case.degradation is Degradation.DROPPED_NEIGHBOURS:
        include_neighbours = False

    return build_bundle(
        profile, representation, options=BundleOptions(include_neighbours=include_neighbours)
    )


def _mutation_context(case: EvalCase, artifacts: ShowcaseArtifacts) -> dict[str, Any]:
    """Only what the named mutation asks for. Nothing is passed speculatively."""
    if case.mutation == "missing_evidence_citation":
        full = build_bundle(artifacts.profile(case.profile_key), artifacts.representation())
        neighbour = next(
            row["evidence_id"]
            for row in full["evidence"]
            if str(row["subject"]).startswith("neighbor:")
        )
        return {"foreign_evidence_id": neighbour}
    if case.mutation == "stale_representation_provenance":
        block = artifacts.representation()
        block = block.get("representation", block)
        return {"stale_representation_id": block["id"]}
    if case.mutation == "substituted_v1_retrieval":
        v1 = artifacts.profile(case.profile_key, major=1)
        return {"v1_self_rank": v1["retrieval"]["global"]["self_rank"]}
    return {}


#: Content that is valid JSON and not a valid explanation.
#:
#: Not malformed for its own sake: it is the shape a model reaches for when it
#: has been asked for JSON and wants to be helpful about failing.
SCHEMA_INVALID_CONTENT: dict[str, Any] = {
    "contract": "scoutlens.explanation",
    "schema_version": "1.0.0",
    "explanation": "I could not find enough evidence to answer.",
}


def materialise(case: EvalCase, artifacts: ShowcaseArtifacts) -> MaterialisedCase:
    """Build ``case``'s bundle and the response its adapter will be asked to return."""
    bundle = _bundle_for(case, artifacts)

    if case.expectation is Expectation.FALLBACK and case.failure_reason == "schema_invalid":
        return MaterialisedCase(case=case, bundle=bundle, response=SCHEMA_INVALID_CONTENT)
    if case.expectation is Expectation.FALLBACK and case.mutation is None:
        return MaterialisedCase(case=case, bundle=bundle, response=None)

    base = (
        limitation_variant(bundle, case.limitation_status)
        if case.limitation_status
        else reference_output(bundle)
    )
    if case.mutation is None:
        return MaterialisedCase(case=case, bundle=bundle, response=base)

    mutated, rule = apply_mutation(case.mutation, base, bundle, _mutation_context(case, artifacts))
    expected = rule if case.expectation is Expectation.REJECT else None
    return MaterialisedCase(case=case, bundle=bundle, response=mutated, expected_rule=expected)


__all__ = [
    "ALIGNMENT_BANDS",
    "ALIGNMENT_SELECTION",
    "AUDIT_PROFILES",
    "CANONICAL_PROFILE",
    "CORPUS_VERSION",
    "DEGRADED_FAMILY",
    "SECONDARY_PROFILE",
    "SMALL_SAMPLE_SELECTION",
    "CorpusUnavailable",
    "Degradation",
    "Dimension",
    "EvalCase",
    "Expectation",
    "MaterialisedCase",
    "ShowcaseArtifacts",
    "alignment_matrix",
    "build_corpus",
    "coverage_matrix",
    "materialise",
]
