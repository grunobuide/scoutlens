"""The production smoke gate, held to the thing it exists to catch.

`scoutlens-vif.3`. The gate's job is to fail a 200 that served the wrong page.
It could not do that: its four route sentinels were `ScoutLens`,
`Fingerprint Lab`, `How it works` and `Fingerprint Lab`, and every one of them
lives in the shared site chrome. A host serving the home page at every path
satisfied three of the four.

Two properties are asserted here, and they pull in opposite directions:

1. **Renaming the brand must not change route detection.** A rebrand is a copy
   change; a deploy gate that fails on one is a gate that gets disabled.
2. **Serving the wrong page must still fail.** Loosening the sentinel to buy
   property 1 would trade a weak check for no check at all.

Every fetch is stubbed. This suite makes no network call, so it runs in the
same offline CI as everything else, and it never sleeps — `fetch` is replaced
wholesale, so the retry backoff is never reached.
"""

from __future__ import annotations

import importlib.util
import sys
import urllib.error
from types import ModuleType
from typing import Any

import pytest

from scoutlens.release.manifest import REPO_ROOT

SCRIPT = REPO_ROOT / ".github" / "scripts" / "smoke-production.py"


def _load() -> ModuleType:
    """Import the hyphenated script by path.

    `smoke-production.py` is not an importable module name and the script is
    deliberately standard-library-only so it runs on a bare CI runner with no
    project environment. Loading it by path is what keeps that true: nothing
    here makes the script depend on the package, and nothing in the package
    imports the script.
    """
    spec = importlib.util.spec_from_file_location("smoke_production", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


smoke = _load()

BASE = "https://grunobuide.github.io/scoutlens/"

#: One asset reference, written the way Next.js writes it under a base path:
#: root-absolute and already carrying `/scoutlens`. Joining this onto a base
#: that also carries `/scoutlens` is where the doubled-prefix bug lived.
ASSET = "/scoutlens/_next/static/chunks/main-6f2a1c9d.js"


def _page(*, heading: str, brand: str = "ScoutLens", monogram: str = "SL") -> str:
    """A page carrying the full shared chrome, then one route-specific h1.

    The chrome matters more than the heading here: the nav labels are exactly
    the strings the old sentinels looked for, so a fixture without them could
    not reproduce the defect this bead fixes.
    """
    return (
        '<!doctype html><html lang="en">'
        '<head><title>' + brand + ' — Player Fingerprints</title></head><body>'
        '<a class="skip-link" href="#main-content">Skip to content</a>'
        '<header><a class="wordmark" href="/scoutlens/" aria-label="' + brand + ' home">'
        '<span aria-hidden="true">' + monogram + "</span><span>" + brand + "</span></a>"
        '<nav aria-label="Primary navigation"><ul>'
        '<li><a href="/scoutlens/">Overview</a></li>'
        '<li><a href="/scoutlens/lab/">Fingerprint Lab</a></li>'
        '<li><a href="/scoutlens/science/">How it works</a></li>'
        "</ul></nav></header>"
        '<main id="main-content"><h1>' + heading + "</h1></main>"
        "<footer>Evidence-first football analytics.</footer>"
        '<script src="' + ASSET + '"></script></body></html>'
    )


HOME_H1 = "A player leaves a reproducible fingerprint—and it still identifies them half a season later."
LAB_H1 = "Compare one player with himself."
SCIENCE_H1 = "The science is the sequence, not one headline number."

HEADINGS = {
    "": HOME_H1,
    "lab/": LAB_H1,
    "science/": SCIENCE_H1,
    "lab/?player=wy-8287-c-795": LAB_H1,
}


class Host:
    """A stand-in host. Records every URL asked for, answers from a routing table."""

    def __init__(self, pages: dict[str, str], *, headers: dict[str, str] | None = None) -> None:
        self.pages = pages
        # `is None`, not `or`: an explicitly empty header map is a real case —
        # it is how a host that sets no Cache-Control at all is simulated, and
        # `or` would silently replace it with the default.
        self.headers = {"cache-control": "max-age=600"} if headers is None else headers
        self.requested: list[str] = []

    def fetch(self, url: str, *, retry: bool = True) -> tuple[int, dict[str, str], str]:
        self.requested.append(url)
        if url in self.pages:
            return 200, dict(self.headers), self.pages[url]
        raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)  # type: ignore[arg-type]


def _site(
    *, brand: str = "ScoutLens", monogram: str = "SL", base: str = BASE
) -> dict[str, str]:
    """Every route a healthy deployment serves, plus the asset they reference."""
    pages = {
        base + route: _page(heading=heading, brand=brand, monogram=monogram)
        for route, heading in HEADINGS.items()
    }
    # Root-absolute, so it hangs off the origin regardless of the base path.
    pages["https://grunobuide.github.io" + ASSET] = "console.log(0)"
    return pages


def _install(monkeypatch: pytest.MonkeyPatch, host: Host) -> Host:
    monkeypatch.setattr(smoke, "fetch", host.fetch)
    return host


def _failures(results: list[Any]) -> list[str]:
    return [f"{r.name}: {r.detail}" for r in results if not r.ok]


# --- 1. the rebrand must not change route detection -----------------------


def test_a_healthy_site_passes_every_check(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, Host(_site()))
    routes, home = smoke.check_routes(BASE)
    results = [
        *smoke.check_https(BASE),
        *routes,
        *smoke.check_assets(BASE, home),
        *smoke.check_caching(BASE, home),
        *smoke.check_no_secrets(BASE, home),
    ]
    assert _failures(results) == []
    assert len(results) == 9, "the gate lost a check"


def test_renaming_the_wordmark_changes_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC1. The same site under the new display brand is detected identically.

    This is the property the whole bead exists for. If it did not hold, the
    display rename in `scoutlens-vif.4` would turn the deploy gate red for a
    copy change, and someone would eventually loosen the gate to ship.
    """
    before = _install(monkeypatch, Host(_site()))
    old_results, old_home = smoke.check_routes(BASE)

    after = _install(monkeypatch, Host(_site(brand="Yumusarái Labs", monogram="YL")))
    new_results, new_home = smoke.check_routes(BASE)

    assert [(r.name, r.ok) for r in old_results] == [(r.name, r.ok) for r in new_results]
    assert _failures(new_results) == []
    assert before.requested == after.requested
    assert "ScoutLens" in old_home and "ScoutLens" not in new_home
    assert "Yumusarái Labs" in new_home


def test_no_sentinel_is_a_brand_or_chrome_string() -> None:
    """The defect, stated as a property rather than a story.

    Each sentinel must be absent from the other routes' pages. A phrase that
    appears in the header, nav or footer fails this by construction.
    """
    for route, expected in smoke.EXPECTED_TEXT.items():
        for other, heading in HEADINGS.items():
            page = _page(heading=heading)
            if HEADINGS[other] == HEADINGS[route]:
                assert expected in page, f"{route!r}'s sentinel is missing from its own page"
            else:
                assert expected not in page, (
                    f"{route!r}'s sentinel {expected!r} also appears on {other!r} — "
                    "it is chrome, not route-specific content"
                )


def test_the_old_sentinels_would_have_passed_the_wrong_page() -> None:
    """Why the change was needed, asserted instead of asserted-in-a-comment."""
    home = _page(heading=HOME_H1)
    for retired in ("ScoutLens", "Fingerprint Lab", "How it works"):
        assert retired in home
        assert retired not in smoke.EXPECTED_TEXT.values()


# --- 2. serving the wrong page must still fail ---------------------------


@pytest.mark.parametrize("wrong", ["lab/", "science/"])
def test_the_home_page_served_at_another_route_fails(
    monkeypatch: pytest.MonkeyPatch, wrong: str
) -> None:
    """AC2. The exact failure the old sentinels could not see.

    Under the retired values this passed: the home page carries `Fingerprint
    Lab` in its nav four times and `How it works` twice.
    """
    pages = _site()
    pages[BASE + wrong] = _page(heading=HOME_H1)
    _install(monkeypatch, Host(pages))

    results, _ = smoke.check_routes(BASE)
    failed = _failures(results)
    assert len(failed) == 1, failed
    assert failed[0].startswith(f"route {wrong}")
    assert "is not in the page" in failed[0]


def test_an_empty_200_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    pages = _site()
    pages[BASE + "science/"] = ""
    _install(monkeypatch, Host(pages))

    results, _ = smoke.check_routes(BASE)
    assert len(_failures(results)) == 1


def test_a_missing_route_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    pages = _site()
    del pages[BASE + "lab/?player=wy-8287-c-795"]
    _install(monkeypatch, Host(pages))

    results, _ = smoke.check_routes(BASE)
    failed = _failures(results)
    assert len(failed) == 1
    assert "404" in failed[0]


def test_the_shareable_deep_link_is_checked_separately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The query string is the point: a static host has no router.

    `/lab/?player=…` only resolves if the path itself is a real file, so the
    deep link cannot be folded into the `lab/` check.
    """
    assert "lab/?player=wy-8287-c-795" in smoke.ROUTES
    pages = _site()
    pages[BASE + "lab/?player=wy-8287-c-795"] = _page(heading=SCIENCE_H1)
    _install(monkeypatch, Host(pages))

    results, _ = smoke.check_routes(BASE)
    failed = _failures(results)
    assert len(failed) == 1
    assert "player=wy-8287-c-795" in failed[0]


# --- the subpath, where the gate has already been wrong once -------------


def test_asset_urls_are_not_prefixed_twice(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC2's `/scoutlens/` coverage. The regression guard for the #122 bug.

    An earlier version stripped the leading slash off a ref that already
    carried the base path, producing `/scoutlens/scoutlens/_next/…`. It passed
    locally because at an origin root `/_next/x` and `_next/x` resolve
    identically — only a subpath deploy can tell the difference, which is
    exactly why this test pins the subpath case.
    """
    host = _install(monkeypatch, Host(_site()))
    _, home = smoke.check_routes(BASE)
    host.requested.clear()

    results = smoke.check_assets(BASE, home)

    assert _failures(results) == []
    assert host.requested == ["https://grunobuide.github.io" + ASSET]
    assert not any("/scoutlens/scoutlens/" in url for url in host.requested)


def test_the_same_doubling_is_absent_from_the_cache_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The second call site. Fixing only the first one left this one failing."""
    host = _install(monkeypatch, Host(_site()))
    _, home = smoke.check_routes(BASE)
    host.requested.clear()

    results = smoke.check_caching(BASE, home)

    assert _failures(results) == []
    assert not any("/scoutlens/scoutlens/" in url for url in host.requested)


def test_an_unserved_asset_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """The base-path mistake and the Jekyll strip: HTML intact, page blank."""
    pages = _site()
    del pages["https://grunobuide.github.io" + ASSET]
    _install(monkeypatch, Host(pages))

    _, home = smoke.check_routes(BASE)
    results = smoke.check_assets(BASE, home)
    assert len(_failures(results)) == 1
    assert "404" in _failures(results)[0]


def test_a_page_referencing_no_asset_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    results = smoke.check_assets(BASE, "<html><body><h1>hi</h1></body></html>")
    assert len(_failures(results)) == 1
    assert "references no _next asset" in results[0].detail


# --- 3. the other checks keep their previous behaviour -------------------


def test_https_is_still_required() -> None:
    assert smoke.check_https(BASE)[0].ok
    assert not smoke.check_https("http://grunobuide.github.io/scoutlens/")[0].ok


def test_a_secret_marker_in_the_html_still_fails() -> None:
    assert smoke.check_no_secrets(BASE, _page(heading=HOME_H1))[0].ok
    for marker in smoke.SECRET_MARKERS:
        leaked = _page(heading=HOME_H1).replace("</footer>", f"{marker}</footer>")
        result = smoke.check_no_secrets(BASE, leaked)[0]
        assert not result.ok, f"{marker} passed the secret scan"


def test_hard_cached_html_still_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reported, not enforced, where the host decides — but `immutable` HTML is a defect."""
    _install(
        monkeypatch,
        Host(_site(), headers={"cache-control": "public, max-age=31536000, immutable"}),
    )
    _, home = smoke.check_routes(BASE)
    results = smoke.check_caching(BASE, home)
    assert not results[0].ok
    assert "immutable" in results[0].detail


def test_a_missing_asset_cache_header_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, Host(_site(), headers={}))
    _, home = smoke.check_routes(BASE)
    results = smoke.check_caching(BASE, home)
    assert not results[1].ok
    assert "(none)" in results[1].detail


def test_the_retry_statuses_are_only_the_ones_propagation_explains() -> None:
    """A 403 must not be retried: waiting will not change it."""
    assert 403 not in smoke.RETRY_STATUSES
    assert {404, 500, 502, 503, 504} <= smoke.RETRY_STATUSES


def test_usage_without_a_url_is_an_error_not_a_pass() -> None:
    assert smoke.main(["smoke-production.py"]) == 2


def test_the_script_imports_nothing_from_this_project() -> None:
    """It runs on a bare CI runner with no project environment.

    A single `from scoutlens import …` would make the deploy gate depend on
    `uv sync`, which is the opposite of what a smoke check should need.
    """
    source = SCRIPT.read_text(encoding="utf-8")
    assert "scoutlens." not in source.replace("grunobuide.github.io/scoutlens", "")
    assert "import scoutlens" not in source


def test_the_suite_covers_every_route_the_gate_checks() -> None:
    """A route added to the script without a heading here would test nothing."""
    assert set(smoke.ROUTES) == set(smoke.EXPECTED_TEXT) == set(HEADINGS)


def test_the_script_path_is_where_the_workflow_expects_it() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "deploy.yml").read_text(encoding="utf-8")
    assert ".github/scripts/smoke-production.py" in workflow
    assert SCRIPT.is_file()
