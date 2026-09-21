"""Say enough about a failure to act on it, and nothing more.

Two constraints pull against each other here. A failure report that only says
"case 41 failed" sends whoever reads it back to a debugger, which in practice
means nobody reads it. A failure report that pastes the model's answer puts
untrusted text — possibly the exact unsupported sentence the validator just
refused — into a file that gets committed, quoted and skimmed.

So a diagnostic carries the case, the rules, and short scrubbed fragments of the
validator's own detail. Model prose never travels. The validator writes its
details itself, from the bundle and from the rule that fired, which is why they
are quotable at all; the parts that can contain model-authored strings are
truncated and passed through `redact` regardless.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from scoutlens.explanations.validator import ValidationResult

#: Longest fragment of a validator detail that travels into a report.
#:
#: Enough for a rule, a field name and a number. Not enough for a sentence.
MAX_DETAIL_CHARS = 160

#: Substrings that mean a fragment is dropped rather than truncated.
#:
#: Belt and braces: nothing in this package ever puts a credential in a
#: validator detail, and a redactor that only runs where a secret is expected is
#: a redactor that runs nowhere useful.
_CREDENTIAL_MARKERS: tuple[str, ...] = (
    "authorization",
    "api_key",
    "api-key",
    "bearer ",
    "secret",
    "password",
    "token=",
    "scoutlens_model_api_key",
)

_WHITESPACE = re.compile(r"\s+")


def redact(text: str) -> str:
    """Collapse, truncate, and drop anything that looks like a credential."""
    collapsed = _WHITESPACE.sub(" ", str(text)).strip()
    lowered = collapsed.lower()
    if any(marker in lowered for marker in _CREDENTIAL_MARKERS):
        return "[redacted: fragment matched a credential marker]"
    if len(collapsed) <= MAX_DETAIL_CHARS:
        return collapsed
    return collapsed[: MAX_DETAIL_CHARS - 1] + "…"


@dataclass(frozen=True)
class FailureDiagnostic:
    """One case that did not do what the corpus said it would."""

    case_id: str
    expectation: str
    summary: str
    expected_rule: str | None = None
    rules_fired: tuple[str, ...] = ()
    details: tuple[str, ...] = ()
    evidence_count: int | None = None
    used_fallback: bool = False

    def as_record(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "expectation": self.expectation,
            "summary": self.summary,
            "expected_rule": self.expected_rule,
            "rules_fired": list(self.rules_fired),
            "details": list(self.details),
            "evidence_count": self.evidence_count,
            "used_fallback": self.used_fallback,
        }

    def __str__(self) -> str:
        head = f"{self.case_id} [{self.expectation}]: {self.summary}"
        if not self.details:
            return head
        return head + "\n  " + "\n  ".join(self.details)


def scrub_rejections(result: ValidationResult, *, limit: int = 4) -> tuple[str, ...]:
    """The first few rejections, each as one short redacted line.

    Capped because a single malformed output can produce one rejection per
    claim, and a report in which one case fills a screen is a report nobody
    finishes reading.
    """
    return tuple(redact(str(rejection)) for rejection in result.rejections[:limit])


__all__ = [
    "MAX_DETAIL_CHARS",
    "FailureDiagnostic",
    "redact",
    "scrub_rejections",
]
