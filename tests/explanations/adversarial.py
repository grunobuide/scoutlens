"""The adversarial fixture set, as the validator tests have always seen it.

The mutations themselves moved into `scoutlens.explanations.evals.mutations`
when `jtt.6.3` made the corpus a shipped deliverable. This module is the view
`test_validator.py` needs: the subset that runs against a plain published
bundle, with no extra context and no degradation.

Keeping it as a view rather than a copy is deliberate. Two lists of "every way
an explanation can lie" would drift, and the one that drifted would be the one
nobody was reading — which is the failure mode `CLAUDE.md` names for duplicated
policy.
"""

from __future__ import annotations

from typing import Any

from scoutlens.explanations.evals.mutations import MUTATIONS, REQUIRES_SETUP, apply_mutation

#: case name -> (mutation, the rule that must fire).
#:
#: Everything except the four cases that need a context value or a degraded
#: bundle to be reachable at all; the corpus runs those, with the setup they
#: require, in `tests/explanations/test_evals_corpus.py`.
ADVERSARIAL: dict[str, tuple[Any, str]] = {
    name: entry for name, entry in MUTATIONS.items() if name not in REQUIRES_SETUP
}


def build_case(
    name: str, valid: dict[str, Any], bundle: dict[str, Any]
) -> tuple[dict[str, Any], str]:
    """Break a copy of ``valid`` the one way ``name`` describes."""
    return apply_mutation(name, valid, bundle)


__all__ = ["ADVERSARIAL", "build_case"]
