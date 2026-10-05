"""One published caveat says "cosine" about weighted retrieval, by decision (`D063`).

`within_role_display_differs_from_global_model` reads "Within-role percentiles
aid display; cosine retrieval uses globally standardized values." Under v2 the
retrieval is the learned weighted similarity - cosine in the space scaled by
`sqrt(w)`, which is how contract v2 section 5 itself defines it - so the word is
imprecise rather than false, and the sentence's actual claim (display scale vs
model scale) holds.

Rewording it now would change the content digest that *is* the dataset version,
and with it the pin, the release archive and every document quoting the
identity. `D063` keeps the wording for the dataset it shipped in and makes the
next re-export reword it. This file is the "makes": the exemption is bound to one
dataset version, so a re-export that keeps the old sentence fails here instead
of quietly re-publishing it under a new identity.

v1 is untouched by all of this. Its retrieval genuinely is plain cosine, so the
sentence is exactly right there; the rewording must be v2-specific.
"""

from __future__ import annotations

import json
import re

import pytest

from scoutlens.release.manifest import REPO_ROOT
from scoutlens.showcase.caveats import CAVEATS

V2 = REPO_ROOT / "public" / "showcase" / "v2"
CODE = "within_role_display_differs_from_global_model"

#: The one dataset identity allowed to carry the sentence (`D063`).
EXEMPT_DATASET = "wyscout-2017-18-v2-332766e3a822"

CANONICAL_PROFILE = V2 / "players" / "wy-8287-c-795.json"


def _served_dataset() -> str:
    return json.loads((V2 / "manifest.json").read_text(encoding="utf-8"))["dataset_version"]


def _published_messages() -> list[str]:
    profile = json.loads(CANONICAL_PROFILE.read_text(encoding="utf-8"))
    return [caveat["message"] for caveat in profile["caveats"] if caveat["code"] == CODE]


requires_profile = pytest.mark.skipif(
    not CANONICAL_PROFILE.is_file(),
    reason="requires a hydrated public/showcase/v2 (uv run --frozen python -m scoutlens.showcase.payload hydrate)",
)


def test_the_caveat_still_exists_and_still_makes_its_real_claim() -> None:
    """Whatever the rewording, the caveat is not dropped: the display/model
    scale distinction is a real limitation a reader needs."""
    message = CAVEATS[CODE]["message"]
    assert "Within-role percentiles aid display" in message
    assert "globally standardized" in message


@requires_profile
def test_the_cosine_wording_is_exempt_only_for_the_dataset_it_shipped_in() -> None:
    dataset = _served_dataset()
    messages = _published_messages()
    assert messages, f"the canonical v2 profile no longer carries {CODE}"

    if dataset == EXEMPT_DATASET:
        # The exemption describes what actually shipped, not a hypothetical.
        assert any(re.search(r"\bcosine retrieval\b", message) for message in messages)
        return

    offending = [message for message in messages if re.search(r"\bcosine\b", message, re.IGNORECASE)]
    assert not offending, (
        f"the v2 payload was re-exported as {dataset} and still calls weighted retrieval "
        f"'cosine': {offending}. D063 kept that wording only for {EXEMPT_DATASET}. Give "
        "this caveat a v2-specific message without plain 'cosine' (v1 keeps its own, which "
        "is correct there), then remove the exemption here and in "
        "web/e2e/rendered-values.spec.ts."
    )
