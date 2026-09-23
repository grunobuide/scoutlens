#!/usr/bin/env python
"""Smoke the published site, against the URL that was actually deployed.

    python .github/scripts/smoke-production.py https://owner.github.io/scoutlens/

`scoutlens-jtt.7.2` AC4 and AC6. Checks the things a static deploy gets wrong and
a local server cannot tell you about: the subpath actually resolves, direct
navigation to a deep route works without a rewrite rule, the JavaScript the page
references is really there, immutable assets carry a long cache and the HTML does
not, and nothing that looks like a secret reached the bundle.

**Deliberately not Lighthouse or axe.** Those run against the built export in
`quality`, on every commit, with budgets. Repeating them here would be slower and
would tell us the same thing; what only production can answer is whether the
*hosting* serves what the build produced.

Standard library only, so it runs with no project environment and no install.
"""

from __future__ import annotations

import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from urllib.parse import urljoin

TIMEOUT = 30

#: Routes that must survive direct navigation, including a shareable deep link.
#:
#: The query string is the point of the last one: a static host has no router,
#: so `/lab/?player=…` only works if the path itself resolves to a real file.
ROUTES = (
    "",
    "lab/",
    "science/",
    "lab/?player=wy-8287-c-795",
)

#: Text each route must contain, so a 200 that served the wrong page still fails.
EXPECTED_TEXT = {
    "": "ScoutLens",
    "lab/": "Fingerprint Lab",
    "science/": "How it works",
    "lab/?player=wy-8287-c-795": "Fingerprint Lab",
}

SECRET_MARKERS = (
    "SCOUTLENS_MODEL_API_KEY",
    "-----BEGIN",
    "AKIA",
    "ghp_",
    "xoxb-",
)

ASSET_REF = re.compile(r'(?:src|href)="([^"]*_next/static/[^"]+)"')


@dataclass
class Result:
    name: str
    ok: bool
    detail: str = ""

    def __str__(self) -> str:
        return f"[{'PASS' if self.ok else 'FAIL'}] {self.name}" + (
            f" - {self.detail}" if self.detail else ""
        )


def fetch(url: str) -> tuple[int, dict[str, str], str]:
    request = urllib.request.Request(url, headers={"User-Agent": "scoutlens-smoke"})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310
        body = response.read()
        headers = {k.lower(): v for k, v in response.headers.items()}
        return response.status, headers, body.decode("utf-8", errors="replace")


def check_routes(base: str) -> tuple[list[Result], str]:
    results: list[Result] = []
    home = ""
    for route in ROUTES:
        url = urljoin(base, route)
        try:
            status, _, body = fetch(url)
        except urllib.error.HTTPError as error:
            results.append(Result(f"route {route or '/'}", False, f"HTTP {error.code}"))
            continue
        except OSError as error:
            results.append(Result(f"route {route or '/'}", False, str(error)))
            continue

        expected = EXPECTED_TEXT[route]
        if status != 200:
            results.append(Result(f"route {route or '/'}", False, f"HTTP {status}"))
        elif expected not in body:
            results.append(
                Result(f"route {route or '/'}", False, f"200 but {expected!r} is not in the page")
            )
        else:
            results.append(Result(f"route {route or '/'}", True))
        if route == "":
            home = body
    return results, home


def check_assets(base: str, home: str) -> list[Result]:
    """Every asset the home page references must actually be served.

    This is the check that catches a base-path mistake and a Jekyll strip, both
    of which leave the HTML intact and the page blank.
    """
    refs = sorted(set(ASSET_REF.findall(home)))
    if not refs:
        return [Result("assets", False, "the home page references no _next asset at all")]

    missing = []
    for ref in refs[:8]:
        url = urljoin(base, ref.lstrip("/") if not ref.startswith("http") else ref)
        try:
            status, _, _ = fetch(url)
            if status != 200:
                missing.append(f"{ref} -> HTTP {status}")
        except (urllib.error.HTTPError, OSError) as error:
            missing.append(f"{ref} -> {error}")

    if missing:
        return [Result("assets", False, "; ".join(missing))]
    return [Result("assets", True, f"{len(refs)} referenced, {min(len(refs), 8)} fetched")]


def check_caching(base: str, home: str) -> list[Result]:
    """Immutable assets should be cacheable; HTML should not be cached hard.

    Reported rather than enforced where the host decides the policy: GitHub Pages
    sets its own headers and this project does not control them. A finding here
    is a fact to record in the hosting ADR, not necessarily a defect.
    """
    results: list[Result] = []
    try:
        _, html_headers, _ = fetch(base)
    except OSError as error:
        return [Result("cache headers", False, str(error))]

    html_cache = html_headers.get("cache-control", "(none)")
    results.append(
        Result(
            "html is not cached hard",
            "immutable" not in html_cache,
            f"Cache-Control: {html_cache}",
        )
    )

    refs = sorted(set(ASSET_REF.findall(home)))
    if refs:
        asset_url = urljoin(base, refs[0].lstrip("/"))
        try:
            _, asset_headers, _ = fetch(asset_url)
            results.append(
                Result(
                    "asset cache header present",
                    "cache-control" in asset_headers,
                    f"Cache-Control: {asset_headers.get('cache-control', '(none)')}",
                )
            )
        except OSError as error:
            results.append(Result("asset cache header present", False, str(error)))
    return results


def check_no_secrets(base: str, home: str) -> list[Result]:
    found = [marker for marker in SECRET_MARKERS if marker in home]
    return [
        Result(
            "no secret in the delivered HTML",
            not found,
            f"found {found}" if found else "",
        )
    ]


def check_https(base: str) -> list[Result]:
    return [Result("served over HTTPS", base.startswith("https://"), base)]


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    base = argv[1]
    if not base.endswith("/"):
        base += "/"

    print(f"smoking {base}\n")
    route_results, home = check_routes(base)
    results = [
        *check_https(base),
        *route_results,
        *(check_assets(base, home) if home else [Result("assets", False, "home page not fetched")]),
        *(check_caching(base, home) if home else []),
        *(check_no_secrets(base, home) if home else []),
    ]

    for result in results:
        print(result)

    failed = [result for result in results if not result.ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    if failed:
        print("\nProduction does not serve what the build produced.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
