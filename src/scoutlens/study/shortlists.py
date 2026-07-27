"""Blinded shortlist generation for the recruitment-validation study
(h00), per `recruitment-validation-protocol.md` (D016).

Builds, from the frozen Wyscout v0.1 data (CC BY 4.0 — cleaner than
StatsBomb for materials shown to external raters), the study materials a
scout rates: for each of 40 role-stratified query players ("replace this
player"), three arms of 5 candidates each —

- **B**: Baseline B, cosine top-5 on the 32 standardized features;
- **C_role**: the role+minutes heuristic (same role, closest minutes);
- **R**: random same-role.

The query's own period-B row (the trivial "true match") and the query
player are excluded — the scenario is replacement, so the player himself
is never a candidate. Arms are built mutually exclusive (B first, then
C_role from what's left, then R) so the 15-candidate merged list has 15
distinct players and every rating attributes to exactly one arm. The
merged list is shuffled per query with no arm labels (blinding); the
arm-assignment key is written to a **separate** file the raters never see.

Run with:

    uv run python -m scoutlens.study.shortlists

Writes artifacts/recruitment_study/{rating_sheet,arm_key,manifest}.json.
Deterministic for a fixed seed.
"""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl

from scoutlens.evaluation.retrieval import get_top_k_neighbors, select_eligible_both_periods
from scoutlens.evaluation.similarity import impute_and_standardize
from scoutlens.evaluation.temporal import assign_periods, build_period_profiles
from scoutlens.features.aggregation import FEATURE_COLUMNS

REPO_ROOT = Path(__file__).resolve().parents[3]
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
OUT_DIR = REPO_ROOT / "artifacts" / "recruitment_study"

DOMESTIC_LEAGUES = [364, 412, 426, 524, 795]
MINUTES_THRESHOLD = 450
N_PER_ROLE = 10
K_PER_ARM = 5
CARD_STATS = ["passes_p90", "pass_completion_pct", "shots_p90", "key_passes_p90",
              "interceptions_p90", "duels_p90", "carry_proxy_p90", "mean_x"]


def _role_lookup(players: pl.DataFrame) -> pl.DataFrame:
    return players.select(pl.col("wyId").alias("player_id"), pl.col("role").struct.field("name").alias("role"))


def _player_meta(players: pl.DataFrame, competitions: pl.DataFrame) -> pl.DataFrame:
    comp = competitions.select(pl.col("wyId").alias("competitionId"), pl.col("name").alias("league"))
    return players.select(
        pl.col("wyId").alias("player_id"),
        (pl.col("firstName") + pl.lit(" ") + pl.col("lastName")).alias("name"),
        pl.col("birthDate").str.slice(0, 4).cast(pl.Int64, strict=False).alias("birth_year"),
    ), comp


def sample_queries(query_a: pl.DataFrame, primary_team_a: pl.DataFrame, seed: int) -> list[dict]:
    """40 queries = N_PER_ROLE per role, sampled with a fixed seed under two
    constraints: no two queries share a period-A primary team, and league
    spread is enforced (round-robin over leagues within each role where the
    pool allows). Returns query rows with player_id, competitionId, role."""
    import random
    rng = random.Random(seed)
    with_team = query_a.join(primary_team_a, on=["player_id", "competitionId"], how="left")
    chosen: list[dict] = []
    used_teams: set = set()
    for role in ["Goalkeeper", "Defender", "Midfielder", "Forward"]:
        pool = with_team.filter(pl.col("role") == role).to_dicts()
        rng.shuffle(pool)
        by_league: dict = {}
        for r in pool:
            by_league.setdefault(r["competitionId"], []).append(r)
        leagues = sorted(by_league)
        rng.shuffle(leagues)
        picked: list[dict] = []
        # round-robin over leagues for spread, skipping team collisions
        while len(picked) < N_PER_ROLE and any(by_league.values()):
            progressed = False
            for lg in leagues:
                if len(picked) >= N_PER_ROLE:
                    break
                bucket = by_league[lg]
                while bucket:
                    cand = bucket.pop()
                    if cand.get("team_id") not in used_teams:
                        picked.append(cand)
                        used_teams.add(cand.get("team_id"))
                        progressed = True
                        break
            if not progressed:
                break
        chosen.extend({"player_id": p["player_id"], "competitionId": p["competitionId"], "role": role}
                      for p in picked)
    return chosen


def build_arms(
    query: dict, query_a_std: pl.DataFrame, cand_b: pl.DataFrame, cand_b_std: pl.DataFrame, seed: int
) -> dict[str, list[dict]]:
    """Three mutually-exclusive arms of K_PER_ARM candidates each. Excludes
    the query player himself and his own period-B true-match row."""
    import random
    rng = random.Random(seed)
    qpid, qcid, qrole = query["player_id"], query["competitionId"], query["role"]

    def not_self(pid, cid):
        return not (pid == qpid and cid == qcid) and pid != qpid

    # Arm B: cosine top-K neighbours (fetch extra, drop self/true-match)
    q_row = query_a_std.filter((pl.col("player_id") == qpid) & (pl.col("competitionId") == qcid))
    neigh = get_top_k_neighbors(q_row, cand_b_std, FEATURE_COLUMNS, k=K_PER_ARM + 5)
    b_arm = [{"player_id": n["neighbor_player_id"], "competitionId": n["neighbor_competitionId"]}
             for n in neigh.sort("neighbor_rank").iter_rows(named=True)
             if not_self(n["neighbor_player_id"], n["neighbor_competitionId"])][:K_PER_ARM]
    taken = {(c["player_id"], c["competitionId"]) for c in b_arm}

    same_role = cand_b.filter((pl.col("role") == qrole))
    q_minutes = cand_b.filter((pl.col("player_id") == qpid) & (pl.col("competitionId") == qcid))
    q_min_val = q_minutes["minutes_played"][0] if q_minutes.height else 0.0

    # Arm C_role: same role, closest period-B minutes to the query, not in B
    crole_pool = [r for r in same_role.iter_rows(named=True)
                  if not_self(r["player_id"], r["competitionId"])
                  and (r["player_id"], r["competitionId"]) not in taken]
    crole_pool.sort(key=lambda r: abs(r["minutes_played"] - q_min_val))
    c_arm = [{"player_id": r["player_id"], "competitionId": r["competitionId"]} for r in crole_pool[:K_PER_ARM]]
    taken |= {(c["player_id"], c["competitionId"]) for c in c_arm}

    # Arm R: random same role, not in B or C_role
    r_pool = [r for r in same_role.iter_rows(named=True)
              if not_self(r["player_id"], r["competitionId"])
              and (r["player_id"], r["competitionId"]) not in taken]
    rng.shuffle(r_pool)
    r_arm = [{"player_id": r["player_id"], "competitionId": r["competitionId"]} for r in r_pool[:K_PER_ARM]]

    return {"B": b_arm, "C_role": c_arm, "R": r_arm}


def _card(pid: int, cid: int, profiles: pl.DataFrame, meta: pl.DataFrame, comp: pl.DataFrame) -> dict:
    prow = profiles.filter((pl.col("player_id") == pid) & (pl.col("competitionId") == cid))
    mrow = meta.filter(pl.col("player_id") == pid)
    lg = comp.filter(pl.col("competitionId") == cid)
    card = {
        "player_id": pid, "competitionId": cid,
        "name": mrow["name"][0] if mrow.height else str(pid),
        "birth_year": (mrow["birth_year"][0] if mrow.height else None),
        "role": prow["role"][0] if prow.height else None,
        "league": lg["league"][0] if lg.height else None,
        "minutes_played": round(prow["minutes_played"][0], 0) if prow.height else None,
        "stats": {s: (round(prow[s][0], 3) if prow.height and prow[s][0] is not None else None)
                  for s in CARD_STATS},
    }
    return card


def run(seed: int = 0) -> dict:
    players = pl.read_parquet(PROCESSED_DIR / "players.parquet")
    competitions = pl.read_parquet(PROCESSED_DIR / "competitions.parquet")
    matches = pl.read_parquet(PROCESSED_DIR / "matches.parquet")
    minutes = pl.read_parquet(PROCESSED_DIR / "minutes.parquet")
    events = pl.read_parquet(PROCESSED_DIR / "events.parquet")

    role_lookup = _role_lookup(players)
    meta, comp = _player_meta(players, competitions)
    period_assignment = assign_periods(matches)
    period_profiles = build_period_profiles(events, minutes, period_assignment)

    eligible = select_eligible_both_periods(period_profiles, MINUTES_THRESHOLD, DOMESTIC_LEAGUES)
    eligible = eligible.join(role_lookup, on="player_id", how="left")
    std = impute_and_standardize(eligible, FEATURE_COLUMNS)

    query_a = eligible.filter(pl.col("period") == "A")
    query_a_std = std.filter(pl.col("period") == "A")
    cand_b = eligible.filter(pl.col("period") == "B")
    cand_b_std = std.filter(pl.col("period") == "B")

    from scoutlens.evaluation.diagnostics import compute_primary_team
    primary_team = compute_primary_team(minutes, period_assignment)
    primary_team_a = primary_team.filter(pl.col("period") == "A").select("player_id", "competitionId", "team_id")

    queries = sample_queries(query_a, primary_team_a, seed)

    rating_sheet, arm_key = [], []
    import random
    for i, q in enumerate(queries):
        arms = build_arms(q, query_a_std, cand_b, cand_b_std, seed=seed + i + 1)
        merged = [{**c, "arm": arm} for arm, cands in arms.items() for c in cands]
        random.Random(seed * 1000 + i).shuffle(merged)
        query_card = _card(q["player_id"], q["competitionId"], eligible, meta, comp)
        candidate_cards = [_card(c["player_id"], c["competitionId"], cand_b, meta, comp) for c in merged]
        rating_sheet.append({
            "query_id": i, "query": query_card,
            "candidates": [{k: v for k, v in c.items() if k != "arm"} for c in candidate_cards],
        })
        for c in merged:
            arm_key.append({"query_id": i, "player_id": c["player_id"],
                            "competitionId": c["competitionId"], "arm": c["arm"]})

    manifest = {
        "protocol": "docs/recruitment-validation-protocol.md (D016)",
        "dataset": "Wyscout 2017/18 (CC BY 4.0)",
        "seed": seed, "n_queries": len(queries), "arms": ["B", "C_role", "R"], "k_per_arm": K_PER_ARM,
        "blinding": "candidates merged+shuffled per query, no arm labels; arm_key stored separately",
        "n_ratings_expected_per_rater": len(queries) * 3 * K_PER_ARM,
    }
    return {"rating_sheet": rating_sheet, "arm_key": arm_key, "manifest": manifest}


if __name__ == "__main__":
    out = run()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "rating_sheet.json").write_text(json.dumps(out["rating_sheet"], indent=2, ensure_ascii=False))
    (OUT_DIR / "arm_key.json").write_text(json.dumps(out["arm_key"], indent=2))
    (OUT_DIR / "manifest.json").write_text(json.dumps(out["manifest"], indent=2))
    print(json.dumps(out["manifest"], indent=2))
