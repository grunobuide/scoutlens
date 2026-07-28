import os
from pathlib import Path

import pytest

from scoutlens.showcase.export import export_showcase
from scoutlens.showcase.validation import validate_published_directory

REPO_ROOT = Path(__file__).resolve().parents[2]
HAS_LOCAL_INPUTS = (REPO_ROOT / "data" / "processed" / "events.parquet").is_file()


@pytest.mark.skipif(
    os.environ.get("SCOUTLENS_SHOWCASE_INTEGRATION") != "1" or not HAS_LOCAL_INPUTS,
    reason="requires local processed Wyscout data and SCOUTLENS_SHOWCASE_INTEGRATION=1",
)
def test_complete_export_is_deterministic_valid_and_within_budgets(tmp_path: Path) -> None:
    first = tmp_path / "first" / "v1"
    second = tmp_path / "second" / "v1"
    timestamp = "2026-07-28T00:00:00+00:00"

    first_result = export_showcase(output_dir=first, generated_at=timestamp)
    second_result = export_showcase(output_dir=second, generated_at=timestamp)

    assert first_result == second_result
    assert first_result["profile_count"] == 1257
    assert first_result["catalog_gzip_bytes"] <= 400 * 1024
    assert first_result["max_profile_gzip_bytes"] <= 30 * 1024
    first_files = {path.relative_to(first).as_posix(): path.read_bytes() for path in first.rglob("*.json")}
    second_files = {path.relative_to(second).as_posix(): path.read_bytes() for path in second.rglob("*.json")}
    assert first_files == second_files

    index_path = second / "players.index.json"
    index_path.write_bytes(index_path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="canonically serialized|integrity metadata mismatch"):
        validate_published_directory(second)
