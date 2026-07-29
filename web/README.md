# ScoutLens web

Static Next.js App Router shell for the evidence-first Player Fingerprint Lab.
Scientific computation remains in Python; this package validates and reads the
versioned `scoutlens.showcase/1.0.0` artifacts.

## Toolchain

- Node `24.14.0` (`.node-version` and `.nvmrc`)
- pnpm `11.9.0` (`packageManager` and `engines`)

## Clean install and quality gates

From a clean repository clone, hydrate the pinned public player pack before
installing the web toolchain:

```bash
uv sync --frozen
uv run --frozen python -m scoutlens.showcase.payload hydrate

cd web
corepack enable
corepack install --global pnpm@11.9.0
pnpm install --frozen-lockfile
pnpm exec playwright install --with-deps chromium
pnpm release:check
```

`pnpm build` copies the four Git-tracked showcase artifacts into the static
public directory and writes the production export to `web/out`. If the optional
verified player pack from Beads `scoutlens-jtt.10` has been hydrated under the
root `public/showcase/v1/players`, it is copied too. No provider data, backend,
API route, authentication, or live network service is required.

The dependency build allowlist is explicit in `pnpm-workspace.yaml`. A newly
introduced dependency install script therefore fails closed until reviewed.

`pnpm release:check` runs the deterministic contract, lint, type, unit, static
build, gzip budget, Playwright, axe and Lighthouse gates. Playwright and
Lighthouse both exercise `web/out` through the same local production server;
the development server is never used for release evidence. The exact device,
network, cache and manual-keyboard protocol is recorded in
[`docs/flagship-quality-gates.md`](../docs/flagship-quality-gates.md).

## Contract workflow

The TypeScript declarations are generated from the Python-owned JSON Schema:

```bash
pnpm contracts:generate
pnpm contracts:check
```

Runtime validation uses the same schema through Ajv at the
`StaticShowcaseRepository` boundary. Components consume domain types returned
by `ShowcaseRepository`; they never receive unchecked fetch payloads.
