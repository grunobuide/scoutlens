# Hosting ADR — static deployment for ScoutLens v1

**Status:** accepted, 2026-09-23. **Bead:** `scoutlens-jtt.7.2`.
**Decision:** GitHub Pages, project subpath, deployed by GitHub Actions from the
commit whose quality gates passed.

---

## Context

ScoutLens v1 is a static export: four prerendered routes, no backend, no
database, no runtime model call. `docs/release-candidate-v1.md` froze the
candidate at version `1.0.0`. What remains is to serve it.

The constraints are not negotiable, and they narrow the field before any
preference does:

* **No runtime backend.** The architecture publishes a versioned artifact and
  the site consumes it; there is nothing to run.
* **No credential in the deployed surface.** The site makes zero third-party
  requests, verified in a browser during the release audit.
* **The deploy consumes the audited commit**, not a rebuild of something else.
* **Rollback must exist and must be rehearsed**, not assumed.

## Decision

**GitHub Pages**, serving the project repository at
`https://grunobuide.github.io/scoutlens/`.

The bead's design says to default to GitHub Pages and use Cloudflare Pages *only
if a documented base-path or header smoke test fails*. So the base-path test was
the deciding experiment, and it was run rather than reasoned about.

### The base-path test, and what it found

A project Pages site serves from `/<repo>/`, not from the origin root. Every
asset reference the export emits is **root-absolute** — `/_next/static/…`,
`/lab/` — and nothing in the codebase read a base path. Deployed as-is, the site
would have returned its HTML and then 404'd on every script it referenced: a
blank page with a 200.

Tested by building with a base path, staging the output under `/scoutlens/`, and
driving a real browser against it:

| Check | Result |
|---|---|
| `/scoutlens/` loads | 11 requests, **all 200**, zero console errors |
| `/scoutlens/lab/` direct navigation | renders, no errors |
| `/scoutlens/lab/?player=wy-8287-c-795` — the shareable deep link | renders the selected profile |
| `/scoutlens/science/` | renders, no errors |
| Runtime data fetches | **none** — profiles are baked in at prerender |

That last row matters more than it looks. Because the site fetches no data at
runtime, there is no client-side URL construction that a base path could break
after load. The whole risk is in the build, and the build is where it was fixed.

**So the smoke test passed, and the default stands.** Cloudflare Pages was not
adopted.

### How the base path is applied

`next.config.ts` reads `SCOUTLENS_BASE_PATH`, and the deploy workflow sets it to
the repository name. It is **opt-in**, not hard-coded, so the default build,
every unit test and the entire e2e suite continue to run at the root. A base
path baked into the config would make local development differ from what CI
checks — and the difference would only show up in production, which is the worst
place to learn about it.

## Rejected alternatives

### Cloudflare Pages

Serves at the root of a project subdomain, so no base path would be needed —
genuinely the simpler deployment.

Rejected because the base-path test passed, and because it costs more than it
saves here: a second vendor account, a deploy token held as a repository secret,
and a second place where the publishing configuration lives. The project's whole
posture is that a clean clone reproduces everything with no credential; adding a
deploy secret to avoid a two-line config change is the wrong trade.

Worth reconsidering if a custom domain is ever wanted, where its edge rules and
header control become real advantages.

### A user site at `grunobuide.github.io`

Would serve at the root and need no base path, but the repository would have to
be named `grunobuide.github.io`, and that name is a personal namespace rather
than this project's. It also makes a second project awkward forever.

### Netlify, Vercel, S3 + CloudFront

All work. All introduce an account, a token and a bill for a four-page static
site that GitHub already hosts for free from the repository it lives in. None
offers anything this project needs.

## Consequences

**The URL contains a subpath.** `https://grunobuide.github.io/scoutlens/`. A
custom domain would remove it and is a later decision, not a blocker.

**Deploys are gated on green.** The workflow triggers on *completion* of the
`quality` workflow and refuses to publish unless it succeeded. A push-triggered
deploy would race the tests and could publish a commit whose e2e or Lighthouse
gates were still red — the one failure a deploy pipeline must not have.

**Jekyll is disabled explicitly.** `_next/` and the `__next*.txt` payloads all
begin with an underscore, which Jekyll strips. The Actions Pages pipeline does
not run Jekyll, but a `.nojekyll` file costs nothing and removes the question
permanently. The failure it prevents — a site that loses its JavaScript
directory — is silent and total.

**Headers are the host's.** GitHub Pages sets its own caching and does not allow
custom headers. Measured on the built export: HTML `no-cache`, hashed assets
`public, max-age=31536000, immutable`. That is the behaviour this project wants
and it happens to be the default, which is luck rather than design — recorded so
the next person knows it is not enforced by anything here. If custom headers
ever become a requirement, that is the trigger to revisit Cloudflare.

## Rollback

**Redeploy the previous commit.** `workflow_dispatch` takes a `ref` input, so
rolling back is dispatching the deploy workflow with an earlier SHA.

No revert commit, no history rewrite, and the restored state is a commit that
already passed its own gates. The rehearsal is recorded in
`docs/release-candidate-v1.md`.

Rollback is *not* re-running an old workflow: that would rebuild from whatever
the action versions resolve to today. Dispatching a SHA rebuilds that commit's
own tree from its own lockfiles.

## Verification

`.github/scripts/smoke-production.py` runs against the URL that was actually
published, as a second job that depends on the deploy. It checks what only
production can answer: that the subpath resolves, that direct navigation to a
deep route works without a rewrite rule, that the referenced JavaScript is
really served, that cache headers are sane, and that nothing secret-shaped
reached the delivered HTML.

It deliberately does **not** repeat Lighthouse or axe. Those run against the
built export in `quality`, on every commit, with budgets. Re-running them here
would be slower and would answer a question already answered.
