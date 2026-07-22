# ScoutLens — Temporal Role Stability Experiment: Within-Role Retrieval (SLS-019)

Implementation: `run_within_role_retrieval_experiment` in
[`src/scoutlens/evaluation/retrieval.py`](../src/scoutlens/evaluation/retrieval.py)
(a thin wrapper over the same machinery as SLS-018, with
`scope_column="role"`). This is the experiment that actually tests H4:
*"does the signal survive once nominal position stops resolving the
problem?"* — the global result alone (SLS-018) can't answer that.

## Method

Identical setup to
[`temporal-retrieval-global.md`](temporal-retrieval-global.md) — same
1,257 eligible player×competition combinations, same five domestic
leagues, same ≥450 min/period threshold, same standardization (fit once
on the full all-roles population, per D008 — only the candidate pool at
**ranking time** is restricted, not the feature scale itself, so this
isn't re-normalizing away cross-role variance). The only change: each
query's candidate pool is filtered to players sharing its nominal role
before ranking.

## Results

| Metric | Baseline A (role + minutes) | Baseline B (standardized features + cosine) |
|---|---|---|
| MRR | 0.0256 | **0.2787** |
| Median rank | 128 | **12** |
| Recall@1 | 0.32% | **17.8%** |
| Recall@5 | 2.70% | **38.2%** |
| Recall@10 | 4.85% | **47.7%** |
| Avg. candidate pool size | 391 | 391 |

**MRR delta (B − A): +0.253, 95% bootstrap CI [0.232, 0.274].**

## A non-obvious result, explained: Baseline A's numbers are *identical* to the global run

Baseline A's MRR, median rank, and Recall@K here are bit-for-bit the same
as in [SLS-018's global result](temporal-retrieval-global.md) — 0.0256,
128, 0.32%. This looks like a bug on first read. It isn't. It's a
structural property of Baseline A's own ranking rule:

Baseline A sorts every candidate pool by `(same_role, minutes_distance)`
— same-role candidates always come before different-role candidates,
regardless of minutes. The true match for any query is, by construction,
always the same nominal role as the query (`players.role` doesn't vary by
period). So in the **global** pool, no different-role candidate could
ever out-rank the true match — the true match's rank was already
determined entirely by its position *within the same-role subset*.
Restricting the candidate pool to same-role-only (dropping the average
pool from 1,257 to 391 candidates) removes only candidates that could
never have out-ranked the true match anyway. The rank is unchanged.

This is worth stating plainly: **Baseline A cannot be made to perform any
differently by a within-role restriction — it was already an
effectively-within-role method.** This makes it a *stronger*, not
weaker, comparison point for Baseline B here, not a redundant one.

## Reading against H4

**Baseline B is not just "finding another player with a similar role."**
If it were, restricting Baseline A — a method that gets role-matching for
free — to within-role should have caught up. It didn't move at all,
because it had nothing left to gain from a restriction it was already
functionally applying. Baseline B, given the exact same role-homogeneous
391-candidate pools, still separates the correct match from same-role
peers well above chance: Recall@10 of 47.7% among candidates who are
*all* nominally the same position is a materially different, and harder,
claim than a global Recall@10 among a mixed-position pool.

**Caveat on comparing within-role numbers to the global numbers
directly:** the two conditions have different average pool sizes (391 vs
1,257). A rank of 12 out of 391 is not the same achievement as a rank of
12 out of 1,257 — smaller pools produce better-looking absolute ranks
almost mechanically. The comparison that matters is **within each
condition**: Baseline B vs. Baseline A on the *same* pool. Both deltas
are large and confidently non-zero (global +0.228 [0.208, 0.248];
within-role +0.253 [0.232, 0.274]) — the within-role delta being at least
as large as the global one is the actual H4 result: **the advantage
Baseline B has over the trivial baseline does not shrink, and if
anything grows slightly, once role stops being able to explain any of
it.**

## Preview: signal by role (Baseline B, within-role condition)

Not yet a full stratified analysis (that's SLS-020) — noted here because
it fell out of this run and previews what SLS-020 should look at closely:

| Role | n | MRR | Median rank |
|---|---|---|---|
| Goalkeeper | 97 | 0.129 | 23 |
| Defender | 473 | 0.208 | 19 |
| Midfielder | 450 | 0.361 | 7 |
| Forward | 237 | 0.327 | 7 |

Goalkeepers show the weakest signal by a clear margin — plausible, since
the feature catalog (SLS-013) is built almost entirely around outfield
actions (passing, shooting, defensive duels); very few features
meaningfully differentiate one goalkeeper's statistical profile from
another's. Midfielders and Forwards show the strongest within-role
separability. Whether this pattern holds up, and why, is SLS-020's job.
