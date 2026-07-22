"""Baseline A (SLS-016): `same nominal role -> nearest minutes played`.

Per the brief, this is the trivial baseline the "real" method (Baseline B,
SLS-017: standardized event-derived features + cosine similarity) has to
beat. It exists to make explicit what "beating the baseline" even means —
if Baseline B can't outperform "just find someone in the same position
with a similar workload," added complexity isn't earning its place.

Both baselines share the same shape (`rank_candidates(query, candidates)
-> ranked DataFrame with a 1-indexed `rank` column`), so SLS-018's
retrieval evaluation can run either one through identical harness code.
"""

from __future__ import annotations

import polars as pl


def baseline_a_rank(query_role: str, query_minutes: float, candidates: pl.DataFrame) -> pl.DataFrame:
    """Ranks `candidates` (must have `player_id`, `role`, `minutes_played`)
    against a query player's `role` and `minutes_played`.

    Ordering: same role as the query first, ordered by ascending minutes
    distance; different-role candidates after, also ordered by ascending
    minutes distance. This is a full ranking over every candidate (not a
    same-role filter) so it plugs directly into rank-based retrieval
    metrics (MRR, Recall@K, SLS-018) where the correct answer might, in
    principle, be a different nominal role.

    `player_id` is used as a final, deterministic tiebreak — ties on
    (same_role, minutes_distance) would otherwise have unstable order.
    """
    ranked = candidates.with_columns(
        same_role=(pl.col("role") == query_role),
        minutes_distance=(pl.col("minutes_played") - query_minutes).abs(),
    ).sort(["same_role", "minutes_distance", "player_id"], descending=[True, False, False])
    return ranked.with_row_index("rank", offset=1)
