"""Tests for the pre-registered recruitment-study analysis (h00)."""

from __future__ import annotations

import pytest

from scoutlens.study.analysis import (
    analyze_study,
    bootstrap_paired_ci,
    krippendorff_alpha_interval,
    wilcoxon_signed_rank,
)


def test_krippendorff_perfect_agreement_is_one():
    assert krippendorff_alpha_interval([[3, 3], [5, 5], [1, 1]]) == pytest.approx(1.0)


def test_krippendorff_hand_computed_case():
    # units [1,2] and [4,5]: Do=1.0, De=80/12 -> alpha = 1 - 1/(80/12) = 0.85
    assert krippendorff_alpha_interval([[1, 2], [4, 5]]) == pytest.approx(0.85, abs=1e-6)


def test_krippendorff_handles_missing_and_needs_two_ratings():
    # second unit has only one rating -> ignored; first is perfect -> alpha 1.0
    assert krippendorff_alpha_interval([[4, 4], [2, None]]) == pytest.approx(1.0)
    with pytest.raises(ValueError):
        krippendorff_alpha_interval([[1, None], [None, 2]])


def test_wilcoxon_all_positive_is_significant():
    r = wilcoxon_signed_rank([1.0, 2.0, 1.5, 0.8, 2.2, 1.1, 0.9, 1.3, 1.7, 2.0])
    assert r["W"] == 55.0            # all positive: sum of ranks 1..10
    assert r["p_value"] < 0.05


def test_wilcoxon_symmetric_is_not_significant():
    r = wilcoxon_signed_rank([1.0, -1.0, 2.0, -2.0, 0.5, -0.5])
    assert r["p_value"] > 0.4


def test_bootstrap_ci_is_deterministic_and_brackets_mean():
    diffs = [0.2, 0.5, -0.1, 0.3, 0.4, 0.1, 0.6, -0.2]
    a = bootstrap_paired_ci(diffs, seed=7)
    b = bootstrap_paired_ci(list(reversed(diffs)), seed=7)
    assert a == b                                   # order-independent, seeded
    assert a["ci_low"] <= a["mean"] <= a["ci_high"]


def _ratings(b, crole, r, n_queries=40, n_raters=3):
    """Synthetic long-format ratings: each arm's candidates rated near a
    fixed per-arm mean, every rater, every query."""
    import random as _rnd
    rng = _rnd.Random(0)
    rows = []
    for q in range(n_queries):
        for rater in range(n_raters):
            for arm, mu in (("B", b), ("C_role", crole), ("R", r)):
                for _cand in range(5):
                    val = min(5, max(1, round(mu + rng.uniform(-0.4, 0.4))))
                    rows.append({"query_id": q, "arm": arm, "rater_id": rater, "rating": val})
    return rows


def _reliability_agreeing(n=50):
    return [[4, 4, 4] for _ in range(n)]


def test_decision_go_when_b_beats_crole_and_random_reliably():
    ratings = _ratings(b=4.2, crole=2.8, r=2.0)
    out = analyze_study(ratings, _reliability_agreeing())
    assert out.decision == "GO"
    assert out.failures == {"claim_fails": False, "instrument_fails": False, "floor_fails": False}


def test_decision_nogo_when_b_does_not_beat_crole():
    ratings = _ratings(b=3.0, crole=3.0, r=2.0)
    out = analyze_study(ratings, _reliability_agreeing())
    assert out.decision == "NO-GO"
    assert out.failures["claim_fails"] is True


def test_decision_redesign_when_raters_disagree():
    ratings = _ratings(b=4.2, crole=2.8, r=2.0)
    disagreeing = [[1, 3, 5] for _ in range(50)]     # wide spread -> low alpha
    out = analyze_study(ratings, disagreeing)
    assert out.decision == "REDESIGN"
    assert out.failures["instrument_fails"] is True


def test_decision_nogo_floor_when_b_not_above_random():
    ratings = _ratings(b=2.0, crole=1.8, r=2.0)       # B ~ random
    out = analyze_study(ratings, _reliability_agreeing())
    assert out.failures["floor_fails"] is True
    assert out.decision == "NO-GO"
