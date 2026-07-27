# ScoutLens — External Replication on StatsBomb 2015/16 (results)

Beads issue `scoutlens-8mc.3`. Re-runs the v0.1 temporal-stability
battery on the StatsBomb four-league 2015/16 processed set
([`statsbomb-pipeline.md`](statsbomb-pipeline.md), D021) using the frozen
canonical 28-feature set ([`statsbomb-feature-compatibility.md`](statsbomb-feature-compatibility.md),
D020). This is the first test of whether the v0.1 signal — established on
Wyscout 2017/18, five leagues, 32 features — survives a **different
provider, different season, different (four-of-five) leagues, and a
partly-different feature set**. Logged as D022. Reproduce with
`uv run python -m scoutlens.statsbomb.replication`; numbers pinned in
`artifacts/statsbomb_replication_results.json`.

## Headline: the signal replicates

Eligible population: **1,061** player×competition units (≥450 min in both
chronological halves of 2015/16, four leagues), vs 1,257 on Wyscout.

| Metric | Wyscout v0.1 (5 lg, 2017/18, 32 feat) | StatsBomb (4 lg, 2015/16, 28 feat) |
|---|---|---|
| Baseline A (role+minutes) MRR | 0.0256 | 0.0381 |
| **Baseline B (features+cosine) MRR** | **0.2539** | **0.2031** |
| Baseline B median rank | 16 | 19 |
| Baseline B Recall@10 | 43.3% | 37.9% |
| B − A delta (95% CI) | large, CI ≫ 0 | **0.165 [0.146, 0.185]** |
| B / A multiple on MRR | ~10× | ~5.3× |
| Within-role Baseline B MRR | 0.2787 | 0.2265 |

**The core v0.1 result holds.** Event-derived standardized profiles
recover a player's own second-half-of-season fingerprint far better than
a role-and-minutes baseline — a confidently non-zero advantage (CI well
clear of zero) that **survives within role** (0.2265), exactly the v0.1
pattern. It reproduces on an independent provider, a different season,
and a different league set.

**But the effect is somewhat smaller on StatsBomb** — absolute MRR 0.20
vs 0.25, and a ~5× rather than ~10× multiple over the trivial baseline.
Two non-exclusive reasons, neither undermining the qualitative result:
the canonical set is 28 approximated/mapped features rather than the
native 32; and Baseline A itself is a little stronger here (MRR 0.038 vs
0.026), shrinking the multiple. The honest read is **"replicates, at
somewhat lower magnitude,"** not "identical."

## The team-continuity confound also replicates

| Baseline C (role+team+minutes) | Wyscout | StatsBomb |
|---|---|---|
| MRR | 0.5893 | 0.6020 |
| median rank | 2 | 2 |
| Recall@5 | 94.7% | 95.9% |

Baseline C — using team membership, which Baseline B never sees — again
beats the 28-feature model by roughly 3×, because eligible players almost
never change clubs mid-season (D010's finding). The confound is a
property of the same-season retrieval *design*, and it reappears
identically on StatsBomb.

## Transferred players: positive but inconclusive again (weaker here)

Isolating the players who changed primary team between periods — where
Baseline C's team shortcut structurally cannot apply:

| On transferred only | Wyscout (n=26) | StatsBomb (n=19) |
|---|---|---|
| Baseline C MRR | 0.010 | 0.028 |
| Baseline B MRR | 0.239 | 0.083 |
| Baseline B − A delta (95% CI) | small +, wide | **0.054 [−0.004, 0.124]** |

The **qualitative** finding replicates: Baseline C collapses to
chance-level once team continuity is removed, while Baseline B retains a
*positive* edge over the trivial baseline. But that edge is **not
statistically distinguishable from zero at n=19** (CI includes 0), and
its point estimate is markedly weaker than Wyscout's. So the
transferred-player question remains what it was after v0.1 —
**encouraging but unproven at small n** — and if anything the StatsBomb
sample argues for more caution, not less. A larger transferred-player
sample is still the single most valuable follow-up.

## Sensitivity: native carry (+2 features)

Adding the two StatsBomb-native `Carry` features back (the 30-feature
`CANONICAL_PLUS_CARRY` variant, held out of the primary 28 because
Wyscout only had an `Acceleration` proxy — D020/D021) raises global
Baseline B from MRR 0.2031 to **0.2265**. That lift is a *measurement*
improvement (StatsBomb genuinely sees carrying that Wyscout inferred),
not evidence about the method — exactly why it is reported separately and
kept out of the like-for-like comparison. It does not change any
conclusion above.

## Verdict

**The v0.1 signal replicates externally.** The central claim — a
temporally stable, event-derived individual fingerprint that a
feature+cosine model recovers far better than role+minutes, holding
within role — reproduces on StatsBomb 2015/16 with a confidently non-zero
effect, at somewhat lower magnitude. The team-continuity confound
reproduces. The transferred-player edge reproduces in sign but stays
inconclusive at small n (and weaker than on Wyscout). Nothing here
overturns Gate 2; it strengthens the external-validity side of it while
keeping the same honest boundary on the transferred-player /
recruitment-usefulness question.
