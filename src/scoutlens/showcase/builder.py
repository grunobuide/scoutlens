"""Pure builders for the ScoutLens public showcase artifacts."""

from __future__ import annotations

import bisect
import dataclasses
import math
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

import polars as pl

from scoutlens.evaluation.retrieval import select_eligible_both_periods
from scoutlens.evaluation.similarity import apply_scaler, baseline_a_rank, baseline_b_rank, fit_scaler
from scoutlens.evaluation.temporal import assign_periods, build_period_profiles
from scoutlens.features.aggregation import FEATURE_COLUMNS, FEATURE_FAMILIES
from scoutlens.showcase.catalog import (
    CONTRACT,
    EXPECTED_PROFILE_COUNT,
    FAMILY_ORDER,
    FEATURE_CATALOG,
    FEATURE_ORDER,
    RATIO_SUPPORT_COLUMNS,
    SCHEMA_VERSION,
)
from scoutlens.showcase.caveats import profile_caveats
from scoutlens.showcase.io import canonical_content_digest
from scoutlens.showcase.research import build_research_summary, load_research_sources

VERSION_PLACEHOLDER = "__DATASET_VERSION__"


@dataclasses.dataclass(frozen=True)
class ShowcaseInputs:
    period_profiles: pl.DataFrame
    support_profiles: pl.DataFrame
    players: pl.DataFrame
    competitions: pl.DataFrame
    teams: pl.DataFrame
    matches: pl.DataFrame
    minutes: pl.DataFrame
    period_assignment: pl.DataFrame
    research_sources: dict[str, dict]


@dataclasses.dataclass(frozen=True)
class ShowcaseBundle:
    dataset_version: str
    artifacts: dict[str, dict]
    profile_count: int


def load_showcase_inputs(processed_dir: Path, artifact_dir: Path, competition_ids: list[int]) -> ShowcaseInputs:
    """Load local processed inputs and recompute ratio supports with frozen code."""
    matches = pl.read_parquet(processed_dir / "matches.parquet").filter(
        pl.col("competitionId").is_in(competition_ids)
    )
    assignment = assign_periods(matches)
    match_ids = assignment["match_id"].to_list()
    minutes = pl.read_parquet(processed_dir / "minutes.parquet").filter(pl.col("match_id").is_in(match_ids))
    events = pl.read_parquet(processed_dir / "events.parquet").filter(pl.col("matchId").is_in(match_ids))
    support_profiles = build_period_profiles(events, minutes, assignment, with_counts=True)
    return ShowcaseInputs(
        period_profiles=pl.read_parquet(processed_dir / "period_profiles.parquet"),
        support_profiles=support_profiles,
        players=pl.read_parquet(processed_dir / "players.parquet"),
        competitions=pl.read_parquet(processed_dir / "competitions.parquet"),
        teams=pl.read_parquet(processed_dir / "teams.parquet"),
        matches=matches,
        minutes=minutes,
        period_assignment=assignment,
        research_sources=load_research_sources(artifact_dir),
    )


def profile_key(player_id: int, competition_id: int) -> str:
    return f"wy-{player_id}-c-{competition_id}"


def player_key(player_id: int) -> str:
    return f"wy-{player_id}"


def _percentile(value: float, sorted_values: list[float]) -> float:
    if len(sorted_values) <= 1:
        return 50.0
    left = bisect.bisect_left(sorted_values, value)
    right = bisect.bisect_right(sorted_values, value)
    average_zero_based_rank = (left + right - 1) / 2
    return average_zero_based_rank / (len(sorted_values) - 1) * 100


def _build_percentile_lookup(standardized: pl.DataFrame) -> tuple[dict, dict]:
    global_lookup: dict[tuple[int, int, str, str], float] = {}
    role_lookup: dict[tuple[int, int, str, str], float] = {}
    rows = standardized.select(["player_id", "competitionId", "period", "role"] + FEATURE_COLUMNS).to_dicts()
    for feature_id in FEATURE_COLUMNS:
        globally_sorted = sorted(float(row[feature_id]) for row in rows)
        by_role: dict[str, list[float]] = defaultdict(list)
        for row in rows:
            by_role[str(row["role"])].append(float(row[feature_id]))
        for role in by_role:
            by_role[role].sort()
        for row in rows:
            key = (int(row["player_id"]), int(row["competitionId"]), str(row["period"]), feature_id)
            value = float(row[feature_id])
            global_lookup[key] = _percentile(value, globally_sorted)
            role_lookup[key] = _percentile(value, by_role[str(row["role"])])
    return global_lookup, role_lookup


def _identity_lookups(inputs: ShowcaseInputs) -> tuple[dict[int, dict], dict[int, dict], dict[int, str]]:
    players = {
        int(row["wyId"]): {
            "display_name": row["shortName"] or " ".join(
                part for part in (row["firstName"], row["lastName"]) if part
            ),
            "role": row["role"]["name"],
        }
        for row in inputs.players.select("wyId", "shortName", "firstName", "lastName", "role").to_dicts()
    }
    competitions = {
        int(row["wyId"]): {
            "id": int(row["wyId"]),
            "name": row["name"],
            "country": row["area"]["name"],
        }
        for row in inputs.competitions.select("wyId", "name", "area").to_dicts()
    }
    teams = {int(row["wyId"]): str(row["name"]) for row in inputs.teams.select("wyId", "name").to_dicts()}
    return players, competitions, teams


def _period_metadata(inputs: ShowcaseInputs, team_names: dict[int, str]) -> tuple[dict, dict]:
    assigned_matches = inputs.period_assignment.join(
        inputs.matches.select(pl.col("wyId").alias("match_id"), "dateutc"), on="match_id", how="left"
    )
    date_ranges: dict[tuple[int, str], tuple[str, str]] = {}
    for row in (
        assigned_matches.group_by("competitionId", "period")
        .agg(pl.col("dateutc").min().alias("start"), pl.col("dateutc").max().alias("end"))
        .to_dicts()
    ):
        date_ranges[(int(row["competitionId"]), str(row["period"]))] = (
            str(row["start"])[:10],
            str(row["end"])[:10],
        )

    appearances = (
        inputs.minutes.filter(pl.col("minutes_played") > 0)
        .join(inputs.period_assignment, on="match_id", how="inner")
        .group_by("player_id", "competitionId", "period", "team_id")
        .agg(
            pl.col("minutes_played").sum().alias("minutes"),
            pl.col("match_id").n_unique().alias("match_count"),
        )
    )
    contexts: dict[tuple[int, int, str], dict] = {}
    grouped: dict[tuple[int, int, str], list[dict]] = defaultdict(list)
    for row in appearances.to_dicts():
        grouped[(int(row["player_id"]), int(row["competitionId"]), str(row["period"]))].append(row)
    for key, rows in grouped.items():
        rows.sort(key=lambda row: (-int(row["minutes"]), int(row["team_id"])))
        contexts[key] = {
            "minutes": sum(int(row["minutes"]) for row in rows),
            "match_count": sum(int(row["match_count"]) for row in rows),
            "teams": [
                {"id": int(row["team_id"]), "name": team_names[int(row["team_id"])], "minutes": int(row["minutes"])}
                for row in rows
            ],
        }
    return date_ranges, contexts


def _pending_feature_uncertainty() -> dict:
    return {
        "status": "pending",
        "valid_resamples": None,
        "raw_ci_95": None,
        "within_role_percentile_ci_95": None,
    }


def _pending_rank_uncertainty() -> dict:
    return {
        "status": "pending",
        "valid_resamples": None,
        "median_rank": None,
        "rank_ci_95": None,
        "recall_at_1_rate": None,
        "recall_at_5_rate": None,
        "recall_at_10_rate": None,
    }


def _pending_neighbor_stability() -> dict:
    return {
        "status": "pending",
        "valid_resamples": None,
        "top_5_selection_rate": None,
        "median_rank": None,
        "rank_ci_95": None,
    }


def _pending_uncertainty() -> dict:
    return {
        "status": "pending",
        "design_version": None,
        "seed": None,
        "requested_resamples": None,
        "valid_resamples": None,
        "interval": None,
        "resampling_unit": None,
        "cohort_policy": None,
        "warning": (
            "Match-bootstrap sampling stability is pending. Future intervals describe observed-match sampling "
            "variation, not causal effects, provider annotation error, or future performance."
        ),
    }


def _support(feature_id: str, support_row: dict[str, Any], minutes: int) -> dict:
    mapping = RATIO_SUPPORT_COLUMNS.get(feature_id)
    if mapping is None:
        return {"minutes": minutes, "attempts": None, "successes": None}
    success_column, attempt_columns = mapping
    attempts = sum(int(support_row[column]) for column in attempt_columns)
    return {"minutes": minutes, "attempts": attempts, "successes": int(support_row[success_column])}


def _period_fingerprint(
    raw_row: dict[str, Any],
    standardized_row: dict[str, Any],
    support_row: dict[str, Any],
    global_percentiles: dict,
    role_percentiles: dict,
    date_range: tuple[str, str],
    context: dict,
) -> dict:
    period = str(raw_row["period"])
    row_prefix = (int(raw_row["player_id"]), int(raw_row["competitionId"]), period)
    feature_values = []
    for feature_id in FEATURE_COLUMNS:
        raw_value = raw_row[feature_id]
        z_score = float(standardized_row[feature_id])
        feature_values.append(
            {
                "feature_id": feature_id,
                "raw_value": None if raw_value is None else float(raw_value),
                "global_z_score": z_score,
                "global_percentile": global_percentiles[row_prefix + (feature_id,)],
                "within_role_percentile": role_percentiles[row_prefix + (feature_id,)],
                "imputed_for_model": raw_value is None,
                "support": _support(feature_id, support_row, int(raw_row["minutes_played"])),
                "uncertainty": _pending_feature_uncertainty(),
            }
        )
    return {
        "label": "First chronological half" if period == "A" else "Second chronological half",
        "date_start": date_range[0],
        "date_end": date_range[1],
        "minutes": int(raw_row["minutes_played"]),
        "match_count": int(context["match_count"]),
        "features": feature_values,
    }


def _interpretation(contribution: float) -> str:
    if contribution > 0:
        return "alignment"
    if contribution < 0:
        return "disagreement"
    return "neutral"


def _evidence_for_candidate(
    subject: str,
    id_prefix: str,
    query: dict[str, Any],
    candidate: dict[str, Any],
) -> tuple[float, list[dict]]:
    query_norm = math.sqrt(math.fsum(float(query[feature]) ** 2 for feature in FEATURE_COLUMNS))
    candidate_norm = math.sqrt(math.fsum(float(candidate[feature]) ** 2 for feature in FEATURE_COLUMNS))
    denominator = query_norm * candidate_norm
    feature_rows: list[dict] = []
    by_family: dict[str, list[float]] = defaultdict(list)
    for feature_id in FEATURE_COLUMNS:
        contribution = (
            float(query[feature_id]) * float(candidate[feature_id]) / denominator if denominator > 0 else 0.0
        )
        family = FEATURE_CATALOG[FEATURE_ORDER[feature_id]]["family"]
        by_family[family].append(contribution)
        feature_rows.append(
            {
                "evidence_id": f"{id_prefix}-feature-{feature_id}",
                "subject": subject,
                "kind": "feature_contribution",
                "feature_id": feature_id,
                "family": family,
                "query_global_z": float(query[feature_id]),
                "candidate_global_z": float(candidate[feature_id]),
                "contribution": contribution,
                "interpretation": _interpretation(contribution),
            }
        )
    feature_rows.sort(key=lambda row: (-abs(row["contribution"]), FEATURE_ORDER[row["feature_id"]]))
    family_rows: list[dict[str, Any]] = []
    for family in FEATURE_FAMILIES:
        contribution = math.fsum(by_family[family])
        family_rows.append(
            {
                "evidence_id": f"{id_prefix}-family-{family}",
                "subject": subject,
                "kind": "family_contribution",
                "feature_id": None,
                "family": family,
                "query_global_z": None,
                "candidate_global_z": None,
                "contribution": contribution,
                "interpretation": _interpretation(contribution),
            }
        )
    family_rows.sort(key=lambda row: (-abs(row["contribution"]), FAMILY_ORDER[row["family"]]))
    cosine = math.fsum(row["contribution"] for row in feature_rows)
    return cosine, feature_rows + family_rows


def _retrieval_outcome(candidate_count: int, self_rank: int, cosine: float | None, evidence_refs: list[str]) -> dict:
    return {
        "candidate_count": candidate_count,
        "self_rank": self_rank,
        "reciprocal_rank": 1.0 / self_rank,
        "cosine_similarity": cosine,
        "evidence_refs": evidence_refs,
        "uncertainty": _pending_rank_uncertainty(),
    }


def _normalized_name(value: str) -> str:
    return unicodedata.normalize("NFKD", value).casefold()


def build_showcase_bundle(
    inputs: ShowcaseInputs,
    *,
    competition_ids: list[int],
    minutes_threshold: int,
    expected_profile_count: int | None = EXPECTED_PROFILE_COUNT,
) -> ShowcaseBundle:
    players, competitions, team_names = _identity_lookups(inputs)
    role_lookup = inputs.players.select(
        pl.col("wyId").alias("player_id"), pl.col("role").struct.field("name").alias("role")
    )
    eligible = select_eligible_both_periods(inputs.period_profiles, minutes_threshold, competition_ids).join(
        role_lookup, on="player_id", how="left"
    )
    profile_count = eligible.select("player_id", "competitionId").unique().height
    if expected_profile_count is not None and profile_count != expected_profile_count:
        raise ValueError(f"expected {expected_profile_count} eligible profiles, found {profile_count}")
    if eligible["role"].null_count():
        raise ValueError("eligible profiles contain player ids without a nominal role")

    scaler = fit_scaler(eligible, FEATURE_COLUMNS)
    standardized = apply_scaler(eligible, FEATURE_COLUMNS, scaler)
    global_percentiles, role_percentiles = _build_percentile_lookup(standardized)
    date_ranges, contexts = _period_metadata(inputs, team_names)

    eligible_keys = eligible.select("player_id", "competitionId", "period")
    supports = inputs.support_profiles.join(eligible_keys, on=["player_id", "competitionId", "period"], how="inner")
    raw_rows = {
        (int(row["player_id"]), int(row["competitionId"]), str(row["period"])): row
        for row in eligible.to_dicts()
    }
    std_rows = {
        (int(row["player_id"]), int(row["competitionId"]), str(row["period"])): row
        for row in standardized.to_dicts()
    }
    support_rows = {
        (int(row["player_id"]), int(row["competitionId"]), str(row["period"])): row
        for row in supports.to_dicts()
    }
    if set(raw_rows) != set(support_rows):
        raise ValueError("recomputed feature supports do not cover the frozen eligible profile rows")
    for row_key, raw_row in raw_rows.items():
        support_row = support_rows[row_key]
        for feature_id in FEATURE_COLUMNS:
            left, right = raw_row[feature_id], support_row[feature_id]
            if left is None or right is None:
                if left is not right:
                    raise ValueError(f"frozen profile drift at {row_key}/{feature_id}: {left!r} != {right!r}")
            elif not math.isclose(float(left), float(right), rel_tol=0, abs_tol=1e-12):
                raise ValueError(f"frozen profile drift at {row_key}/{feature_id}: {left!r} != {right!r}")

    query_rows = standardized.filter(pl.col("period") == "A").sort(["player_id", "competitionId"])
    candidate_rows = standardized.filter(pl.col("period") == "B").sort(["player_id", "competitionId"])
    candidate_rank_frame = candidate_rows.select(
        ["player_id", "competitionId", "role", "minutes_played"] + FEATURE_COLUMNS
    )
    role_counts = {
        str(row["role"]): int(row["len"])
        for row in query_rows.group_by("role").len().to_dicts()
    }

    profile_artifacts: dict[str, dict] = {}
    index_items: list[dict] = []
    for query in query_rows.to_dicts():
        player_id = int(query["player_id"])
        competition_id = int(query["competitionId"])
        key = profile_key(player_id, competition_id)
        role = str(query["role"])
        query_features = {feature_id: float(query[feature_id]) for feature_id in FEATURE_COLUMNS}

        ranked_global = baseline_b_rank(query_features, candidate_rank_frame, FEATURE_COLUMNS)
        ranked_role = baseline_b_rank(
            query_features,
            candidate_rank_frame.filter(pl.col("role") == role),
            FEATURE_COLUMNS,
        )
        baseline = baseline_a_rank(role, float(query["minutes_played"]), candidate_rank_frame)
        same = (pl.col("player_id") == player_id) & (pl.col("competitionId") == competition_id)
        global_self = ranked_global.filter(same).row(0, named=True)
        role_self = ranked_role.filter(same).row(0, named=True)
        baseline_self = baseline.filter(same).row(0, named=True)
        self_candidate = std_rows[(player_id, competition_id, "B")]
        self_cosine, self_evidence = _evidence_for_candidate(
            "self_retrieval", "self", query, self_candidate
        )
        self_refs = [row["evidence_id"] for row in self_evidence]

        neighbor_rows = (
            ranked_role.filter(pl.col("player_id") != player_id)
            .with_columns(
                pl.format("wy-{}-c-{}", pl.col("player_id"), pl.col("competitionId")).alias("_profile_key")
            )
            .sort(["cosine_similarity", "_profile_key"], descending=[True, False])
            .head(5)
            .to_dicts()
        )
        if len(neighbor_rows) != 5:
            raise ValueError(f"{key}: fewer than five non-self within-role candidates")
        neighbors = []
        evidence_index = list(self_evidence)
        for rank, neighbor in enumerate(neighbor_rows, start=1):
            neighbor_player_id = int(neighbor["player_id"])
            neighbor_competition_id = int(neighbor["competitionId"])
            neighbor_key = profile_key(neighbor_player_id, neighbor_competition_id)
            neighbor_candidate = std_rows[(neighbor_player_id, neighbor_competition_id, "B")]
            cosine, evidence = _evidence_for_candidate(
                f"neighbor:{neighbor_key}", f"neighbor-{neighbor_key}", query, neighbor_candidate
            )
            evidence_index.extend(evidence)
            neighbor_context = contexts[(neighbor_player_id, neighbor_competition_id, "B")]
            neighbors.append(
                {
                    "rank": rank,
                    "player_key": player_key(neighbor_player_id),
                    "profile_key": neighbor_key,
                    "display_name": players[neighbor_player_id]["display_name"],
                    "role": players[neighbor_player_id]["role"],
                    "competition": competitions[neighbor_competition_id],
                    "teams": [
                        {"id": team["id"], "name": team["name"]} for team in neighbor_context["teams"]
                    ],
                    "candidate_period": "b",
                    "cosine_similarity": cosine,
                    "evidence_refs": [row["evidence_id"] for row in evidence],
                    "stability": _pending_neighbor_stability(),
                }
            )

        period_contexts = {
            period.lower(): contexts[(player_id, competition_id, period)] for period in ("A", "B")
        }
        periods = {
            period.lower(): _period_fingerprint(
                raw_rows[(player_id, competition_id, period)],
                std_rows[(player_id, competition_id, period)],
                support_rows[(player_id, competition_id, period)],
                global_percentiles,
                role_percentiles,
                date_ranges[(competition_id, period)],
                period_contexts[period.lower()],
            )
            for period in ("A", "B")
        }
        identity = {
            "player_key": player_key(player_id),
            "display_name": players[player_id]["display_name"],
            "role": role,
            "competition": competitions[competition_id],
            "season": "2017/18",
            "period_contexts": period_contexts,
        }
        profile = {
            "contract": CONTRACT,
            "schema_version": SCHEMA_VERSION,
            "dataset_version": VERSION_PLACEHOLDER,
            "profile_key": key,
            "identity": identity,
            "cohort": {
                "global_profile_count": profile_count,
                "within_role_profile_count": role_counts[role],
                "minutes_threshold_per_period": minutes_threshold,
                "scaler_scope": "eligible_period_a_and_b_combined",
                "default_display_percentile_scope": "within_role",
            },
            "periods": periods,
            "retrieval": {
                "query_period": "a",
                "candidate_period": "b",
                "method": "combined_scaler_cosine_v1",
                "global": _retrieval_outcome(
                    ranked_global.height, int(global_self["rank"]), self_cosine, self_refs
                ),
                "within_role": _retrieval_outcome(
                    ranked_role.height, int(role_self["rank"]), self_cosine, self_refs
                ),
                "baseline_role_minutes": _retrieval_outcome(
                    baseline.height, int(baseline_self["rank"]), None, []
                ),
            },
            "neighbors": neighbors,
            "uncertainty": _pending_uncertainty(),
            "caveats": profile_caveats(role),
            "evidence_index": evidence_index,
            "provenance_ref": "manifest.json",
        }
        relative_path = f"players/{key}.json"
        profile_artifacts[relative_path] = profile
        index_items.append(
            {
                "player_key": player_key(player_id),
                "profile_key": key,
                "display_name": identity["display_name"],
                "role": role,
                "competition": competitions[competition_id],
                "period_contexts": period_contexts,
                "total_minutes": period_contexts["a"]["minutes"] + period_contexts["b"]["minutes"],
                "self_rank_within_role": int(role_self["rank"]),
                "uncertainty_status": "pending",
                "artifact_path": relative_path,
            }
        )

    index_items.sort(key=lambda item: (_normalized_name(item["display_name"]), item["profile_key"]))
    artifacts: dict[str, dict] = {
        "feature-catalog.json": {
            "contract": CONTRACT,
            "schema_version": SCHEMA_VERSION,
            "dataset_version": VERSION_PLACEHOLDER,
            "features": FEATURE_CATALOG,
        },
        "players.index.json": {
            "contract": CONTRACT,
            "schema_version": SCHEMA_VERSION,
            "dataset_version": VERSION_PLACEHOLDER,
            "profiles": index_items,
        },
        "research-summary.json": build_research_summary(VERSION_PLACEHOLDER, inputs.research_sources),
        **profile_artifacts,
    }
    digest = canonical_content_digest(artifacts)
    dataset_version = f"wyscout-2017-18-v1-{digest[:12]}"
    for artifact in artifacts.values():
        artifact["dataset_version"] = dataset_version
    return ShowcaseBundle(dataset_version=dataset_version, artifacts=artifacts, profile_count=profile_count)
