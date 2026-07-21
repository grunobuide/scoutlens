"""Reproducible acquisition of the Pappalardo et al. Wyscout event dataset.

Downloads each artifact from its pinned Figshare file endpoint, verifies it
against the checksum Figshare itself reports (`supplied_md5`), and converts
it to Parquet under `data/processed/`. Source of truth for what gets
downloaded is `ARTIFACTS` below — see docs/data-provenance.md for the
corresponding license verification (SLS-002).
"""

from __future__ import annotations

import csv
import dataclasses
import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import polars as pl
import requests

REPO_ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = REPO_ROOT / "data" / "raw"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
MANIFEST_PATH = REPO_ROOT / "docs" / "data-manifest.csv"

CITATION = (
    "Pappalardo, L., Cintia, P., Rossi, A. et al. A public data set of "
    "spatio-temporal match events in soccer competitions. Sci Data 6, 236 "
    "(2019). https://doi.org/10.1038/s41597-019-0247-7"
)


@dataclasses.dataclass(frozen=True)
class Artifact:
    key: str
    item_doi: str
    item_version: int
    filename: str
    download_url: str
    expected_md5: str
    declared_license: str
    is_zip: bool = False


# Pinned from the Figshare API (https://api.figshare.com/v2/articles/<id>)
# on 2026-07-20. Re-running SLS-002's verification step is required before
# updating any of these values.
ARTIFACTS: list[Artifact] = [
    Artifact(
        key="events",
        item_doi="10.6084/m9.figshare.7770599",
        item_version=1,
        filename="events.zip",
        download_url="https://ndownloader.figshare.com/files/14464685",
        expected_md5="7c20e8647e7eda58d7838a0c7b1ec6ab",
        declared_license="CC BY 4.0",
        is_zip=True,
    ),
    Artifact(
        key="matches",
        item_doi="10.6084/m9.figshare.7770422",
        item_version=1,
        filename="matches.zip",
        download_url="https://ndownloader.figshare.com/files/14464622",
        expected_md5="51d80beb17480919f69a53a0152c2d71",
        declared_license="CC BY 4.0",
        is_zip=True,
    ),
    Artifact(
        key="players",
        item_doi="10.6084/m9.figshare.7765196",
        item_version=3,
        filename="players.json",
        download_url="https://ndownloader.figshare.com/files/15073721",
        expected_md5="f28ddf6326281efeda6488b2169f5609",
        declared_license="CC BY 4.0",
    ),
    Artifact(
        key="teams",
        item_doi="10.6084/m9.figshare.7765310",
        item_version=3,
        filename="teams.json",
        download_url="https://ndownloader.figshare.com/files/15073697",
        expected_md5="1381ff9449f21105090729cf0e086b5b",
        declared_license="CC BY 4.0",
    ),
    Artifact(
        key="competitions",
        item_doi="10.6084/m9.figshare.7765316",
        item_version=4,
        filename="competitions.json",
        download_url="https://ndownloader.figshare.com/files/15073685",
        expected_md5="3dc210a4805dda5337b0ff9f7eaa407a",
        declared_license="CC BY 4.0",
    ),
    Artifact(
        key="eventid2name",
        item_doi="10.6084/m9.figshare.11743836",
        item_version=1,
        filename="eventid2name.csv",
        download_url="https://ndownloader.figshare.com/files/21385245",
        expected_md5="46daf16100ece0c743eedc9adcfea162",
        declared_license="CC BY 4.0",
    ),
    Artifact(
        key="tags2name",
        item_doi="10.6084/m9.figshare.11743818",
        item_version=1,
        filename="tags2name.csv",
        download_url="https://ndownloader.figshare.com/files/21385239",
        expected_md5="e7acb14918d00e40c80a898b1da8fc39",
        declared_license="CC BY 4.0",
    ),
]


def _download(artifact: Artifact) -> bytes:
    response = requests.get(artifact.download_url, timeout=120)
    response.raise_for_status()
    content = response.content
    actual_md5 = hashlib.md5(content).hexdigest()
    if actual_md5 != artifact.expected_md5:
        raise ValueError(
            f"{artifact.filename}: md5 mismatch — expected "
            f"{artifact.expected_md5}, got {actual_md5}. The Figshare file "
            "may have changed; re-run SLS-002 license verification before "
            "trusting this artifact."
        )
    return content


def _normalize_null_sentinels(record: dict) -> dict:
    """Some top-level fields (observed in players.json: currentTeamId,
    currentNationalTeamId) encode "missing" inconsistently — sometimes JSON
    null, sometimes the literal string "null". Both are folded to None so a
    single column dtype can be inferred. See docs/data-dictionary.md."""
    return {k: (None if v == "null" else v) for k, v in record.items()}


def _json_records_to_parquet(records: list[dict], dest: Path) -> None:
    records = [_normalize_null_sentinels(r) for r in records]
    pl.DataFrame(records).write_parquet(dest)


def _normalize_event_record(record: dict) -> dict:
    """Wyscout events.json is inconsistent in two documented ways:
    - `subEventId` is `""` (not null/absent) specifically for Offside
      events, which have no subtype — normalized to None here.
    - `eventSec` serializes as either int or float depending on whether
      the value happens to be a whole number — normalized to float.
    See docs/data-dictionary.md for the empirical audit this was found in.
    """
    record = dict(record)
    if record.get("subEventId") == "":
        record["subEventId"] = None
    if "eventSec" in record and record["eventSec"] is not None:
        record["eventSec"] = float(record["eventSec"])
    return record


def _events_zip_to_parquet(raw_bytes: bytes, dest_dir: Path) -> list[str]:
    """events.zip contains one JSON array per competition. Concatenate all
    into a single events.parquet, tagging rows with their source file."""
    frames = []
    written_members = []
    with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
        for member in sorted(zf.namelist()):
            if not member.lower().endswith(".json"):
                continue
            with zf.open(member) as fh:
                records = json.load(fh)
            records = [_normalize_event_record(r) for r in records]
            df = pl.DataFrame(records)
            df = df.with_columns(pl.lit(member).alias("_source_file"))
            frames.append(df)
            written_members.append(member)
    combined = pl.concat(frames, how="diagonal_relaxed")
    combined.write_parquet(dest_dir / "events.parquet")
    return written_members


def _normalize_match_record(record: dict) -> dict:
    """`teamsData` is a dict keyed by a dynamic (per-match) team id, so its
    struct shape differs row to row — not representable as a flat Parquet
    column. Serialized to a JSON string here to stay lossless; decomposing
    lineup/bench/substitutions into proper rows is SLS-008/SLS-009's job,
    not ingestion's."""
    record = dict(record)
    if "teamsData" in record:
        record["teamsData"] = json.dumps(record["teamsData"])
    return record


def _matches_zip_to_parquet(raw_bytes: bytes, dest_dir: Path) -> list[str]:
    frames = []
    written_members = []
    with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
        for member in sorted(zf.namelist()):
            if not member.lower().endswith(".json"):
                continue
            with zf.open(member) as fh:
                records = json.load(fh)
            records = [_normalize_match_record(r) for r in records]
            df = pl.DataFrame(records)
            df = df.with_columns(pl.lit(member).alias("_source_file"))
            frames.append(df)
            written_members.append(member)
    combined = pl.concat(frames, how="diagonal_relaxed")
    combined.write_parquet(dest_dir / "matches.parquet")
    return written_members


def acquire_all() -> list[dict]:
    """Download every artifact, verify checksum, convert to Parquet, and
    return manifest rows (also written to docs/data-manifest.csv)."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    manifest_rows = []

    for artifact in ARTIFACTS:
        retrieved_at = datetime.now(timezone.utc).isoformat()
        raw_bytes = _download(artifact)

        raw_path = RAW_DIR / artifact.filename
        raw_path.write_bytes(raw_bytes)
        sha256 = hashlib.sha256(raw_bytes).hexdigest()

        if artifact.key == "events":
            zip_members = _events_zip_to_parquet(raw_bytes, PROCESSED_DIR)
            note = f"zip members: {', '.join(zip_members)}"
        elif artifact.key == "matches":
            zip_members = _matches_zip_to_parquet(raw_bytes, PROCESSED_DIR)
            note = f"zip members: {', '.join(zip_members)}"
        else:
            records = json.loads(raw_bytes) if artifact.filename.endswith(".json") else None
            if records is not None:
                _json_records_to_parquet(records, PROCESSED_DIR / f"{artifact.key}.parquet")
                note = f"{len(records)} records"
            else:
                # CSV mapping files
                df = pl.read_csv(io.BytesIO(raw_bytes))
                df.write_parquet(PROCESSED_DIR / f"{artifact.key}.parquet")
                note = f"{df.height} rows"

        manifest_rows.append(
            {
                "artifact": artifact.key,
                "source_url": artifact.download_url,
                "source_version": artifact.item_version,
                "retrieved_at": retrieved_at,
                "checksum_sha256": sha256,
                "declared_license": artifact.declared_license,
                "citation": CITATION,
                "redistribution_status": "not redistributed — raw data gitignored, manifest tracked",
                "notes": note,
            }
        )

    _write_manifest(manifest_rows)
    return manifest_rows


def _write_manifest(rows: list[dict]) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with MANIFEST_PATH.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    for row in acquire_all():
        print(row["artifact"], "->", row["notes"])
