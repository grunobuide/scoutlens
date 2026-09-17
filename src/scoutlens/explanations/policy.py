"""What a model may say about a ScoutLens profile, and what it may never say.

This module is the vocabulary the rest of the package is written against. It
holds no I/O and no model: it classifies evidence, names the caveats an
explanation must carry, and enumerates the intents the project forbids.

**The distinction this module exists for.** A showcase-v2 profile publishes an
``evidence_index`` covering all 32 catalogued features, but the learned diagonal
representation ranks on 28 of them. So a feature carrying ``feature_weight ==
0.0`` is one of two completely different things:

* **excluded** - absent from the representation's ``feature_order``. The model
  never saw it. It is displayed as descriptive context and contributed nothing
  to any rank.
* **learned zero** - present in ``feature_order``, and the fit assigned it no
  weight. The model *did* see it and found it carried nothing.

Weight alone cannot tell them apart; only membership in ``feature_order`` can.
Collapsing the two is the most plausible way for a fluent explanation to say
something false while citing a real number - "carries per 90 did not matter to
the model" is true of a learned zero and a category error about an excluded
feature, which the model was never given.

A third case, **unmeasured**, is a feature whose z-score is absent for the
period being described. It is not evidence of similarity or difference; it is
an absence, and an explanation may not convert it into either.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

CONTRACT: Final = "scoutlens.explanation"
"""Contract name stamped on every bundle and every accepted output."""

BUNDLE_SCHEMA_VERSION: Final = "1.0.0"
OUTPUT_SCHEMA_VERSION: Final = "1.0.0"


class EvidenceStatus(StrEnum):
    """How a feature relates to the representation that produced the ranking."""

    WEIGHTED = "weighted"
    """In ``feature_order`` with a non-zero weight. Citable as ranking evidence."""

    LEARNED_ZERO = "learned_zero"
    """In ``feature_order``, fitted to zero. Citable only as "the fit gave it no weight"."""

    EXCLUDED = "excluded"
    """Not in ``feature_order``. Descriptive context only; never ranking evidence."""

    UNMEASURED = "unmeasured"
    """No z-score for this period. An absence, not a similarity or a difference."""


#: Statuses a claim of the form "this feature drove the match" may cite.
CITABLE_AS_RANKING_EVIDENCE: Final[frozenset[EvidenceStatus]] = frozenset(
    {EvidenceStatus.WEIGHTED}
)


class ClaimSurface(StrEnum):
    """The only kinds of statement an explanation may make.

    Anything a model wants to say has to land in one of these. The list is
    deliberately short: every entry is something the published artifact can be
    held against, which is what makes a citation checkable.
    """

    SIMILARITY = "similarity"
    """How close two profiles are under the published representation."""

    FEATURE_CONTRIBUTION = "feature_contribution"
    """How much a weighted feature contributed to that closeness."""

    RETRIEVAL_OUTCOME = "retrieval_outcome"
    """Where the true profile ranked, and with what uncertainty."""

    PROVENANCE = "provenance"
    """Which representation, dataset and method produced the numbers."""

    LIMITATION = "limitation"
    """A caveat the artifact publishes."""


#: Caveat codes an explanation must carry whenever it cites neighbour evidence.
#:
#: These are the three ``critical`` severities the profile publishes. They are
#: required together rather than individually because the failure they guard is
#: a reader taking a similarity for a scouting judgement, and each closes a
#: different route to that reading: style proof, recruitment, and the team
#: confound that makes same-season retrieval easier than it looks.
MANDATORY_NEIGHBOUR_CAVEATS: Final[frozenset[str]] = frozenset(
    {
        "fingerprint_not_style_proof",
        "similarity_not_recruitment",
        "same_season_team_confound",
    }
)


class ForbiddenIntent(StrEnum):
    """Intents the project does not permit, whatever evidence is cited.

    These are not style preferences. Each one is a claim the research design
    cannot support: the study measures whether a profile re-identifies the same
    player across two chronological halves of one historical season, and
    nothing about quality, style, fit or the future follows from that.
    """

    RECOMMENDATION = "recommendation"
    """Advising a signing, replacement or shortlist."""

    QUALITY_JUDGEMENT = "quality_judgement"
    """Ranking players as better or worse."""

    STYLE_PROOF = "style_proof"
    """Treating statistical proximity as proof of playing style."""

    FUTURE_CLAIM = "future_claim"
    """Predicting performance, development, value or transfer success."""

    CAUSAL_CLAIM = "causal_claim"
    """Asserting that one measured thing caused another."""


#: Phrases that betray a forbidden intent, grouped by the intent they betray.
#:
#: Matched case-insensitively against an explanation's rendered sentences. This
#: is a backstop, not the primary control: the primary control is that every
#: sentence must cite evidence IDs that exist, and none of these claims can be
#: grounded in the published evidence. The list catches the fluent case where a
#: model cites correctly and then editorialises in the same sentence.
#:
#: Deliberately phrased as assertions. A bare topic word cannot be banned - the
#: mandatory caveats themselves contain "playing style" and "recruitment", and a
#: filter that fires on the disclaimer teaches people to drop the disclaimer.
FORBIDDEN_PHRASES: Final[dict[ForbiddenIntent, tuple[str, ...]]] = {
    ForbiddenIntent.RECOMMENDATION: (
        "should sign",
        "should recruit",
        "recommend signing",
        "recommended signing",
        "ideal replacement",
        "best replacement",
        "a good fit for",
        "shortlist",
    ),
    ForbiddenIntent.QUALITY_JUDGEMENT: (
        "better player",
        "worse player",
        "is stronger than",
        "is weaker than",
        "higher quality",
        "elite player",
    ),
    ForbiddenIntent.STYLE_PROOF: (
        "proves playing style",
        "proven playing style",
        "same playing style",
        "similar playing style",
        "plays like",
        "style twin",
    ),
    ForbiddenIntent.FUTURE_CLAIM: (
        "will improve",
        "will develop",
        "predicts future",
        "future performance",
        "transfer success",
        "market value",
    ),
    ForbiddenIntent.CAUSAL_CLAIM: (
        "because he is",
        "caused by",
        "leads to better",
        "results in better",
    ),
}
