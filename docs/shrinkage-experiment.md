# ScoutLens — Ratio-Shrinkage Experiment (v0.2)

Beads issue `scoutlens-dul`, addressing feasibility-report.md Known
Limitation #11: the 7 ratio features (`*_pct`) computed from very few
attempts are extreme and over-trusted — a 1-shot-1-goal player gets
`shot_conversion_pct = 1.0`, the same value as a 20-of-20 striker, with
no attempt-count weighting. Logged as D024. Code:
`src/scoutlens/features/shrinkage.py` +
`src/scoutlens/evaluation/run_shrinkage_experiment.py`.

**This is an additive experiment, not a change to the v0.1 catalog.** The
feature catalog, `FEATURE_COLUMNS`, and every published v0.1 number are
untouched; the experiment builds a *second* Baseline B with shrunk ratios
and compares. `compute_player_features` still returns raw ratios by
default (`with_counts=True` is the only, purely-additive, addition).

## Method

Empirical-Bayes Beta-Binomial shrinkage. For each ratio, a Beta(α, β)
prior is fit to the population of `(numerator, denominator)` counts by
method of moments, and the reported value becomes `(k + α) / (n + α + β)`.
High-attempt players barely move; a 1-of-1 rate is pulled most of the way
to the population mean; a zero-attempt player (previously `null`) gets the
prior mean. The prior is fit on the eligible A+B population, matching
D008's standardization scope. Reproduce with
`uv run python -m scoutlens.evaluation.run_shrinkage_experiment`.

## Result: shrinkage fixes the pathology but is a wash for retrieval

Shrinkage does exactly what Limitation #11 asks at the feature level —
low-sample ratios are pulled toward the mean by up to **0.75** (e.g. a
1-of-1 completion) — but the aggregate retrieval signal barely moves:

| Baseline B | raw (v0.1) | shrunk | Δ |
|---|---|---|---|
| Global MRR | 0.2539 | 0.2512 | −0.0027 |
| Global median rank | 16 | 15 | −1 (better) |
| Global Recall@10 | 43.3% | 43.5% | +0.2 pp |
| Within-role MRR | 0.2787 | 0.2770 | −0.0017 |
| Within-role median rank | 12 | 11 | −1 (better) |

The raw arm reproduces the v0.1 headline **exactly** (0.2539), confirming
the experiment's plumbing. Shrinkage nudges MRR down by a hair and median
rank down by one — **no material change either way**.

**Reading:** the low-sample-ratio pathology is real per feature (max
shifts 0.4–0.75) but immaterial to the headline, consistent with v0.1's
finding that the signal is distributed across many weak-to-moderate
features rather than carried by any single ratio
([`robustness-checks.md`](robustness-checks.md) Check 5). Standardization
+ cosine over 32 features already dilutes any one over-trusted ratio.

## Recommendation

**Do not adopt shrinkage into the default catalog** — it adds complexity
and a fitted prior for no retrieval benefit, against the charter's
"complexity must earn its place" rule. Keep the implementation available
for any *future* use where individual ratio features are read directly
(per-player interpretation, a scout-facing card, a downstream model that
weights features), where well-behaved low-sample ratios do matter even
though same-player retrieval doesn't surface the difference. Limitation
#11 is thereby **resolved**: the pathology is characterized, a fix
exists, and its (non-)effect on the headline is measured and documented.
