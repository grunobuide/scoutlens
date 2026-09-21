"""The guard that decides whether a missing payload is a choice or an outage.

This is the only test in this directory that must run on an un-hydrated clone,
because it is about what happens when the payload is absent. It carries no
`requires_showcase` mark for that reason.

`scoutlens-iex.10`: for as long as the `pytest` CI job did not hydrate, every
other test here skipped and the job went green. The skip guard was doing its
job for a developer and hiding an outage in CI, and nothing distinguished the
two situations. `SCOUTLENS_REQUIRE_SHOWCASE` is that distinction, so it gets
tested rather than assumed.
"""

from __future__ import annotations

from pathlib import Path

import conftest as explanations_conftest
import pytest


def test_a_present_payload_is_never_an_outage(monkeypatch: pytest.MonkeyPatch) -> None:
    """With the payload hydrated the flag changes nothing, in either state."""
    for require in (True, False):
        monkeypatch.setattr(explanations_conftest, "REQUIRE_SHOWCASE", require)
        guard = explanations_conftest._guard(True, what="a test payload", reason="absent")
        assert guard.args[0] is False, "a present payload must never skip"


def test_an_absent_payload_skips_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """A developer's un-hydrated clone stays pleasant to work in."""
    monkeypatch.setattr(explanations_conftest, "REQUIRE_SHOWCASE", False)

    guard = explanations_conftest._guard(False, what="a test payload", reason="absent")
    assert guard.args[0] is True
    assert guard.kwargs["reason"] == "absent"


def test_an_absent_payload_is_an_error_when_the_flag_is_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """In CI the same absence is an outage, and says so loudly."""
    monkeypatch.setattr(explanations_conftest, "REQUIRE_SHOWCASE", True)

    with pytest.raises(RuntimeError) as error:
        explanations_conftest._guard(
            False, what="a hydrated public/showcase/v2", reason="absent"
        )

    message = str(error.value)
    assert "would silently skip" in message
    assert "scoutlens.showcase.payload hydrate" in message
    assert "scoutlens-iex.10" in message


def test_the_flag_is_read_from_the_environment() -> None:
    """The workflow sets an env var; nothing else wires it up."""
    assert isinstance(explanations_conftest.REQUIRE_SHOWCASE, bool)
    source = Path(explanations_conftest.__file__).read_text(encoding="utf-8")
    assert 'os.environ.get("SCOUTLENS_REQUIRE_SHOWCASE"' in source


def test_the_error_message_survives_a_non_utf8_console() -> None:
    """CI log encoding is not this repository's to choose.

    A remedy nobody can read is not a remedy, and the first version of this
    message rendered its em-dash as a replacement character on the Windows
    console it was developed on.
    """
    source = Path(explanations_conftest.__file__).read_text(encoding="utf-8")
    start = source.index("SCOUTLENS_REQUIRE_SHOWCASE=1 and {what}")
    source[start : start + 400].encode("ascii")


def test_the_ci_workflow_hydrates_before_pytest() -> None:
    """The step this bead exists to add, asserted where it cannot drift unnoticed.

    A comment in the workflow explains why it is there; this is what notices if
    someone removes it. The two together are the whole fix — the hydrate step
    makes the tests run, and the flag makes its removal loud.
    """
    github = Path(explanations_conftest.REPO_ROOT) / ".github"
    workflow = github / "workflows" / "tests.yml"
    if not workflow.exists():  # pragma: no cover - not every checkout ships CI config
        pytest.skip("no workflow file in this checkout")

    text = workflow.read_text(encoding="utf-8")
    hydrate = text.index("hydrate-showcase.sh")
    pytest_run = text.index("pytest -q")
    assert hydrate < pytest_run, "hydrate must come before the pytest run it feeds"
    assert 'SCOUTLENS_REQUIRE_SHOWCASE: "1"' in text

    script = github / "scripts" / "hydrate-showcase.sh"
    assert script.exists(), "the workflow calls a script that is not in the checkout"
    assert "scoutlens.showcase.payload hydrate" in script.read_text(encoding="utf-8")
