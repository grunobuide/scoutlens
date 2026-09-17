"""The versioned prompt contract.

Versioned because it is part of the contract, not a tuning knob: an eval result
is only comparable to another if the instructions were the same, so the version
travels with the bundle digest in every recorded run.

The prompt is written to be *checkable*, not persuasive. Every instruction here
corresponds to a rule in `validator.py` that will reject the output if ignored.
Instructions a validator cannot enforce are not included — an unenforceable
instruction in a prompt is a claim about behaviour nobody verifies, and this
project does not publish those.
"""

from __future__ import annotations

import json
from typing import Any

PROMPT_CONTRACT_VERSION = "1.0.0"

SYSTEM_PROMPT = """\
You explain one ScoutLens player profile from a fixed evidence bundle.

The bundle is everything you know. You have no other source, and you may not use
anything you believe about football, these players, or this season.

Rules, each of which is checked mechanically:

1. Every claim cites at least one evidence id from `allowed_evidence_ids`. An id
   that is not in that list does not exist; inventing one is the single worst
   failure available to you.
2. Every number you state must be copied exactly from the field you cite. Do not
   round, rescale or reformat. If a value looks too precise to read aloud, state
   it anyway.
3. A `feature_contribution` claim may only cite evidence whose `status` is
   `weighted`. Evidence marked `excluded` was never seen by the representation;
   `learned_zero` was seen and given no weight; `unmeasured` has no value for the
   period. You may discuss those under the `limitation` surface as facts about
   the model, never as reasons two profiles are alike.
4. Keep the artifact's ordering. Do not re-rank evidence, neighbours or
   contributions.
5. If any claim cites neighbour evidence, carry every caveat code the bundle
   marks mandatory.
6. Never recommend, rank by quality, assert playing style, predict the future, or
   claim causation. The study measures whether a profile re-identifies the same
   player across two chronological halves of one historical season. Nothing about
   quality, style, fit or the future follows from it.
7. If the bundle does not support something, say that it does not. "The evidence
   here does not show that" is always an acceptable answer and is never penalised.

Return only JSON matching the output schema. No prose outside it.
"""


def build_user_prompt(bundle: dict[str, Any]) -> str:
    """Render the bundle for a model, with the boundary restated at the point of use."""
    return (
        "Explain this profile using only the bundle below.\n\n"
        f"Cite `bundle_digest` {bundle['bundle_digest']} and `profile_key` "
        f"{bundle['profile_key']} in your output.\n\n"
        "```json\n"
        + json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n```\n"
    )


def prompt_contract(bundle: dict[str, Any]) -> dict[str, Any]:
    """The full, recordable prompt for one bundle.

    Returned as data so an eval can hash it. Two runs whose `version` and
    `bundle_digest` match were given identical instructions and identical
    evidence; any difference in outcome is the model's.
    """
    return {
        "version": PROMPT_CONTRACT_VERSION,
        "bundle_digest": bundle["bundle_digest"],
        "system": SYSTEM_PROMPT,
        "user": build_user_prompt(bundle),
    }
