# AI explanation contract

The rules a model must satisfy before anything it writes about a ScoutLens
profile may be shown or scored. Frozen by `scoutlens-jtt.6.1`.

This contract contains no model. It defines the evidence a model is given, the
shape it may answer in, and a deterministic validator that decides the answer
without calling anything. The adapter that satisfies it arrives in
`scoutlens-jtt.6.2`; the evals that use it in `scoutlens-jtt.6.3`.

Implementation: `src/scoutlens/explanations/`. Tests: `tests/explanations/`.

## 1. The trust boundary

```
published artifact  →  bundle  →  [ model ]  →  output  →  validator  →  shown / scored
   (validated)       (derived)    (untrusted)            (deterministic)
```

**Everything left of the model is derived and checked. Everything the model
returns is untrusted until the validator accepts it.** The model sits inside the
boundary and is treated as hostile — not because it is expected to misbehave,
but because a contract that assumes good faith cannot tell good faith from a
fluent mistake.

Three properties carry the weight:

1. **The bundle is the whole world.** A model receives one bundle and nothing
   else. It has no retrieval, no tools, and no access to the repository. Every
   citable fact is in `allowed_evidence_ids`, which is a closed set.
2. **Every claim is grounded.** A claim with no evidence ID is rejected. There is
   no "general knowledge" surface, because a sentence nobody can check is a
   sentence nobody can correct.
3. **The validator never calls a model.** It is a pure function of (output,
   bundle). The same function judges a live adapter and a stored fixture, which
   is what makes an eval result mean anything.

### What the bundle deliberately does not contain

Raw provider rows, unpublished fields, anything from `artifacts/`, and any value
this contract computed itself. The builder derives and selects; it never
calculates a statistic and never rounds. If a profile lacks something the
contract needs, the build **fails** and the fix is a dependency on the showcase
workstream — never a field invented here.

## 2. Threat table

| # | Threat | What it looks like | Control | Rule |
|---|---|---|---|---|
| 1 | Fabricated entity | describes a player the bundle is not about | envelope check against `profile_key` | `envelope.profile_key` |
| 2 | Fabricated feature | cites a feature that does not exist | closed citation set | `claim.fabricated_citation` |
| 3 | Fabricated value | states a number the artifact does not publish | numeric equality against the cited field | `claim.value_mismatch` |
| 4 | Fabricated citation | plausible-looking evidence ID that is absent | closed citation set | `claim.fabricated_citation` |
| 5 | Omitted caveat | cites neighbour evidence without the mandatory caveats | caveat set check | `caveats.missing` |
| 6 | Invented caveat | carries a caveat the artifact never published | caveat set check | `caveats.unknown` |
| 7 | Recommendation | "should sign", "ideal replacement" | forbidden intent | `claim.forbidden_intent.recommendation` |
| 8 | Quality judgement | "better player than" | forbidden intent | `claim.forbidden_intent.quality_judgement` |
| 9 | Style proof | "proves playing style" | forbidden intent | `claim.forbidden_intent.style_proof` |
| 10 | Future claim | "predicts future performance" | forbidden intent | `claim.forbidden_intent.future_claim` |
| 11 | Causal claim | "caused by", "leads to better" | forbidden intent | `claim.forbidden_intent.causal_claim` |
| 12 | Prompt injection | instruction text presented as evidence | closed citation set | `claim.fabricated_citation` |
| 13 | Excluded feature as evidence | cites a feature the model never saw | evidence status | `claim.unweighted_evidence` |
| 14 | Learned zero as evidence | cites a feature the fit gave no weight | evidence status | `claim.unweighted_evidence` |
| 15 | Cosine as the score | presents the audit baseline as the ranking score | bundle major | `claim.cosine_as_primary` |
| 16 | Missing provenance | reports numbers without naming the method | provenance claim required | `provenance.missing` |
| 17 | Reordered evidence | cites contributions out of artifact order | order check | `claim.reordered_evidence` |
| 18 | Mismatched bundle | answer to one bundle offered against another | digest check | `envelope.bundle_digest` |
| 19 | Unrecognised surface | a claim kind the contract does not define | fail-closed enum | `claim.surface` |
| 20 | Ungrounded claim | a sentence citing nothing | grounding check | `claim.ungrounded` |

Threat 12 is worth a note. Prompt injection needs no dedicated filter: an
injected instruction is text, and text still has to cite an ID from a closed
set. The defence is the grounding rule, not a phrase list somebody has to keep
extending as attackers rephrase.

## 3. The evidence taxonomy

This is the part most likely to produce a confident falsehood, so it is stated
precisely. A showcase-v2 profile publishes evidence for all **32** catalogued
features, but the learned diagonal representation ranks on **28**. So
`feature_weight == 0.0` is two completely different facts:

| Status | In `feature_order`? | Weight | Means | May support a feature-contribution claim? |
|---|---|---|---|---|
| `weighted` | yes | > 0 | entered the ranking | **yes** |
| `learned_zero` | yes | 0.0 | the fit saw it and gave it nothing | no |
| `excluded` | **no** | 0.0 | the model never saw it | no |
| `unmeasured` | n/a | n/a | no z-score for this period | no |

On the published profile `wy-8287-c-795` that is 150 weighted feature rows, 18
learned-zero, 24 excluded, and 48 family aggregates.

**Weight alone cannot separate `excluded` from `learned_zero`** — both are
`0.0`, and only membership in `feature_order` distinguishes them. Collapsing the
two is the most plausible way for a fluent explanation to say something false
while citing a real number: "carries per 90 did not matter to the model" is true
of a learned zero and a category error about an excluded feature, which was
never in the model to matter.

`learned_zero` and `excluded` may still be *discussed* — under the `limitation`
surface, where the claim is about the model rather than about the match. What
they may never do is answer "why are these two profiles alike?".

**Family rows are aggregates, not features.** A `family_contribution` row carries
`feature_id: null`, `feature_weight: null` and null z-scores by design, and its
`weighted_contribution` is the exact sum of its members' — verified against the
artifact: the `passing` family's `0.3524` is the sum of its five members. Reading
that null weight as "the fit gave it no weight" would attach a false statement
about the model to 48 of 240 rows.

## 4. The supported claim surface

Five surfaces, and nothing else:

| Surface | May state |
|---|---|
| `similarity` | how close two profiles are under the published representation |
| `feature_contribution` | how much a **weighted** feature contributed |
| `retrieval_outcome` | where the true profile ranked, and its uncertainty |
| `provenance` | which representation, dataset and method produced the numbers |
| `limitation` | a caveat the artifact publishes |

An unrecognised surface is rejected, not ignored. Fail-closed has no
"unknown, allow" branch.

**Mandatory caveats.** Any explanation citing neighbour evidence must carry
`fingerprint_not_style_proof`, `similarity_not_recruitment` and
`same_season_team_confound` — the three `critical` severities. Required together
because each closes a different route to reading a similarity as a scouting
judgement.

## 5. Numbers

Values are compared **numerically against the cited field**, not as rendered
strings. `0.25` for a published `0.2539` is a different number, however
reasonable the rounding looks. The tolerance (`1e-9` relative) absorbs float
round-tripping through JSON and nothing else.

`D046` is why this is not loosened: unrounded rank bounds shipped publicly once
because a display path was assumed to be cosmetic. Display rounding is the
consumer's job; a contract that blesses it here cannot tell a rounding from a
mistake.

## 6. The two majors

| | v2 (default) | v1 (audit baseline) |
|---|---|---|
| method | `weighted_cosine_diagonal_v1` | `combined_scaler_cosine_v1` |
| representation | required | none published |
| weights | learned, 28 features | unit weights, all features |
| taxonomy | all four statuses | `weighted` / `unmeasured` only |
| may cite `cosine_contribution` as the score | **no** | yes |

The v1 path is reached **only** by passing `audit_baseline=True` explicitly. A v1
profile without it is refused, and a v2 profile with it is refused. Neither
direction is available by omission, because a silent downgrade would let a v2
explanation describe v1 semantics — the confusion `D047` and `D049` renamed the
published method to prevent, after it had already shipped once.

Everything else applies to the audit path unchanged: it may cite the cosine term
as the score, and it still may not fabricate, recommend, or drop a caveat.

## 7. Stop conditions

Stop and escalate rather than working around, if:

1. **The profile lacks evidence the contract requires.** Record a dependency on
   the owning showcase workstream. Do not add a field, copy a value, or widen
   validation here.
2. **A rule would have to be relaxed to accept a desirable output.** The output
   is wrong, or the rule is — resolve which, in a decision record, before
   changing either.
3. **A number would have to be reformatted to match.** See §5.
4. **The taxonomy stops distinguishing excluded from learned-zero.** That is a
   change to what the representation means, and belongs to the modeling
   workstream.
5. **A forbidden intent seems necessary to answer usefully.** It is not. "The
   evidence here does not show that" is always available and never penalised.

## 8. What this contract does not give you

It does not make a model truthful. It makes an untruthful model **detectable**,
deterministically and offline, before anything reaches a reader.

It says nothing about explanation quality — whether an accepted explanation is
clear, useful or worth showing. That is `scoutlens-jtt.6.3`'s question, and a
green validator is not evidence for it.
