# Changelog

All notable changes to ScoutLens. This project records decisions in
[`docs/decisions-log.md`](docs/decisions-log.md); this file records releases.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning is [semantic](https://semver.org/spec/v2.0.0.html): the public
surface being versioned is the **published artifact contract**
(`scoutlens.showcase`), the **explanation contract**
(`scoutlens.explanation`), and the command-line entry points — not the internal
Python API, which is free to move.

## [1.0.0] — unreleased

First release candidate. Frozen and audited under `scoutlens-jtt.7.1`; the
evidence packet is [`docs/release-candidate-v1.md`](docs/release-candidate-v1.md).

### The claim, and its boundary

Event-derived profiles contain a reproducible individual fingerprint that
supports same-player temporal retrieval across two chronological halves of one
historical season.

Not claimed, in the artifact and in this file: statistical similarity does not
prove playing style, a statistical neighbour is not a recruitment
recommendation, and nothing here predicts future performance, tactical fit,
value or transfer success.

### Added

- **Published showcase artifact contract `scoutlens.showcase/2.0.0`** — 1,257
  player × competition profiles, a feature catalog, a research summary, a
  learned diagonal representation and a content-addressed payload pin. Every
  profile carries its evidence index, neighbours, uncertainty and caveats.
- **Static site** — three routes (`/`, `/lab`, `/science`). The Fingerprint Lab
  is an interactive evidence browser; `/science` is the method and decision
  trail. No backend, no analytics, no third-party request.
- **Uncertainty layer** — bootstrap rank intervals and neighbour stability,
  published per profile and surfaced in the Lab.
- **StatsBomb replication** — an independent provider and season, as aggregate
  results only.
- **Provider-neutral grounded-explanation toolkit** — an evidence-bundle
  contract with a fail-closed validator, a model-agnostic adapter boundary with
  a conformance suite, a 64-case evaluation corpus with a preregistered gate, a
  typed deterministic fallback, and a local CLI. Offline by default and
  enforced; no provider SDK in the base runtime.
- **Recorded AI evaluation report**
  (`artifacts/ai-evals/grounded-explanations-v1.json`) — byte-deterministic,
  regenerable by one named command, and verified in CI against the committed
  copy.

### Known limitations

These are recorded rather than resolved, and each has an open bead.

- **No demonstration model has been evaluated.** The live evaluation harness,
  its preregistered threshold and its drop rule all exist and are tested
  against stubs, but no model has been run against them. The live gate records
  `not_run`, which is deliberately distinct from a pass. The project therefore
  makes no claim about any model's behaviour (`scoutlens-jtt.6.3` AC3,
  `scoutlens-jtt.6` AC4).
- **Public comprehension was validated with n=1.** One evaluator, recorded as a
  block at 2:53 (`D056`). Communication defects were remediated technically;
  this is not a retroactive pass and comprehension is not claimed as validated
  (`scoutlens-9a3.7`).
- **The v1 cosine audit baseline has no CI coverage.** One payload pin hydrates
  v2 only, so no clean clone can obtain a v1 payload (`scoutlens-jtt.18`).
- **Two RSC prefetch payloads 404 on every page load** of the static export.
  Navigation is unaffected; the console is not (`scoutlens-uze.17`).

### Null results, published

- **Shrinkage did not improve retrieval.** Low-support ratio extremes were
  reduced and retrieval did not improve, so raw ratios remain the default. The
  experiment is published rather than retried differently.
- **Neural contrastive representations did not clear the gate.** The learned
  diagonal metric is what ships.

### Security and privacy

- No credential is required to build, test or deploy anything in this release.
- The published site makes zero third-party requests. Fonts are self-hosted.
- The AI toolkit is a local command-line tool. There is no AI in the published
  site, and nothing in it runs in a browser or a backend.

[1.0.0]: https://github.com/grunobuide/scoutlens/releases/tag/v1.0.0
