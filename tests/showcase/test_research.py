from pathlib import Path

from scoutlens.showcase.research import build_research_summary, load_research_sources
from scoutlens.showcase.schema import validate_schema

REPO_ROOT = Path(__file__).resolve().parents[2]


def _metric(summary: dict, experiment_id: str, metric_id: str) -> float:
    experiment = next(item for item in summary["experiments"] if item["experiment_id"] == experiment_id)
    return next(item["value"] for item in experiment["metrics"] if item["metric_id"] == metric_id)


def test_research_summary_copies_versioned_source_values() -> None:
    sources = load_research_sources(REPO_ROOT / "artifacts")
    summary = build_research_summary("wyscout-2017-18-v1-0123456789ab", sources)
    validate_schema(summary, label="research-summary.json")

    assert _metric(summary, "wyscout_global_gate2", "fingerprint_mrr") == sources["gate2"]["global"]["baseline_b"]["mrr"]
    assert _metric(summary, "wyscout_role_team_minutes", "baseline_c_mrr") == sources["robustness"]["check_3_baseline_c_role_team_minutes"]["mrr"]
    assert _metric(summary, "wyscout_transferred_players", "transferred_count") == sources["transfer"]["transferred_only"]["n_queries"]
    assert _metric(summary, "statsbomb_global_replication", "fingerprint_mrr") == sources["statsbomb"]["global_28"]["baseline_b"]["mrr"]
    assert _metric(summary, "wyscout_ratio_shrinkage", "shrunk_global_mrr") == sources["shrinkage"]["shrunk"]["global"]["baseline_b"]["mrr"]


def test_statsbomb_is_aggregate_only_in_research_summary() -> None:
    sources = load_research_sources(REPO_ROOT / "artifacts")
    summary = build_research_summary("wyscout-2017-18-v1-0123456789ab", sources)
    statsbomb = [item for item in summary["experiments"] if item["provider"] == "statsbomb_open_data"]
    assert len(statsbomb) == 3
    assert all(set(item) == {
        "experiment_id", "title", "provider", "population", "metrics", "conclusion",
        "caveat_codes", "source_artifact", "report_url"
    } for item in statsbomb)

