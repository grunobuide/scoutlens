# Yumusarái Labs — case study

**Live: [grunobuide.github.io/scoutlens](https://grunobuide.github.io/scoutlens/)**
· [Source](https://github.com/grunobuide/scoutlens)
· [How it works](https://grunobuide.github.io/scoutlens/science/)
· [Architecture](architecture.md) · [Decisions](decisions-log.md) · [Licences](../DATA_LICENSES.md)

> **On the two names.** The published name is Yumusarái Labs. Every technical
> identifier — repository, package, imports, URLs, environment variables,
> artifact contract, dataset pins, release tags — is still `scoutlens`, and
> stays that way: renaming one would break a published link, a pinned digest or
> a reproduction command below. Frozen in
> [`public-identity-contract.md`](public-identity-contract.md) (`D058`).

---

## The 90-second version

**The question.** Do a footballer's on-ball actions identify them the way a
fingerprint does? Take the first half of a player's season as a query and ask
whether 32 event-derived measurements can find that same player again in the
second half.

**The answer.** Yes, measurably. Against a role-and-minutes baseline scoring
**0.0256 MRR**, the 32-feature fingerprint scores **0.2539** — a median self-rank
of **16** out of 1,257 candidates. It replicates on a different provider and a
different season at **0.2031**, lower but real.

**The catch, and the reason to trust the rest.** A baseline that knows only
*role, team and minutes* scores **0.5893** — more than twice the fingerprint, at a
median rank of 2. Same-season club continuity is a stronger shortcut than the
fingerprint itself. That confound is published on the site, carried as a
`critical` caveat on every claim that touches it, and it is the single most
important thing to understand about this result.

**What it is not.** Not a quality score. Not a style proof. Not a recruitment
recommendation. Not a prediction of anything. The study measures re-identification
across two halves of one historical season, and nothing about quality, style, fit
or the future follows from it.

### What it looks like

![The Fingerprint Lab at desktop width. The header shows a circular YL monogram beside the wordmark "Yumusarái Labs". A badge row reads "Historical reproducible benchmark", "2017/18", "CC BY 4.0" and the dataset version wyscout-2017-18-v2-332766e3a822. The heading says "Compare one player with himself." A highlighted note reads: "This is a statistical fingerprint—not a quality score, style proof, recruitment ranking, or automated verdict."](media/lab-desktop.png)

The claim, and the evidence behind it, on one screen:

![The stored experiment replay for L. Modric, headed "Identity retrieval, one query at a time", using representation combined_scaler_diagonal_v1. Three result cards compare the same query. Global: rank 1 of 1,257, reciprocal rank 1.0000, similarity score 0.9069. Within role: rank 1 of 450, same reciprocal rank and score. Role and minutes baseline: rank 249 of 1,257, reciprocal rank 0.0040, similarity score not used. Each card reports uncertainty from 500 valid resamples with a median rank and a rank interval.](media/lab-retrieval-desktop.png)

One player, one query. The fingerprint puts Modric first out of 1,257; the
role-and-minutes control puts him 249th. Every number carries its bootstrap
interval, and the representation that produced it is named on the card.

Further stills, with alt text and the capture command, are in
[`media/`](media/README.md) — including the mobile layout. There is **no demo
video**: the stills cover the same content, and calling them a video would be a
claim this project has not earned.

---

## The five-minute version

### 1. Problem

Football analytics is full of similarity scores whose meaning is never pinned
down. "These two players are alike" is easy to compute and nearly impossible to
falsify, because nobody states what would make it wrong.

So this project asked a question that *can* be wrong: **does an event-derived
profile re-identify the same player across time?** Re-identification has a
correct answer for every query — the same player — so retrieval metrics mean
something, and a baseline can beat you.

### 2. Hypothesis and the frozen task

A chronological split: period A (first half of a season) queries period B
(second half). 1,257 eligible player × competition units from the 2017/18
Wyscout/Pappalardo open dataset, each with at least 450 minutes in *each* period.

The task and its thresholds were frozen before the result was read. That matters
more than it sounds: the interesting numbers below include one that contradicts
the project's own headline, and a task defined after seeing the data would have
quietly avoided it.

### 3. Evidence

| Experiment | Metric | Value |
|---|---|---|
| Role + minutes baseline | MRR | **0.0256** |
| 32-feature fingerprint | MRR | **0.2539** |
| | median self-rank | **16** of 1,257 |
| Within role only | MRR | **0.2787** |
| | median self-rank | **12** |
| | recall@5 | **0.3819** |

The within-role result is the one that rules out the boring explanation. If the
fingerprint were merely detecting "this is a goalkeeper", restricting candidates
to the same nominal role would destroy it. It goes *up*.

### 4. The confound, and what was done about it

| Baseline | MRR | median rank |
|---|---|---|
| Role + minutes | 0.0256 | — |
| **Role + team + minutes** | **0.5893** | **2** |
| 32-feature fingerprint | 0.2539 | 16 |

**The team-aware baseline beats the fingerprint by more than 2×.**

Within a single season most players stay at one club, so knowing the club plus
role and minutes narrows 1,257 candidates to a handful. The fingerprint is
competing against a shortcut it cannot see.

This was not buried. It is:

- published as an experiment in the artifact the site renders, with its own
  conclusion — *"Team continuity is a stronger shortcut than the fingerprint in
  this same-season design"*;
- attached as the `same_season_team_confound` caveat, severity `critical`, to
  every claim it qualifies;
- surfaced in the Lab's own copy, not only in a methods page.

A cross-season design would separate the two effects. That is named as the next
experiment rather than claimed as a result.

### 5. Replication, and a published null

**Replication.** An independent provider (StatsBomb open data), a different
season (2015/16), four leagues, 1,061 eligible units, 28 canonical features:

| | MRR | median rank |
|---|---|---|
| Role + minutes baseline | 0.0381 | — |
| Canonical fingerprint | **0.2031** | **19** |
| Within role only | 0.2265 | 15 |

Positive, and **lower in magnitude** than the Wyscout result. That gap is carried
as its own caveat rather than averaged away.

**A published null.** Ratio features computed from few attempts are noisy, so
empirical-Bayes shrinkage should help. It did not:

| | raw | shrunk |
|---|---|---|
| Global MRR | 0.2539 | **0.2512** |
| Within-role MRR | 0.2787 | **0.2770** |

Shrinkage reduced low-support extremes and slightly *reduced* retrieval. Raw
ratios remain the default, and the experiment ships as a null result. The
project's rule is that a null is a result — not a prompt to try again differently
until something works.

**A second null.** Neural contrastive representations were benchmarked against a
learned diagonal metric and did not earn their place. The diagonal metric ships.

**An inconclusive result, labelled as one.** Transferred players — the cleanest
test, since a player who changes club breaks the team shortcut — are too few to
settle it: 26 in Wyscout (MRR 0.2387, encouraging) and 19 in StatsBomb (MRR
0.0835, inconclusive). Both carry the `small_transfer_sample` caveat.

### 6. System design

Two ingestion pipelines with provider-scoped features feed a provider-agnostic
evaluation layer. Result artifacts embed their config, code revision, environment
and input hashes.

The web does **not** recompute research logic. It consumes a versioned artifact
contract (`scoutlens.showcase/2.0.0`) validated fail-closed at the boundary. The
site is a static export: no backend, no database, no runtime model call, and
**zero third-party requests** — verified in a browser, not asserted.

The engineering worth pointing at is not the model. It is the machinery that
makes a claim checkable:

- **Content-addressed data.** 1,257 profiles are distributed as an immutable
  pinned archive; a clean clone reproduces the dataset exactly, and the site
  cannot drift from the numbers it renders.
- **A claims matrix derived from the artifact**, not hand-maintained. It fails
  the build if any published conclusion lacks evidence or a caveat, or if a
  `critical` caveat is carried by no claim.
- **A release candidate with a computed identity** — commit, contracts, dataset
  pin, config and dependency digests — which refuses to be produced from a dirty
  tree.

### 7. The AI trust boundary

There is **no AI in the deployed site**, and none is planned.

What exists is a local, provider-neutral toolkit: an evidence-bundle contract, a
fail-closed validator, a model-agnostic adapter boundary, a 64-case evaluation
corpus with a preregistered gate, a typed deterministic fallback and a CLI. It
runs offline by default — *enforced*, not promised: without `--online` the
process refuses to open a socket.

The interesting design problem was not prompting. It was deciding **what a model
is allowed to say**, and making that checkable:

- every claim must cite evidence IDs from a closed set;
- every number must equal the published one, compared numerically, not as a
  rendered string;
- a feature-contribution claim may only rest on *weighted* evidence — a feature
  the representation never saw and a feature the fit gave zero weight are
  different things, and conflating them is the most plausible way for fluent
  output to be false while citing a real number;
- a refused output is never shown: the CLI returns a typed deterministic
  fallback and a non-zero exit code.

**Critically: no demonstration model has been evaluated.** The live harness, its
preregistered 0.95 threshold over three runs and its drop rule all exist and are
tested — against stubs. No model has been run against them. The live gate records
`not_run`, deliberately distinct from a pass, and this project makes **no claim
about any model's behaviour**.

The recorded evaluation report measures the validator, the corpus and the
fallback. It says so in its own metadata, so a number quoted from it carries the
caveat with it.

### 8. What was deliberately not built

- **No recommendation engine.** The data cannot support it and the caveats say so.
- **No AI in the public UI.** It would put unverifiable text in front of readers
  who cannot check it.
- **No cross-season design yet.** It is the right next experiment, not a shipped
  claim.
- **No second documentation source.** Every metric here is generated from the
  same artifact the site renders; a test asserts this page does not disagree with
  it.

### 9. Known limitations

- **Same-season confound.** Team continuity outperforms the fingerprint. §4.
- **n=1 comprehension.** Public comprehension was validated with **one**
  evaluator; run 1 was a block at 2:53, four findings were recorded, and remedies
  were implemented. There was **no fresh independent post-fix validation**. An
  optional follow-up with the same reviewer would be non-blind and is not a
  second participant. Comprehension is therefore **not** claimed as validated.
- **No demonstration model.** §7.
- **Small transfer samples.** 26 and 19 players.
- **One historical season per provider.** Nothing here speaks to the present day.

### 10. Next experiments

1. **Cross-season retrieval**, to separate the fingerprint from team continuity.
2. **A larger transferred-player sample**, the cleanest confound-free test.
3. **Run a real model through the eval harness**, and publish the result whether
   it clears the bar or drops.

---

## For the reader in a hurry

| Question | Answer |
|---|---|
| **What is claimed?** | Event-derived profiles contain a reproducible individual fingerprint supporting same-player retrieval across two chronological halves of one season. |
| **What is the evidence?** | 0.2539 MRR vs a 0.0256 baseline on 1,257 units; replicated at 0.2031 on a different provider and season; survives restriction to the same role. |
| **What is the biggest limitation?** | A role + team + minutes baseline scores 0.5893 — better than the fingerprint. Same-season club continuity is a stronger shortcut. |
| **What is the engineering contribution?** | A verifiable pipeline: content-addressed data, a versioned artifact contract consumed fail-closed by a static site, a claims matrix derived from the artifact, and a release candidate with a computed identity. |
| **What is the AI's role?** | A local, offline-by-default, provider-neutral explanation toolkit with a fail-closed validator. Not in the site. No model has been evaluated, and no claim is made about any model. |

## Reproducing it

Two paths, and they need different things.

**Showcase build — no raw data, no credential.** Everything the site shows:

```bash
uv sync --frozen --all-groups
uv run --frozen python -m scoutlens.showcase.payload hydrate
cd web && pnpm install --frozen-lockfile && pnpm build
```

**Research reproduction — needs the raw provider data.** Recomputes the numbers
above from source, and is the only path that requires the Wyscout/Pappalardo
download:

```bash
uv run --frozen python -m scoutlens.evaluation.run_report
SCOUTLENS_DRIFT=1 uv run --frozen pytest tests/evaluation/test_artifact_drift.py
```

**The AI toolkit — no model required:**

```bash
uv run --frozen python -m scoutlens.explanations.cli explain --profile wy-8287-c-795
uv run --frozen python -m scoutlens.explanations.evals.run_report --check
```

Full setup in the [README](../README.md); the release audit is
[`release-candidate-v1.md`](release-candidate-v1.md).
