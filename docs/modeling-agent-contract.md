# Modeling agent contract

Frozen by `scoutlens-iex.3` on 2026-08-10. Decision record: `D040` in
[`decisions-log.md`](decisions-log.md).

This contract lets a specialist modeling agent pick one ready bead and execute
it end to end without authority over frozen configuration, recorded research
results or published artifacts. It is binding for any agent or human executing
a bead labelled `modeling`, and it is subordinate to a current instruction from
the user and to the repository's `AGENTS.md` / `CLAUDE.md`.

If this contract and a bead disagree, the bead loses and the executor stops.

It is also subordinate to the `CONTAINMENT` block in
[`bd_orchestrator.py`](../bd_orchestrator.py), which is injected above every
persona. Where this contract appears to grant something containment forbids —
running `bd`, editing `.beads/`, committing, pushing, merging, rebasing or
checking out — containment wins and the executor stops.

This is the modeling counterpart to
[`frontend-agent-contract.md`](frontend-agent-contract.md). The two are
deliberately symmetrical: the same three ownership levels, the same
Denied-by-default rule, the same precedence, and mirrored Denied entries so
neither track can reach into the other.

---

## 1. File ownership

Three levels. **Allowed** = edit freely within the bead's stated scope.
**Conditional** = edit only when the bead names the exact file and the named
reviewer has approved. **Denied** = never edit in a modeling bead; crossing the
line stops the task.

| Path | Level | Reviewer / owning workstream | Notes |
|---|---|---|---|
| `src/scoutlens/**` | Allowed | — | The pipeline, within the bead's stated scope. Changing a metric definition, feature id, population rule, split, seed or frozen threshold is Denied — see §1.1. |
| `tests/**` | Allowed | — | New tests and fixtures. Deleting, skipping or weakening an existing assertion is **Conditional** (reviewer: bead author). |
| `notebooks/**` | Allowed | — | Exploratory only. A number that reaches a document or artifact must come from a tested module, never from a notebook cell. |
| `docs/` new evidence documents | Allowed | — | A new measurement or method note the bead produces. Editing an existing research report is Denied. |
| `docs/decisions-log.md` | **Conditional** | Bead author | **Append a new sequential `D` record only.** Editing or deleting an existing record is Denied — the ledger is append-only (`CLAUDE.md`). Supersede by writing a new record that names the old one. |
| `config/experiment.json`, `config/uncertainty.json` | **Conditional** | `scoutlens-jtt` | Frozen experiment configuration. Only when the bead names the exact file **and** the exact key. A changed value that moves a published number also requires a `D` record. |
| `config/showcase-payload-pack.json` | **Conditional**, regeneration only | `scoutlens-jtt` | The content-addressed pin. Writable only as the recorded output of a republished pack under §4.4, never by hand. |
| `public/showcase/**` | **Conditional**, regeneration only | `scoutlens-jtt` | Published artifacts. Writable **only** as the deterministic output of a named command in §4.2, never by hand. |
| `artifacts/uncertainty/**`, `artifacts/showcase-payload/**`, `artifacts/recruitment_study/**` | **Conditional**, regeneration only | `scoutlens-jtt` | Same rule as `public/showcase/**`. |
| `artifacts/*.json` result files | **Denied** | `scoutlens-jtt` | `chance_control_results.json`, `gate2_results.json`, `robustness_results.json`, `shrinkage_experiment_results.json` are recorded results. A new run writes a **new** file; it never overwrites a recorded one. |
| `pyproject.toml`, `uv.lock` | **Conditional** | Bead author | Only for a dependency the bead explicitly justifies, stating weight and the rejected alternative. Never to relax `requires-python`, lint or type settings. |
| `data/**` | **Denied** | `scoutlens-jtt` | Provider inputs and derived Parquet. Read-only to every modeling bead. Regenerating ingestion output is its own bead with its own review. |
| `docs/*.md` research reports | **Denied** | `scoutlens-jtt` | Frozen science. Includes every gate, split, feature, provenance, robustness, replication and method report in `docs/`. |
| `docs/frontend-agent-contract.md`, `docs/modeling-agent-contract.md` | **Denied** | `scoutlens-uze` / `scoutlens-iex` | A contract is changed by its own bead, never in passing. |
| `web/**` | **Denied** | `scoutlens-uze` | Presentation. One narrow regeneration-adjacent exception exists — see scenario **D** in §3. |
| `web/src/contracts/generated/**` | **Denied** | `scoutlens-uze` | Generated from the schema by `pnpm contracts:generate`. |
| `.beads/**` | **Denied** as a hand edit | — | Change issues through `bd`. Under orchestrator containment, do not run `bd` at all. |
| `bd_orchestrator.py`, `bd_recover.py`, `personas/**` | **Denied** | `scoutlens-iex` | Delegation machinery. |
| `.github/**`, `.claude/**`, `.codex/**`, `.agents/**`, `.continue/**`, `.orchestrator/**` | **Denied** | — | CI and agent scaffolding. |
| `AGENTS.md`, `CLAUDE.md` | **Denied** | `scoutlens-iex` | The instruction files this contract defers to. An executor never edits the rules it is bound by. Both are untracked by design (`.gitignore`), so an edit is invisible to review — a second reason to stop. |
| `README.md`, `LICENSE`, `DATA_LICENSES.md` | **Denied** | — | Project-level statements, including data licensing. |
| `.gitignore`, `.gitattributes` | **Denied** | — | Changing what is tracked or how it is normalized is never part of a modeling bead. |
| `dist/**`, `.venv/**`, `__pycache__/**`, `.pytest_cache/**`, `.mypy_cache/**`, `.ruff_cache/**` | **Denied** | — | Build output and local caches. Ignored by Git; never edited, and never "cleaned" as part of a bead. |
| `schemas/**` | **Denied** (reserved) | `scoutlens-jtt` | Does not exist as of 2026-08-10. Reserved so that creating it does not silently land in an unlisted, and therefore Denied, path. Creating it requires a contract bead. |
| `configs/**` | **Denied** (reserved) | `scoutlens-jtt` | Contains only `README.md`. `config/` — singular — is the live directory. Named here so the near-miss is explicit rather than accidental. |

Anything not listed is **Denied by default**. "It is scientifically motivated"
is never a reason to cross a line.

### 1.1 Scientific invariants

A modeling bead may change **how** a value is computed only when the bead says
so in those words. It may never, as a side effect:

- change a metric definition, feature id, evidence id, caveat code or claim
  string;
- change a population rule, eligibility filter, split boundary, random seed or
  a frozen threshold;
- change a **recorded result value** in `artifacts/` or in any `docs/` report;
- weaken the fail-closed behaviour of any validator, checksum, manifest or
  schema check, including turning a raise into a warning or a skip;
- widen a numeric tolerance, or relax an availability rule such as the
  450-of-500 valid-resample floor;
- change the dataset version pin without republishing the pack under §4.4;
- introduce a causal, recruitment or future-performance claim into code,
  copy, docstring or commit message (`CLAUDE.md`).

Loosening a tolerance to make a test green is a stop condition, not a
trade-off. A null result is a result: if a change does not improve the measured
outcome, record the null and stop — do not retry with a different design absent
a stop/go rule written in the bead.

---

## 2. Delivery protocol

1. **One bead, one branch.** Branch from the current integration branch, named
   for the bead id.
2. **Preserve an unrelated dirty worktree.** Stage only the files the bead
   owns. Never `git add -A`, never `git checkout --` a file you did not change,
   never stash someone else's work. If an unrelated modification is present,
   say so in the handoff and leave it alone.
3. **Never commit, push, merge or run `bd dolt push` without current
   authority.** The default is conservative: report the proposed commands and
   stop. Authority from one session does not carry to the next. Under
   orchestrator containment, these are forbidden outright.
4. **Run the gates the bead names**, at minimum:
   ```bash
   uv run --frozen pytest -q
   uv run --frozen ruff check .
   uv run --frozen mypy src/scoutlens
   ```
   Quote the actual output. "Tests pass" without a command and a result is not
   evidence.
5. **Opt-in gates count only when run.** Several suites are `skipif`-gated
   behind an environment variable and local provider data —
   `SCOUTLENS_SHOWCASE_INTEGRATION`, `SCOUTLENS_SHOWCASE_PAYLOAD_INTEGRATION`,
   `SCOUTLENS_UNCERTAINTY_INTEGRATION`, `SCOUTLENS_DRIFT`. If an acceptance
   criterion depends on determinism, budgets or drift, the default `pytest -q`
   run does **not** prove it. Run the opt-in suite and quote it, or state
   plainly that the criterion is unproven.
6. **Fail closed on scope.** If the fix needs a Denied file, stop with partial
   work rather than widening the diff.

---

## 3. Boundary scenarios, resolved

**A. Pipeline change with no artifact effect — proceed.**
Refactoring, typing, adding a test, or fixing a bug inside `src/scoutlens/**`
whose output is byte-identical is Allowed. Evidence: the relevant suite plus,
where a published artifact exists, one regeneration showing an empty diff.

**B. Pipeline change that moves a published number — stop and escalate.**
If output changes, the bead must have said it would. An unplanned numeric
change is a stop condition, not a result to be written up. Record the observed
delta, stop, and route to `scoutlens-jtt`. This is true even when the new
number is better.

**C. Frozen configuration or schema change — always blocks modeling execution.**
If the work needs a new schema field, a new artifact file, or a changed key in
`config/experiment.json` or `config/uncertainty.json`, the modeling bead stops
unless the bead names the file and the key and the reviewer approved before
work started. It is never bundled in, and never worked around by a default
value, an optional field or a local override.

**D. Removing a downstream compensation for the defect being fixed — narrow,
Conditional.**
This is the one place a modeling bead may touch `web/**`, and it exists because
the case is real: `scoutlens-jtt.12` (`D037`) fixed identity escaping at the
producer boundary, and the same defect had a per-view decoder in the web layer
that became both redundant and harmful once the producer was correct.

Permitted only when **all** of the following hold:

1. the compensation exists solely because of the defect this bead fixes;
2. the bead names the exact web files;
3. `scoutlens-uze` has approved before work starts;
4. the change only **deletes or simplifies** the compensation — it adds no
   presentation logic;
5. the rendered DOM text is proven unchanged, because the producer now emits
   what the compensation used to synthesize;
6. `pnpm test` and `pnpm build` pass, and the web unit tests asserting the old
   behaviour are updated in the same change.

Anything touching layout, styling, copy, ordering, component structure or a
displayed **value** is Denied and belongs to a frontend bead under the frontend
contract. If conditions 1–6 do not all hold, split the work: the modeling bead
stops at the producer boundary and files a paired frontend bead with a
dependency.

---

## 4. Artifact regeneration

This section is the substance of this contract. A published artifact is never
hand-edited. It is only ever the recorded output of a named command, proven
reproducible.

### 4.1 The rule

An artifact under `public/showcase/**`, `artifacts/uncertainty/**`,
`artifacts/showcase-payload/**` or `artifacts/recruitment_study/**` may be
written only when:

1. a command from §4.2 produced it;
2. running that command **twice** yields byte-identical output;
3. the resulting diff is explainable as the bead's stated change **and nothing
   else**;
4. the reviewer receives the evidence packet in §4.3.

Failing any of the four means the artifact is not publishable. Regenerating
because a validator is red is prohibited — a red validator is a finding.

### 4.2 Commands that may produce an artifact

No other command may write a published artifact. Each is a module entry point,
run through `uv run --frozen`.

| Artifact | Command |
|---|---|
| `public/showcase/v1/**` | `python -m scoutlens.showcase.export` |
| `public/showcase/v1/players/**` (clean clone) | `python -m scoutlens.showcase.payload hydrate` |
| `artifacts/showcase-payload/**` and the pin | `python -m scoutlens.showcase.payload` (build/pack path) |
| `artifacts/uncertainty/**` | `python -m scoutlens.uncertainty.run` |
| `data/processed/**` (own bead; Denied here) | `python -m scoutlens.data.ingestion`, `.minutes`, `.eligibility`, `.validation` |
| `artifacts/*_results.json` (new file only) | `python -m scoutlens.evaluation.run_report`, `.run_robustness`, `.run_chance_control`, `.run_shrinkage_experiment`, `.run_transfer_analysis` |
| `artifacts/recruitment_study/**` | `python -m scoutlens.study.shortlists` |
| StatsBomb replication outputs | `python -m scoutlens.statsbomb.ingestion`, `.replication` |

### 4.3 Evidence the reviewer receives

Every regeneration hands the reviewer, at minimum:

1. **The exact command**, including every environment variable, and its output.
2. **Proof of byte-identical reproduction**: the command run twice into two
   directories, compared. `tests/showcase/test_export_integration.py::test_complete_export_is_deterministic_valid_and_within_budgets`
   is the canonical form of this proof for the showcase export; it requires
   `SCOUTLENS_SHOWCASE_INTEGRATION=1` and local processed data.
3. **The changed manifest digests**, before and after, named explicitly —
   including the `dataset_version`.
4. **A count of affected records, with the expected count derived
   independently** of the code that produced the change. D037's "2,081 player
   fields and 8 team names" is the standard: a number counted from the source
   data, not read back from the new artifact. A count that can only be obtained
   by trusting the change proves nothing.
5. **A statement of what did not change.** For an identity-only or
   presentation-neutral change, that every value, metric, rank and evidence
   entry is numerically identical to the prior export.
6. **The validator result**: `validate_published_directory` passing on the new
   directory, and still failing closed on a deliberate one-byte tamper.

### 4.4 Dataset version and payload pin

Per `D030` and `D037`, a changed dataset is not published by editing the pin:

1. the export produces a new content-addressed `dataset_version`;
2. the pack is rebuilt from **validated exporter output only**, with sorted
   paths and normalized archive metadata;
3. it is published as a **new immutable release asset** with a new
   content-addressed filename — an existing asset is never replaced;
4. only then is `config/showcase-payload-pack.json` repinned, and only then may
   the pin test be updated.

A modeling agent that cannot perform step 3 — publishing a release asset is
outward-facing and normally outside its authority — **stops after step 2**,
reports the new digest and byte count, and hands off. It does not repin against
an asset that does not yet exist.

### 4.5 Web-side consequence

`web/public/showcase/**` is produced by `pnpm assets:sync` and is Denied to the
modeling track. After a republished pack, the web sync and its budget check are
a frontend concern; note the dependency and hand off.

---

## 5. Stop conditions

Stop, report, and do not continue when:

- a needed path is Denied, or unlisted and therefore Denied;
- output changes in a way the bead did not predict (scenario B);
- a regeneration is not byte-identical on the second run;
- a diff contains anything the bead's stated change does not explain;
- the independently derived record count disagrees with the observed count;
- a gate can only be made green by widening a tolerance, relaxing a threshold,
  skipping a test or weakening a validator;
- classifying a path would require deciding **who owns a scientific result** —
  route that decision to the owning workstream rather than assuming it;
- the bead contradicts this contract, `AGENTS.md`, `CLAUDE.md`, or a current
  user instruction.

Default to Denied. This contract exists to make safe work possible, not to
grant reach.

---

## 6. Handoff template

Copy into the bead before starting. An unfilled field is a blocker, not a
formality.

````markdown
## Bead
<id> — <title>

## Outcome
<one sentence: what is true after this lands that is not true now>

## Allowed files
<explicit list; must be a subset of the Allowed column in §1>

## Conditional files
<file + named reviewer + the approval that already exists>

## Forbidden files
<the Denied paths this bead comes closest to; state the stop condition>

## Artifact effect
<none | regeneration; if regeneration, the §4.2 command and the expected diff>

## Independent count
<how the number of affected records is derived without trusting the change>

## Acceptance commands
<exact commands, including opt-in env vars, whose output goes in the closure
notes>

## Scientific invariants
<the definitions, ids, seeds, thresholds and recorded values this bead must not
change — see §1.1>

## Stop conditions
<what makes this bead stop rather than continue>

## Escalation
<the bead id to depend on, and the reviewer, if a boundary is hit>
````

---

## 7. Definition of Done

- Every acceptance criterion is mapped to evidence: a command and its output, a
  measured number, or a named artifact digest. No criterion is closed on
  assertion.
- Gates run with their real output quoted. Deviations — environment, skipped
  gate, opt-in suite not run — are stated, not omitted.
- `git status` is reported. Files the bead does not own are untouched and their
  presence is called out.
- Any regeneration ships the full §4.3 evidence packet.
- Follow-up work is filed as beads, not left as TODOs.
- The handoff names what was **not** done and why.

---

## 8. Worked example — `scoutlens-jtt.12`

A dry run of §6 against the identity-escaping bug, the case named in
`scoutlens-iex.3` as the one the contract must resolve without ambiguity. It is
reconstructed from the delivered change (`35748b5`) and `D037`, and it is the
reason scenario **D** and §4.4 exist in this form.

- **Bead** `scoutlens-jtt.12` — Normalize literal Unicode escapes in showcase identity fields.
- **Outcome** Parsed showcase JSON contains real UTF-8 identity text, normalized once at the producer boundary.
- **Allowed files** `src/scoutlens/showcase/builder.py`, `src/scoutlens/showcase/validation.py`, `tests/showcase/test_identity.py`, `tests/showcase/test_payload.py`.
- **Conditional files** `public/showcase/v1/**` and `config/showcase-payload-pack.json` — regeneration only, reviewer `scoutlens-jtt`, under §4.1 and §4.4. `docs/decisions-log.md` — append `D037` only. `docs/showcase-artifact-contract.md` and `docs/showcase-payload-pack.md` — the contract documents the change makes untrue; named by the bead, reviewer `scoutlens-jtt`.
- **Web files** `web/src/content/showcase-lab.ts`, `showcase-story.ts`, `web/src/components/lab-explorer.tsx`, `neighbor-comparison-drawer.tsx`, `web/tests/showcase-lab.test.tsx` — permitted **only** under scenario D: `decodeIdentityText` / `decodeEscapedUnicode` existed solely to compensate for this defect, the change deletes them, and the rendered text is unchanged because the artifact now carries the decoded value.
- **Forbidden** `data/**` — the escapes originate in provider data; normalizing at ingestion instead would change the raw record and is a different bead.
- **Artifact effect** Regeneration via `python -m scoutlens.showcase.export`, then a rebuilt and repinned pack under §4.4.
- **Independent count** 2,081 player fields and 8 team names carrying literal escapes, counted from the Wyscout source rather than read back from the new artifact; 205 team names and 266 of 1,257 display names changed on screen.
- **Evidence** New `dataset_version` `wyscout-2017-18-v1-31d2ccc6af37`; all values, metrics, ranks and evidence numerically identical to the prior export — only identity text bytes changed; validator rejects any remaining literal escape fail-closed.
- **Invariants** No metric, rank, cosine, percentile, support or uncertainty value changes; no feature or evidence id changes; index ordering changes only because it now collates on display text rather than escape text, which the bead states explicitly.
- **Stop conditions** A value other than identity text changes; the export is not byte-identical on a second run; the release asset cannot be published (stop after §4.4 step 2 and hand off).
- **Escalation** Presentation change beyond deleting the compensation → `scoutlens-uze`. Schema or config change → `scoutlens-jtt`.

Every field resolves from this contract plus `D030` and `D037`. No file,
threshold or behavioural decision is left unstated.
