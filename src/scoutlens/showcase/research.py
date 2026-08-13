"""Assemble public claims directly from the five checked-in result artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scoutlens.showcase.catalog import CONTRACT, SCHEMA_VERSION
from scoutlens.showcase.caveats import caveat

SOURCE_FILES = {
    "gate2": "gate2_results.json",
    "robustness": "robustness_results.json",
    "transfer": "transfer_analysis_results.json",
    "statsbomb": "statsbomb_replication_results.json",
    "shrinkage": "shrinkage_experiment_results.json",
}


def load_research_sources(artifact_dir: Path) -> dict[str, dict]:
    return {
        key: json.loads((artifact_dir / filename).read_text(encoding="utf-8"))
        for key, filename in SOURCE_FILES.items()
    }


def _metric(
    metric_id: str,
    label: str,
    value: int | float,
    unit: str,
    *,
    ci: list[float] | None = None,
    precision: int = 4,
) -> dict[str, Any]:
    return {
        "metric_id": metric_id,
        "label": label,
        "value": value,
        "ci_95": ci,
        "unit": unit,
        "display_precision": precision,
    }


def _experiment(
    experiment_id: str,
    title: str,
    provider: str,
    population: str,
    metrics: list[dict],
    conclusion: str,
    caveat_codes: list[str],
    source_artifact: str,
    report_url: str,
) -> dict:
    return {
        "experiment_id": experiment_id,
        "title": title,
        "provider": provider,
        "population": population,
        "metrics": metrics,
        "conclusion": conclusion,
        "caveat_codes": caveat_codes,
        "source_artifact": f"artifacts/{source_artifact}",
        "report_url": report_url,
    }


def build_research_summary(
    dataset_version: str, sources: dict[str, dict], *, schema_version: str = SCHEMA_VERSION
) -> dict:
    """The research summary for one dataset.

    `schema_version` is a parameter rather than the module constant because the
    summary is published under whichever contract major the bundle is: a v2
    bundle carrying a `1.0.0`-stamped summary is rejected, and a consumer
    reading that field would route it to the cosine schema.
    """
    gate2 = sources["gate2"]
    robustness = sources["robustness"]
    transfer = sources["transfer"]
    statsbomb = sources["statsbomb"]
    shrinkage = sources["shrinkage"]

    global_result = gate2["global"]
    within_role = gate2["within_role"]
    transfer_result = transfer["transferred_only"]
    statsbomb_global = statsbomb["global_28"]
    statsbomb_within = statsbomb["within_role_28"]
    statsbomb_transfer = statsbomb["transferred_players"]["transferred_only"]
    raw = shrinkage["raw_v01"]
    shrunk = shrinkage["shrunk"]

    experiments = [
        _experiment(
            "wyscout_global_gate2",
            "Wyscout global same-player retrieval",
            "wyscout_pappalardo",
            f"{global_result['n_eligible']:,} eligible player×competition units, 2017/18",
            [
                _metric("baseline_a_mrr", "Role + minutes baseline MRR", global_result["baseline_a"]["mrr"], "mrr"),
                _metric("fingerprint_mrr", "32-feature cosine MRR", global_result["baseline_b"]["mrr"], "mrr"),
                _metric(
                    "mrr_delta",
                    "Fingerprint minus baseline MRR",
                    global_result["mrr_delta"]["point_estimate"],
                    "mrr",
                    ci=[global_result["mrr_delta"]["ci_low"], global_result["mrr_delta"]["ci_high"]],
                ),
                _metric("median_rank", "Fingerprint median self-rank", global_result["baseline_b"]["median_rank"], "median_rank", precision=0),
            ],
            "The 32-feature fingerprint retrieves the same player far better than the role-and-minutes baseline.",
            ["fingerprint_not_style_proof", "same_season_team_confound"],
            SOURCE_FILES["gate2"],
            "docs/gate-2-decision.md#wyscout-global-retrieval",
        ),
        _experiment(
            "wyscout_within_role_gate2",
            "Wyscout within-role retrieval",
            "wyscout_pappalardo",
            f"{within_role['n_eligible']:,} eligible units with candidates restricted to nominal role",
            [
                _metric("fingerprint_mrr", "Within-role fingerprint MRR", within_role["baseline_b"]["mrr"], "mrr"),
                _metric("median_rank", "Within-role median self-rank", within_role["baseline_b"]["median_rank"], "median_rank", precision=0),
                _metric("recall_at_5", "Within-role recall at 5", within_role["baseline_b"]["recall_at_5"], "recall"),
            ],
            "The signal remains when nominal role can no longer resolve the retrieval problem.",
            ["fingerprint_not_style_proof", "same_season_team_confound"],
            SOURCE_FILES["gate2"],
            "docs/temporal-retrieval-within-role.md",
        ),
        _experiment(
            "wyscout_role_team_minutes",
            "Role + team + minutes control",
            "wyscout_pappalardo",
            f"{robustness['check_3_baseline_c_role_team_minutes']['n']:,} eligible Wyscout units",
            [
                _metric("baseline_c_mrr", "Role + team + minutes MRR", robustness["check_3_baseline_c_role_team_minutes"]["mrr"], "mrr"),
                _metric("median_rank", "Role + team + minutes median rank", robustness["check_3_baseline_c_role_team_minutes"]["median_rank"], "median_rank", precision=0),
            ],
            "Team continuity is a stronger shortcut than the fingerprint in this same-season design.",
            ["same_season_team_confound"],
            SOURCE_FILES["robustness"],
            "docs/robustness-checks.md#team-aware-baseline",
        ),
        _experiment(
            "wyscout_transferred_players",
            "Wyscout transferred-player stress test",
            "wyscout_pappalardo",
            f"{transfer_result['n_queries']} players who changed team between periods",
            [
                _metric("transferred_count", "Transferred-player count", transfer_result["n_queries"], "count", precision=0),
                _metric("fingerprint_mrr", "Transferred-player fingerprint MRR", transfer_result["baseline_b"]["mrr"], "mrr"),
                _metric(
                    "mrr_delta",
                    "Fingerprint minus role-and-minutes MRR",
                    transfer_result["mrr_delta_b_minus_a"]["point_estimate"],
                    "mrr",
                    ci=[transfer_result["mrr_delta_b_minus_a"]["ci_low"], transfer_result["mrr_delta_b_minus_a"]["ci_high"]],
                ),
            ],
            "The Wyscout fingerprint remains encouraging after a team change, but the sample is small.",
            ["small_transfer_sample", "fingerprint_not_style_proof"],
            SOURCE_FILES["transfer"],
            "docs/transfer-analysis.md",
        ),
        _experiment(
            "statsbomb_global_replication",
            "StatsBomb global replication",
            "statsbomb_open_data",
            f"{statsbomb_global['n_eligible']:,} eligible units across four leagues, 2015/16",
            [
                _metric("baseline_a_mrr", "Role + minutes baseline MRR", statsbomb_global["baseline_a"]["mrr"], "mrr"),
                _metric("fingerprint_mrr", "28-feature canonical MRR", statsbomb_global["baseline_b"]["mrr"], "mrr"),
                _metric("median_rank", "Fingerprint median self-rank", statsbomb_global["baseline_b"]["median_rank"], "median_rank", precision=0),
            ],
            "The fingerprint signal replicates with a different provider and season at a lower magnitude.",
            ["provider_replication_lower_magnitude", "same_season_team_confound"],
            SOURCE_FILES["statsbomb"],
            "docs/statsbomb-replication.md",
        ),
        _experiment(
            "statsbomb_within_role_replication",
            "StatsBomb within-role replication",
            "statsbomb_open_data",
            f"{statsbomb_within['n_eligible']:,} eligible units with candidates restricted to role",
            [
                _metric("fingerprint_mrr", "Within-role fingerprint MRR", statsbomb_within["baseline_b"]["mrr"], "mrr"),
                _metric("median_rank", "Within-role median self-rank", statsbomb_within["baseline_b"]["median_rank"], "median_rank", precision=0),
            ],
            "The cross-provider signal is not explained only by nominal role.",
            ["provider_replication_lower_magnitude", "same_season_team_confound"],
            SOURCE_FILES["statsbomb"],
            "docs/statsbomb-replication.md#within-role-retrieval",
        ),
        _experiment(
            "statsbomb_transferred_players",
            "StatsBomb transferred-player stress test",
            "statsbomb_open_data",
            f"{statsbomb_transfer['n_queries']} transferred players",
            [
                _metric("transferred_count", "Transferred-player count", statsbomb_transfer["n_queries"], "count", precision=0),
                _metric("fingerprint_mrr", "Transferred-player fingerprint MRR", statsbomb_transfer["baseline_b"]["mrr"], "mrr"),
                _metric(
                    "mrr_delta",
                    "Fingerprint minus role-and-minutes MRR",
                    statsbomb_transfer["mrr_delta_b_minus_a"]["point_estimate"],
                    "mrr",
                    ci=[statsbomb_transfer["mrr_delta_b_minus_a"]["ci_low"], statsbomb_transfer["mrr_delta_b_minus_a"]["ci_high"]],
                ),
            ],
            "The transferred-player effect is inconclusive in the smaller StatsBomb sample.",
            ["small_transfer_sample", "provider_replication_lower_magnitude"],
            SOURCE_FILES["statsbomb"],
            "docs/statsbomb-replication.md#transferred-players",
        ),
        _experiment(
            "wyscout_ratio_shrinkage",
            "Raw versus shrunk ratio features",
            "wyscout_pappalardo",
            f"{raw['global']['n_eligible']:,} eligible Wyscout units",
            [
                _metric("raw_global_mrr", "Raw-ratio global MRR", raw["global"]["baseline_b"]["mrr"], "mrr"),
                _metric("shrunk_global_mrr", "Shrunk-ratio global MRR", shrunk["global"]["baseline_b"]["mrr"], "mrr"),
                _metric("raw_within_role_mrr", "Raw-ratio within-role MRR", raw["within_role"]["baseline_b"]["mrr"], "mrr"),
                _metric("shrunk_within_role_mrr", "Shrunk-ratio within-role MRR", shrunk["within_role"]["baseline_b"]["mrr"], "mrr"),
            ],
            "Shrinkage reduced low-support ratio extremes but did not improve retrieval, so raw ratios remain the default.",
            ["fingerprint_not_style_proof"],
            SOURCE_FILES["shrinkage"],
            "docs/shrinkage-experiment.md",
        ),
    ]

    return {
        "contract": CONTRACT,
        "schema_version": schema_version,
        "dataset_version": dataset_version,
        "supported_claim": (
            "Event-derived profiles contain a reproducible individual fingerprint that supports same-player "
            "temporal retrieval across two chronological halves."
        ),
        "unsupported_claims": [
            "Statistical similarity proves playing style.",
            "A statistical neighbor is a recruitment recommendation or replacement.",
            "The experiment predicts future performance, tactical fit, value, or transfer success.",
        ],
        "experiments": experiments,
        "narrative_steps": [
            {"order": 1, "kind": "question", "title": "Can an event profile identify a player?", "summary": "Freeze a chronological same-player retrieval task before reading the result.", "experiment_ids": []},
            {"order": 2, "kind": "result", "title": "A strong temporal fingerprint appears", "summary": "The 32-feature cosine model materially exceeds the role-and-minutes baseline.", "experiment_ids": ["wyscout_global_gate2", "wyscout_within_role_gate2"]},
            {"order": 3, "kind": "challenge", "title": "Team continuity is a powerful shortcut", "summary": "A role, team, and minutes control outperforms the fingerprint and narrows the interpretation.", "experiment_ids": ["wyscout_role_team_minutes"]},
            {"order": 4, "kind": "correction", "title": "Stress-test players who changed team", "summary": "The Wyscout signal survives the shortcut removal, with wide uncertainty from a small sample.", "experiment_ids": ["wyscout_transferred_players"]},
            {"order": 5, "kind": "replication", "title": "Repeat with another provider", "summary": "StatsBomb independently reproduces the core signal at a lower magnitude; its transfer subset is inconclusive.", "experiment_ids": ["statsbomb_global_replication", "statsbomb_within_role_replication", "statsbomb_transferred_players"]},
            {"order": 6, "kind": "null_result", "title": "Keep a useful correction out when it does not help", "summary": "Ratio shrinkage fixes a local pathology but does not improve retrieval, so it is not promoted.", "experiment_ids": ["wyscout_ratio_shrinkage"]},
        ],
        "caveats": [
            caveat("fingerprint_not_style_proof"),
            caveat("same_season_team_confound"),
            caveat("small_transfer_sample"),
            caveat("provider_replication_lower_magnitude"),
        ],
    }

