from scoutlens.features.aggregation import FEATURE_COLUMNS, FEATURE_FAMILIES
from scoutlens.showcase.catalog import FEATURE_CATALOG


def test_public_catalog_matches_frozen_scientific_order_and_partition() -> None:
    assert [item["feature_id"] for item in FEATURE_CATALOG] == FEATURE_COLUMNS
    assert [item["order"] for item in FEATURE_CATALOG] == list(range(32))
    assert {item["family"] for item in FEATURE_CATALOG} == set(FEATURE_FAMILIES)
    assert len({item["feature_id"] for item in FEATURE_CATALOG}) == 32
    for item in FEATURE_CATALOG:
        assert item["direction_semantics"] == "descriptive_not_quality"
        assert item["model_null_handling"] == "population_mean_then_z_zero"

