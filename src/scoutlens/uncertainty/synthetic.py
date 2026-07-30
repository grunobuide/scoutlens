"""Executable truth-case harness for the preregistered synthetic fixture."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

from scoutlens.uncertainty.draws import build_draw_plan


def _stratum_key(competition_id: int, period: str) -> str:
    return f"{competition_id}:{period}"


def _aggregate_plan(fixture: dict[str, Any], draws: dict[str, list[int]]) -> dict[tuple[int, str], dict[str, float]]:
    match_lookup = {int(item["match_id"]): item for item in fixture["matches"]}
    multiplicities = {
        match_id: selected.count(match_id)
        for selected in draws.values()
        for match_id in set(selected)
    }
    players = {
        int(item["player_id"]): int(item["competition_id"])
        for item in fixture["players"]
    }
    totals: dict[tuple[int, str], dict[str, float]] = {}
    for observation in fixture["player_match_observations"]:
        match_id = int(observation["match_id"])
        weight = multiplicities.get(match_id, 0)
        if weight == 0:
            continue
        player_id = int(observation["player_id"])
        match = match_lookup[match_id]
        if players[player_id] != int(match["competition_id"]):
            raise ValueError("synthetic observation crosses competition identity")
        key = (player_id, str(match["period"]))
        target = totals.setdefault(key, {"minutes": 0.0, "signal_events": 0.0, "attempts": 0.0, "successes": 0.0})
        for field in target:
            target[field] += float(observation[field]) * weight
    features = {}
    for key, totals_row in totals.items():
        minutes = totals_row["minutes"]
        attempts = totals_row["attempts"]
        features[key] = {
            "signal_p90": 90 * totals_row["signal_events"] / minutes,
            "success_pct": totals_row["successes"] / attempts if attempts > 0 else np.nan,
            "minutes": minutes,
            "signal_events": totals_row["signal_events"],
            "attempts": attempts,
            "successes": totals_row["successes"],
        }
    return features


def validate_synthetic_fixture(path: Path, config: dict[str, Any]) -> dict[str, Any]:
    fixture = json.loads(path.read_text(encoding="utf-8"))
    matches = pl.DataFrame(fixture["matches"]).rename({"competition_id": "competitionId"})
    expected_by_stratum = {
        _stratum_key(int(group["competitionId"][0]), str(group["period"][0])): set(
            int(value) for value in group["match_id"].to_list()
        )
        for group in matches.partition_by("competitionId", "period")
    }
    forced_results = []
    strata_valid = True
    for plan in fixture["forced_draw_plans"]:
        for stratum, draws in plan["draws"].items():
            expected = expected_by_stratum[stratum]
            strata_valid &= len(draws) == len(expected) and set(draws) <= expected
        forced_results.append(_aggregate_plan(fixture, plan["draws"]))

    invariant_signal = [result[(1001, "A")]["signal_p90"] for result in forced_results]
    invariant_success = [result[(1001, "A")]["success_pct"] for result in forced_results]
    volatile_signal = [result[(1004, "A")]["signal_p90"] for result in forced_results]
    volatile_success = [result[(1004, "A")]["success_pct"] for result in forced_results]
    invariant_valid = (
        max(invariant_signal) - min(invariant_signal) == 0
        and max(invariant_success) - min(invariant_success) == 0
    )
    volatile_valid = (
        max(volatile_signal) - min(volatile_signal) > 0
        and max(volatile_success) - min(volatile_success) > 0
    )

    doubled = forced_results[1][(1004, "A")]
    duplicate_weight_valid = (
        doubled["minutes"] == 30
        and doubled["signal_events"] == 16
        and doubled["attempts"] == 2
        and doubled["successes"] == 2
    )

    missing_case = next(case for case in fixture["truth_cases"] if case["case_id"] == "missing_in_resample")
    absent_replicate = int(missing_case["forced_absent_replicate"])
    missing_valid = (1005, "A") not in forced_results[absent_replicate]

    base = forced_results[0]
    query = np.array([base[(1001, "A")]["signal_p90"], base[(1001, "A")]["success_pct"]])
    candidate_ids = np.array([1002, 1003])
    candidates = np.array(
        [
            [base[(int(player_id), "B")]["signal_p90"], base[(int(player_id), "B")]["success_pct"]]
            for player_id in candidate_ids
        ]
    )
    query = query / np.linalg.norm(query)
    candidates = candidates / np.linalg.norm(candidates, axis=1)[:, None]
    similarities = candidates @ query
    tie_order = candidate_ids[np.lexsort((candidate_ids, -similarities))].tolist()
    tied_valid = tie_order == [1002, 1003]

    seeded_plan = build_draw_plan(
        matches,
        requested_resamples=config["requested_resamples"],
        seed=config["seed"],
        design_version=config["design_version"],
    )
    match_index = seeded_plan.match_ids.tolist().index(101)
    missing_player_valid_resamples = int(np.sum(seeded_plan.multiplicities[:, match_index] > 0))
    insufficient_valid = missing_player_valid_resamples < config["minimum_valid_resamples"]

    cases = {
        "invariant_player": invariant_valid,
        "high_variance_low_support": volatile_valid,
        "missing_in_resample": missing_valid and insufficient_valid,
        "tied_candidates": tied_valid,
        "multi_competition_strata": strata_valid,
        "duplicate_match_weighting": duplicate_weight_valid,
    }
    return {
        "fixture_version": fixture["fixture_version"],
        "cases": cases,
        "all_passed": all(cases.values()),
        "missing_player_valid_resamples": missing_player_valid_resamples,
        "invariant_width": max(invariant_signal) - min(invariant_signal),
        "volatile_width": max(volatile_signal) - min(volatile_signal),
    }
