#!/usr/bin/env python
"""Smoke the published site, against the URL that was actually deployed.

    python .github/scripts/smoke-production.py https://owner.github.io/scoutlens/ [commit]

The optional second argument is the commit the deploy just published. Given
it, the script also asserts the delivered HTML names that commit, which is
the one thing every other check here would pass on a stale deployment.

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
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from urllib.parse import urljoin

TIMEOUT = 30

#: A CDN-backed host is not instantly consistent, so a miss is retried briefly.
#:
#: **Honest provenance for this constant**: it was added after the first deploy
#: failed with every asset 404ing, on the theory that the assets had not yet
#: propagated. That theory was wrong. The real cause was a URL-joining bug in
#: `check_assets` below, which requested `/scoutlens/scoutlens/…`; the site was
#: serving correctly the whole time.
#:
#: The retry is kept anyway, because a deploy gate that hits a CDN seconds after
#: publication genuinely can race it, and a gate that cries wolf is a gate
#: nobody believes. But it is kept on that reasoning, not on the incident that
#: prompted it — an invented justification in a comment is worse than no comment.
#:
#: Only statuses propagation can explain are retried. A 403 or a malformed
#: response fails immediately, because waiting will not change it.
RETRY_STATUSES = frozenset({404, 500, 502, 503, 504})
RETRY_DELAYS = (2, 5, 10, 20)

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
#:
#: Each value is that route's own `h1`. Nothing here is a brand string, a nav
#: label or a footer line, and that is the whole point: the previous sentinels
#: were `ScoutLens`, `Fingerprint Lab`, `How it works` and `Fingerprint Lab`,
#: and **every one of them is in the shared site chrome**. Measured against
#: production, the home page alone contains `Fingerprint Lab` four times and
#: `How it works` twice — so three of the four route checks would have passed
#: on a host that served the home page at every path. The check that exists to
#: catch "a 200 that served the wrong page" could not have caught it.
#:
#: These four phrases were measured on the live site and form a clean diagonal:
#: each appears twice on its own route and zero times on the other two.
#:
#: They are also load-bearing elsewhere, so they cannot drift silently:
#: `web/scripts/check-static-output.mjs` asserts the home phrase and
#: `web/e2e/claims-consistency.spec.ts` asserts it against the rendered page.
#:
#: If a route's `h1` is ever rewritten, this gate fails loudly and the fix is a
#: new route-specific phrase — never a shorter one, and never a header or
#: footer string that every route would satisfy.
EXPECTED_TEXT = {
    "": "A player leaves a reproducible fingerprint",
    "lab/": "Compare one player with himself.",
    "science/": "The science is the sequence, not one headline number.",
    "lab/?player=wy-8287-c-795": "Compare one player with himself.",
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


def fetch(url: str, *, retry: bool = True) -> tuple[int, dict[str, str], str]:
    """Fetch, retrying the statuses a propagating CDN produces.

    Retries only what propagation can explain. A 403 or a malformed response is
    returned immediately, because waiting will not change it.
    """
    delays = RETRY_DELAYS if retry else ()
    for attempt in range(len(delays) + 1):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "scoutlens-smoke"})
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310
                body = response.read()
                headers = {k.lower(): v for k, v in response.headers.items()}
                return response.status, headers, body.decode("utf-8", errors="replace")
        except urllib.error.HTTPError as error:
            if error.code not in RETRY_STATUSES or attempt == len(delays):
                raise
        except OSError:
            if attempt == len(delays):
                raise
        wait = delays[attempt]
        print(f"    ... {url} not ready, retrying in {wait}s", flush=True)
        time.sleep(wait)
    raise RuntimeError("unreachable")  # pragma: no cover


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
        # `urljoin` already resolves a root-absolute ref against the origin, so
        # it must be passed through untouched. An earlier version stripped the
        # leading slash first, which on a subpath deploy produced
        # `/scoutlens/scoutlens/_next/…` and 404'd every asset on a site that was
        # serving them perfectly well.
        #
        # It passed locally because at the origin root `/_next/x` and `_next/x`
        # resolve identically — the self-test could not have caught it, and the
        # first real deploy did.
        url = urljoin(base, ref)
        try:
            status, _, _ = fetch(url)
            if status != 200:
                missing.append(f"{ref} -> HTTP {status}")
        except (urllib.error.HTTPError, OSError) as error:
            missing.append(f"{ref} -> {error}")

    if missing:
        return [Result("assets", False, "; ".join(missing))]
    return [Result("assets", True, f"{len(refs)} referenced, {min(len(refs), 8)} fetched")]


#: What the cache headers must satisfy, as a floor rather than an exact value
#: (`scoutlens-uze.18`).
#:
#: This project does not set these headers — GitHub Pages does, and allows no
#: override — so the gate asserts what the site RELIES ON, not what the host
#: currently happens to send. Pinning the exact observed value would turn a host
#: improvement into a red build, which is the wrong incentive for a number
#: nobody here controls.
#:
#: Hashed assets: at least ten minutes. The filenames are content-addressed, so
#: a stale copy is never wrong; the floor exists to catch the host dropping
#: caching altogether. `immutable`, or a year, passes — that is the outcome this
#: project would prefer and cannot ask for.
#:
#: HTML: must NOT be immutable and must stay under a day. A stale HTML document
#: IS wrong, because it can reference assets a later deploy removed.
MIN_ASSET_MAX_AGE = 600
MAX_HTML_MAX_AGE = 86_400

MAX_AGE = re.compile(r"\bmax-age\s*=\s*(\d+)")


def _max_age(header: str) -> int | None:
    """Seconds from a Cache-Control header, or None when it does not say."""
    match = MAX_AGE.search(header)
    return int(match.group(1)) if match else None


def check_caching(base: str, home: str) -> list[Result]:
    """Assert the cache policy the site depends on, as a floor.

    This used to report rather than assert, because the host owns the values.
    That left the one claim the project had already got wrong — the hosting ADR
    said hashed assets were served `immutable`, measured from the local dev
    server, which sets those headers itself — with nothing to catch it but a
    human reading output. It asserts now (`scoutlens-uze.18`).
    """
    results: list[Result] = []
    try:
        _, html_headers, _ = fetch(base)
    except OSError as error:
        return [Result("cache headers", False, str(error))]

    html_cache = html_headers.get("cache-control", "(none)")
    html_age = _max_age(html_cache)
    html_ok = "immutable" not in html_cache and (html_age is None or html_age <= MAX_HTML_MAX_AGE)
    results.append(
        Result(
            "html is not cached hard",
            html_ok,
            f"Cache-Control: {html_cache} (must not be immutable, max-age <= {MAX_HTML_MAX_AGE})",
        )
    )

    refs = sorted(set(ASSET_REF.findall(home)))
    if refs:
        # Same rule as `check_assets`: pass the ref through untouched. This was
        # the second call site of the same bug, and fixing only the first one
        # left this check failing while the rest went green — which is precisely
        # how a half-fixed bug survives.
        asset_url = urljoin(base, refs[0])
        try:
            _, asset_headers, _ = fetch(asset_url)
            asset_cache = asset_headers.get("cache-control", "(none)")
            asset_age = _max_age(asset_cache)
            cacheable = "immutable" in asset_cache or (
                asset_age is not None and asset_age >= MIN_ASSET_MAX_AGE
            )
            results.append(
                Result(
                    "hashed assets are cacheable",
                    cacheable,
                    f"Cache-Control: {asset_cache} "
                    f"(need immutable or max-age >= {MIN_ASSET_MAX_AGE})",
                )
            )
        except OSError as error:
            results.append(Result("hashed assets are cacheable", False, str(error)))
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


def check_build_identity(home: str, expected: str) -> list[Result]:
    """The page must name the commit that built it (`scoutlens-uze.20`).

    Next bakes the build ID into the flight payload and into
    `_next/static/<buildId>/`, and the deploy workflow sets that ID to the
    commit it checked out. So this closes the loop the other checks cannot:
    every other check here would pass just as happily against a stale
    deployment of an older commit.
    """
    return [
        Result(
            "the page names the deployed commit",
            expected in home,
            f"expected {expected[:12]} in the delivered HTML",
        )
    ]


def check_https(base: str) -> list[Result]:
    return [Result("served over HTTPS", base.startswith("https://"), base)]


def main(argv: list[str]) -> int:
    if not 2 <= len(argv) <= 3:
        print(__doc__, file=sys.stderr)
        return 2
    base = argv[1]
    if not base.endswith("/"):
        base += "/"
    # Optional, so the script stays usable standalone against any deployment —
    # which is how `scoutlens-vif.6` audited production without a build to
    # compare against.
    expected_build = argv[2].strip() if len(argv) == 3 else ""

    print(f"smoking {base}\n")
    route_results, home = check_routes(base)
    results = [
        *check_https(base),
        *route_results,
        *(check_assets(base, home) if home else [Result("assets", False, "home page not fetched")]),
        *(check_caching(base, home) if home else []),
        *(check_no_secrets(base, home) if home else []),
        *(check_build_identity(home, expected_build) if home and expected_build else []),
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
