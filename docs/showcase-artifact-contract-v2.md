# Showcase artifact contract — `scoutlens.showcase/2.0.0`

Frozen by `scoutlens-qop.6.2` on 2026-08-12. Decision record: `D047`.

Normative counterpart of
[`showcase-2.0.0.schema.json`](../src/scoutlens/showcase/schemas/showcase-2.0.0.schema.json).
Where this document and the schema appear to disagree, the schema is
authoritative — it is what validation executes. Every rule below is expressed
there and has a failing test.

**This contract is frozen before any v2 artifact exists.** No
`public/showcase/v2` file, payload pack, uncertainty run or ranking value was
produced by the bead that wrote it. That ordering is the point: a producer and
a consumer that agree only after data exists have agreed on the data, not on a
contract.

**v1 is unchanged and remains supported.**
[`showcase-artifact-contract.md`](showcase-artifact-contract.md) continues to
describe it, its schema is byte-identical, and its generated consumer types are
byte-identical. v1 is the frozen cosine contract and the audit baseline.

---

## 1. What changes, and why a new major

v1 publishes rankings produced by **unweighted cosine** over 28 standardized
features. v2 publishes rankings produced by the **diagonal representation**
kept in `D045`: cosine in the space scaled by `√w`, with 28 learned
non-negative weights.

That is a breaking change in meaning rather than in shape. The same field name
carrying a differently-computed number is the most dangerous kind of silent
break, so three things change together:

1. the score is renamed `cosine_similarity` → **`similarity_score`**, because a
   weighted metric must not be published under a name claiming plain cosine;
2. every ranking-bearing block must name the **representation** that produced
   it;
3. the dataset version marker moves from `-v1-` to `-v2-`, so the two can never
   be confused by version string alone.

## 2. File layout

```
public/showcase/v2/
  manifest.json           required, hashes every file below
  representation.json     required, NEW in v2
  feature-catalog.json
  players.index.json
  research-summary.json
  players/<profile_key>.json
```

`representation.json` is required and **must be hashed by the manifest**. An
unhashed representation could be swapped without detection, which would let a
dataset silently describe rankings it did not produce.

## 3. Representation identity

`representation.json` carries one `representation` object. Every field is
required; unknown fields are rejected.

| Field | Meaning |
|---|---|
| `id` | `rep-` + 16 hex. The identity every other artifact references. |
| `ranking_method` | Exactly `weighted_cosine_diagonal_v1`. |
| `weight_digest` | sha256 over `[[feature_id, weight], …]` in declared order. |
| `feature_order` | The 28 canonical feature ids, ordered, unique. |
| `feature_order_digest` | sha256 over that ordered list. |
| `feature_count` | Exactly 28. |
| `weights` | 28 `{feature_id, weight ≥ 0}` entries, **in `feature_order`**. |
| `training` | Provider, season, `split: train`, `split_digest`, population. |
| `lineage` | `protocol_hash` (D044), `spec_hash` (D042), `decision_records`. |
| `uncertainty_design` | Exactly `match_bootstrap_diagonal_v1`. |
| `audit_baseline` | `cosine_v1` at `scoutlens.showcase/1.0.0`, plus a note. |
| `prohibited_claims` | Non-empty; see §7. |

**Order is part of the identity.** The same weights attached to a different
feature order describe a different metric, so `weights` must appear in
`feature_order` and both digests are checked independently. A payload whose
`weights` are permuted is rejected even when every individual weight is
correct.

**Digests are recomputed, not trusted.** Validation recomputes
`weight_digest` and `feature_order_digest` from the declared content and
rejects a mismatch. A digest that is merely carried alongside the data it
describes proves nothing.

## 4. Binding: one representation per dataset

Every `retrieval_outcome`, `statistical_neighbor`, `evidence_item`,
`uncertainty_block`, `rank_uncertainty` and `neighbor_stability` block requires
a `representation_id`, and the manifest requires one too.

All of them must equal the id in `representation.json`. A dataset that mixes
two representations, or that publishes rankings without naming one, is
rejected — not downgraded, not partially accepted.

## 5. Weighted retrieval and evidence semantics

For standardized query `q` and candidate `c` with weights `w`:

```
similarity_score(q, c) = Σᵢ wᵢ qᵢ cᵢ / ( √(Σᵢ wᵢ qᵢ²) · √(Σᵢ wᵢ cᵢ²) )
```

which is cosine in the space scaled by `√w`. With `w = 1` it reduces exactly to
the v1 score, which is why v1 remains a faithful audit baseline rather than a
different family of method.

Each `evidence_item` of kind `feature_contribution` additionally carries:

- `feature_weight` — the weight applied to that feature, or `null`;
- `weighted_contribution` — that feature's signed share of the score.

**Reconstruction rule.** For a given subject, the `weighted_contribution`
values of its `feature_contribution` items must sum to that subject's
`similarity_score` within `1e-6`. Evidence that does not reconstruct the number
it explains is not evidence.

Ordering is unchanged from v1: evidence is emitted in a deterministic order and
the ranking is by descending `similarity_score`.

## 6. Uncertainty coupling

`match_bootstrap_diagonal_v1` is the **only** publishable v2 uncertainty
design. `match_bootstrap_v1` — the v1 design — is rejected in a v2 payload.

This is deliberate and is the trap most worth naming: v1 intervals describe the
sampling stability of **cosine-based** ranks. Attaching them to diagonal
rankings would present an interval that does not describe the number shown
beside it. Uncertainty blocks therefore also carry `representation_id`, so an
interval can always be traced to the metric it was computed under.

## 7. Compatibility and prohibited claims

- Known majors are **1** and **2**. Both validate.
- An **unknown major fails closed**. A consumer must not fall back to the
  newest schema it happens to have: silently validating a future payload
  against today's rules reports success for something it does not understand.
- v1 artifacts, schema and generated types are immutable. v2 is emitted
  alongside, never in place of them.
- `pnpm contracts:generate` is the only writer of
  `web/src/contracts/generated/**`, and `pnpm contracts:check` fails on drift.

Cosine audit evidence is exposed through the frozen v1 contract, `D045`, and
the `audit_baseline` metadata above — **not** through a browser-side
recomputation or a primary-flow toggle. Reproducing the audit baseline is a
producer-side activity.

`prohibited_claims` is required and non-empty. Nothing in a v2 artifact may
assert a causal relationship, a recruitment or transfer-success judgement, or a
prediction of future performance. Better same-player retrieval means the
fingerprint is a more reliable description of observed play, and nothing more.

## 8. What this contract does not do

It defines no ranking values, computes no uncertainty, publishes no
`public/showcase/v2` file, builds no payload pack, repins no dataset version
and changes no UI copy or component. Those are separate beads under
`scoutlens-qop.6`, and each is gated on this contract rather than the reverse.

## 9. Verification

```bash
uv run --frozen pytest tests/showcase/test_contract_v2.py -q
uv run --frozen pytest tests/showcase -q
pnpm contracts:check
pnpm test
```
