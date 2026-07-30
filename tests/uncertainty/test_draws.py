from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

from scoutlens.uncertainty.config import load_uncertainty_config
from scoutlens.uncertainty.draws import build_draw_plan, counter_source_index

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "tests" / "uncertainty" / "fixtures" / "match_bootstrap_v1.json"


def _matches() -> pl.DataFrame:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return pl.DataFrame(fixture["matches"]).rename(
        {"competition_id": "competitionId"}
    )


def test_sha256_draw_algorithm_matches_frozen_test_vector() -> None:
    config = load_uncertainty_config()
    vector = config["draw_algorithm_test_vector"]
    selected = counter_source_index(
        design_version=config["design_version"],
        seed=config["seed"],
        replicate=0,
        competition_id=10,
        period="A",
        draw_index=0,
        source_size=vector["source_size"],
    )
    assert selected == vector["selected_source_index"]


def test_draw_plan_is_order_independent_stratified_and_deterministic() -> None:
    matches = _matches()
    kwargs = {"requested_resamples": 20, "seed": 1729, "design_version": "match_bootstrap_v1"}
    first = build_draw_plan(matches, **kwargs)
    reversed_plan = build_draw_plan(matches.reverse(), **kwargs)

    assert first.sha256 == reversed_plan.sha256
    assert first.multiplicities.tolist() == reversed_plan.multiplicities.tolist()
    assert first.requested_resamples == 20

    ordered = pl.DataFrame(
        {
            "match_id": first.match_ids,
            "competitionId": first.competition_ids,
            "period": first.periods,
        }
    )
    for stratum in ordered.partition_by("competitionId", "period"):
        indices = [
            first.match_ids.tolist().index(match_id)
            for match_id in stratum["match_id"].to_list()
        ]
        assert (first.multiplicities[:, indices].sum(axis=1) == len(indices)).all()

    weights = first.weights(0)
    assert weights["multiplicity"].min() >= 1
    assert weights["multiplicity"].sum() == matches.height


@pytest.mark.parametrize("source_size", [0, -1])
def test_counter_draw_rejects_empty_source(source_size: int) -> None:
    with pytest.raises(ValueError, match="positive"):
        counter_source_index(
            design_version="match_bootstrap_v1",
            seed=1729,
            replicate=0,
            competition_id=10,
            period="A",
            draw_index=0,
            source_size=source_size,
        )
