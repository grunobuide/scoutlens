# ScoutLens — Qualitative Error Analysis (SLS-021)

Case-level investigation of Baseline B's global retrieval results
(five domestic leagues, ≥450 min/period, 1,257 queries). Per the brief's
own caution: football intuition is used here to *interpret* cases the
quantitative results already flagged — never as a substitute for the
primary metric, and never as "I recognize this player and it looks
right." Every case below is selected by an objective rule (rank,
minutes), not by browsing for a story.

## Does low minutes explain bad ranks? Partially.

Across all 1,257 queries, `corr(min(minutes_A, minutes_B), reciprocal
rank) = 0.18` — a real but modest positive relationship, confirming the
pattern SLS-020's aggregate threshold curve already suggested, now at the
individual level:

| Minutes bucket (min of the two periods) | n | Median rank | Mean reciprocal rank |
|---|---|---|---|
| 450–600 | 200 | 29 | 0.147 |
| 600–900 | 371 | 23 | 0.205 |
| 900–1500 | 581 | 10 | 0.312 |
| 1500+ | 105 | 11 | 0.308 |

Players near the eligibility floor do retrieve noticeably worse on
average. But 0.18 is a modest correlation, not a strong one — minutes
alone doesn't explain most of the variance in retrieval quality, which
the four worst-case investigations below confirm directly.

## The 4 worst cases: not all explained by sample size

The four highest (worst) ranks in the entire experiment, checked against
minutes in each period and whether the player changed clubs between
periods (a real, legitimate reason for a profile to shift that would be
wrongly blamed on "noise" otherwise):

| Player | Role | Rank (of 1,257) | Minutes A → B | Same club both periods? | What's established vs. speculative |
|---|---|---|---|---|---|
| J. Livermore | Midfielder | 791 | 1,512 → 1,164 | Yes (West Brom) | **Established:** not sample noise — substantial minutes in both periods, no club change. **Speculative:** *why* the profile changed (tactical shift, form, manager change) is not determined here. |
| D. D'Ambrosio | Defender | 701 | 1,589 → 1,395 | Yes (Inter) | **Established:** same as above — not sample noise. **Speculative:** cause unknown. |
| F. Grillitsch | Midfielder | 544 | 548 → 1,344 | Yes (Hoffenheim) | **Established:** consistent with sample noise — period A sits right at the eligibility floor (548 min, barely 6 matches), a plausible source of an unrepresentative profile. This one doesn't need a speculative cause. |
| Jorge | Defender | 701\* | 1,342 → 580 | Yes (Monaco) | **Established:** mixed signal — period B is well above the floor but far below period A. **Speculative:** reduced role/rotation is one plausible reading; not confirmed. |

\* Both D'Ambrosio and Jorge landed at rank 701 in this run — not a typo.

**Reading:** of the four worst cases, only one (Grillitsch) fits the
"small sample → apparent instability" pattern D006 worried about
cleanly. What can be said with confidence about the other three: they are
**not** explained by low minutes or a club change — their statistical
profile genuinely shifted while everything about their situation that
this dataset can observe stayed constant. What specifically drove that
shift (tactical role change, squad rotation, loss of form, a new
manager's system) is a plausible *hypothesis* offered for football
context, not a claim this analysis verified — the dataset has no field
for "reason." This matters for the final report's limitations section:
not every retrieval failure is a data-quality artifact, but attributing
the *specific* football cause of a real change would be overclaiming
beyond what event data alone can establish.

## Close misses: is rank 2 usually a coherent confusion?

Checked two queries that landed at rank 2 (the true match narrowly beaten
by one other candidate) — a good test of whether "wrong" answers are at
least football-plausible, not random:

- **K. Walker** (right-back) — the top-ranked neighbor was **E. Hysaj**,
  also a right-back known for a similar profile (progressive,
  attack-involved fullback). Rank 3 was **D. Sidibé**, another attacking
  right-back. All three are the same specific sub-role within "Defender,"
  not an arbitrary mismatch.
- **M. Schneiderlin** (holding/defensive midfielder) — the top-ranked
  neighbor was **J. Marié**, rank 3 was **J. Weigl**, a well-known
  deep-lying, low-risk-passing defensive midfielder. Schneiderlin fits
  the same mold.

**Reading:** in both cases, Baseline B's "wrong" answer is a
specifically-similar player within a narrower functional niche than the
nominal role category — evidence the feature space is capturing a real,
finer-grained sub-role signal (e.g. "attacking fullback" vs. "defensive
fullback," not just "Defender"), which is a more interesting and more
defensible result than either "it's basically random" or "it's just
role."

## What this does and doesn't support

This is illustrative case review of a handful of extreme/borderline
examples, not a systematic audit of all 1,257 queries — it should be read
as qualitative texture on top of SLS-018/019/020's quantitative results,
not as independent evidence. Its purpose here is narrow: showing that
failures have identifiable, varied causes (real profile change, genuine
sample-size noise, and — per SLS-020 — a modest team/league confound)
rather than being unexplained noise, and that near-misses tend to be
football-coherent rather than arbitrary.
