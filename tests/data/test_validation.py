import polars as pl

from scoutlens.data.validation import (
    check_composite_key_unique,
    check_coordinate_bounds,
    check_dual_null_sentinel,
    check_foreign_key,
    check_mapping_coverage,
    check_no_negative,
    check_primary_key_unique,
    check_required_not_null,
    check_row_count_min,
    check_sentinel_zero,
    check_tags_coverage,
    check_value_range,
)


def test_primary_key_unique_passes_on_unique_keys():
    df = pl.DataFrame({"wyId": [1, 2, 3]})
    result = check_primary_key_unique(df, "t", "wyId")
    assert result.status == "ok"


def test_primary_key_unique_fails_on_duplicates():
    df = pl.DataFrame({"wyId": [1, 1, 2]})
    result = check_primary_key_unique(df, "t", "wyId")
    assert result.status == "fail"
    assert result.count == 1


def test_required_not_null_flags_nulls():
    df = pl.DataFrame({"a": [1, None, 3]})
    results = check_required_not_null(df, "t", ["a"])
    assert results[0].status == "fail"
    assert results[0].count == 1


def test_required_not_null_ok_when_no_nulls():
    df = pl.DataFrame({"a": [1, 2, 3]})
    results = check_required_not_null(df, "t", ["a"])
    assert results[0].status == "ok"


def test_row_count_min():
    df = pl.DataFrame({"a": [1, 2]})
    assert check_row_count_min(df, "t", 2).status == "ok"
    assert check_row_count_min(df, "t", 3).status == "fail"


def test_sentinel_zero_warns_but_does_not_fail():
    df = pl.DataFrame({"weight": [70, 0, 80]})
    result = check_sentinel_zero(df, "players", "weight")
    assert result.status == "warn"
    assert result.count == 1


def test_dual_null_sentinel_detects_both_encodings():
    df = pl.DataFrame({"foot": ["right", "", None, "left"]})
    result = check_dual_null_sentinel(df, "players", "foot")
    assert result.status == "warn"


def test_dual_null_sentinel_ok_with_single_encoding():
    df = pl.DataFrame({"foot": ["right", None, "left"]})
    result = check_dual_null_sentinel(df, "players", "foot")
    assert result.status == "ok"


def test_coordinate_bounds_flags_out_of_range():
    events = pl.DataFrame(
        {
            "positions": [
                [{"x": 50, "y": 50}, {"x": 101, "y": 50}],
                [{"x": -1, "y": 20}],
            ]
        }
    )
    results = check_coordinate_bounds(events)
    by_axis = {r.check: r for r in results}
    # x values are [50, 101, -1] -> two out of range (101 and -1)
    assert by_axis["coordinate_bounds[x]"].status == "warn"
    assert by_axis["coordinate_bounds[x]"].count == 2
    # y values are [50, 50, 20] -> none out of range
    assert by_axis["coordinate_bounds[y]"].status == "ok"


def test_coordinate_bounds_ok_when_all_within_range():
    events = pl.DataFrame({"positions": [[{"x": 10, "y": 10}, {"x": 90, "y": 90}]]})
    results = check_coordinate_bounds(events)
    assert all(r.status == "ok" for r in results)


def test_mapping_coverage_fails_on_unmapped_value():
    events = pl.DataFrame({"eventId": [1, 2, 99]})
    mapping = pl.DataFrame({"event": [1, 2, 3]})
    result = check_mapping_coverage(events, mapping, "eventId", "event", "event_id")
    assert result.status == "fail"
    assert result.count == 1


def test_mapping_coverage_ok_when_fully_covered():
    events = pl.DataFrame({"eventId": [1, 2]})
    mapping = pl.DataFrame({"event": [1, 2, 3]})
    result = check_mapping_coverage(events, mapping, "eventId", "event", "event_id")
    assert result.status == "ok"


def test_tags_coverage_fails_on_unmapped_tag():
    events = pl.DataFrame({"tags": [[{"id": 101}, {"id": 999}]]})
    tags2name = pl.DataFrame({"Tag": [101, 102]})
    result = check_tags_coverage(events, tags2name)
    assert result.status == "fail"
    assert result.count == 1


def test_tags_coverage_ok_when_fully_covered():
    events = pl.DataFrame({"tags": [[{"id": 101}]]})
    tags2name = pl.DataFrame({"Tag": [101, 102]})
    result = check_tags_coverage(events, tags2name)
    assert result.status == "ok"


def test_foreign_key_ok_when_all_resolve():
    child = pl.DataFrame({"matchId": [1, 2, 1]})
    parent = pl.DataFrame({"wyId": [1, 2, 3]})
    result = check_foreign_key(child, "matchId", parent, "wyId", "test_fk")
    assert result.status == "ok"


def test_foreign_key_fails_on_orphan():
    child = pl.DataFrame({"matchId": [1, 99]})
    parent = pl.DataFrame({"wyId": [1, 2, 3]})
    result = check_foreign_key(child, "matchId", parent, "wyId", "test_fk")
    assert result.status == "fail"
    assert result.count == 1


def test_foreign_key_excludes_sentinel_values():
    child = pl.DataFrame({"playerId": [1, 0, 0]})
    parent = pl.DataFrame({"wyId": [1, 2]})
    result = check_foreign_key(child, "playerId", parent, "wyId", "test_fk", sentinel_values=(0,))
    assert result.status == "ok"


def test_foreign_key_sentinel_does_not_hide_real_orphans():
    child = pl.DataFrame({"playerId": [1, 0, 999]})
    parent = pl.DataFrame({"wyId": [1, 2]})
    result = check_foreign_key(child, "playerId", parent, "wyId", "test_fk", sentinel_values=(0,))
    assert result.status == "fail"
    assert result.count == 1


def test_composite_key_unique_ok_when_no_duplicate_combinations():
    df = pl.DataFrame({"player_id": [1, 1, 2], "match_id": [10, 11, 10]})
    result = check_composite_key_unique(df, "minutes", ["player_id", "match_id"])
    assert result.status == "ok"


def test_composite_key_unique_fails_on_duplicate_combination():
    df = pl.DataFrame({"player_id": [1, 1, 2], "match_id": [10, 10, 10]})
    result = check_composite_key_unique(df, "minutes", ["player_id", "match_id"])
    assert result.status == "fail"
    assert result.count == 1


def test_no_negative_ok_when_all_non_negative():
    df = pl.DataFrame({"minutes_played": [0, 45, 90]})
    result = check_no_negative(df, "minutes", "minutes_played")
    assert result.status == "ok"


def test_no_negative_fails_on_negative_value():
    df = pl.DataFrame({"minutes_played": [0, -5, 90]})
    result = check_no_negative(df, "minutes", "minutes_played")
    assert result.status == "fail"
    assert result.count == 1


def test_value_range_ok_within_bounds():
    df = pl.DataFrame({"minutes_played": [0, 90, 120]})
    result = check_value_range(df, "minutes", "minutes_played", 0, 130)
    assert result.status == "ok"


def test_value_range_fails_outside_bounds():
    df = pl.DataFrame({"minutes_played": [0, 90, 200]})
    result = check_value_range(df, "minutes", "minutes_played", 0, 130)
    assert result.status == "fail"
    assert result.count == 1
