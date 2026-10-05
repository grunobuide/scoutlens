"""Every `docs/*.md` a tracked file cites is a document a fresh clone has.

`scoutlens-iex.11`. `web/e2e/prose-typography.spec.ts` named
`docs/product-roadmap.md` as the source of its gate's design. The document had
only ever existed in the session that wrote the gate; it was never committed,
and the citation looked answerable while pointing nowhere. `scoutlens-iex.8`
found the same class of defect in the frontend agent contract.

The sweep that found both was run by hand. This makes it a test, so the next
dangling citation fails the build where it is introduced instead of waiting for
someone to sweep again.
"""

from __future__ import annotations

import re
import subprocess

from scoutlens.release.manifest import REPO_ROOT

CITED_SUFFIXES = (".md", ".ts", ".tsx", ".py", ".mjs", ".yml", ".yaml")
CITATION = re.compile(r"docs/[A-Za-z0-9_./-]+\.md")

#: Synthetic `report_url` values inside test fixtures - data, not references.
FIXTURE_VALUES = {
    "docs/fixture.md": "web/tests/research-story.test.tsx",
    "docs/x.md": "tests/release/test_claims.py",
}


def _tracked() -> list[str]:
    listed = subprocess.run(
        ["git", "ls-files", "-z"], cwd=REPO_ROOT, capture_output=True, check=True
    ).stdout.decode("utf-8")
    return [path for path in listed.split("\0") if path.endswith(CITED_SUFFIXES)]


def test_no_tracked_file_cites_a_document_the_repository_lacks() -> None:
    dangling: dict[str, list[str]] = {}
    for path in _tracked():
        if path.startswith(("web/node_modules/", "node_modules/")):
            continue
        text = (REPO_ROOT / path).read_text(encoding="utf-8", errors="replace")
        for cited in set(CITATION.findall(text)):
            if FIXTURE_VALUES.get(cited) == path:
                continue
            if not (REPO_ROOT / cited).is_file():
                dangling.setdefault(cited, []).append(path)
    assert not dangling, (
        "these documents are cited but not in the repository - commit them, or point "
        f"the citation at something a clone can reach: {dangling}"
    )


def test_the_fixture_values_are_still_where_the_allowance_says() -> None:
    """An allowance that outlives its reason would hide a real citation."""
    for cited, path in FIXTURE_VALUES.items():
        assert cited in (REPO_ROOT / path).read_text(encoding="utf-8"), (
            f"{cited} is no longer in {path}; remove it from FIXTURE_VALUES"
        )
